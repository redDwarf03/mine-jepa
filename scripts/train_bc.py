"""
Behavioral Cloning — Phase 4b: imitating Zenodo human demos.

Pipeline:
  1. Load encoder_demos.pt (frozen) + data from minerl_goal/episodes.npz
  2. Train an MLP head: 128-d embedding → 17 actions (cross-entropy)
  3. Measure accuracy on val split
  4. Save bc_policy.pt

Phase 4b Gate: val_accuracy > 40%
(random baseline = 1/17 ≈ 5.9%)

Usage:
    run.bat scripts/train_bc.py
    run.bat scripts/train_bc.py --config configs/train_bc.yaml
"""
import argparse
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, random_split
import yaml

from mine_jepa.encoder.crafter_encoder import CrafterJEPA
from mine_jepa.encoder.dataset import _load_npz, _to_float
from mine_jepa.policy import ActionHead


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/train_bc.yaml")
    return p.parse_args()


def load_cfg(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


class BCDataset(Dataset):
    """(embedding, action) pairs for direct imitation."""

    def __init__(self, embeddings: torch.Tensor, actions: torch.Tensor):
        self.embeddings = embeddings
        self.actions = actions

    def __len__(self) -> int:
        return len(self.embeddings)

    def __getitem__(self, idx: int):
        return self.embeddings[idx], self.actions[idx]


@torch.no_grad()
def encode_all(encoder: nn.Module, frames: torch.Tensor, batch_size: int, device: torch.device) -> torch.Tensor:
    """Encode all frames into embeddings (batched forward pass)."""
    embeddings = []
    for i in range(0, len(frames), batch_size):
        batch = frames[i:i + batch_size].to(device)
        embeddings.append(encoder(batch).cpu())
    return torch.cat(embeddings, dim=0)


def load_encoder(cfg: dict, device: torch.device) -> nn.Module:
    ckpt = torch.load(cfg["encoder"]["checkpoint"], map_location=device, weights_only=False)
    m = ckpt["cfg"]["model"]
    t = ckpt["cfg"]["training"]
    v = ckpt["cfg"]["vicreg"]
    jepa = CrafterJEPA(
        embed_dim=m["embed_dim"], hidden_dim=m["hidden_dim"],
        predictor_hidden=m["predictor_hidden"],
        ema_decay=t["ema_decay"], std_coeff=v["std_coeff"], cov_coeff=v["cov_coeff"],
    )
    jepa.load_state_dict(ckpt["model_state"])
    enc = jepa.encoder.to(device).eval()
    for p in enc.parameters():
        p.requires_grad_(False)
    return enc


def main():
    args = parse_args()
    cfg = load_cfg(args.config)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # --- Load frozen encoder ---
    print("\nLoading encoder (frozen)...")
    encoder = load_encoder(cfg, device)

    # --- Load data ---
    print(f"Loading data: {cfg['data']['path']}")
    data = _load_npz(cfg["data"]["path"])
    frames = _to_float(data["frames"])            # [N, 3, H, W]
    actions = torch.from_numpy(data["actions"].astype(np.int64))  # [N]
    dones = data["dones"]

    # Filter episode boundaries
    valid = np.where(~dones)[0]
    frames = frames[valid]
    actions = actions[valid]
    print(f"  Valid transitions: {len(frames):,} (filtered {len(dones) - len(valid):,} done-frames)")

    # Action distribution
    counts = torch.bincount(actions, minlength=cfg["model"]["n_actions"])
    top3 = counts.argsort(descending=True)[:3]
    print(f"  Top-3 actions: " + ", ".join(f"a{i}={counts[i].item()} ({counts[i]/len(actions)*100:.1f}%)" for i in top3))

    # --- Encode all frames once (stored in RAM) ---
    print("\nEncoding all frames (once)...")
    m_cfg = cfg["model"]
    embeddings = encode_all(encoder, frames, batch_size=512, device=device)
    print(f"  Embeddings shape: {embeddings.shape}")

    # --- Train/val split ---
    val_frac = cfg["data"].get("val_fraction", 0.1)
    n_val = int(len(embeddings) * val_frac)
    n_train = len(embeddings) - n_val
    dataset = BCDataset(embeddings, actions)
    train_ds, val_ds = random_split(dataset, [n_train, n_val],
                                    generator=torch.Generator().manual_seed(42))
    print(f"  Train : {n_train:,}  Val : {n_val:,}")

    t_cfg = cfg["training"]
    train_loader = DataLoader(train_ds, batch_size=t_cfg["batch_size"], shuffle=True,
                              num_workers=t_cfg["num_workers"])
    val_loader = DataLoader(val_ds, batch_size=t_cfg["batch_size"], shuffle=False,
                            num_workers=t_cfg["num_workers"])

    # --- Create action head ---
    head = ActionHead(
        input_dim=m_cfg["input_dim"],
        hidden_dim=m_cfg.get("hidden_dim", 128),
        n_actions=m_cfg["n_actions"],
    ).to(device)
    n_params = sum(p.numel() for p in head.parameters())
    print(f"\nAction head: {n_params:,} params (input={m_cfg['input_dim']} → {m_cfg['n_actions']} classes)")

    optimizer = torch.optim.Adam(head.parameters(), lr=t_cfg["lr"], weight_decay=t_cfg["weight_decay"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=t_cfg["epochs"])

    # Class weights inversely proportional to frequency
    # Without this: model always predicts action 6 (58.5%) → reward=0
    n_actions = m_cfg["n_actions"]
    class_weights = torch.zeros(n_actions)
    for i in range(n_actions):
        class_weights[i] = 1.0 / (counts[i].float() + 1.0)
    class_weights = class_weights / class_weights.sum() * n_actions  # re-normalize
    print(f"  Class weights enabled (corrects a6=58% imbalance)")

    baseline_acc = 1.0 / n_actions * 100
    print(f"Baseline aléatoire : {baseline_acc:.1f}%")
    print(f"\n{'Epoch':>5}  {'train_loss':>10}  {'train_acc':>9}  {'val_loss':>8}  {'val_acc':>7}")

    criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))

    best_val_acc = 0.0
    best_state = None
    log_every = cfg["logging"]["log_every"]

    for epoch in range(1, t_cfg["epochs"] + 1):
        # Train
        head.train()
        train_loss, train_correct, train_total = 0.0, 0, 0
        for emb, act in train_loader:
            emb, act = emb.to(device), act.to(device)
            optimizer.zero_grad()
            logits = head(emb)
            loss = criterion(logits, act)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(emb)
            train_correct += (logits.argmax(1) == act).sum().item()
            train_total += len(emb)
        scheduler.step()

        train_loss /= train_total
        train_acc = train_correct / train_total * 100

        # Val
        head.eval()
        val_loss, val_correct, val_total = 0.0, 0, 0
        with torch.no_grad():
            for emb, act in val_loader:
                emb, act = emb.to(device), act.to(device)
                logits = head(emb)
                loss = criterion(logits, act)
                val_loss += loss.item() * len(emb)
                val_correct += (logits.argmax(1) == act).sum().item()
                val_total += len(emb)
        val_loss /= val_total
        val_acc = val_correct / val_total * 100

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.cpu().clone() for k, v in head.state_dict().items()}

        if epoch % log_every == 0 or epoch == 1:
            print(f"{epoch:>5}  {train_loss:>10.4f}  {train_acc:>8.1f}%  {val_loss:>8.4f}  {val_acc:>6.1f}%")

    gate = best_val_acc > 40.0
    print(f"\nBest val_acc: {best_val_acc:.1f}%  ({'✅ GATE' if gate else '❌ GATE'}: >40% required)")

    # --- Save ---
    ckpt_dir = Path(cfg["checkpoint"]["dir"])
    ckpt_dir.mkdir(exist_ok=True)
    ckpt_path = ckpt_dir / cfg["checkpoint"]["name"]

    head.load_state_dict(best_state)
    torch.save({
        "head_state": head.state_dict(),
        "cfg": cfg,
        "val_acc": best_val_acc,
    }, ckpt_path)
    print(f"Checkpoint → {ckpt_path}")


if __name__ == "__main__":
    main()

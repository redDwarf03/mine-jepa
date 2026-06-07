"""
End-to-end BC — CNN pixels → actions, no JEPA encoder.

Why not JEPA: the JEPA encoder captures visual scenes, not action-relevant
information (tree direction, distance). An end-to-end CNN can learn the
decision-relevant features directly.

Architecture: Nature DQN (Mnih 2015) adapted to 64×64 frames.
  3×64×64 → Conv(32,8,4) → Conv(64,4,2) → Conv(64,3,1) → FC(256) → 17 logits

Phase 4b Gate: val_accuracy > 35% (random baseline = 5.9%)

Usage:
    run.bat scripts/train_bc_cnn.py
    run.bat scripts/train_bc_cnn.py --config configs/train_bc_cnn.yaml
"""
import argparse
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, random_split
import yaml

from mine_jepa.encoder.dataset import _load_npz, _to_float
from mine_jepa.policy import BCNN


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/train_bc_cnn.yaml")
    return p.parse_args()


def load_cfg(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


class PixelBCDataset(Dataset):
    """(frame, action) pairs — frames are loaded raw (not pre-encoded)."""

    def __init__(self, frames: torch.Tensor, actions: torch.Tensor):
        self.frames = frames
        self.actions = actions

    def __len__(self) -> int:
        return len(self.frames)

    def __getitem__(self, idx: int):
        return self.frames[idx], self.actions[idx]



def main():
    args = parse_args()
    cfg = load_cfg(args.config)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # --- Load data ---
    print(f"Loading data: {cfg['data']['path']}")
    data = _load_npz(cfg["data"]["path"])
    frames = _to_float(data["frames"])
    actions = torch.from_numpy(data["actions"].astype(np.int64))
    dones = data["dones"]

    valid = np.where(~dones)[0]
    frames = frames[valid]
    actions = actions[valid]
    print(f"  Valid transitions: {len(frames):,}")

    n_actions = cfg["model"]["n_actions"]
    counts = torch.bincount(actions, minlength=n_actions)
    top3 = counts.argsort(descending=True)[:3]
    print(f"  Top-3 : " + ", ".join(f"a{i}={counts[i]/len(actions)*100:.1f}%" for i in top3))

    # --- Split train/val ---
    val_frac = cfg["data"].get("val_fraction", 0.1)
    n_val = int(len(frames) * val_frac)
    n_train = len(frames) - n_val
    dataset = PixelBCDataset(frames, actions)
    train_ds, val_ds = random_split(dataset, [n_train, n_val],
                                    generator=torch.Generator().manual_seed(42))
    print(f"  Train : {n_train:,}  Val : {n_val:,}")

    t_cfg = cfg["training"]
    train_loader = DataLoader(train_ds, batch_size=t_cfg["batch_size"], shuffle=True,
                              num_workers=t_cfg["num_workers"], pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=t_cfg["batch_size"] * 2, shuffle=False,
                            num_workers=t_cfg["num_workers"], pin_memory=True)

    # --- CNN ---
    model = BCNN(n_actions=n_actions).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"\nCNN : {n_params:,} params (pixel 64×64 → {n_actions} actions)")

    class_weights = torch.zeros(n_actions)
    for i in range(n_actions):
        class_weights[i] = 1.0 / (counts[i].float() + 1.0)
    class_weights = class_weights / class_weights.sum() * n_actions
    criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))

    optimizer = torch.optim.Adam(model.parameters(), lr=t_cfg["lr"],
                                 weight_decay=t_cfg["weight_decay"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=t_cfg["epochs"])

    print(f"Baseline aléatoire : {100/n_actions:.1f}%")
    print(f"\n{'Epoch':>5}  {'train_loss':>10}  {'train_acc':>9}  {'val_loss':>8}  {'val_acc':>7}")

    best_val_acc = 0.0
    best_state = None
    log_every = cfg["logging"]["log_every"]

    for epoch in range(1, t_cfg["epochs"] + 1):
        model.train()
        tr_loss, tr_correct, tr_total = 0.0, 0, 0
        for frm, act in train_loader:
            frm, act = frm.to(device), act.to(device)
            optimizer.zero_grad()
            logits = model(frm)
            loss = criterion(logits, act)
            loss.backward()
            optimizer.step()
            tr_loss += loss.item() * len(frm)
            tr_correct += (logits.argmax(1) == act).sum().item()
            tr_total += len(frm)
        scheduler.step()
        tr_loss /= tr_total
        tr_acc = tr_correct / tr_total * 100

        model.eval()
        va_loss, va_correct, va_total = 0.0, 0, 0
        with torch.no_grad():
            for frm, act in val_loader:
                frm, act = frm.to(device), act.to(device)
                logits = model(frm)
                loss = criterion(logits, act)
                va_loss += loss.item() * len(frm)
                va_correct += (logits.argmax(1) == act).sum().item()
                va_total += len(frm)
        va_loss /= va_total
        va_acc = va_correct / va_total * 100

        if va_acc > best_val_acc:
            best_val_acc = va_acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        if epoch % log_every == 0 or epoch == 1:
            print(f"{epoch:>5}  {tr_loss:>10.4f}  {tr_acc:>8.1f}%  {va_loss:>8.4f}  {va_acc:>6.1f}%")

    gate = best_val_acc > 35.0
    print(f"\nBest val_acc: {best_val_acc:.1f}%  ({'✅ GATE' if gate else '❌ GATE'}: >35%)")

    ckpt_dir = Path(cfg["checkpoint"]["dir"])
    ckpt_dir.mkdir(exist_ok=True)
    ckpt_path = ckpt_dir / cfg["checkpoint"]["name"]
    model.load_state_dict(best_state)
    torch.save({"model_state": model.state_dict(), "cfg": cfg, "val_acc": best_val_acc}, ckpt_path)
    print(f"Checkpoint → {ckpt_path}")


if __name__ == "__main__":
    main()

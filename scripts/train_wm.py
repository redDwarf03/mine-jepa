"""
Phase 2 — Action-conditioned world model training.

The encoder (Phase 1) is frozen. Only the predictor is trained:
    ŝ_{t+1} = Predictor(s_t, a_t)

Loss is the MSE between the prediction and the real latent state s_{t+1},
produced by the frozen encoder (no EMA needed here — the target is fixed).

Monitor:
  pred_loss  — should decrease. Reference baseline = copy_loss (MSE between s_t and s_{t+1}).
  If pred_loss < copy_loss → predictor BETTER than "do nothing".

Usage:
    run.bat scripts/train_wm.py
    run.bat scripts/train_wm.py --epochs 50 --lr 1e-3
"""
import argparse
from pathlib import Path

import torch
import torch.nn.functional as F
import torch.optim as optim
import yaml
from torch.utils.data import DataLoader, random_split

from mine_jepa.encoder.crafter_encoder import CrafterJEPA
from mine_jepa.encoder.dataset import CrafterWMDataset
from mine_jepa.predictor import ActionConditionedPredictor


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/train_wm.yaml")
    p.add_argument("--epochs", type=int, default=None)
    p.add_argument("--lr", type=float, default=None)
    return p.parse_args()


def load_cfg(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_frozen_encoder(ckpt_path: str, cfg: dict, device: torch.device) -> torch.nn.Module:
    """Loads the Phase 1 encoder and freezes all its parameters."""
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    m_cfg = ckpt["cfg"]["model"]
    t_cfg = ckpt["cfg"]["training"]
    v_cfg = ckpt["cfg"]["vicreg"]

    jepa = CrafterJEPA(
        embed_dim=m_cfg["embed_dim"],
        hidden_dim=m_cfg["hidden_dim"],
        predictor_hidden=m_cfg["predictor_hidden"],
        ema_decay=t_cfg["ema_decay"],
        std_coeff=v_cfg["std_coeff"],
        cov_coeff=v_cfg["cov_coeff"],
    )
    jepa.load_state_dict(ckpt["model_state"])
    encoder = jepa.encoder.to(device)
    for p in encoder.parameters():
        p.requires_grad_(False)
    encoder.eval()
    print(f"Encoder loaded: epoch {ckpt['epoch']}, val_loss={ckpt['val_loss']:.4f} [FROZEN]")
    return encoder


def train(cfg: dict) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # --- Frozen encoder ---
    encoder = load_frozen_encoder(cfg["encoder"]["checkpoint"], cfg, device)

    # --- Dataset ---
    dataset = CrafterWMDataset(cfg["data"]["path"])
    val_size = max(256, len(dataset) // 10)
    train_ds, val_ds = random_split(
        dataset,
        [len(dataset) - val_size, val_size],
        generator=torch.Generator().manual_seed(42),
    )
    t_cfg = cfg["training"]
    train_loader = DataLoader(
        train_ds,
        batch_size=t_cfg["batch_size"],
        shuffle=True,
        num_workers=t_cfg["num_workers"],
        pin_memory=device.type == "cuda",
        drop_last=True,
    )
    val_loader = DataLoader(val_ds, batch_size=t_cfg["batch_size"], shuffle=False)
    print(f"Train: {len(train_ds)} triplets | Val: {len(val_ds)} triplets")

    # --- Predictor ---
    m_cfg = cfg["model"]
    predictor = ActionConditionedPredictor(
        embed_dim=m_cfg["embed_dim"],
        n_actions=m_cfg["n_actions"],
        action_dim=m_cfg["action_dim"],
        hidden_dim=m_cfg["hidden_dim"],
    ).to(device)
    n_params = sum(p.numel() for p in predictor.parameters())
    print(f"Predictor parameters: {n_params:,}")

    # --- Optimizer ---
    optimizer = optim.AdamW(
        predictor.parameters(),
        lr=t_cfg["lr"],
        weight_decay=t_cfg["weight_decay"],
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=t_cfg["epochs"])

    log_every = cfg["logging"]["log_every"]
    best_val_loss = float("inf")
    ckpt_dir = Path(cfg["checkpoint"]["dir"])
    ckpt_dir.mkdir(exist_ok=True)
    ckpt_path = ckpt_dir / cfg["checkpoint"]["name"]

    for epoch in range(1, t_cfg["epochs"] + 1):
        predictor.train()
        running_pred = 0.0
        running_copy = 0.0
        steps = 0

        for step, (x_ctx, actions, x_tgt) in enumerate(train_loader):
            x_ctx = x_ctx.to(device)
            actions = actions.to(device)
            x_tgt = x_tgt.to(device)

            with torch.no_grad():
                s_t = encoder(x_ctx)    # [B, D] — current state
                s_t1 = encoder(x_tgt)  # [B, D] — next state (fixed target)

            s_hat = predictor(s_t, actions)
            pred_loss = F.mse_loss(s_hat, s_t1)

            pred_loss.backward()
            optimizer.step()
            optimizer.zero_grad()

            copy_loss = F.mse_loss(s_t, s_t1).item()
            running_pred += pred_loss.item()
            running_copy += copy_loss
            steps += 1

            if step % log_every == 0 and step > 0:
                ratio = pred_loss.item() / (copy_loss + 1e-8)
                better = "✅" if ratio < 1.0 else "  "
                print(
                    f"  step {step:4d} | pred={pred_loss.item():.4f} "
                    f"copy={copy_loss:.4f} ratio={ratio:.3f} {better}"
                )

        avg_pred = running_pred / steps
        avg_copy = running_copy / steps

        # Validation ---
        predictor.eval()
        val_pred = 0.0
        val_copy = 0.0
        with torch.no_grad():
            for x_ctx, actions, x_tgt in val_loader:
                x_ctx = x_ctx.to(device)
                actions = actions.to(device)
                x_tgt = x_tgt.to(device)
                s_t = encoder(x_ctx)
                s_t1 = encoder(x_tgt)
                s_hat = predictor(s_t, actions)
                val_pred += F.mse_loss(s_hat, s_t1).item()
                val_copy += F.mse_loss(s_t, s_t1).item()
        val_pred /= len(val_loader)
        val_copy /= len(val_loader)

        scheduler.step()

        ratio = val_pred / (val_copy + 1e-8)
        gate = "✅ BETTER THAN BASELINE" if ratio < 1.0 else "  below baseline"
        print(
            f"Epoch {epoch:3d}/{t_cfg['epochs']} | "
            f"pred={avg_pred:.4f} copy={avg_copy:.4f} ratio={ratio:.3f} | "
            f"val_pred={val_pred:.4f} val_copy={val_copy:.4f} {gate}"
        )

        if val_pred < best_val_loss:
            best_val_loss = val_pred
            torch.save(
                {
                    "epoch": epoch,
                    "predictor_state": predictor.state_dict(),
                    "cfg": cfg,
                    "val_pred_loss": val_pred,
                    "val_copy_loss": val_copy,
                },
                ckpt_path,
            )

    print(f"\nBest checkpoint → {ckpt_path}  (val_pred={best_val_loss:.4f})")


def main():
    args = parse_args()
    cfg = load_cfg(args.config)
    if args.epochs:
        cfg["training"]["epochs"] = args.epochs
    if args.lr:
        cfg["training"]["lr"] = args.lr
    train(cfg)


if __name__ == "__main__":
    main()

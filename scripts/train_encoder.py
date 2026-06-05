"""
Phase 1 — Entraînement de l'encodeur JEPA sur Crafter.

Ce script entraîne un CrafterJEPA en self-supervised sur les trajectoires
collectées par scripts/collect.py. Pas d'étiquettes, pas de récompense :
uniquement la dynamique des frames (frame_t → frame_t+1).

À surveiller absolument :
  batch_var  — variance des embeddings. Si < 1e-4 → collapse imminent.
  jepa_loss  — doit diminuer. Si stagne → predictor ou encodeur trop faible.
  std_loss   — doit rester proche de 0 (variance >= 1). Monte → risque de collapse.

Usage :
    uv run python scripts/train_encoder.py
    uv run python scripts/train_encoder.py --epochs 50 --lr 1e-3
"""
import argparse
from pathlib import Path

import torch
import torch.optim as optim
import yaml
from torch.utils.data import DataLoader, random_split

from mine_jepa.encoder.crafter_encoder import CrafterJEPA
from mine_jepa.encoder.dataset import CrafterFrameDataset


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/train_encoder.yaml")
    p.add_argument("--epochs", type=int, default=None)
    p.add_argument("--lr", type=float, default=None)
    p.add_argument("--batch_size", type=int, default=None)
    return p.parse_args()


def load_cfg(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def train(cfg: dict) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # --- Dataset ---
    dataset = CrafterFrameDataset(cfg["data"]["path"])
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
    print(f"Train: {len(train_ds)} paires | Val: {len(val_ds)} paires")

    # --- Modèle ---
    m_cfg = cfg["model"]
    v_cfg = cfg["vicreg"]
    model = CrafterJEPA(
        embed_dim=m_cfg["embed_dim"],
        hidden_dim=m_cfg["hidden_dim"],
        predictor_hidden=m_cfg["predictor_hidden"],
        ema_decay=t_cfg["ema_decay"],
        std_coeff=v_cfg["std_coeff"],
        cov_coeff=v_cfg["cov_coeff"],
    ).to(device)

    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Paramètres entraînables : {n_params:,}")

    # --- Optimiseur ---
    optimizer = optim.AdamW(
        list(model.encoder.parameters()) + list(model.predictor.parameters()),
        lr=t_cfg["lr"],
        weight_decay=t_cfg["weight_decay"],
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=t_cfg["epochs"])

    # --- Boucle d'entraînement ---
    log_every = cfg["logging"]["log_every"]
    collapse_thr = cfg["logging"]["collapse_threshold"]
    best_val_loss = float("inf")
    ckpt_dir = Path(cfg["checkpoint"]["dir"])
    ckpt_dir.mkdir(exist_ok=True)
    ckpt_path = ckpt_dir / cfg["checkpoint"]["name"]

    for epoch in range(1, t_cfg["epochs"] + 1):
        model.train()
        running = {"total": 0.0, "jepa": 0.0, "std": 0.0, "cov": 0.0, "batch_var": 0.0}
        steps = 0

        for step, (x_ctx, x_tgt) in enumerate(train_loader):
            x_ctx = x_ctx.to(device)
            x_tgt = x_tgt.to(device)

            losses = model(x_ctx, x_tgt)
            losses["total"].backward()
            optimizer.step()
            optimizer.zero_grad()
            model.update_ema()

            for k in running:
                v = losses[k]
                running[k] += v.item() if hasattr(v, "item") else v
            steps += 1

            if step % log_every == 0:
                bv = losses["batch_var"]
                if bv < collapse_thr:
                    print(
                        f"  ⚠️  COLLAPSE DÉTECTÉ step {step}: batch_var={bv:.2e} < {collapse_thr:.0e}"
                    )

        # Moyennes d'époque
        avgs = {k: v / steps for k, v in running.items()}

        # Validation
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for x_ctx, x_tgt in val_loader:
                x_ctx, x_tgt = x_ctx.to(device), x_tgt.to(device)
                val_loss += model(x_ctx, x_tgt)["total"].item()
        val_loss /= len(val_loader)

        scheduler.step()

        print(
            f"Epoch {epoch:3d}/{t_cfg['epochs']} | "
            f"loss={avgs['total']:.4f} jepa={avgs['jepa']:.4f} "
            f"std={avgs['std']:.4f} cov={avgs['cov']:.4f} "
            f"batch_var={avgs['batch_var']:.4f} | "
            f"val={val_loss:.4f}"
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(
                {
                    "epoch": epoch,
                    "model_state": model.state_dict(),
                    "cfg": cfg,
                    "val_loss": val_loss,
                },
                ckpt_path,
            )

    print(f"\nMeilleur checkpoint → {ckpt_path}  (val_loss={best_val_loss:.4f})")


def main():
    args = parse_args()
    cfg = load_cfg(args.config)
    if args.epochs:
        cfg["training"]["epochs"] = args.epochs
    if args.lr:
        cfg["training"]["lr"] = args.lr
    if args.batch_size:
        cfg["training"]["batch_size"] = args.batch_size
    train(cfg)


if __name__ == "__main__":
    main()

"""
Phase 5 — Train the Plan2Explore disagreement ensemble on FROZEN eb-JEPA latents.

Why: the curiosity bonus (ensemble disagreement) guides the planner toward novel
states when no tree is visible (flat goal-centroid score).  The ensemble is trained
on the *existing* checkpoint so it learns what the WM already knows — disagreement
then flags truly unseen regions of latent space.

Guardrails:
  - ebwm.pt is NEVER touched (loaded read-only, encoder frozen for the whole run).
  - Ensemble saved to checkpoints/curiosity_ensemble.pt (separate file).
  - SEPARATE Adam optimizer on ensemble parameters only.
  - Seeded (torch, numpy, CUDA deterministic) for reproducibility.

Usage: run.bat scripts/train_curiosity.py
       run.bat scripts/train_curiosity.py --config configs/train_curiosity.yaml
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import yaml
from torch.utils.data import DataLoader, random_split

from mine_jepa.ebwm import build_ac_jepa
from mine_jepa.ebwm.curiosity import DisagreementEnsemble
from mine_jepa.ebwm.dataset import MineRLSeqDataset


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/train_curiosity.yaml")
    return p.parse_args()


def load_cfg(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def load_jepa(ckpt_path: str, device: torch.device):
    """Load the frozen eb-JEPA encoder + action encoder (weights_only=False for compat)."""
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    m = ckpt["cfg"]["model"]
    r = ckpt["cfg"]["regularizer"]
    model = build_ac_jepa(
        embed_dim=m["embed_dim"],
        encoder_hidden=m["encoder_hidden"],
        n_actions=m["n_actions"],
        action_embed_dim=m["action_embed_dim"],
        predictor_hidden=m["predictor_hidden"],
        std_coeff=r["std_coeff"],
        cov_coeff=r["cov_coeff"],
        sim_coeff_t=r["sim_coeff_t"],
    ).to(device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    return model, m["embed_dim"], m["action_embed_dim"]


@torch.no_grad()
def encode_batch(
    jepa, obs: torch.Tensor, actions: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Encode a batch of observations and actions into frozen latents.

    obs     : [B, 3, T, H, W]
    actions : [B, 1, T]
    Returns : (latents [B, D, T, H, W], action_enc [B, E, T])
    """
    latents = jepa.encode(obs)                         # [B, D, T, H, W]
    action_enc = jepa.action_encoder(actions)          # [B, E, T]
    return latents, action_enc


def main():
    args = parse_args()
    cfg = load_cfg(args.config)
    seed = cfg.get("seed", 42)
    seed_everything(seed)
    print(f"Seed: {seed}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # --- Load frozen JEPA (read-only, never overwritten) ---
    wm_path = cfg["model"]["checkpoint"]
    print(f"Loading frozen JEPA from {wm_path}...")
    jepa, embed_dim, action_embed_dim = load_jepa(wm_path, device)
    print(f"  embed_dim={embed_dim}, action_embed_dim={action_embed_dim} — frozen.")

    # --- Dataset ---
    d_cfg = cfg["data"]
    print(f"Loading dataset: {d_cfg['path']} (T={d_cfg['num_frames']})")
    ds = MineRLSeqDataset(
        d_cfg["path"],
        num_frames=d_cfg["num_frames"],
        subsample=d_cfg.get("subsample", 1),
    )
    n_val = int(len(ds) * d_cfg.get("val_fraction", 0.1))
    n_train = len(ds) - n_val
    train_ds, val_ds = random_split(
        ds, [n_train, n_val],
        generator=torch.Generator().manual_seed(seed),
    )
    print(f"  Windows: train {n_train:,}  val {n_val:,}")

    t_cfg = cfg["training"]
    train_loader = DataLoader(
        train_ds, batch_size=t_cfg["batch_size"], shuffle=True,
        num_workers=t_cfg.get("num_workers", 0), drop_last=True,
    )
    val_loader = DataLoader(
        val_ds, batch_size=t_cfg["batch_size"], shuffle=False,
        num_workers=t_cfg.get("num_workers", 0),
    )

    # --- Ensemble (separate optimizer, detached latents) ---
    e_cfg = cfg["ensemble"]
    ens = DisagreementEnsemble(
        state_dim=embed_dim,
        action_embed_dim=action_embed_dim,
        n_heads=e_cfg["n_heads"],
        head_hidden=e_cfg["head_hidden"],
    ).to(device)
    n_params = sum(p.numel() for p in ens.parameters())
    print(f"Ensemble params: {n_params:,}  ({e_cfg['n_heads']} heads × {n_params // e_cfg['n_heads']:,})")

    optimizer = torch.optim.Adam(
        ens.parameters(),
        lr=t_cfg["lr"],
        weight_decay=t_cfg.get("weight_decay", 1e-5),
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=t_cfg["epochs"]
    )
    loss_fn = nn.MSELoss()

    print(f"\n{'Epoch':>5}  {'train_loss':>10}  {'val_loss':>9}  {'val_disagree':>12}")

    best_val = float("inf")
    best_state = None

    for epoch in range(1, t_cfg["epochs"] + 1):
        ens.train()
        tot, nb = 0.0, 0
        for obs, actions, _ in train_loader:
            obs = obs.to(device)
            actions = actions.to(device)
            # Encode with the frozen JEPA
            with torch.no_grad():
                latents, action_enc = encode_batch(jepa, obs, actions)
            # Target: latent at t+1 (for each t in [0, T-2])
            # state_in  = latents[:, :, :-1, :, :]  [B, D, T-1, H, W]
            # state_tgt = latents[:, :,  1:, :, :]  [B, D, T-1, H, W]
            # action_in = action_enc[:, :, :-1]      [B, E, T-1]
            s_in  = latents[:, :, :-1].detach()     # [B, D, T-1, H, W]
            s_tgt = latents[:, :, 1:].detach()      # [B, D, T-1, H, W]
            a_in  = action_enc[:, :, :-1].detach()  # [B, E, T-1]

            # Each head predicts s_tgt; loss = mean over heads of MSE
            preds = ens(s_in, a_in)                  # [k, B, D, T-1, H, W]
            # Expand target to match [k, B, D, T-1, H, W]
            tgt_exp = s_tgt.unsqueeze(0).expand_as(preds)
            loss = loss_fn(preds, tgt_exp)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            tot += loss.item()
            nb += 1

        scheduler.step()

        # --- Validation ---
        ens.eval()
        vtot, vdis, vn = 0.0, 0.0, 0
        with torch.no_grad():
            for obs, actions, _ in val_loader:
                obs = obs.to(device)
                actions = actions.to(device)
                latents, action_enc = encode_batch(jepa, obs, actions)
                s_in  = latents[:, :, :-1]
                s_tgt = latents[:, :, 1:]
                a_in  = action_enc[:, :, :-1]
                preds = ens(s_in, a_in)
                tgt_exp = s_tgt.unsqueeze(0).expand_as(preds)
                vloss = loss_fn(preds, tgt_exp)
                # disagreement = variance across heads
                dis = preds.var(dim=0).mean().item()
                b = obs.size(0)
                vtot += vloss.item() * b
                vdis += dis * b
                vn += b

        val_loss = vtot / vn
        val_dis  = vdis / vn
        if val_loss < best_val:
            best_val = val_loss
            best_state = {k: v.cpu().clone() for k, v in ens.state_dict().items()}

        if epoch % cfg["logging"].get("log_every", 1) == 0 or epoch == 1:
            print(f"{epoch:>5}  {tot/nb:>10.4f}  {val_loss:>9.4f}  {val_dis:>12.6f}")

    print(f"\nBest val_loss: {best_val:.4f}")

    ckpt_dir = Path(cfg["checkpoint"]["dir"])
    ckpt_dir.mkdir(exist_ok=True)
    ckpt_path = ckpt_dir / cfg["checkpoint"]["name"]
    if best_state is not None:
        ens.load_state_dict(best_state)
    ens.save(str(ckpt_path))
    print(f"Ensemble checkpoint → {ckpt_path}")

    # Quick smoke-test: forward pass on a random batch
    ens.eval()
    with torch.no_grad():
        dummy_lat = torch.randn(4, embed_dim, 7, 8, 8, device=device)
        dummy_act = torch.randn(4, action_embed_dim, 7, device=device)
        dis = ens.disagreement(dummy_lat, dummy_act)
        print(f"Smoke-test disagreement shape: {tuple(dis.shape)}  "
              f"mean={dis.mean().item():.4f}  — OK")


if __name__ == "__main__":
    main()

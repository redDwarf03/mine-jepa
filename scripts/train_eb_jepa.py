"""
Phase 4c step 3 — Train the action-conditioned world model (eb_jepa).

Key difference vs Phase 2: here encoder AND predictor are trained JOINTLY,
conditioned on action. The latent is thus structured around action consequences
(≠ old frozen frame→frame encoder → ratio 0.959).

Criteria (gates):
  - ratio val_pred/val_copy < 1.0 (WM predicts better than copying state)
  - batch_var > collapse_threshold each epoch (NO collapse — risk #1)

Usage: run.bat scripts/train_eb_jepa.py
"""
import argparse
from pathlib import Path

import numpy as np
import torch
import yaml
from torch.utils.data import DataLoader, random_split

from mine_jepa.ebwm import build_ac_jepa
from mine_jepa.ebwm.dataset import MineRLSeqDataset


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/train_eb_jepa.yaml")
    return p.parse_args()


def load_cfg(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


@torch.no_grad()
def eval_ratio(model, loader, device) -> tuple[float, float, float, float]:
    """Computes val_pred, val_copy, ratio, and batch_var on the validation set."""
    model.eval()
    pred_sum, copy_sum, var_sum, n = 0.0, 0.0, 0.0, 0
    for obs, actions, _ in loader:
        obs, actions = obs.to(device), actions.to(device)
        state = model.encode(obs)                              # [B, D, T, H, W]
        preds, _ = model.unroll(obs, actions, nsteps=1,
                                unroll_mode="parallel", compute_loss=False)
        # positions prédites (t>=1), on ignore le contexte t=0
        pred_loss = ((preds[:, :, 1:] - state[:, :, 1:]) ** 2).mean().item()
        copy_loss = ((state[:, :, :-1] - state[:, :, 1:]) ** 2).mean().item()
        # variance of latent features across the batch (anti-collapse)
        bvar = state.var(dim=0).mean().item()
        b = obs.size(0)
        pred_sum += pred_loss * b
        copy_sum += copy_loss * b
        var_sum += bvar * b
        n += b
    val_pred = pred_sum / n
    val_copy = copy_sum / n
    batch_var = var_sum / n
    ratio = val_pred / max(val_copy, 1e-9)
    return val_pred, val_copy, ratio, batch_var


def main():
    args = parse_args()
    cfg = load_cfg(args.config)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # --- Data ---
    d_cfg = cfg["data"]
    print(f"Loading: {d_cfg['path']} (T={d_cfg['num_frames']}, subsample={d_cfg['subsample']})")
    ds = MineRLSeqDataset(d_cfg["path"], num_frames=d_cfg["num_frames"], subsample=d_cfg["subsample"])
    n_val = int(len(ds) * d_cfg["val_fraction"])
    n_train = len(ds) - n_val
    train_ds, val_ds = random_split(ds, [n_train, n_val],
                                    generator=torch.Generator().manual_seed(42))
    print(f"  Windows: train {n_train:,}  val {n_val:,}")

    t_cfg = cfg["training"]
    train_loader = DataLoader(train_ds, batch_size=t_cfg["batch_size"], shuffle=True,
                              num_workers=t_cfg["num_workers"], drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=t_cfg["batch_size"], shuffle=False,
                            num_workers=t_cfg["num_workers"])

    # --- Model ---
    m_cfg = cfg["model"]
    r_cfg = cfg["regularizer"]
    model = build_ac_jepa(
        embed_dim=m_cfg["embed_dim"], encoder_hidden=m_cfg["encoder_hidden"],
        n_actions=m_cfg["n_actions"], action_embed_dim=m_cfg["action_embed_dim"],
        predictor_hidden=m_cfg["predictor_hidden"],
        std_coeff=r_cfg["std_coeff"], cov_coeff=r_cfg["cov_coeff"],
        sim_coeff_t=r_cfg["sim_coeff_t"],
    ).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"Params: {n_params:,}")

    optimizer = torch.optim.Adam(model.parameters(), lr=t_cfg["lr"],
                                 weight_decay=t_cfg["weight_decay"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=t_cfg["epochs"])

    collapse_thr = cfg["logging"]["collapse_threshold"]
    print(f"\n{'Epoch':>5}  {'train_loss':>10}  {'pred':>7}  {'reg':>7}  "
          f"{'val_pred':>8}  {'val_copy':>8}  {'ratio':>6}  {'batch_var':>9}")

    best_ratio = float("inf")
    best_state = None

    for epoch in range(1, t_cfg["epochs"] + 1):
        model.train()
        tot, tot_p, tot_r, nb = 0.0, 0.0, 0.0, 0
        for obs, actions, _ in train_loader:
            obs, actions = obs.to(device), actions.to(device)
            optimizer.zero_grad()
            _, losses = model.unroll(obs, actions, nsteps=1,
                                     unroll_mode="parallel", compute_loss=True)
            loss, rloss, _, _, ploss = losses
            loss.backward()
            optimizer.step()
            tot += loss.item()
            tot_p += ploss.item()
            tot_r += rloss.item()
            nb += 1
        scheduler.step()

        val_pred, val_copy, ratio, batch_var = eval_ratio(model, val_loader, device)
        collapsed = batch_var < collapse_thr
        flag = "  ⚠️ COLLAPSE" if collapsed else ""

        if ratio < best_ratio and not collapsed:
            best_ratio = ratio
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        if epoch % cfg["logging"]["log_every"] == 0 or epoch == 1:
            print(f"{epoch:>5}  {tot/nb:>10.4f}  {tot_p/nb:>7.4f}  {tot_r/nb:>7.4f}  "
                  f"{val_pred:>8.4f}  {val_copy:>8.4f}  {ratio:>6.3f}  {batch_var:>9.4f}{flag}")

    gate = best_ratio < 1.0
    print(f"\nBest ratio: {best_ratio:.3f}  ({'✅ GATE' if gate else '❌ GATE'}: <1.0 required)")

    ckpt_dir = Path(cfg["checkpoint"]["dir"])
    ckpt_dir.mkdir(exist_ok=True)
    ckpt_path = ckpt_dir / cfg["checkpoint"]["name"]
    if best_state is not None:
        model.load_state_dict(best_state)
    torch.save({"model_state": model.state_dict(), "cfg": cfg, "ratio": best_ratio}, ckpt_path)
    print(f"Checkpoint → {ckpt_path}")



if __name__ == "__main__":
    main()

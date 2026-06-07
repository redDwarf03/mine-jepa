"""
Phase 2 — Gate: world model evaluation (1-step and multi-step latent error).

Questions answered by this script:
  1. 1-step error: does the predictor beat "copy the state"?
  2. Multi-step error (k=1..10): how does rollout error evolve?

Method:
  1-step  : MSE(ŝ_{t+1}, s_{t+1}) vs MSE(s_t, s_{t+1})
  k-step  : unroll ŝ_1 = pred(s_0, a_0), ŝ_2 = pred(ŝ_1, a_1), ...
            compare ŝ_k to s_k and to s_0 (constant baseline)

Phase 2 Gate:
  - 1-step error < copy_baseline error
  - multi-step error < constant baseline for most k

Usage:
    run.bat scripts/eval_wm.py
    run.bat scripts/eval_wm.py --max_k 15
"""
import argparse
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
import yaml
from torch.utils.data import DataLoader, Subset

from mine_jepa.encoder.crafter_encoder import CrafterJEPA
from mine_jepa.encoder.dataset import CrafterSeqDataset, CrafterWMDataset
from mine_jepa.predictor import ActionConditionedPredictor


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/train_wm.yaml")
    p.add_argument("--encoder_ckpt", default=None)
    p.add_argument("--wm_ckpt", default=None)
    p.add_argument("--max_k", type=int, default=None)
    return p.parse_args()


def load_cfg(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_encoder(ckpt_path: str, device: torch.device) -> torch.nn.Module:
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
    return encoder


def load_predictor(ckpt_path: str, cfg: dict, device: torch.device) -> ActionConditionedPredictor:
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    m_cfg = cfg["model"]
    predictor = ActionConditionedPredictor(
        embed_dim=m_cfg["embed_dim"],
        n_actions=m_cfg["n_actions"],
        action_dim=m_cfg["action_dim"],
        hidden_dim=m_cfg["hidden_dim"],
    ).to(device)
    predictor.load_state_dict(ckpt["predictor_state"])
    predictor.eval()
    print(
        f"World model loaded: epoch {ckpt['epoch']}, "
        f"val_pred={ckpt['val_pred_loss']:.4f}, "
        f"val_copy={ckpt['val_copy_loss']:.4f}"
    )
    return predictor


@torch.no_grad()
def eval_one_step(encoder, predictor, cfg: dict, device: torch.device) -> dict:
    """1-step MSE of the predictor vs copy baseline."""
    dataset = CrafterWMDataset(cfg["data"]["path"])
    loader = DataLoader(dataset, batch_size=512, shuffle=False, num_workers=0)

    pred_errors, copy_errors = [], []
    for x_ctx, actions, x_tgt in loader:
        x_ctx = x_ctx.to(device)
        actions = actions.to(device)
        x_tgt = x_tgt.to(device)

        s_t = encoder(x_ctx)
        s_t1 = encoder(x_tgt)
        s_hat = predictor(s_t, actions)

        pred_errors.append(F.mse_loss(s_hat, s_t1, reduction="none").mean(dim=1).cpu())
        copy_errors.append(F.mse_loss(s_t, s_t1, reduction="none").mean(dim=1).cpu())

    pred_mean = torch.cat(pred_errors).mean().item()
    copy_mean = torch.cat(copy_errors).mean().item()
    return {"pred": pred_mean, "copy": copy_mean, "ratio": pred_mean / (copy_mean + 1e-8)}


@torch.no_grad()
def eval_multistep(encoder, predictor, cfg: dict, device: torch.device, max_k: int) -> dict:
    """Latent rollout error for k=1..max_k."""
    e_cfg = cfg["eval"]
    dataset = CrafterSeqDataset(cfg["data"]["path"], k=max_k)

    # Limit to n_sequences for speed
    n = min(e_cfg["n_sequences"], len(dataset))
    idx = np.random.RandomState(42).choice(len(dataset), n, replace=False)
    subset = Subset(dataset, idx.tolist())
    loader = DataLoader(subset, batch_size=128, shuffle=False, num_workers=0)

    # Accumulate MSE per step k
    pred_errors_k = [[] for _ in range(max_k)]
    copy_errors_k = [[] for _ in range(max_k)]

    for seq_frames, seq_actions in loader:
        # seq_frames : [B, k+1, 3, H, W]
        # seq_actions: [B, k]
        B = seq_frames.shape[0]
        seq_frames = seq_frames.to(device)
        seq_actions = seq_actions.to(device)

        # Encode all frames in the sequence
        # [B, k+1, D]
        all_states = torch.stack(
            [encoder(seq_frames[:, t]) for t in range(max_k + 1)], dim=1
        )

        # Predictor rollout
        s_hat = all_states[:, 0]  # real initial state
        for k in range(max_k):
            a_k = seq_actions[:, k]        # [B]
            s_hat = predictor(s_hat, a_k)  # [B, D]
            s_real = all_states[:, k + 1]  # [B, D] — real state at step k+1
            s_init = all_states[:, 0]      # [B, D] — constant baseline

            pred_err = F.mse_loss(s_hat, s_real, reduction="none").mean(dim=1)  # [B]
            copy_err = F.mse_loss(s_init, s_real, reduction="none").mean(dim=1) # [B]

            pred_errors_k[k].append(pred_err.cpu())
            copy_errors_k[k].append(copy_err.cpu())

    results = {}
    for k in range(max_k):
        p = torch.cat(pred_errors_k[k]).mean().item()
        c = torch.cat(copy_errors_k[k]).mean().item()
        results[k + 1] = {"pred": p, "copy": c, "ratio": p / (c + 1e-8)}
    return results


def main():
    args = parse_args()
    cfg = load_cfg(args.config)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    encoder_ckpt = args.encoder_ckpt or cfg["encoder"]["checkpoint"]
    wm_ckpt = args.wm_ckpt or (Path(cfg["checkpoint"]["dir"]) / cfg["checkpoint"]["name"])
    max_k = args.max_k or cfg["eval"]["max_k"]

    if not Path(wm_ckpt).exists():
        print(f"WM checkpoint not found: {wm_ckpt}")
        print("Run first: run.bat scripts/train_wm.py")
        return

    encoder = load_encoder(encoder_ckpt, device)
    predictor = load_predictor(str(wm_ckpt), cfg, device)

    # --- 1-step eval ---
    print("\n--- 1-step evaluation ---")
    r1 = eval_one_step(encoder, predictor, cfg, device)
    gate_1step = r1["ratio"] < 1.0
    print(f"  pred_loss  = {r1['pred']:.5f}")
    print(f"  copy_loss  = {r1['copy']:.5f}")
    print(f"  ratio      = {r1['ratio']:.3f}  {'✅ BETTER THAN BASELINE' if gate_1step else '❌ not yet better'}")

    # --- Multi-step eval ---
    print(f"\n--- Multi-step evaluation (k=1..{max_k}, {cfg['eval']['n_sequences']} sequences) ---")
    mk = eval_multistep(encoder, predictor, cfg, device, max_k)

    print(f"\n{'k':>3} | {'pred':>8} | {'copy':>8} | {'ratio':>6} | gate")
    print("-" * 45)
    gates_ok = 0
    for k, v in mk.items():
        ok = v["ratio"] < 1.0
        if ok:
            gates_ok += 1
        print(
            f"{k:>3} | {v['pred']:>8.5f} | {v['copy']:>8.5f} | "
            f"{v['ratio']:>6.3f} | {'✅' if ok else '  '}"
        )

    print(f"\n{'='*45}")
    print(f"Phase 2 Gate")
    print(f"{'='*45}")
    gate_multistep = gates_ok >= max_k // 2
    print(f"  1-step < baseline    : {'✅' if gate_1step else '❌'}")
    print(f"  multi-step ({gates_ok}/{max_k} k): {'✅' if gate_multistep else '❌'}")
    overall = gate_1step and gate_multistep
    print(f"\n  Phase 2 Gate         : {'✅ PASSED' if overall else '❌ NOT PASSED'}")
    if not overall:
        print("  → Re-run train_wm.py with more epochs or a higher lr.")


if __name__ == "__main__":
    main()

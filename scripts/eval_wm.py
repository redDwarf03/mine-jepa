"""
Phase 2 — Gate : évaluation du world model (erreur latente 1-pas et multi-pas).

Questions auxquelles ce script répond :
  1. Erreur 1-pas : le predictor fait-il mieux que "copier l'état" ?
  2. Erreur multi-pas (k=1..10) : comment l'erreur de rollout évolue-t-elle ?

Méthode :
  1-pas  : MSE(ŝ_{t+1}, s_{t+1}) vs MSE(s_t, s_{t+1})
  k-pas  : dérouler ŝ_1 = pred(s_0, a_0), ŝ_2 = pred(ŝ_1, a_1), ...
           comparer ŝ_k à s_k et à s_0 (baseline constante)

Gate Phase 2 :
  - erreur 1-pas < erreur copy_baseline
  - erreur multi-pas < baseline constante sur la majorité des k

Usage :
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
        f"World model chargé : epoch {ckpt['epoch']}, "
        f"val_pred={ckpt['val_pred_loss']:.4f}, "
        f"val_copy={ckpt['val_copy_loss']:.4f}"
    )
    return predictor


@torch.no_grad()
def eval_one_step(encoder, predictor, cfg: dict, device: torch.device) -> dict:
    """MSE 1-pas du predictor vs baseline copie."""
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
    """Erreur de rollout latent pour k=1..max_k."""
    e_cfg = cfg["eval"]
    dataset = CrafterSeqDataset(cfg["data"]["path"], k=max_k)

    # Limiter à n_sequences pour la rapidité
    n = min(e_cfg["n_sequences"], len(dataset))
    idx = np.random.RandomState(42).choice(len(dataset), n, replace=False)
    subset = Subset(dataset, idx.tolist())
    loader = DataLoader(subset, batch_size=128, shuffle=False, num_workers=0)

    # Accumuler MSE par pas k
    pred_errors_k = [[] for _ in range(max_k)]
    copy_errors_k = [[] for _ in range(max_k)]

    for seq_frames, seq_actions in loader:
        # seq_frames : [B, k+1, 3, H, W]
        # seq_actions: [B, k]
        B = seq_frames.shape[0]
        seq_frames = seq_frames.to(device)
        seq_actions = seq_actions.to(device)

        # Encoder toutes les frames de la séquence
        # [B, k+1, D]
        all_states = torch.stack(
            [encoder(seq_frames[:, t]) for t in range(max_k + 1)], dim=1
        )

        # Rollout du predictor
        s_hat = all_states[:, 0]  # état initial réel
        for k in range(max_k):
            a_k = seq_actions[:, k]        # [B]
            s_hat = predictor(s_hat, a_k)  # [B, D]
            s_real = all_states[:, k + 1]  # [B, D] — état réel au pas k+1
            s_init = all_states[:, 0]      # [B, D] — baseline constante

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
        print(f"Checkpoint WM introuvable : {wm_ckpt}")
        print("Lance d'abord : run.bat scripts/train_wm.py")
        return

    encoder = load_encoder(encoder_ckpt, device)
    predictor = load_predictor(str(wm_ckpt), cfg, device)

    # --- Éval 1-pas ---
    print("\n--- Évaluation 1-pas ---")
    r1 = eval_one_step(encoder, predictor, cfg, device)
    gate_1step = r1["ratio"] < 1.0
    print(f"  pred_loss  = {r1['pred']:.5f}")
    print(f"  copy_loss  = {r1['copy']:.5f}")
    print(f"  ratio      = {r1['ratio']:.3f}  {'✅ MIEUX QUE BASELINE' if gate_1step else '❌ pas encore mieux'}")

    # --- Éval multi-pas ---
    print(f"\n--- Évaluation multi-pas (k=1..{max_k}, {cfg['eval']['n_sequences']} séquences) ---")
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
    print(f"Gate Phase 2")
    print(f"{'='*45}")
    gate_multistep = gates_ok >= max_k // 2
    print(f"  1-pas < baseline     : {'✅' if gate_1step else '❌'}")
    print(f"  multi-pas ({gates_ok}/{max_k} k) : {'✅' if gate_multistep else '❌'}")
    overall = gate_1step and gate_multistep
    print(f"\n  Gate Phase 2         : {'✅ PASSÉ' if overall else '❌ NON PASSÉ'}")
    if not overall:
        print("  → Relancer train_wm.py avec plus d'epochs ou lr plus élevé.")


if __name__ == "__main__":
    main()

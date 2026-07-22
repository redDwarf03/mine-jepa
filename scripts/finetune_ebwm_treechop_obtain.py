"""
Cold-start attempt #14, Phase 2 (docs/10 follow-up) — fine-tune ebwm.pt ITSELF on
a mixed Treechop + Obtain dataset, with per-window photometric augmentation.

Why this differs from attempts #7/#11 (both closed as a frozen-encoder brightness
shortcut): those attempts trained a small head on ebwm.pt's FROZEN latents; the
confound most plausibly lives in the frozen encoder's own representation, which
neither attempt touched. This script fine-tunes the encoder+predictor themselves.

Resumes from checkpoints/ebwm.pt's own weights (NOT retrained from scratch), same
architecture (embed_dim=64 unchanged), a 10x-lower learning rate, few epochs (per
the Phase 4 ablation lesson: over-training broke the agent even as the loss/ratio
looked better — "lower ratio != better"). Saves ONE snapshot per epoch; selection
of which snapshot (if any) "wins" is by a separate gate
(scripts/diagnose_score_generalization.py re-run against each snapshot), never by
val_pred/ratio alone.

checkpoints/ebwm.pt is NEVER written by this script (see checkpoint.name_prefix).

Usage: run.bat scripts/finetune_ebwm_treechop_obtain.py --config configs/finetune_ebwm_treechop_obtain.yaml
"""
import argparse
import random
from pathlib import Path

import numpy as np
import torch
import yaml
from torch.utils.data import DataLoader, WeightedRandomSampler, random_split

from mine_jepa.ebwm import build_ac_jepa
from mine_jepa.ebwm.dataset import MineRLSeqDataset


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/finetune_ebwm_treechop_obtain.yaml")
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


def photometric_augment_window(x: torch.Tensor, aug_cfg: dict, rng: np.random.Generator) -> torch.Tensor:
    """
    x: [B, 3, T, H, W] float [0,1]. Draws ONE brightness/contrast/saturation/gamma
    factor per WINDOW (per batch element b), broadcast across all T frames of that
    window — unlike scripts/train_value_projector.py's per-frame-independent
    jitter (appropriate there for single frames; would corrupt temporal dynamics
    here, where the predictor needs consistent lighting within a sequence).
    """
    cj = aug_cfg.get("color_jitter", {}) if aug_cfg else {}
    if not cj.get("enabled", False):
        return x
    b, c, t, h, w = x.shape
    device = x.device

    def jitter(strength: float) -> torch.Tensor:
        lo, hi = 1.0 - strength, 1.0 + strength
        return torch.from_numpy(rng.uniform(lo, hi, size=b).astype(np.float32)).to(device)

    brightness = jitter(float(cj.get("brightness", 0.0))).view(b, 1, 1, 1, 1)
    contrast = jitter(float(cj.get("contrast", 0.0))).view(b, 1, 1, 1, 1)
    saturation = jitter(float(cj.get("saturation", 0.0))).view(b, 1, 1, 1, 1)
    g_lo, g_hi = cj.get("gamma_range", [1.0, 1.0])
    gamma = torch.from_numpy(
        rng.uniform(float(g_lo), float(g_hi), size=b).astype(np.float32)
    ).to(device).view(b, 1, 1, 1, 1)

    x = (x * brightness).clamp(0.0, 1.0)

    gray = x.mean(dim=1, keepdim=True)                          # [B,1,T,H,W]
    img_mean = gray.mean(dim=(2, 3, 4), keepdim=True)            # [B,1,1,1,1]
    x = ((x - img_mean) * contrast + img_mean).clamp(0.0, 1.0)

    gray = x.mean(dim=1, keepdim=True)
    x = (gray + (x - gray) * saturation).clamp(0.0, 1.0)

    x = x.clamp(min=1e-4).pow(gamma).clamp(0.0, 1.0)
    return x


@torch.no_grad()
def eval_ratio(model, loader, device) -> tuple[float, float, float, float]:
    """Same computation as scripts/train_eb_jepa.py::eval_ratio, always on CLEAN
    unaugmented frames (val_loader never sees photometric_augment_window) so the
    ratio stays comparable to ebwm.pt's original numbers."""
    model.eval()
    pred_sum, copy_sum, var_sum, n = 0.0, 0.0, 0.0, 0
    for obs, actions, _ in loader:
        obs, actions = obs.to(device), actions.to(device)
        state = model.encode(obs)
        preds, _ = model.unroll(obs, actions, nsteps=1,
                                unroll_mode="parallel", compute_loss=False)
        pred_loss = ((preds[:, :, 1:] - state[:, :, 1:]) ** 2).mean().item()
        copy_loss = ((state[:, :, :-1] - state[:, :, 1:]) ** 2).mean().item()
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
    t_cfg = cfg["training"]
    seed = int(t_cfg.get("seed", 0))
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}  |  seed: {seed}")

    # --- Data ---
    d_cfg = cfg["data"]
    print(f"Loading: {d_cfg['path']} (T={d_cfg['num_frames']}, subsample={d_cfg['subsample']}, "
          f"max_action={d_cfg.get('max_action')})")
    source_weights = {int(k): float(v) for k, v in d_cfg.get("source_weights", {}).items()} or None
    ds = MineRLSeqDataset(
        d_cfg["path"], num_frames=d_cfg["num_frames"], subsample=d_cfg["subsample"],
        max_action=d_cfg.get("max_action"), source_weights=source_weights,
    )
    n_val = int(len(ds) * d_cfg["val_fraction"])
    n_train = len(ds) - n_val
    train_ds, val_ds = random_split(ds, [n_train, n_val],
                                    generator=torch.Generator().manual_seed(42))
    print(f"  Windows: train {n_train:,}  val {n_val:,}")

    train_weights = ds.weights[train_ds.indices]
    use_sampler = source_weights is not None and np.ptp(train_weights) > 0
    if use_sampler:
        sampler = WeightedRandomSampler(
            weights=torch.as_tensor(train_weights, dtype=torch.double),
            num_samples=len(train_ds), replacement=True,
            generator=torch.Generator().manual_seed(seed),
        )
        print(f"  Oversampling ON (WeightedRandomSampler): weights={source_weights}")
        train_loader = DataLoader(train_ds, batch_size=t_cfg["batch_size"], sampler=sampler,
                                  num_workers=t_cfg["num_workers"], drop_last=True)
    else:
        train_loader = DataLoader(train_ds, batch_size=t_cfg["batch_size"], shuffle=True,
                                  num_workers=t_cfg["num_workers"], drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=t_cfg["batch_size"], shuffle=False,
                            num_workers=t_cfg["num_workers"])

    # --- Model: build with the ORIGINAL architecture, then resume ebwm.pt's weights ---
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

    resume_path = t_cfg["resume_from"]
    ckpt = torch.load(resume_path, map_location=device, weights_only=False)
    model.load_state_dict(ckpt["model_state"])
    print(f"Resumed weights from {resume_path} (original ratio={ckpt.get('ratio', float('nan')):.4f})")

    optimizer = torch.optim.Adam(model.parameters(), lr=t_cfg["lr"],
                                 weight_decay=t_cfg["weight_decay"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=t_cfg["epochs"])

    aug_cfg = cfg.get("augmentation")
    cj = (aug_cfg or {}).get("color_jitter", {})
    if cj.get("enabled", False):
        print(f"Photometric augmentation ENABLED (training windows only, one shared "
              f"draw per window): brightness={cj.get('brightness')} contrast={cj.get('contrast')} "
              f"saturation={cj.get('saturation')} gamma_range={cj.get('gamma_range')}")
    else:
        print("Photometric augmentation disabled.")
    aug_rng = np.random.default_rng(seed)

    collapse_thr = cfg["logging"]["collapse_threshold"]
    ckpt_dir = Path(cfg["checkpoint"]["dir"])
    ckpt_dir.mkdir(exist_ok=True)
    prefix = cfg["checkpoint"]["name_prefix"]

    print(f"\n{'Epoch':>5}  {'train_loss':>10}  {'pred':>7}  {'reg':>7}  "
          f"{'val_pred':>8}  {'val_copy':>8}  {'ratio':>6}  {'batch_var':>9}  snapshot")

    for epoch in range(1, t_cfg["epochs"] + 1):
        model.train()
        tot, tot_p, tot_r, nb = 0.0, 0.0, 0.0, 0
        for obs, actions, _ in train_loader:
            obs, actions = obs.to(device), actions.to(device)
            obs = photometric_augment_window(obs, aug_cfg, aug_rng)
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

        snap_path = ckpt_dir / f"{prefix}_epoch{epoch}.pt"
        torch.save({"model_state": model.state_dict(), "cfg": cfg, "ratio": ratio,
                    "batch_var": batch_var, "epoch": epoch}, snap_path)

        print(f"{epoch:>5}  {tot/nb:>10.4f}  {tot_p/nb:>7.4f}  {tot_r/nb:>7.4f}  "
              f"{val_pred:>8.4f}  {val_copy:>8.4f}  {ratio:>6.3f}  {batch_var:>9.4f}{flag}  "
              f"-> {snap_path.name}")

    print(f"\nAll {t_cfg['epochs']} epoch snapshots saved under {ckpt_dir} as "
          f"{prefix}_epoch{{1..{t_cfg['epochs']}}}.pt")
    print("Next: re-run scripts/diagnose_score_generalization.py against EACH snapshot "
          "(model.checkpoint override) and select by the Obtain-reversal gate, not by ratio.")


if __name__ == "__main__":
    main()

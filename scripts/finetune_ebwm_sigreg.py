"""
Cold-start attempt #19, Run B — fine-tune ebwm.pt with SIGReg
(mine_jepa.eb_jepa.losses.SIGRegRegularizer) replacing VICReg's std/cov terms as
the anti-collapse regularizer, on the ORIGINAL data/minerl_treechop_obtain
dataset (Run A's action-coverage-fixed _v2 dataset is that run's own variable,
not this one's). Photometric augmentation is disabled so SIGReg is the only new
variable versus the unmodified checkpoints/ebwm.pt baseline.

Why SIGReg at all (see the Run B scoping): VC_IDM_Sim_Regularizer.forward only
ever received sim_coeff_t=0.0 and idm_coeff=0.0 in build_ac_jepa (both already
inert) — the actual anti-collapse term in ebwm.pt's whole training history has
only ever been HingeStdLoss+CovarianceLoss. SIGReg replaces that pair with BCS's
marginal-gaussianity statistic (epps_pulley on random projections), a
distributionally different anti-collapse mechanism. Invariance stays owned by
predcost (SquareLossSeq) elsewhere in JEPA.unroll — SIGReg's own invariance term
is 0 by construction here (z1=z2=x_for_vc).

batch_var does not detect DIMENSIONAL collapse (non-constant on average but
collapsed onto a low-rank subspace) — a failure mode CovarianceLoss explicitly
penalized and this run removes. This script additionally logs an effective-rank
(participation ratio) diagnostic every epoch, and enforces an EARLY-STOP gate
(not just a post-hoc check) on batch_var, effective-rank drop, and ratio.

checkpoints/ebwm.pt is NEVER written by this script (see checkpoint.name_prefix).

Usage: run.bat scripts/finetune_ebwm_sigreg.py --config configs/finetune_ebwm_sigreg.yaml
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
    p.add_argument("--config", default="configs/finetune_ebwm_sigreg.yaml")
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
    """Identical to scripts/finetune_ebwm_treechop_obtain.py's version. Kept for
    config-shape parity, but inert here (augmentation.color_jitter.enabled=false
    in configs/finetune_ebwm_sigreg.yaml) — SIGReg is the only tested variable."""
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

    gray = x.mean(dim=1, keepdim=True)
    img_mean = gray.mean(dim=(2, 3, 4), keepdim=True)
    x = ((x - img_mean) * contrast + img_mean).clamp(0.0, 1.0)

    gray = x.mean(dim=1, keepdim=True)
    x = (gray + (x - gray) * saturation).clamp(0.0, 1.0)

    x = x.clamp(min=1e-4).pow(gamma).clamp(0.0, 1.0)
    return x


@torch.no_grad()
def eval_ratio(model, loader, device) -> tuple[float, float, float, float]:
    """Same computation as scripts/train_eb_jepa.py::eval_ratio, always on clean
    unaugmented frames so the ratio stays comparable to ebwm.pt's original numbers."""
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


@torch.no_grad()
def effective_rank(model, loader, device, max_samples: int) -> float:
    """
    Participation ratio (Σλ)²/Σλ² of the covariance of x_for_vc — the SAME
    reshape build_ac_jepa's regularizer operates on (state.permute(0,2,1,3,4)
    .reshape(b,t,-1).reshape(-1,D), i.e. first_t_only=False,
    spatial_as_samples=False). Detects dimensional collapse (non-constant on
    average, collapsed onto a low-rank subspace) that batch_var is blind to —
    exactly the failure mode CovarianceLoss used to penalize and SIGReg removes.

    Computed via singular values of the (mean-centered) [N, D] feature matrix
    (N samples pooled from loader, D = C*H*W) rather than an explicit DxD
    covariance eigendecomposition — equivalent (eig = s^2) and much cheaper for
    D in the thousands.
    """
    model.eval()
    feats = []
    n = 0
    for obs, actions, _ in loader:
        obs = obs.to(device)
        state = model.encode(obs)  # [B, C, T, H, W]
        b, c, t, h, w = state.shape
        x = state.permute(0, 2, 1, 3, 4).reshape(b, t, -1).reshape(-1, c * h * w)
        feats.append(x.cpu())
        n += x.shape[0]
        if n >= max_samples:
            break
    feats = torch.cat(feats, dim=0)[:max_samples].double()
    feats = feats - feats.mean(dim=0, keepdim=True)
    s = torch.linalg.svdvals(feats)
    eig = s ** 2
    return (eig.sum() ** 2 / (eig.pow(2).sum() + 1e-12)).item()


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
    data_path = Path(d_cfg["path"])
    assert data_path.exists(), f"data path does not exist: {data_path}"
    print(f"Loading: {data_path} (T={d_cfg['num_frames']}, subsample={d_cfg['subsample']}, "
          f"max_action={d_cfg.get('max_action')})")
    source_weights = {int(k): float(v) for k, v in d_cfg.get("source_weights", {}).items()} or None
    ds = MineRLSeqDataset(
        str(data_path), num_frames=d_cfg["num_frames"], subsample=d_cfg["subsample"],
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

    # --- Model: build with the ORIGINAL architecture + SIGReg regularizer, resume ebwm.pt's weights ---
    m_cfg = cfg["model"]
    r_cfg = cfg["regularizer"]
    reg_type = r_cfg.get("type", "vicreg")
    assert reg_type == "sigreg", (
        f"configs/finetune_ebwm_sigreg.yaml regularizer.type={reg_type!r} — this script tests "
        "SIGReg only; use scripts/finetune_ebwm_treechop_obtain.py or scripts/finetune_ebwm_actioncoverage "
        "configs for the VICReg path."
    )
    model = build_ac_jepa(
        embed_dim=m_cfg["embed_dim"], encoder_hidden=m_cfg["encoder_hidden"],
        n_actions=m_cfg["n_actions"], action_embed_dim=m_cfg["action_embed_dim"],
        predictor_hidden=m_cfg["predictor_hidden"],
        std_coeff=r_cfg.get("std_coeff", 0.0), cov_coeff=r_cfg.get("cov_coeff", 0.0),
        sim_coeff_t=r_cfg["sim_coeff_t"],
        regularizer_type=reg_type, sigreg_coeff=r_cfg.get("sigreg_coeff", 1.0),
    ).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"Params: {n_params:,}  |  regularizer: {reg_type} (sigreg_coeff={r_cfg.get('sigreg_coeff', 1.0)})")

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
        print(f"Photometric augmentation ENABLED: brightness={cj.get('brightness')} "
              f"contrast={cj.get('contrast')} saturation={cj.get('saturation')} "
              f"gamma_range={cj.get('gamma_range')}")
    else:
        print("Photometric augmentation disabled (SIGReg is the only tested variable).")
    aug_rng = np.random.default_rng(seed)

    l_cfg = cfg["logging"]
    collapse_thr = float(l_cfg["collapse_threshold"])
    eff_rank_drop_thr = float(l_cfg.get("effective_rank_drop_threshold", 0.5))
    ratio_thr = float(l_cfg.get("ratio_threshold", 1.0))
    eff_rank_max_samples = int(l_cfg.get("effective_rank_max_samples", 2048))

    ckpt_dir = Path(cfg["checkpoint"]["dir"])
    ckpt_dir.mkdir(exist_ok=True)
    prefix = cfg["checkpoint"]["name_prefix"]

    baseline_eff_rank = effective_rank(model, val_loader, device, eff_rank_max_samples)
    print(f"\nBaseline (resumed ebwm.pt, before any SIGReg fine-tuning) effective rank: "
          f"{baseline_eff_rank:.2f}")

    print(f"\n{'Epoch':>5}  {'train_loss':>10}  {'pred':>7}  {'reg':>7}  "
          f"{'val_pred':>8}  {'val_copy':>8}  {'ratio':>6}  {'batch_var':>9}  {'eff_rank':>9}  snapshot")

    stop_reason = None
    epochs_run = 0
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
        eff_rank = effective_rank(model, val_loader, device, eff_rank_max_samples)
        epochs_run = epoch

        snap_path = ckpt_dir / f"{prefix}_epoch{epoch}.pt"
        torch.save({"model_state": model.state_dict(), "cfg": cfg, "ratio": ratio,
                    "batch_var": batch_var, "effective_rank": eff_rank,
                    "baseline_effective_rank": baseline_eff_rank, "epoch": epoch}, snap_path)

        collapsed = batch_var < collapse_thr
        eff_rank_dropped = eff_rank < eff_rank_drop_thr * baseline_eff_rank
        ratio_worse_than_copy = ratio > ratio_thr

        flag = ""
        if collapsed:
            flag = "  ⚠️ COLLAPSE (batch_var)"
        elif eff_rank_dropped:
            flag = f"  ⚠️ DIMENSIONAL COLLAPSE (eff_rank {eff_rank:.1f} < {eff_rank_drop_thr}x baseline {baseline_eff_rank:.1f})"
        elif ratio_worse_than_copy:
            flag = f"  ⚠️ RATIO>{ratio_thr} (predictor worse than copy)"

        print(f"{epoch:>5}  {tot/nb:>10.4f}  {tot_p/nb:>7.4f}  {tot_r/nb:>7.4f}  "
              f"{val_pred:>8.4f}  {val_copy:>8.4f}  {ratio:>6.3f}  {batch_var:>9.4f}  {eff_rank:>9.2f}{flag}  "
              f"-> {snap_path.name}")

        if collapsed:
            stop_reason = (f"batch_var={batch_var:.6f} < collapse_threshold={collapse_thr} at epoch {epoch}")
            break
        if eff_rank_dropped:
            stop_reason = (f"effective_rank={eff_rank:.2f} dropped below "
                           f"{eff_rank_drop_thr}x baseline ({baseline_eff_rank:.2f}) at epoch {epoch}")
            break
        if ratio_worse_than_copy:
            stop_reason = f"ratio={ratio:.4f} exceeded {ratio_thr} (predictor worse than copy) at epoch {epoch}"
            break

    if stop_reason:
        print(f"\n⚠️ EARLY STOP after epoch {epochs_run}: {stop_reason}")
        print(f"Only {epochs_run}/{t_cfg['epochs']} epoch snapshot(s) were produced under {ckpt_dir} "
              f"as {prefix}_epoch{{1..{epochs_run}}}.pt")
    else:
        print(f"\nAll {t_cfg['epochs']} epoch snapshots saved under {ckpt_dir} as "
              f"{prefix}_epoch{{1..{t_cfg['epochs']}}}.pt (no early-stop criterion triggered)")
    print("Next: re-run scripts/diagnose_score_generalization_gates.py against each produced "
          "snapshot (checkpoints list override) and judge by Gate A/Gate B/Gate C (magnitude only), "
          "not by ratio/batch_var/effective_rank alone.")


if __name__ == "__main__":
    main()

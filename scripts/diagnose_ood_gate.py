"""
Cold-start attempt #17 (docs/10_coldstart_engineering.md) — offline OOD-detection
gate. Attempt #10 confirmed ebwm.pt's own goal-centroid score REVERSES direction
on MineRLObtainIronPickaxeDense's spawn distribution (closer trees score LOWER
than open/treeless views — the opposite of Treechop). Fixing the score directly
is closed 5-fold (attempts #7, #11, #14 Phase1/Phase2, #15 all found the same
brightness/scene-composition shortcut in any small trained head bolted onto
ebwm.pt's frozen latent). This script tests an alternative: can a plain
statistical out-of-distribution DETECTOR — no gradient training, nothing for a
downstream head to shortcut with — flag when the score is being computed on a
frame ebwm.pt was never calibrated on, so a LATER dispatch can fall back to the
already-validated FrontierTracker coverage search (attempt #12) instead of
trusting a backwards-pointing compass?

Method: Lee et al., "A Simple Unified Framework for Detecting Out-of-Distribution
Samples and Adversarial Attacks", arXiv:1807.03888 (NeurIPS 2018) — fit a single
Gaussian (mean mu, covariance Sigma) over the training distribution's features,
then flag test points by their Mahalanobis distance to (mu, Sigma). Applied here
to the SAME pooled latent CraftPlannerV4 / SwitchingCraftPlanner already compute
every replan (mine_jepa/ebwm/planner.py: vpool = predicted.mean(dim=(3,4))),
evaluated at a single frame's own encoded latent (h=0, before any action — the
same quantity vpool[:, 0] would be inside a live rollout, no actions needed to
compute it for a static frame). (mu, Sigma) are closed-form statistics fit once
over a Treechop subsample, not a trained model — there is no loss function here
for a brightness shortcut to be found BY.

Three offline gates, no MineRL/Java, no checkpoint touched (ebwm.pt loaded
frozen, requires_grad_(False) verified):
  A. Separation  : mean Mahalanobis distance, Obtain frames vs Treechop frames.
  B. Specificity : is distance elevated SPECIFICALLY on the frames attempt #10
                   hand-labeled and confirmed the score got backwards, or
                   uniformly across all Obtain frames regardless of whether the
                   score happened to be right or wrong on that particular one?
  C. Negative control: Pearson r between Mahalanobis distance and raw mean frame
                   brightness (mine_jepa's 5th independent brightness confound
                   check this campaign, attempts #7/#11/#14x2/#15 all landed
                   between r=0.117 and r=0.947 — if this lands in that range
                   too, the "orthogonal" OOD signal is just brightness again).

Usage: run.bat scripts/diagnose_ood_gate.py --config configs/diagnose_ood_gate.yaml
"""
import argparse
import random
from pathlib import Path

import numpy as np
import torch
import yaml

from mine_jepa.ebwm.dataset import _load_npz
from scripts.diagnose_score_generalization import gather_obtain_frames, gather_treechop_frames
from scripts.play_ebwm import load_model
from scripts.train_value_projector import brightness_of


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/diagnose_ood_gate.yaml")
    return p.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def frames_to_batch(frames: list, device) -> torch.Tensor:
    """list of [H,W,3]-ish arrays (possibly not 64x64, e.g. spawn thumbnails)
    -> [B,3,1,64,64] float [0,1], same resize convention as scripts/play_ebwm.py::preprocess."""
    import cv2
    resized = np.stack([cv2.resize(f[:, :, :3], (64, 64)) for f in frames], axis=0)
    t = torch.from_numpy(resized).float() / 255.0
    return t.permute(0, 3, 1, 2).unsqueeze(2).to(device)  # [B,3,1,64,64]


@torch.no_grad()
def pooled_latents(model, frames: list, device, batch_size: int = 256) -> np.ndarray:
    """
    [N, D] globally-pooled encoder latents — the exact same pooling operation as
    mine_jepa/ebwm/planner.py's `vpool = predicted.mean(dim=(3, 4))`, evaluated at
    a single frame's own encoded state (h=0, pre-action) instead of inside a
    multi-step rollout: model.encode(obs).squeeze(2) is [B,D,H',W'], the mean over
    (H',W') is what vpool[:, 0] would be for that same frame as obs_init.
    """
    out = []
    for i in range(0, len(frames), batch_size):
        obs = frames_to_batch(frames[i:i + batch_size], device)
        z = model.encode(obs).squeeze(2)             # [B,D,H',W']
        vpool = z.mean(dim=(2, 3))                    # [B,D]
        out.append(vpool.cpu().numpy())
    return np.concatenate(out, axis=0)


def sample_fit_frames(data_path: str, n_fit: int, seed: int, exclude_idx: set) -> tuple[np.ndarray, int, int]:
    """
    n_fit frame indices drawn uniformly at random from the WHOLE file (marginal
    distribution, not tied to episode/offset structure), excluding any index that
    also appears in the diagnostic treechop set so fit and evaluation are disjoint.
    Returns (frames, n_kept, n_excluded_hits).
    """
    d = _load_npz(data_path)
    n = len(d["frames"])
    rng = np.random.RandomState(seed)
    buffer = min(n, n_fit + len(exclude_idx) + 200)
    candidates = rng.choice(n, size=buffer, replace=False)
    kept = [int(i) for i in candidates if int(i) not in exclude_idx][:n_fit]
    n_hits = buffer - len([i for i in candidates if int(i) not in exclude_idx])
    return d["frames"][kept], len(kept), n_hits


def fit_gaussian(x: np.ndarray, shrinkage: float) -> tuple[np.ndarray, np.ndarray]:
    """Closed-form mean + regularised-inverse-covariance, arXiv:1807.03888 Eq. 1-2."""
    mu = x.mean(axis=0)
    xc = x - mu
    cov = (xc.T @ xc) / (len(x) - 1)
    cov_reg = cov + shrinkage * np.eye(cov.shape[0])
    cov_inv = np.linalg.inv(cov_reg)
    return mu, cov_inv


def mahalanobis(x: np.ndarray, mu: np.ndarray, cov_inv: np.ndarray) -> np.ndarray:
    xc = x - mu
    return np.sqrt(np.clip(np.einsum("ij,jk,ik->i", xc, cov_inv, xc), a_min=0.0, a_max=None))


def summarize(values: np.ndarray) -> dict:
    return {
        "n": len(values), "mean": float(np.mean(values)), "median": float(np.median(values)),
        "std": float(np.std(values)), "p10": float(np.percentile(values, 10)),
        "p90": float(np.percentile(values, 90)),
    }


def print_summary(title: str, values: np.ndarray) -> None:
    s = summarize(values)
    print(f"  {title:<32} n={s['n']:>4}  mean={s['mean']:.4f}  median={s['median']:.4f}  "
          f"std={s['std']:.4f}  p10={s['p10']:.4f}  p90={s['p90']:.4f}")


def is_wrong_labeled(row: dict, dc: dict) -> bool:
    """True for the hand-labeled subset attempt #10 confirmed the goal-centroid
    score got backwards on (both tree_close-scored-low and no_tree-scored-high
    frames — the WHOLE direction_check set, since attempt #10 found the reversal
    on every one of these, not a mix of right/wrong)."""
    if row["group"] == "obtain_spawn":
        return row["episode"] in set(dc["spawn_tree_close"]) | set(dc["spawn_no_tree"])
    if row["group"] == "obtain_coverage":
        return (row["episode"] in set(dc["coverage_tree_close"]) | set(dc["coverage_no_tree"])
                and float(row["offset"]) == 0.0)
    return False


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    seed = int(cfg.get("seed", 0))
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}  |  seed: {seed}")

    print("\nLoading ebwm.pt frozen (read-only, no gradient, no checkpoint write)...")
    model, ratio = load_model(cfg["model"]["checkpoint"], device)
    model.requires_grad_(False)
    for p in model.parameters():
        assert not p.requires_grad
    print(f"  ebwm.pt loaded (ratio={ratio:.3f}), requires_grad_(False) verified")

    rng = np.random.RandomState(seed)
    print("\nGathering the 251-frame diagnostic set (verbatim from "
          "scripts/diagnose_score_generalization.py)...")
    treechop_rows = gather_treechop_frames(cfg["treechop"], rng)
    obtain_rows = gather_obtain_frames(cfg["obtain"])
    n_spawn = sum(1 for r in obtain_rows if r["group"] == "obtain_spawn")
    n_cov = sum(1 for r in obtain_rows if r["group"] == "obtain_coverage")
    print(f"  {len(treechop_rows)} treechop frames, {n_spawn} obtain_spawn, {n_cov} obtain_coverage")

    exclude_idx = {r["frame_idx"] for r in treechop_rows if r["group"] == "treechop"} \
        if cfg["fit"]["data_path"] == cfg["treechop"]["data_path"] else set()
    fit_frames, n_fit_kept, n_fit_excluded = sample_fit_frames(
        cfg["fit"]["data_path"], int(cfg["fit"]["n_fit_frames"]), seed + 1, exclude_idx,
    )
    print(f"\nFitting (mu, Sigma) on {n_fit_kept} random Treechop frames from "
          f"{cfg['fit']['data_path']} ({n_fit_excluded} candidate draws excluded for "
          f"overlapping the diagnostic treechop set -> fit/eval frames are disjoint)")

    print("\nEncoding all frames through ebwm.pt and pooling (same vpool op as "
          "CraftPlannerV4/SwitchingCraftPlanner)...")
    fit_pooled = pooled_latents(model, list(fit_frames), device)
    all_rows = treechop_rows + obtain_rows
    diag_pooled = pooled_latents(model, [r["frame"] for r in all_rows], device)
    print(f"  fit_pooled: {fit_pooled.shape}   diag_pooled: {diag_pooled.shape}")

    shrinkage = float(cfg["fit"]["covariance_shrinkage"])
    mu, cov_inv = fit_gaussian(fit_pooled, shrinkage)
    print(f"  Gaussian fit: D={mu.shape[0]}, covariance shrinkage={shrinkage}")

    md_all = mahalanobis(diag_pooled, mu, cov_inv)
    for row, md in zip(all_rows, md_all):
        row["mahalanobis"] = float(md)

    out_dir = Path(cfg["output"]["dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / cfg["output"]["csv_name"]
    with open(csv_path, "w") as f:
        f.write("group,episode,offset,frame_idx,mahalanobis\n")
        for row in all_rows:
            f.write(f"{row['group']},{row['episode']},{row['offset']},{row['frame_idx']},"
                    f"{row['mahalanobis']:.6f}\n")
    print(f"\nCSV saved -> {csv_path}")

    stats_path = out_dir / cfg["output"]["stats_name"]
    np.savez(str(stats_path), mu=mu, cov_inv=cov_inv, shrinkage=shrinkage, n_fit=n_fit_kept)
    print(f"(mu, Sigma^-1) saved -> {stats_path} (diagnostic artifact, not a checkpoint)")

    md_treechop = np.array([r["mahalanobis"] for r in all_rows if r["group"] == "treechop"])
    md_obtain = np.array([r["mahalanobis"] for r in all_rows if r["group"] != "treechop"])
    md_spawn = np.array([r["mahalanobis"] for r in all_rows if r["group"] == "obtain_spawn"])
    md_cov = np.array([r["mahalanobis"] for r in all_rows if r["group"] == "obtain_coverage"])

    print(f"\n{'=' * 78}\nGATE A — SEPARATION (Mahalanobis distance, Obtain vs Treechop)\n{'=' * 78}")
    print_summary("treechop", md_treechop)
    print_summary("obtain_spawn", md_spawn)
    print_summary("obtain_coverage", md_cov)
    print_summary("obtain (spawn+coverage)", md_obtain)
    ratio_mean = float(md_obtain.mean() / max(md_treechop.mean(), 1e-12))
    ratio_median = float(np.median(md_obtain) / max(np.median(md_treechop), 1e-12))
    min_sep = float(cfg["gates"]["min_separation_ratio"])
    gate_a_pass = ratio_mean >= min_sep
    print(f"\n  Obtain/Treechop mean ratio   = {ratio_mean:.3f}x")
    print(f"  Obtain/Treechop median ratio = {ratio_median:.3f}x")
    print(f"  Gate A ({min_sep}x required, Obtain higher/more OOD): "
          f"{'PASS' if gate_a_pass else 'FAIL'}")

    dc = cfg["direction_check"]
    wrong_rows = [r for r in obtain_rows if is_wrong_labeled(r, dc)]
    other_rows = [r for r in obtain_rows if not is_wrong_labeled(r, dc)]
    md_wrong = np.array([r["mahalanobis"] for r in wrong_rows])
    md_other = np.array([r["mahalanobis"] for r in other_rows])

    print(f"\n{'=' * 78}\nGATE B — SPECIFICITY (attempt #10's hand-labeled wrong-direction "
          f"frames vs. the rest of Obtain)\n{'=' * 78}")
    print(f"  {len(wrong_rows)} hand-labeled frames confirmed wrong-direction by attempt #10 "
          f"(tree_close scored low, no_tree scored high)")
    print_summary("labeled WRONG-direction", md_wrong)
    print_summary("other Obtain (unlabeled)", md_other)
    print_summary("treechop (reference)", md_treechop)
    specific_ratio = float(md_wrong.mean() / max(md_other.mean(), 1e-12))
    specific_bar = float(cfg["gates"]["specific_ratio_bar"])
    gate_b_pass = specific_ratio >= specific_bar
    print(f"\n  wrong-labeled mean / other-Obtain mean = {specific_ratio:.3f}x "
          f"(bar: {specific_bar}x for 'specific')")
    if gate_b_pass:
        print("  Gate B: distance is ELEVATED SPECIFICALLY on the wrong-scored frames "
              "-> the stronger, more useful result")
    else:
        print("  Gate B: distance is roughly UNIFORM across all Obtain frames regardless "
              "of whether the score was confirmed wrong on that particular frame "
              "-> the weaker result (detects 'this is Obtain', not 'this score is wrong')")

    frames_list = [r["frame"] for r in all_rows]
    bright = brightness_of(frames_list)
    bright_r = float(np.corrcoef(md_all, bright)[0, 1])
    max_bright = float(cfg["gates"]["max_brightness_corr"])
    gate_c_pass = abs(bright_r) < max_bright
    print(f"\n{'=' * 78}\nGATE C — NEGATIVE CONTROL (Mahalanobis distance vs. raw mean frame "
          f"brightness)\n{'=' * 78}")
    print(f"  Pearson r(mahalanobis, brightness), n={len(frames_list)}: {bright_r:.4f}")
    print(f"  Prior confounds this campaign found: r=0.117 (attempt #7) to r=0.947 "
          f"(attempt #14/#15) -- this campaign's 5 prior 'orthogonal' signals all turned out "
          f"to be brightness in disguise")
    print(f"  Gate C (|r| < {max_bright} required): {'PASS' if gate_c_pass else 'FAIL'}")

    print(f"\n{'=' * 78}\nOVERALL VERDICT\n{'=' * 78}")
    go = gate_a_pass and gate_b_pass and gate_c_pass
    print(f"  Gate A (separation)  : {'PASS' if gate_a_pass else 'FAIL'} ({ratio_mean:.3f}x)")
    print(f"  Gate B (specificity) : {'PASS' if gate_b_pass else 'FAIL'} ({specific_ratio:.3f}x)")
    print(f"  Gate C (not-brightness): {'PASS' if gate_c_pass else 'FAIL'} (r={bright_r:.4f})")
    print(f"  -> {'GO' if go else 'NO-GO' if not (gate_a_pass or gate_b_pass) else 'MIXED'}")


if __name__ == "__main__":
    main()

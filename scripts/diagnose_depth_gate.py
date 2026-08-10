"""
Cold-start attempt #18 (docs/10_coldstart_engineering.md), Diagnostic 1 of 2 —
offline test of a genuinely different MODALITY (monocular depth, not any
RGB-derived feature) against the standing brightness/scene-composition confound
that has now defeated six independent mechanisms trying to score "is there a
tree nearby" on MineRLObtainIronPickaxeDense-v0 frames: a small trained head on
ebwm.pt's frozen latent (attempt #7), that same head sourced from Obtain-domain
data (attempt #11), an off-the-shelf 400M-image CLIP model (attempt #14 Phase 1),
direct fine-tuning of ebwm.pt's encoder with photometric augmentation (attempt
#14 Phase 2), a hand-designed lighting-invariant per-tile chromaticity ratio
(attempt #15), and an untrained closed-form Mahalanobis OOD statistic (attempt
#17). Every one of them landed on the same shortcut. Attempt #15's own
conclusion was that fixing this needs "additional structure -- multi-frame,
spatial/geometric, or a different modality entirely."

A brand-new paper, Khan, "Depth-Regularized JEPA World Models Learn More
Transferable Representations from Real Outdoor Robot Data" (arXiv:2607.16314,
2026 -- docs/references/index.md), reports that adding a depth-supervision
auxiliary term to a JEPA world model measurably improves both in-domain and
out-of-domain generalization under real photometric domain shift. This script
asks the cheap, falsifiable question first, exactly as attempt #14 Phase 1 did
for CLIP: does an OFF-THE-SHELF monocular depth estimator (MiDaS, Ranftl et al.,
"Towards Robust Monocular Depth Estimation", intel-isl/MiDaS via torch.hub,
MiDaS_small variant) -- a genuinely different modality from RGB brightness, zero
Minecraft-specific training -- already separate "tree close" from "no tree"
correctly on the exact 251-frame set every prior diagnostic in this campaign has
used, WITHOUT sharing the RGB-brightness confound?

Depth signal: MiDaS predicts RELATIVE INVERSE depth (disparity) -- per the
official repo's own convention, HIGHER output value = CLOSER to the camera (not
absolute metric depth, and not the reversed "higher = farther" convention some
other depth formats use). Reduced to one scalar per frame as the MEAN of the
closest (numerically largest) 10% of pixels -- a robust "is there something
salient and close in front of me" statistic: the single closest pixel is too
noise-sensitive, and a whole-frame mean would wash out a small tree against open
sky/distant terrain.

Frame gathering (`gather_treechop_frames`, `gather_obtain_frames`) is imported
VERBATIM from scripts/diagnose_score_generalization.py, and the hand-labeled
direction-check block is copied in the same shape as
configs/diagnose_ood_gate.yaml (same episodes/chunk-indices attempt #17's
`is_wrong_labeled` used) -- identical 251-frame population and identical
labeled subset to every prior campaign diagnostic, for direct comparability.

Two gates only, the same pair and the same bars this campaign has used since
attempt #7/#14/#15/#17 (no invented extra gates):
  Gate A (direction/separation): mean depth-score of hand-labeled tree_close
    frames vs. hand-labeled no_tree frames (spawn + coverage groups pooled),
    ratio >= min_separation_ratio (1.3) to PASS.
  Gate B (brightness-independence): Pearson r between depth-score and raw mean
    frame brightness (brightness_of, reused verbatim) across ALL 251 frames,
    |r| < max_brightness_corr (0.3) to PASS. Every prior mechanism in this
    campaign landed between r=0.117 and r=0.947 and always failed this gate.

Pure offline diagnostic: no MineRL/Java, no training, no checkpoint (ebwm.pt,
craft_wm_v4.pt) loaded, touched, or modified anywhere in this script. MiDaS
itself is loaded read-only (eval mode, no gradient) purely for inference.

Usage: run.bat scripts/diagnose_depth_gate.py --config configs/diagnose_depth_gate.yaml
"""
import argparse
import random
from pathlib import Path

import numpy as np
import torch
import yaml

from scripts.diagnose_score_generalization import gather_obtain_frames, gather_treechop_frames, print_summary
from scripts.train_value_projector import brightness_of


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/diagnose_depth_gate.yaml")
    return p.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def load_depth_model(cfg: dict, device):
    """
    Off-the-shelf MiDaS_small (Ranftl et al., intel-isl/MiDaS), zero
    Minecraft-specific training -- same "outside model" logic as attempt #14
    Phase 1's CLIP test. Loaded read-only: eval() + requires_grad_(False)
    verified, exactly like every checkpoint-touching script in this campaign.
    """
    repo = cfg["repo"]
    # trust_repo=True: intel-isl/MiDaS isn't on torch.hub's built-in trusted
    # list, so torch.hub.load otherwise blocks on an interactive y/N
    # confirmation prompt -- fatal under a non-interactive/Tee'd run. This is
    # the official documented bypass (torch.hub docs), not a security
    # weakening beyond what running arbitrary hub code already implies.
    model = torch.hub.load(repo, cfg["model_type"], trust_repo=True)
    model = model.to(device).eval()
    model.requires_grad_(False)
    for p in model.parameters():
        assert not p.requires_grad
    transforms = torch.hub.load(repo, "transforms", trust_repo=True)
    transform = transforms.small_transform
    return model, transform


@torch.no_grad()
def depth_score(model, transform, frame: np.ndarray, device, top_frac: float) -> float:
    """
    One scalar per frame: mean of the closest (numerically LARGEST, since MiDaS
    outputs relative inverse depth / disparity -- higher = closer, per the
    official repo's own documented convention) top_frac of pixels. Robust
    "nearest salient object" statistic -- not the single closest pixel (noisy),
    not the whole-frame mean (would wash out a small tree against open sky).
    """
    img = frame[:, :, :3]
    inp = transform(img).to(device)
    pred = model(inp)
    pred = torch.nn.functional.interpolate(
        pred.unsqueeze(1), size=img.shape[:2], mode="bicubic", align_corners=False,
    ).squeeze()
    depth = pred.cpu().numpy().reshape(-1)
    k = max(1, int(len(depth) * top_frac))
    top_vals = np.partition(depth, -k)[-k:]
    return float(top_vals.mean())


def score_all(model, transform, frames: list, device, top_frac: float) -> np.ndarray:
    out = []
    for i, f in enumerate(frames):
        out.append(depth_score(model, transform, f, device, top_frac))
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(frames)}", flush=True)
    return np.array(out, dtype=np.float32)


def label_row(row: dict, dc: dict) -> str | None:
    """
    "tree_close" / "no_tree" / None, using the SAME direction_check block and
    matching rule as attempt #17's `is_wrong_labeled` (obtain_spawn matched by
    episode/thumbnail stem, obtain_coverage matched by chunk index AND
    offset==0.0), split by label instead of collapsed into a single "wrong"
    flag.
    """
    if row["group"] == "obtain_spawn":
        if row["episode"] in dc["spawn_tree_close"]:
            return "tree_close"
        if row["episode"] in dc["spawn_no_tree"]:
            return "no_tree"
    elif row["group"] == "obtain_coverage" and float(row["offset"]) == 0.0:
        if row["episode"] in dc["coverage_tree_close"]:
            return "tree_close"
        if row["episode"] in dc["coverage_no_tree"]:
            return "no_tree"
    return None


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    seed = int(cfg.get("seed", 0))
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}  |  seed: {seed}")

    print("\nLoading MiDaS_small (off-the-shelf, zero Minecraft-specific training, "
          "no ebwm.pt/craft_wm_v4 involved, no checkpoint touched)...")
    model, transform = load_depth_model(cfg["depth_model"], device)
    top_frac = float(cfg["depth_model"]["top_frac"])
    print(f"  MiDaS_small loaded, requires_grad_(False) verified, top_frac={top_frac}")

    rng = np.random.RandomState(seed)
    print("\nGathering the 251-frame diagnostic set (verbatim from "
          "scripts/diagnose_score_generalization.py)...")
    treechop_rows = gather_treechop_frames(cfg["treechop"], rng)
    obtain_rows = gather_obtain_frames(cfg["obtain"])
    n_spawn = sum(1 for r in obtain_rows if r["group"] == "obtain_spawn")
    n_cov = sum(1 for r in obtain_rows if r["group"] == "obtain_coverage")
    print(f"  {len(treechop_rows)} treechop frames, {n_spawn} obtain_spawn, {n_cov} obtain_coverage")

    all_rows = treechop_rows + obtain_rows
    print(f"\nScoring {len(all_rows)} frames through MiDaS_small (mean of the "
          f"closest {top_frac * 100:.0f}% of pixels per frame)...")
    frames = [r["frame"] for r in all_rows]
    scores = score_all(model, transform, frames, device, top_frac)
    for row, s in zip(all_rows, scores):
        row["depth_score"] = float(s)

    out_dir = Path(cfg["output"]["dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / cfg["output"]["csv_name"]
    with open(csv_path, "w") as f:
        f.write("group,episode,offset,frame_idx,depth_score\n")
        for row in all_rows:
            f.write(f"{row['group']},{row['episode']},{row['offset']},{row['frame_idx']},"
                    f"{row['depth_score']:.6f}\n")
    print(f"\nCSV saved -> {csv_path}")

    print(f"\n{'=' * 78}\nFULL-POPULATION SUMMARY (depth_score, for context -- not a gate)\n{'=' * 78}")
    groups = {
        "treechop": np.array([r["depth_score"] for r in all_rows if r["group"] == "treechop"]),
        "obtain_spawn": np.array([r["depth_score"] for r in all_rows if r["group"] == "obtain_spawn"]),
        "obtain_coverage": np.array([r["depth_score"] for r in all_rows if r["group"] == "obtain_coverage"]),
    }
    for name, vals in groups.items():
        if len(vals):
            print_summary(name, vals)

    # ------------------------------------------------------------------
    # Gate A -- hand-labeled direction-check set (attempt #17's block, reused
    # verbatim, same episodes/chunk-indices).
    # ------------------------------------------------------------------
    print(f"\n{'=' * 78}\nGATE A -- SEPARATION (hand-labeled direction-check set, reused verbatim)\n{'=' * 78}")
    dc = cfg["direction_check"]
    labels = [label_row(r, dc) for r in obtain_rows]
    tree_scores = np.array([r["depth_score"] for r, l in zip(obtain_rows, labels) if l == "tree_close"])
    notree_scores = np.array([r["depth_score"] for r, l in zip(obtain_rows, labels) if l == "no_tree"])
    print(f"  {len(tree_scores)} tree_close frames, {len(notree_scores)} no_tree frames")

    tree_mean, notree_mean = float(tree_scores.mean()), float(notree_scores.mean())
    print(f"\n  Tree-close frames  (n={len(tree_scores)}): depth_score = "
          f"{np.array2string(tree_scores, precision=4)}  mean={tree_mean:.4f}")
    print(f"  No-tree/open frames (n={len(notree_scores)}): depth_score = "
          f"{np.array2string(notree_scores, precision=4)}  mean={notree_mean:.4f}")

    correct_direction = tree_mean > notree_mean
    if notree_mean > 1e-6:
        sep_ratio = tree_mean / notree_mean
    elif notree_mean < -1e-6:
        sep_ratio = tree_mean / abs(notree_mean) if tree_mean > 0 else tree_mean / notree_mean
    else:
        sep_ratio = float("inf") if tree_mean > 0 else float("-inf")

    min_sep = float(cfg["gates"]["min_separation_ratio"])
    gate_a_pass = correct_direction and sep_ratio >= min_sep
    print(f"\n  correct_direction (tree_close > no_tree) = {correct_direction}   ratio = {sep_ratio:.3f}")
    print(f"  Gate A ({min_sep}x required, correct direction + ratio): "
          f"{'PASS' if gate_a_pass else 'FAIL'}")

    # ------------------------------------------------------------------
    # Gate B -- brightness-independence, over ALL 251 frames.
    # ------------------------------------------------------------------
    print(f"\n{'=' * 78}\nGATE B -- BRIGHTNESS-INDEPENDENCE (depth_score vs. raw mean frame "
          f"brightness, all {len(all_rows)} frames)\n{'=' * 78}")
    bright = brightness_of(frames)
    bright_r = float(np.corrcoef(scores, bright)[0, 1])
    max_bright = float(cfg["gates"]["max_brightness_corr"])
    gate_b_pass = abs(bright_r) < max_bright
    print(f"  Pearson r(depth_score, brightness), n={len(frames)}: {bright_r:.4f}")
    print(f"  Prior confounds this campaign found: r=0.117 (attempt #7) to r=0.947 "
          f"(attempt #14 CLIP) -- every prior 'orthogonal' signal turned out to be "
          f"brightness in disguise")
    print(f"  Gate B (|r| < {max_bright} required): {'PASS' if gate_b_pass else 'FAIL'}")

    print(f"\n{'=' * 78}\nOVERALL VERDICT\n{'=' * 78}")
    print(f"  Gate A (separation)        : {'PASS' if gate_a_pass else 'FAIL'} ({sep_ratio:.3f}x)")
    print(f"  Gate B (not-brightness)    : {'PASS' if gate_b_pass else 'FAIL'} (r={bright_r:.4f})")
    if gate_a_pass and gate_b_pass:
        verdict = "GO"
    elif not gate_a_pass and not gate_b_pass:
        verdict = "NO-GO (both gates failed)"
    else:
        verdict = "MIXED (one pass, one fail)"
    print(f"  -> {verdict}")

    # ------------------------------------------------------------------
    # Extra due-diligence (not a mandated gate, mirrors attempt #14/#15): does
    # the brightness confound (if any) hold across the full 251-frame
    # population and per-group, not just the small labeled set?
    # ------------------------------------------------------------------
    print(f"\nEXTRA (not a gate): r(depth_score, brightness) per group")
    group_masks = {
        "treechop": np.array([r["group"] for r in all_rows]) == "treechop",
        "obtain_spawn": np.array([r["group"] for r in all_rows]) == "obtain_spawn",
        "obtain_coverage": np.array([r["group"] for r in all_rows]) == "obtain_coverage",
    }
    for name, mask in group_masks.items():
        if mask.sum() > 1:
            r_g = float(np.corrcoef(scores[mask], bright[mask])[0, 1])
            print(f"    {name:<20} n={mask.sum():>4}  r={r_g:.4f}")


if __name__ == "__main__":
    main()

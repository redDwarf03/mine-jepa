"""
Cold-start attempt #15 (docs/10_coldstart_engineering.md) — cheap, narrow follow-up
to attempts #7/#11/#14 (Phase 1 CLIP, Phase 2 encoder fine-tune), all of which found
some form of a brightness-linked confound when trying to score "is there a tree/
forest nearby" on MineRLObtainIronPickaxeDense-v0 frames. The Explorer's
re-assessment: building another hand-rolled visual heuristic in the SAME style as
those four (raw hue-dominance / edge-density on the whole frame) would likely just
be a 5th confirmation of the same pattern and isn't worth building. Instead, this
tests one narrower, genuinely different, and much cheaper idea:

mine_jepa/ebwm/hazard.py's detect_underwater() already solves a RELATED problem
(detecting water) successfully using LIGHTING-INVARIANT RATIOS of raw pixel means
(`ratio = mean(B) / max(mean(R), mean(G))`), not raw pixel values, not learned
parameters, not augmentation — and it works precisely because underwater tint is a
uniform, frame-GLOBAL color cast, so a single whole-frame ratio is enough.
Foliage/tree-proximity is different in kind: it's a spatially LOCAL, compositional
cue (a tree occupies some region of the frame, not the whole thing). The open,
cheap, falsifiable question this script answers: does the SAME ratio-normalization
trick that worked for the global water case ALSO work for foliage if computed PER
SPATIAL TILE rather than for the whole frame at once?

Per tile: g_ratio = mean(G) / (mean(R)+mean(G)+mean(B)+eps) (a normalized green-
channel SHARE, invariant to overall scene brightness by construction, the same
reason hazard.py's ratios are lighting-invariant — scaling all three channels by a
constant leaves the ratio unchanged). Aggregated per-frame as the mean of the
top-K highest-g_ratio tiles (a local canopy patch shouldn't be diluted by the rest
of the frame the way a whole-frame mean would; a single max tile is too noise-prone
to trust alone). A secondary per-tile grayscale-std ("texture") score is also
computed as a cheap canopy/trunk structure proxy, reported for context only — the
PRIMARY thing under test is the ratio-normalized chromaticity idea.

Frame gathering (`gather_treechop_frames`, `gather_obtain_frames`) and the labeled
ground-truth loader are reused VERBATIM from scripts/diagnose_score_generalization.py
and scripts/diagnose_clip_score_generalization.py (same 251-frame set: 160 Treechop,
11 real Obtain spawn thumbnails, 80 Obtain coverage frames; same attempt #11
hand-labeled direction_check block from configs/train_value_projector_obtain.yaml)
so results stay directly comparable to every prior diagnostic in this campaign.

Gates (same dual-gate discipline as attempts #7/#11/#14):
  a. Separation: mean chroma_tile score on tree-close labeled frames vs. no-tree
     labeled frames, >= min_separation_ratio, in the CORRECT direction (tree-close
     higher).
  b. Brightness-independence: Pearson r between chroma_tile score and raw mean
     frame brightness (brightness_of, reused verbatim) over the same labeled set,
     compared against the campaign's established brightness-confound numbers
     (attempt #7: 0.117, ColorJitter: 0.498, attempt #11: 0.643, CLIP: 0.947).

Pure offline diagnostic: no MineRL/Java, no training, no checkpoint loaded, touched,
or modified anywhere in this script.

Usage: run.bat scripts/diagnose_chroma_tile_generalization.py --config configs/diagnose_chroma_tile_generalization.yaml
"""
import argparse
import random
from pathlib import Path

import numpy as np
import yaml

from mine_jepa.ebwm.dataset import _load_npz
from scripts.diagnose_clip_score_generalization import load_labeled_frames
from scripts.diagnose_score_generalization import (
    gather_obtain_frames,
    gather_treechop_frames,
    print_summary,
)
from scripts.train_value_projector import brightness_of


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/diagnose_chroma_tile_generalization.yaml")
    return p.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def tile_scores(frame: np.ndarray, grid: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """
    Splits an [H,W,3] uint8 frame into a `grid`=(rows, cols) grid of tiles and
    computes, per tile: (1) g_ratio = mean(G) / (mean(R)+mean(G)+mean(B)+eps) — a
    lighting-invariant green-channel SHARE, the same ratio-normalization idea as
    hazard.py's detect_underwater (mean(B)/max(mean(R),mean(G))), applied per-tile
    instead of whole-frame so a foliage patch occupying only part of the frame
    isn't diluted by the rest of the scene; (2) grayscale intensity std within the
    tile, a cheap proxy for canopy/trunk texture (foliage/bark are locally
    high-variance; open sky or flat grass are locally smooth). Returns
    (g_ratios, tex_scores), both flat arrays of length rows*cols.
    """
    frame = frame.astype(np.float32)
    h, w = frame.shape[:2]
    rows, cols = grid
    g_ratios, tex_scores = [], []
    for ri in range(rows):
        y0, y1 = int(ri * h / rows), int((ri + 1) * h / rows)
        for ci in range(cols):
            x0, x1 = int(ci * w / cols), int((ci + 1) * w / cols)
            tile = frame[y0:y1, x0:x1]
            r, g, b = tile[..., 0].mean(), tile[..., 1].mean(), tile[..., 2].mean()
            g_ratios.append(float(g / (r + g + b + 1e-3)))
            tex_scores.append(float(tile.mean(axis=-1).std()))
    return np.array(g_ratios, dtype=np.float32), np.array(tex_scores, dtype=np.float32)


def chroma_tile_score(frame: np.ndarray, grid: tuple[int, int], top_k: int) -> tuple[float, float]:
    """
    Aggregates per-tile g_ratio into one frame-level primary score: the mean of the
    top_k highest-g_ratio tiles (not the single max tile — one noisy bright-green
    tile shouldn't decide the whole frame; not the mean over ALL tiles — that
    dilutes a local canopy patch by the rest of the scene, exactly the local-vs-
    global distinction the Explorer's brief drew between foliage and hazard.py's
    frame-global water tint). Secondary texture score: mean of ALL tiles' local std
    (context only, not gated). Returns (primary_score, texture_score).
    """
    g_ratios, tex_scores = tile_scores(frame, grid)
    k = max(1, min(top_k, len(g_ratios)))
    primary = float(np.sort(g_ratios)[-k:].mean())
    texture = float(tex_scores.mean())
    return primary, texture


def score_all(frames: list, grid: tuple[int, int], top_k: int) -> tuple[np.ndarray, np.ndarray]:
    primary, texture = [], []
    for f in frames:
        p, t = chroma_tile_score(f, grid, top_k)
        primary.append(p)
        texture.append(t)
    return np.array(primary), np.array(texture)


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    seed = int(cfg.get("seed", 0))
    seed_everything(seed)

    tile_cfg = cfg["tile"]
    grid = (int(tile_cfg["grid_rows"]), int(tile_cfg["grid_cols"]))
    top_k = int(tile_cfg["top_k"])
    print(f"Seed: {seed}  |  tile grid: {grid[0]}x{grid[1]}  |  top_k: {top_k}")
    print("No checkpoint loaded anywhere in this script (pure pixel-statistic diagnostic).")

    rng = np.random.RandomState(seed)
    print("\nGathering frames (VERBATIM from scripts/diagnose_score_generalization.py, "
          "same 160 Treechop + 11 real Obtain spawn + 80 Obtain-coverage frames as attempts #10/#13)...")
    treechop_rows = gather_treechop_frames(cfg["treechop"], rng)
    obtain_rows = gather_obtain_frames(cfg["obtain"])
    n_spawn = sum(1 for r in obtain_rows if r["group"] == "obtain_spawn")
    n_cov = sum(1 for r in obtain_rows if r["group"] == "obtain_coverage")
    print(f"  treechop: {len(treechop_rows)} frames | obtain_spawn: {n_spawn} | obtain_coverage: {n_cov}")

    all_rows = treechop_rows + obtain_rows
    print(f"\nScoring {len(all_rows)} frames with the tile-based chroma ratio "
          f"(mean of top-{top_k} tiles' g_ratio over a {grid[0]}x{grid[1]} grid)...")
    frames = [r["frame"] for r in all_rows]
    primary_scores, tex_scores = score_all(frames, grid, top_k)
    for row, p, t in zip(all_rows, primary_scores, tex_scores):
        row["chroma_tile_score"] = float(p)
        row["texture_score"] = float(t)

    out_dir = Path(cfg["output"]["dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    full_csv = out_dir / cfg["output"]["full_csv_name"]
    with open(full_csv, "w") as f:
        f.write("group,episode,offset,frame_idx,chroma_tile_score,texture_score\n")
        for row in all_rows:
            f.write(f"{row['group']},{row['episode']},{row['offset']},{row['frame_idx']},"
                    f"{row['chroma_tile_score']:.6f},{row['texture_score']:.6f}\n")
    print(f"Full-population CSV saved -> {full_csv}")

    print(f"\n{'=' * 78}\nFULL-POPULATION SUMMARY (chroma_tile_score, for context — not a gate)\n{'=' * 78}")
    groups = {
        "treechop": np.array([r["chroma_tile_score"] for r in all_rows if r["group"] == "treechop"]),
        "obtain_spawn": np.array([r["chroma_tile_score"] for r in all_rows if r["group"] == "obtain_spawn"]),
        "obtain_coverage": np.array([r["chroma_tile_score"] for r in all_rows if r["group"] == "obtain_coverage"]),
    }
    for name, vals in groups.items():
        if len(vals):
            print_summary(name, vals)

    # ------------------------------------------------------------------
    # Ground-truth labeled set (attempt #11's direction_check block, reused
    # verbatim via diagnose_clip_score_generalization.load_labeled_frames) — the
    # actual gates run on this, not the full population.
    # ------------------------------------------------------------------
    print(f"\n{'=' * 78}\nGATES (attempt #11's hand-labeled direction-check set, reused verbatim)\n{'=' * 78}")
    tree_frames, notree_frames = load_labeled_frames(cfg)
    tree_scores, tree_tex = score_all(tree_frames, grid, top_k)
    notree_scores, notree_tex = score_all(notree_frames, grid, top_k)
    tree_bright = brightness_of(tree_frames)
    notree_bright = brightness_of(notree_frames)

    labeled_csv = out_dir / cfg["output"]["labeled_csv_name"]
    with open(labeled_csv, "w") as f:
        f.write("label,index,chroma_tile_score,texture_score,brightness\n")
        for i, (s, t, b) in enumerate(zip(tree_scores, tree_tex, tree_bright)):
            f.write(f"tree_close,{i},{s:.6f},{t:.6f},{b:.6f}\n")
        for i, (s, t, b) in enumerate(zip(notree_scores, notree_tex, notree_bright)):
            f.write(f"no_tree,{i},{s:.6f},{t:.6f},{b:.6f}\n")
    print(f"Labeled-set CSV saved -> {labeled_csv}")

    tree_mean, notree_mean = float(tree_scores.mean()), float(notree_scores.mean())
    print(f"\n  Tree-close frames  (n={len(tree_scores)}): chroma_tile_score = "
          f"{np.array2string(tree_scores, precision=4)}  mean={tree_mean:.4f}")
    print(f"  No-tree/open frames (n={len(notree_scores)}): chroma_tile_score = "
          f"{np.array2string(notree_scores, precision=4)}  mean={notree_mean:.4f}")
    print(f"  (secondary, not gated) texture_score means: tree={tree_tex.mean():.4f}  "
          f"no_tree={notree_tex.mean():.4f}")

    correct_direction = tree_mean > notree_mean
    if notree_mean > 1e-6:
        sep_ratio = tree_mean / notree_mean
    elif notree_mean < -1e-6:
        sep_ratio = tree_mean / abs(notree_mean) if tree_mean > 0 else tree_mean / notree_mean
    else:
        sep_ratio = float("inf") if tree_mean > 0 else float("-inf")

    min_sep = float(cfg["gates"]["min_separation_ratio"])
    gate_a = correct_direction and sep_ratio >= min_sep
    print(f"\nGATE a — SEPARATION: tree_mean={tree_mean:.4f}  no_tree_mean={notree_mean:.4f}  "
          f"correct_direction(tree>no_tree)={correct_direction}  ratio={sep_ratio:.3f}  "
          f"(required >= {min_sep}) -> {'PASS' if gate_a else 'FAIL'}")

    all_labeled_scores = np.concatenate([tree_scores, notree_scores])
    all_labeled_bright = np.concatenate([tree_bright, notree_bright])
    bright_r = float(np.corrcoef(all_labeled_scores, all_labeled_bright)[0, 1])
    target_abs_r = float(cfg["gates"]["brightness_target_abs_r"])
    gate_b = abs(bright_r) < target_abs_r
    print(f"\nGATE b — BRIGHTNESS CONFOUND: r(chroma_tile_score, brightness) over the "
          f"{len(all_labeled_scores)} labeled frames = {bright_r:.4f}  "
          f"(target |r| < {target_abs_r}; campaign baselines — attempt #7: 0.117, "
          f"ColorJitter: 0.498, attempt #11: 0.643, CLIP: 0.947) -> "
          f"{'PASS' if gate_b else 'FAIL'}")

    print(f"\n{'=' * 78}")
    if gate_a and gate_b:
        verdict = "BOTH PASS"
    elif not gate_a and not gate_b:
        verdict = "BOTH FAIL"
    else:
        verdict = "MIXED (one pass, one fail)"
    print(f"OVERALL: gate a = {'PASS' if gate_a else 'FAIL'}, "
          f"gate b = {'PASS' if gate_b else 'FAIL'} -> {verdict}")
    print(f"{'=' * 78}")

    # ------------------------------------------------------------------
    # Extra due-diligence (not a mandated gate, mirrors attempt #14's CLIP script):
    # is the brightness confound specific to the small hand-labeled set, or does it
    # hold across the full 251-frame population too?
    # ------------------------------------------------------------------
    full_bright = brightness_of(frames)
    full_r = float(np.corrcoef(primary_scores, full_bright)[0, 1])
    print(f"\nEXTRA (not a gate): r(chroma_tile_score, brightness) over the FULL "
          f"{len(primary_scores)}-frame population (both domains) = {full_r:.4f}")
    for name, vals in groups.items():
        if len(vals):
            mask = np.array([r["group"] for r in all_rows]) == name
            r_g = float(np.corrcoef(primary_scores[mask], full_bright[mask])[0, 1])
            print(f"    {name:<20} n={mask.sum():>4}  r={r_g:.4f}")


if __name__ == "__main__":
    main()

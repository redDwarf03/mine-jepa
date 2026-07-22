"""
Cold-start attempt #14 (docs/10 follow-up) — merge Treechop training data with
Obtain-domain data so ebwm.pt itself (not a downstream head) can be fine-tuned on
a mixed distribution.

Three sources concatenated in order:
  1. data/minerl_goal/episodes.npz     — Treechop, ebwm.pt's current training data.
  2. data/minerl_craft/episodes.npz    — 40 real ObtainIronPickaxe expert demos.
  3. data/minerl_coverage/episodes.npz — attempt #3's random-policy Obtain coverage
     episodes (genuinely "lost/searching" frames Treechop-only data lacks).

Handles two known catches explicitly (see CLAUDE.md's attempt #14 entry):
  - data/minerl_coverage's `dones` array is entirely False (collect_minerl_multi.py
    shard-merge bug, docs/10 attempt #7) — episodes are actually fixed-length
    (max_steps_per_episode=400, configs/collect_minerl_coverage.yaml). We
    reconstruct true episode boundaries by forcing dones=True every 400 frames.
  - A `source` array (0=treechop, 1=craft, 2=coverage) is written alongside the
    usual fields so MineRLSeqDataset can (a) filter out any window touching a
    craft-only action index >=17 [craft demos/coverage were collected over the
    22-action Obtain space, but ebwm.pt's action-embedding table stays n_actions=17]
    and (b) oversample Obtain-sourced windows relative to Treechop's much larger
    volume, mirroring this project's craft_weight=30 precedent for WM v4.

No inventory stream is kept — ebwm.pt is a pure visual world model, unlike
CraftSeqDataset's WM v4 use case.

Usage:
    run.bat scripts/merge_treechop_obtain.py \
        --treechop data/minerl_goal/episodes.npz \
        --craft data/minerl_craft/episodes.npz \
        --coverage data/minerl_coverage/episodes.npz \
        --out data/minerl_treechop_obtain/episodes.npz \
        --coverage-chunk-size 400
"""
import argparse
from pathlib import Path

import numpy as np


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--treechop", default="data/minerl_goal/episodes.npz")
    p.add_argument("--craft", default="data/minerl_craft/episodes.npz")
    p.add_argument("--coverage", default="data/minerl_coverage/episodes.npz")
    p.add_argument("--out", default="data/minerl_treechop_obtain/episodes.npz")
    p.add_argument("--coverage-chunk-size", type=int, default=400)
    return p.parse_args()


def force_chunk_boundaries(dones: np.ndarray, chunk_size: int) -> np.ndarray:
    """If dones is entirely False, reconstruct fixed-length episode boundaries
    (data/minerl_coverage's known shard-merge bug, docs/10 attempt #7)."""
    dones = dones.copy()
    if not dones.any():
        n = len(dones)
        for end in range(chunk_size - 1, n, chunk_size):
            dones[end] = True
        dones[-1] = True
    return dones


def main():
    args = parse_args()
    treechop = np.load(args.treechop)
    craft = np.load(args.craft)
    coverage = np.load(args.coverage)

    tc_frames, tc_actions = treechop["frames"], treechop["actions"].astype(np.int64)
    tc_dones = treechop["dones"].astype(bool)
    tc_rewards = treechop["rewards"].astype(np.float32)

    cr_frames, cr_actions = craft["frames"], craft["actions"].astype(np.int64)
    cr_dones = craft["dones"].astype(bool)
    cr_rewards = craft["rewards"].astype(np.float32)

    cv_frames, cv_actions = coverage["frames"], coverage["actions"].astype(np.int64)
    cv_dones = force_chunk_boundaries(coverage["dones"].astype(bool), args.coverage_chunk_size)
    cv_rewards = coverage["rewards"].astype(np.float32) if "rewards" in coverage else \
        np.zeros(len(cv_frames), dtype=np.float32)

    n_tc, n_cr, n_cv = len(tc_frames), len(cr_frames), len(cv_frames)

    frames = np.concatenate([tc_frames, cr_frames, cv_frames], axis=0)
    actions = np.concatenate([tc_actions, cr_actions, cv_actions], axis=0)
    dones = np.concatenate([tc_dones, cr_dones, cv_dones], axis=0)
    rewards = np.concatenate([tc_rewards, cr_rewards, cv_rewards], axis=0)
    source = np.concatenate([
        np.zeros(n_tc, dtype=np.uint8),
        np.ones(n_cr, dtype=np.uint8),
        np.full(n_cv, 2, dtype=np.uint8),
    ])

    # Force a boundary at every source-file junction so no sliding window can
    # bridge frames that were never actually consecutive in the real env.
    dones[n_tc - 1] = True
    dones[n_tc + n_cr - 1] = True

    n_over17_cr = int((cr_actions >= 17).sum())
    n_over17_cv = int((cv_actions >= 17).sum())

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_path,
        frames=frames, actions=actions, dones=dones, rewards=rewards, source=source,
    )

    print(f"Treechop : {n_tc:,} frames ({args.treechop})")
    print(f"Craft    : {n_cr:,} frames ({args.craft}), {n_over17_cr:,} frames "
          f"({100 * n_over17_cr / max(n_cr, 1):.1f}%) use craft-only action idx>=17")
    print(f"Coverage : {n_cv:,} frames ({args.coverage}), {n_over17_cv:,} frames "
          f"({100 * n_over17_cv / max(n_cv, 1):.1f}%) use craft-only action idx>=17, "
          f"dones reconstructed every {args.coverage_chunk_size} frames "
          f"({int(cv_dones.sum())} episode boundaries)")
    print(f"Merged   : {frames.shape[0]:,} frames -> {out_path}")
    print(f"  frames shape : {frames.shape}")
    print(f"  source counts: treechop={n_tc:,} craft={n_cr:,} coverage={n_cv:,}")


if __name__ == "__main__":
    main()

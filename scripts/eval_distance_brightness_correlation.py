"""
Offline brightness-confound check for a trained DistanceProjector checkpoint.

Cold-start attempt #7 found that the (unaugmented) projector's live "lost" signal
correlated with scene brightness (day vs. dusk/night, r=-0.57 during MineRL play)
rather than tree-proximity. This script measures the closest OFFLINE analog on a
held-out split: predicted distance-to-goal vs. each frame's mean pixel brightness,
Pearson r, always on UNAUGMENTED frames — so any checkpoint (attempt #7's original,
or a photometric-augmentation retrain) can be scored the exact same way and compared
directly, without spending live MineRL time.

Note: this is not literally the same measurement as attempt #7's r=-0.57 (that one
was goal_score_std over MPC candidates during play; this one is predicted
distance-to-goal on single held-out frames, offline) — it is the requested cheap
offline analog. Comparing two checkpoints against EACH OTHER on this exact metric is
apples-to-apples; comparing either number to attempt #7's -0.57 is only a rough
directional check.

Usage:
  run.bat scripts/eval_distance_brightness_correlation.py \
      --config configs/train_value_projector.yaml --checkpoint checkpoints/value_projector.pt
"""
import argparse

import numpy as np
import torch
import yaml

from mine_jepa.ebwm.value_head import DistanceProjector
from scripts.train_value_projector import (
    PairPool,
    build_chop_goal_flat,
    compute_brightness_correlation,
    load_frozen_model,
    seed_everything,
)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/train_value_projector.yaml")
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--n_samples", type=int, default=500)
    return p.parse_args()


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    seed = int(cfg.get("seed", 42))
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}  |  seed: {seed}")

    model = load_frozen_model(cfg, device)

    d_cfg = cfg["data"]
    pool = PairPool(d_cfg["treechop_path"], d_cfg["coverage_path"],
                     coverage_chunk_size=int(d_cfg.get("coverage_chunk_size", 400)))
    _, val_eps = pool.split(float(d_cfg.get("val_fraction", 0.1)), seed)
    print(f"  Held-out val episodes: {len(val_eps)}")

    goal_flat = build_chop_goal_flat(model, cfg["goal"], device)
    projector = DistanceProjector.load(args.checkpoint, device=device)
    projector.eval()

    rng = np.random.default_rng(seed)
    r, n = compute_brightness_correlation(model, projector, pool, val_eps, goal_flat, device,
                                           args.n_samples, rng)
    print(f"\nCheckpoint: {args.checkpoint}")
    print(f"Brightness confound check (pred dist-to-goal vs. mean pixel brightness), "
          f"held-out UNAUGMENTED, n={n}: r={r:.4f}")


if __name__ == "__main__":
    main()

"""
Offline brightness-confound check for checkpoints/value_projector_obtain.pt
(cold-start attempt #11) — same measurement as
scripts/eval_distance_brightness_correlation.py, but built on the Obtain-domain
pool/goal (scripts/train_value_projector_obtain.py) instead of the Treechop-domain
one, so the Tester can re-check the brightness confound on the saved checkpoint
without re-running training.

Usage:
  run.bat scripts/eval_distance_brightness_correlation_obtain.py \
      --config configs/train_value_projector_obtain.yaml \
      --checkpoint checkpoints/value_projector_obtain.pt
"""
import argparse

import numpy as np
import torch
import yaml

from mine_jepa.ebwm.value_head import DistanceProjector
from scripts.train_value_projector import PairPool, compute_brightness_correlation, load_frozen_model, seed_everything
from scripts.train_value_projector_obtain import build_obtain_goal_flat, exclude_coverage_chunks


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/train_value_projector_obtain.yaml")
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--n_samples", type=int, default=500)
    return p.parse_args()


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    seed = int(cfg.get("seed", 0))
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}  |  seed: {seed}")

    model = load_frozen_model(cfg, device)

    d_cfg = cfg["data"]
    chunk_size = int(d_cfg.get("coverage_chunk_size", 400))
    pool = PairPool(d_cfg["demos_path"], d_cfg["coverage_path"], coverage_chunk_size=chunk_size)
    exclude_coverage_chunks(pool, chunk_size, d_cfg.get("holdout_coverage_chunks", []))
    _, val_eps = pool.split(float(d_cfg.get("val_fraction", 0.1)), seed)
    print(f"  Held-out val episodes: {len(val_eps)}")

    goal_cfg = cfg["goal"]
    goal_flat, n_goal_frames = build_obtain_goal_flat(
        model, d_cfg["demos_path"], device,
        log_item=goal_cfg.get("log_item", "log"), min_frames=int(goal_cfg.get("min_frames", 10)),
    )
    print(f"  goal_flat: {tuple(goal_flat.shape)} (from {n_goal_frames} log-gain frames)")

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

"""
Robust MineRL collection — 1 episode per subprocess, then merge.

Why: MineRL 0.4.4 reset between two episodes is broken on Windows
(MALMOBUSY race condition → mission socket becomes unresponsive → TimeoutError).
Episode 1 of a fresh process always succeeds. We work around the reset by
spawning a fresh Python process (= a fresh Minecraft) per episode.

Each shard = data/minerl/shards/shard_NN/episodes.npz
Final merge → data/minerl/episodes.npz (format expected by train_encoder/train_wm).

Usage:
    run.bat scripts/collect_minerl_multi.py --shards 15
    run.bat scripts/collect_minerl_multi.py --shards 15 --config configs/collect_minerl.yaml
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

KEYS = ["frames", "actions", "dones", "health", "food", "drink", "energy", "rewards"]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--shards", type=int, default=15, help="number of episodes/processes")
    p.add_argument("--config", default="configs/collect_minerl.yaml")
    p.add_argument("--out", default="data/minerl")
    return p.parse_args()


def kill_stray_java():
    """Kill leftover Minecraft processes between shards (Windows)."""
    subprocess.run(
        ["taskkill", "/F", "/IM", "java.exe", "/T"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def collect_one_shard(idx: int, config: str, shard_dir: Path) -> bool:
    out = shard_dir / f"shard_{idx:02d}"
    npz = out / "episodes.npz"
    if npz.exists():
        print(f"[shard {idx:02d}] already present, skip", flush=True)
        return True

    print(f"\n{'='*60}\n[shard {idx:02d}] collecting 1 episode → {out}\n{'='*60}", flush=True)
    proc = subprocess.run(
        [sys.executable, "scripts/collect.py",
         "--config", config, "--episodes", "1", "--out", str(out)],
        env=dict(os.environ),
    )
    ok = proc.returncode == 0 and npz.exists()
    print(f"[shard {idx:02d}] {'OK' if ok else 'FAILED'} (rc={proc.returncode})", flush=True)
    return ok


def merge_shards(shard_dir: Path, out_dir: Path, n: int) -> None:
    acc = {k: [] for k in KEYS}
    n_ok = 0
    for i in range(n):
        npz = shard_dir / f"shard_{i:02d}" / "episodes.npz"
        if not npz.exists():
            continue
        d = np.load(npz)
        for k in KEYS:
            if k in d:
                acc[k].append(d[k])
        n_ok += 1

    if n_ok == 0:
        print("\n⚠️  No valid shards to merge.", flush=True)
        return

    merged = {k: np.concatenate(v) for k, v in acc.items() if v}
    out_path = out_dir / "episodes.npz"
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_path, **merged)

    n_frames = merged["frames"].shape[0]
    print(f"\n{'='*60}", flush=True)
    print(f"MERGE: {n_ok}/{n} shards → {out_path}", flush=True)
    print(f"  transitions : {n_frames}", flush=True)
    print(f"  frames      : {merged['frames'].shape}", flush=True)
    print(f"{'='*60}", flush=True)


def main():
    args = parse_args()
    out_dir = Path(args.out)
    shard_dir = out_dir / "shards"
    shard_dir.mkdir(parents=True, exist_ok=True)

    n_ok = 0
    for i in range(args.shards):
        if collect_one_shard(i, args.config, shard_dir):
            n_ok += 1
        kill_stray_java()

    print(f"\nSuccessful shards: {n_ok}/{args.shards}", flush=True)
    merge_shards(shard_dir, out_dir, args.shards)


if __name__ == "__main__":
    main()

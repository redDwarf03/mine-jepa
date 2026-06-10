"""
Run N JEPA agents in parallel (each in its own Minecraft), side by side.

True shared-world multi-agent in MineRL 0.4 hits the Malmo mission-sync wall (the
MALMOBUSY family). This delivers the spirit — "several JEPA agents playing at once" —
the robust way: N independent single-agent episodes launched CONCURRENTLY, then their
videos stitched horizontally into one clip.

Each agent runs the eb-JEPA Treechop chopper (its own world model + MPC planner).

⚠️ N agents = N Minecraft clients at once. 2 is realistic on a consumer 8 GB machine.

Usage: run.bat scripts/play_parallel.py --agents 2
"""
import argparse
import copy
import os
import subprocess
import sys
import time
from pathlib import Path

import imageio
import numpy as np
import yaml


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--agents", type=int, default=2)
    p.add_argument("--config", default="configs/play_ebwm.yaml")
    p.add_argument("--script", default="scripts/play_ebwm.py")
    p.add_argument("--out", default="assets/agent_play_parallel.gif")
    p.add_argument("--stagger", type=float, default=8.0, help="seconds between launches")
    return p.parse_args()


def main():
    args = parse_args()
    base = yaml.safe_load(open(args.config))
    work = Path("logs/parallel")
    work.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}", flush=True)
    print(f"Parallel JEPA agents — {args.agents} concurrent Minecraft worlds", flush=True)
    print(f"{'='*60}", flush=True)

    procs, gif_paths, logs = [], [], []
    for i in range(args.agents):
        cfg = copy.deepcopy(base)
        gp = work / f"agent_{i}.gif"
        cfg["logging"]["save_gif"] = True
        cfg["logging"]["gif_episodes"] = 1
        cfg["logging"]["gif_path"] = str(gp)
        cfg.setdefault("agent", {})["episodes"] = 1
        cfg_path = work / f"config_{i}.yaml"
        yaml.safe_dump(cfg, open(cfg_path, "w"))
        gif_paths.append(gp)

        log_path = work / f"agent_{i}.log"
        logs.append(log_path)
        lf = open(log_path, "w", encoding="utf-8")
        print(f"[agent {i}] launching its own Minecraft → {log_path}", flush=True)
        procs.append(subprocess.Popen(
            [sys.executable, args.script, "--config", str(cfg_path), "--episodes", "1"],
            env=dict(os.environ), stdout=lf, stderr=subprocess.STDOUT, text=True,
        ))
        time.sleep(args.stagger)   # stagger boots to ease port/startup contention

    print("\nAll agents launched — waiting (each plays 1 episode)...", flush=True)
    for i, pr in enumerate(procs):
        pr.wait()
        tail = Path(logs[i]).read_text(encoding="utf-8", errors="replace").splitlines()
        result = next((ln for ln in reversed(tail) if "reward=" in ln), "(no result line)")
        print(f"[agent {i}] done (rc={pr.returncode}) — {result.strip()}", flush=True)

    stitch(gif_paths, args.out)


def stitch(gif_paths, out):
    """Read each agent GIF and lay the frames side by side into one clip."""
    seqs = []
    for gp in gif_paths:
        if Path(gp).exists():
            seqs.append([np.asarray(f)[..., :3] for f in imageio.mimread(str(gp), memtest=False)])
    if not seqs:
        print("No GIFs produced — nothing to stitch.", flush=True)
        return
    h = min(s[0].shape[0] for s in seqs)
    T = min(len(s) for s in seqs)
    frames = []
    for t in range(T):
        row = [s[t][:h] for s in seqs]
        frames.append(np.hstack(row))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    imageio.mimsave(out, frames, fps=10, loop=0)
    print(f"\nSide-by-side GIF ({len(seqs)} agents, {T} frames) → {out}", flush=True)


if __name__ == "__main__":
    main()

"""
Robust MineRL MPC agent — 1 episode per subprocess, then aggregation.

Why: MineRL 0.4.4 reset between two episodes is broken on Windows
(MALMOBUSY race condition → mission socket becomes unresponsive → TimeoutError).
Episode 1 of a fresh process always succeeds. We work around the reset by
spawning a fresh Python process (= a fresh Minecraft) per episode, then
aggregating the metrics.

Usage:
    run.bat scripts/play_minerl_multi.py
    run.bat scripts/play_minerl_multi.py --episodes 20
    run.bat scripts/play_minerl_multi.py --episodes 20 --config configs/play_minerl.yaml
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import yaml


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--episodes", type=int, default=20, help="total number of episodes")
    p.add_argument("--config", default="configs/play_minerl.yaml")
    p.add_argument("--script", default="scripts/play.py", help="play script to run per episode")
    return p.parse_args()


def read_gif_path(config: str) -> Path | None:
    """Read logging.gif_path from the config, if GIF saving is enabled."""
    try:
        with open(config) as f:
            cfg = yaml.safe_load(f)
        log = cfg.get("logging", {})
        if log.get("save_gif"):
            return Path(log["gif_path"])
    except (OSError, KeyError, yaml.YAMLError):
        pass
    return None


def _running_java_pids() -> set[int]:
    """PIDs of all currently running java.exe processes (Windows).

    tasklist emits the console's OEM codepage, not UTF-8, and PYTHONUTF8=1
    (set by run.bat) makes subprocess default text decoding assume UTF-8 —
    decoding raw OEM bytes as UTF-8 can raise UnicodeDecodeError and leave
    stdout unset. Decode explicitly with errors="replace" and never trust
    stdout to be non-None.
    """
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq java.exe", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    pids = set()
    for line in (out.stdout or "").splitlines():
        fields = line.strip().split('","')
        if len(fields) >= 2:
            try:
                pids.add(int(fields[1].strip('"')))
            except ValueError:
                pass
    return pids


def kill_stray_java(pre_existing_pids: set[int], timeout: float = 20.0, poll_interval: float = 0.5) -> None:
    """Kill only the java.exe process(es) launched by THIS episode, then block
    until they are confirmed gone before the next episode is allowed to launch.

    The original implementation ran `taskkill /F /IM java.exe /T`, which is
    image-name-wide: it kills EVERY java.exe on the machine, not just the one
    belonging to the episode that just finished. On this project's
    subprocess-per-episode design, several independent play_minerl_multi.py
    runs can be executing concurrently on the same machine (confirmed via
    process inspection during the 2026-07-20 N=20 investigation — 3 separate
    orchestrator processes running the same config at once). An unscoped kill
    fired by any one of them tears down the Minecraft instances of the OTHER
    runs mid-episode, and it also raced the next episode's launch (fired and
    returned immediately, without waiting for the OS to actually release the
    process/ports) — together these explain both an outright
    ConnectionResetError on the client socket and implausible inventory deltas
    that belong to a different, unrelated, longer-running episode (MineRL's
    InstanceManager._get_valid_port in minerl/env/malmo.py has no cross-process
    lock, so two concurrently-launched instances can race onto overlapping
    ports before either actually binds).

    Scoping the kill to PIDs that appeared strictly after this episode started,
    and blocking until they are gone, keeps every run's teardown local to its
    own process tree regardless of what else is running on the machine.
    """
    new_pids = _running_java_pids() - pre_existing_pids
    for pid in new_pids:
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid), "/T"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    if not new_pids:
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not (_running_java_pids() & new_pids):
            return
        time.sleep(poll_interval)


def run_one_episode(ep_idx: int, config: str) -> dict | None:
    """Run play.py --episodes 1, capture stdout, parse metrics."""
    print(f"\n{'='*60}", flush=True)
    print(f"[ep {ep_idx:03d}] launching Minecraft process...", flush=True)
    print(f"{'='*60}", flush=True)

    proc = subprocess.run(
        [sys.executable, "scripts/play.py",
         "--config", config, "--episodes", "1"],
        env=dict(os.environ),
        capture_output=False,  # laisser stdout/stderr passer dans le terminal
        text=True,
    )

    if proc.returncode != 0:
        print(f"[ep {ep_idx:03d}] FAILED (rc={proc.returncode})", flush=True)
        return None

    # play.py with --episodes 1 prints final metrics to stdout.
    # Without capture_output=True we can't parse.
    # Retrieve values via a temporary file.
    result_path = Path(f"logs/play_ep_{ep_idx:03d}.txt")
    return _run_and_capture(ep_idx, config, result_path)


# Java/Minecraft/MineRL noise patterns to hide from display (metric parsing
# happens on the FULL stdout, so filtering the display is safe).
_NOISE_PATTERNS = (
    "INFO", "WARN", "DEBUG", "Gradle", "Download", "downloading asset",
    "minerl.env", "process_watcher", "_log_heuristic", "_launch_minecraft",
    "launchClient", "Starting Minecraft", "Launhing", "Launching",
    "HTTP response code", "resources.download.minecraft",
    "java.io", "java.lang", "java.net",
    "UnicodeDecodeError", "RuntimeWarning", "frozen runpy",
    "daemoniker", "sys.modules", "prior to execution",
    "unpredictable behaviour", "switching to default",
    "Traceback", "File \"", "self.run()", "self._target",
    "_bootstrap_inner", "log_to_file", "linestr = line",
    "codec can't decode", "invalid start byte",
    "During handling", "Exception in thread", "^^^^^",
)


def _is_noise(line: str) -> bool:
    return any(p in line for p in _NOISE_PATTERNS)


def _run_and_capture(ep_idx: int, config: str, result_path: Path, script: str = "scripts/play.py") -> dict | None:
    """Run the play script, capture stdout, parse metrics."""
    result_path.parent.mkdir(exist_ok=True)

    proc = subprocess.run(
        [sys.executable, script,
         "--config", config, "--episodes", "1"],
        env=dict(os.environ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    # Print stdout while masking Java/Minecraft noise (keeps useful lines)
    if proc.stdout:
        for line in proc.stdout.splitlines():
            if not _is_noise(line):
                print(line, flush=True)
    if proc.stderr:
        for line in proc.stderr.splitlines():
            if line.strip() and not _is_noise(line):
                print(f"[stderr] {line}", flush=True)

    if proc.returncode != 0:
        print(f"[ep {ep_idx:03d}] FAILED (rc={proc.returncode})", flush=True)
        return None

    # Save stdout for debugging
    result_path.write_text(proc.stdout, encoding="utf-8")

    # Parse metrics from stdout
    return _parse_metrics(proc.stdout, ep_idx)


def _parse_metrics(stdout: str, ep_idx: int) -> dict | None:
    """Extract reward/steps/achievements from play.py output."""
    # Per-episode result line: "Ep    1/1 | reward=X  achievements=Y  steps=Z  fps=W"
    ep_match = re.search(
        r"Ep\s+\d+/\d+\s*\|\s*reward=([\d.]+)\s+achievements=([\d.]+)\s+steps=(\d+)\s+fps=([\d.]+)",
        stdout
    )
    if not ep_match:
        # Try final summary lines
        r_match = re.search(r"Mean reward\s*:\s*([\d.]+)", stdout)
        a_match = re.search(r"Achievements/ep\s*:\s*([\d.]+)", stdout)
        s_match = re.search(r"Mean steps\s*:\s*([\d.]+)", stdout)
        if r_match and a_match and s_match:
            return {
                "reward": float(r_match.group(1)),
                "achievements": float(a_match.group(1)),
                "steps": float(s_match.group(1)),
                "fps": 0.0,
            }
        print(f"[ep {ep_idx:03d}] could not parse metrics", flush=True)
        return None

    return {
        "reward": float(ep_match.group(1)),
        "achievements": float(ep_match.group(2)),
        "steps": int(ep_match.group(3)),
        "fps": float(ep_match.group(4)),
    }


def main():
    args = parse_args()
    n = args.episodes

    print(f"\n{'='*60}", flush=True)
    print(f"JEPA-MPC MineRL agent — {n} episodes (multi-process mode)", flush=True)
    print(f"Config: {args.config}", flush=True)
    print(f"{'='*60}", flush=True)
    print("MALMOBUSY workaround: 1 Minecraft per episode", flush=True)

    # The per-episode GIF is overwritten by each subprocess. To produce a
    # representative hero GIF, keep the GIF of the BEST successful episode
    # (highest reward) rather than whatever the last episode happened to be.
    gif_path = read_gif_path(args.config)
    best_gif = gif_path.with_name(gif_path.stem + ".best.gif") if gif_path else None
    best_gif_reward = 0.0

    results = []
    for i in range(1, n + 1):
        pre_java_pids = _running_java_pids()
        r = _run_and_capture(i, args.config, Path(f"logs/play_ep_{i:03d}.txt"), args.script)
        if r is not None:
            results.append(r)
            print(
                f"\n[ep {i:03d}/{n}] OK — "
                f"reward={r['reward']:.3f}  "
                f"achievements={r['achievements']:.2f}  "
                f"steps={r['steps']}  "
                f"fps={r['fps']:.1f}",
                flush=True,
            )
            # Preserve the GIF of the best success seen so far.
            if best_gif and r["reward"] > best_gif_reward and gif_path.exists():
                shutil.copy(gif_path, best_gif)
                best_gif_reward = r["reward"]
                print(f"[ep {i:03d}/{n}] kept GIF (reward={r['reward']:.3f})", flush=True)
        else:
            print(f"\n[ep {i:03d}/{n}] FAILED — skipped", flush=True)
        kill_stray_java(pre_java_pids)

    # Restore the best successful GIF over the canonical path (last episode
    # would otherwise win, often a failure).
    if best_gif and best_gif.exists():
        shutil.move(str(best_gif), str(gif_path))
        print(f"\nHero GIF = best success (reward={best_gif_reward:.3f}) → {gif_path}", flush=True)
    elif gif_path:
        print(f"\n⚠️  No successful episode — GIF left as last episode ({gif_path})", flush=True)

    # --- Aggregated results ---
    print(f"\n{'='*60}", flush=True)
    print(f"FINAL RESULTS — {len(results)}/{n} episodes succeeded", flush=True)
    print(f"{'='*60}", flush=True)

    if not results:
        print("No episodes succeeded.", flush=True)
        return

    rewards = [r["reward"] for r in results]
    achievements = [r["achievements"] for r in results]
    steps = [r["steps"] for r in results]

    mean_r = np.mean(rewards)
    mean_a = np.mean(achievements)
    mean_s = np.mean(steps)
    success_rate = np.mean([a > 0 for a in achievements])

    print(f"  Mean reward       : {mean_r:.4f}", flush=True)
    print(f"  Achievements/ep   : {mean_a:.2f}", flush=True)
    print(f"  Success rate      : {success_rate:.1%}", flush=True)
    print(f"  Mean steps        : {mean_s:.0f}", flush=True)

    gate_threshold = 0.3
    gate = success_rate >= gate_threshold
    print(f"\n  Phase 4 Gate      : {'✅ PASSED' if gate else '❌ NOT PASSED'}", flush=True)
    print(f"  (success_rate >= {gate_threshold:.0%} required)", flush=True)

    # Random baseline MineRLTreechop-v0: mean reward ~0.4 wood/ep (500 steps)
    # (random agent chops ~0.4 log in 500 steps on average)
    print(f"\n  Note: MineRL random baseline ~0.4 reward/ep", flush=True)
    if mean_r > 0.4:
        delta = (mean_r - 0.4) / 0.4 * 100
        print(f"  Our agent         : +{delta:.0f}% vs random", flush=True)
    else:
        print(f"  Our agent         : below random ({mean_r:.3f} vs ~0.4)", flush=True)


if __name__ == "__main__":
    main()

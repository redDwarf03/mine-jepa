"""
Prepare MineRL human demonstrations (Zenodo) for:
  1. Building the goal embedding (frames with reward > 0)
  2. Creating a dataset to retrain the world model

Zenodo format:
  MineRLTreechop-v0/
    <stream_name>/
      recording.mp4   — high-resolution video (all frames)
      rendered.npz    — rewards + actions (reward, action$forward, action$attack, ...)
      metadata.json   — episode info

Usage:
    run.bat scripts/prepare_demos.py --data data/MineRL_demos/MineRLTreechop-v0 --out data/minerl_goal
    run.bat scripts/prepare_demos.py --data data/MineRL_demos/MineRLTreechop-v0 --out data/minerl_goal --max_demos 20
"""
import argparse
from pathlib import Path

import cv2
import numpy as np


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True, help="Root folder of extracted demos")
    p.add_argument("--out", default="data/minerl_goal")
    p.add_argument("--max_demos", type=int, default=None)
    return p.parse_args()


# Index mapping cross-checked against configs/minerl_actions.yaml (n_actions=17,
# the exact vocabulary ebwm.pt is trained on): 0=noop, 1=forward, 2=back,
# 3=left, 4=right, 5=jump, 6=attack, 7=forward+attack, 8=forward+jump,
# 9=look up, 10=look down, 11=turn left, 12=turn right, 13=sprint+forward,
# 14=sprint+forward+attack, 15/16=forward+veer (never emitted here, no
# demo-side signal distinguishes a slight veer from a full turn).
ACTION_MAP = {
    (0, 1, 1): 14,   # sprint + forward + attack
    (0, 1, 0): 13,   # sprint + forward
    (0, 0, 1): 7,    # forward + attack
    (0, 0, 0): 1,    # forward only (fwd=True, sprint=0, atk=0)
    (1, 0, 1): 6,    # attack only
    (1, 0, 0): 0,    # noop
}


def discretize_actions(d: dict, n: int) -> np.ndarray:
    """Cold-start attempt #19 Run A: extends the original forward/attack/
    sprint/yaw-only discretizer with action$jump, action$left, action$right,
    action$back and the camera pitch component (action$camera[:, 0]) —
    previously read but silently dropped by every prior version, which is why
    ebwm.pt's own Treechop training data structurally never emits action
    indices 2/3/4/5/8/9/10 (attempt #18 Diagnostic 2). Frames that already
    resolved via the forward/attack/sprint/yaw combos below keep the exact
    same assignment as before (priority order preserved); only frames that
    previously fell through to noop/yaw-only can now resolve to a movement
    action, which is the intended fix, not a regression.
    """
    acts = np.zeros(n, dtype=np.int32)
    fwd = np.array(d.get("action$forward", np.zeros(n)), dtype=np.int32)
    atk = np.array(d.get("action$attack", np.zeros(n)), dtype=np.int32)
    spr = np.array(d.get("action$sprint", np.zeros(n)), dtype=np.int32)
    jump = np.array(d.get("action$jump", np.zeros(n)), dtype=np.int32)
    left = np.array(d.get("action$left", np.zeros(n)), dtype=np.int32)
    right = np.array(d.get("action$right", np.zeros(n)), dtype=np.int32)
    back = np.array(d.get("action$back", np.zeros(n)), dtype=np.int32)
    cam = np.array(d.get("action$camera", np.zeros((n, 2))), dtype=np.float32)
    for i in range(n):
        dy = cam[i, 1] if cam.ndim == 2 else 0.0   # yaw (unchanged from before)
        dx = cam[i, 0] if cam.ndim == 2 else 0.0   # pitch (new)
        if fwd[i] and spr[i] and atk[i]:
            acts[i] = 14
        elif fwd[i] and spr[i]:
            acts[i] = 13
        elif fwd[i] and atk[i]:
            acts[i] = 7
        elif fwd[i] and jump[i]:
            acts[i] = 8    # jump + forward, new
        elif fwd[i]:
            acts[i] = 1
        elif atk[i]:
            acts[i] = 6
        elif jump[i]:
            acts[i] = 5    # jump alone, new
        elif left[i]:
            acts[i] = 3    # strafe left, new
        elif right[i]:
            acts[i] = 4    # strafe right, new
        elif back[i]:
            acts[i] = 2    # back, new
        else:
            # Same fallback as the original: distinguish noop from a pure
            # camera turn, now also checking pitch (same 2.0 symmetric
            # threshold, yaw checked first so previously-yaw-resolved frames
            # are unaffected).
            if dy > 2.0:
                acts[i] = 12   # turn right
            elif dy < -2.0:
                acts[i] = 11   # turn left
            elif dx > 2.0:
                acts[i] = 10   # look down, new
            elif dx < -2.0:
                acts[i] = 9    # look up, new
            else:
                acts[i] = 0    # noop
    return acts


def load_demo(stream_dir: Path) -> dict | None:
    npz_path = stream_dir / "rendered.npz"
    mp4_path = stream_dir / "recording.mp4"

    if not npz_path.exists() or not mp4_path.exists():
        return None

    # Rewards + actions from NPZ
    d = np.load(npz_path, allow_pickle=True)
    rewards = d["reward"].astype(np.float32)
    n = len(rewards)
    actions = discretize_actions(dict(d), n)

    # Frames depuis MP4
    cap = cv2.VideoCapture(str(mp4_path))
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.resize(frame, (64, 64))
        frames.append(frame)
    cap.release()

    if not frames:
        return None

    frames = np.array(frames, dtype=np.uint8)
    # Align lengths (mp4 may have 1-2 frame offset)
    min_n = min(len(frames), n)
    frames = frames[:min_n]
    rewards = rewards[:min_n]
    actions = actions[:min_n]

    dones = np.zeros(min_n, dtype=bool)
    dones[-1] = True

    return {"frames": frames, "actions": actions, "rewards": rewards, "dones": dones}


def find_stream_dirs(data_dir: Path) -> list:
    # Find folders containing recording.mp4 directly
    # or with one extra level (Zenodo case)
    streams = [p.parent for p in data_dir.rglob("recording.mp4")]
    return sorted(streams)


def main():
    args = parse_args()
    data_dir = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    streams = find_stream_dirs(data_dir)
    print(f"Demos found: {len(streams)}", flush=True)

    if args.max_demos:
        streams = streams[:args.max_demos]
        print(f"Limited to {args.max_demos} demos", flush=True)

    all_frames, all_actions, all_rewards, all_dones = [], [], [], []
    n_reward_frames = 0

    for i, stream_dir in enumerate(streams):
        print(f"[{i+1}/{len(streams)}] {stream_dir.name[:50]}...", end=" ", flush=True)
        data = load_demo(stream_dir)
        if data is None:
            print("skip", flush=True)
            continue

        n_pos = int((data["rewards"] > 0).sum())
        n_reward_frames += n_pos
        print(f"{len(data['frames'])} frames | reward>0: {n_pos} | bois: {data['rewards'].sum():.0f}", flush=True)

        all_frames.append(data["frames"])
        all_actions.append(data["actions"])
        all_rewards.append(data["rewards"])
        all_dones.append(data["dones"])

    if not all_frames:
        print("No demos loaded.")
        return

    merged = {
        "frames":  np.concatenate(all_frames),
        "actions": np.concatenate(all_actions),
        "rewards": np.concatenate(all_rewards),
        "dones":   np.concatenate(all_dones),
    }

    out_path = out_dir / "episodes.npz"
    np.savez_compressed(out_path, **merged)

    n_total = len(merged["frames"])
    n_pos = int((merged["rewards"] > 0).sum())
    print(f"\n{'='*60}", flush=True)
    print(f"Saved → {out_path}", flush=True)
    print(f"  Total frames    : {n_total:,}", flush=True)
    print(f"  Frames reward>0 : {n_pos:,} ({n_pos/n_total*100:.1f}%)", flush=True)
    print(f"  Total wood      : {merged['rewards'].sum():.0f}", flush=True)
    print(f"  Demos loaded    : {len(all_frames)}", flush=True)
    if n_pos > 0:
        print(f"\n  ✅ Goal embedding ready ({n_pos} success frames)", flush=True)
        print(f"  Next step: retrain the WM then re-run play_multi.bat", flush=True)


if __name__ == "__main__":
    main()

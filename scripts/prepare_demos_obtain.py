"""
Prepare MineRLObtainIronPickaxe-v0 human demos for the crafting milestones.

Unlike prepare_demos.py (Treechop, movement-only), this:
  1. Discretises the CRAFT actions (craft/place/nearbyCraft strings → actions 17-21)
     of configs/minerl_actions_obtain.yaml, on top of the 17 movement actions.
  2. Extracts the INVENTORY stream (log, planks, stick, crafting_table, ...) — the
     structured game state the world model needs to learn crafting mechanics.
  3. Truncates each demo shortly after the first wooden_pickaxe is crafted. Everything
     after (stone/iron/torch) is out-of-vocabulary for our wood tech tree and would only
     add noise.

rendered.npz format (confirmed): reward (T,), observation$inventory$<item> (T+1,),
action$<key> (T,) — movement keys are int, craft/place/nearbyCraft are strings.

Usage:
    run.bat scripts/prepare_demos_obtain.py \
        --data data/MineRL_demos/MineRLObtainIronPickaxe-v0 --out data/minerl_craft
"""
import argparse
from pathlib import Path

import cv2
import numpy as np

# Inventory items tracked, in fixed order → inventory vector columns.
INV_ITEMS = ["log", "planks", "stick", "crafting_table", "wooden_pickaxe", "wooden_axe"]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True, help="Root folder of extracted Obtain demos")
    p.add_argument("--out", default="data/minerl_craft")
    p.add_argument("--max_demos", type=int, default=None)
    return p.parse_args()


def discretize_actions(d: dict, n: int) -> np.ndarray:
    """Map MineRL action dict → 22 discrete actions (movement 0-16 + craft 17-21).

    A craft/place/nearbyCraft event takes precedence over movement — it is the
    meaningful discrete action that step. Out-of-vocabulary craft events (torch,
    stone/iron tools, equip, smelt) fall through to noop (rare before wooden_pickaxe).
    """
    acts = np.zeros(n, dtype=np.int32)

    fwd = np.asarray(d.get("action$forward", np.zeros(n)), dtype=np.int32)
    atk = np.asarray(d.get("action$attack", np.zeros(n)), dtype=np.int32)
    spr = np.asarray(d.get("action$sprint", np.zeros(n)), dtype=np.int32)
    cam = np.asarray(d.get("action$camera", np.zeros((n, 2))), dtype=np.float32)
    craft = np.asarray(d.get("action$craft", np.array(["none"] * n)))
    place = np.asarray(d.get("action$place", np.array(["none"] * n)))
    ncraft = np.asarray(d.get("action$nearbyCraft", np.array(["none"] * n)))

    for i in range(n):
        # --- Craft chain takes precedence ---
        if craft[i] == "planks":
            acts[i] = 17
        elif craft[i] == "stick":
            acts[i] = 18
        elif craft[i] == "crafting_table":
            acts[i] = 19
        elif place[i] == "crafting_table":
            acts[i] = 20
        elif ncraft[i] == "wooden_pickaxe":
            acts[i] = 21
        # --- Other (OOV) craft/place events → noop, don't mislabel as movement ---
        elif craft[i] != "none" or place[i] != "none" or ncraft[i] != "none":
            acts[i] = 0
        # --- Movement (same logic as Treechop) ---
        elif fwd[i] == 0 and spr[i] == 0 and atk[i] == 0:
            dy = cam[i, 1] if cam.ndim == 2 else 0.0
            acts[i] = 12 if dy > 2.0 else (11 if dy < -2.0 else 0)
        elif fwd[i] and spr[i] and atk[i]:
            acts[i] = 14
        elif fwd[i] and spr[i]:
            acts[i] = 13
        elif fwd[i] and atk[i]:
            acts[i] = 7
        elif fwd[i]:
            acts[i] = 1
        elif atk[i]:
            acts[i] = 6
        else:
            acts[i] = 0
    return acts


def extract_inventory(d: dict, n: int) -> np.ndarray:
    """[n, len(INV_ITEMS)] int32 — per-step counts of the tracked items."""
    inv = np.zeros((n, len(INV_ITEMS)), dtype=np.int32)
    for j, item in enumerate(INV_ITEMS):
        col = d.get(f"observation$inventory${item}")
        if col is not None:
            inv[:, j] = np.asarray(col[:n], dtype=np.int32)
    return inv


def truncate_at_pickaxe(inv: np.ndarray) -> int:
    """Index (exclusive) to cut the demo: a few steps after the first wooden_pickaxe.
    Returns len if never crafted."""
    pick_col = INV_ITEMS.index("wooden_pickaxe")
    got = np.where(inv[:, pick_col] >= 1)[0]
    if len(got) == 0:
        return len(inv)
    return min(len(inv), int(got[0]) + 10)  # keep a short tail after the craft


def load_demo(stream_dir: Path) -> dict | None:
    npz_path = stream_dir / "rendered.npz"
    mp4_path = stream_dir / "recording.mp4"
    if not npz_path.exists() or not mp4_path.exists():
        return None

    d = dict(np.load(npz_path, allow_pickle=True))
    rewards = d["reward"].astype(np.float32)
    n = len(rewards)
    actions = discretize_actions(d, n)
    inventory = extract_inventory(d, n)

    # Frames from MP4
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

    # Align lengths, then truncate at the wooden_pickaxe (end of the wood chain)
    m = min(len(frames), n)
    cut = truncate_at_pickaxe(inventory[:m])
    sl = slice(0, cut)
    dones = np.zeros(cut, dtype=bool)
    dones[-1] = True
    return {
        "frames": frames[sl], "actions": actions[sl],
        "rewards": rewards[sl], "inventory": inventory[sl], "dones": dones,
    }


def find_stream_dirs(data_dir: Path) -> list:
    return sorted({p.parent for p in data_dir.rglob("recording.mp4")})


def main():
    args = parse_args()
    data_dir = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    streams = find_stream_dirs(data_dir)
    print(f"Demos found: {len(streams)}", flush=True)
    if args.max_demos:
        streams = streams[: args.max_demos]
        print(f"Limited to {args.max_demos} demos", flush=True)

    parts = {k: [] for k in ("frames", "actions", "rewards", "inventory", "dones")}
    n_planks_steps = n_pickaxe_demos = 0

    for i, stream_dir in enumerate(streams):
        print(f"[{i+1}/{len(streams)}] {stream_dir.name[:45]}...", end=" ", flush=True)
        data = load_demo(stream_dir)
        if data is None:
            print("skip", flush=True)
            continue
        craft_planks = int((data["actions"] == 17).sum())
        got_pick = int(data["inventory"][:, INV_ITEMS.index("wooden_pickaxe")].max() >= 1)
        n_planks_steps += craft_planks
        n_pickaxe_demos += got_pick
        print(f"{len(data['frames'])} fr | craft_planks: {craft_planks} | pickaxe: {got_pick}",
              flush=True)
        for k in parts:
            parts[k].append(data[k])

    if not parts["frames"]:
        print("No demos loaded.")
        return

    merged = {k: np.concatenate(v) for k, v in parts.items()}
    merged["inventory_items"] = np.array(INV_ITEMS)  # metadata

    out_path = out_dir / "episodes.npz"
    np.savez_compressed(out_path, **merged)

    n_total = len(merged["frames"])
    print(f"\n{'='*60}", flush=True)
    print(f"Saved -> {out_path}", flush=True)
    print(f"  Total frames        : {n_total:,}", flush=True)
    print(f"  Inventory items     : {INV_ITEMS}", flush=True)
    print(f"  Steps crafting planks: {n_planks_steps:,}  (action 17)", flush=True)
    print(f"  Demos reaching pickaxe: {n_pickaxe_demos}/{len(parts['frames'])}", flush=True)
    print(f"\n  Next: train the inventory+reward-aware world model (WM v3)", flush=True)


if __name__ == "__main__":
    main()

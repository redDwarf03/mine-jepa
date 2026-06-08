"""
Craft agent — WM v4 + CraftPlannerV4 in MineRLObtainIronPickaxeDense.

Milestone: chop a log, then CRAFT it into planks. The world model knows the craft
rule (dPlanks@craft = +4); the hard part is the visual chopping. The planner unrolls
both the visual latent (perception) and the inventory dynamics (crafting), starting the
inventory rollout from the agent's REAL current inventory.

Prints metrics in the format parsed by play_minerl_multi.py (1 episode per process,
MALMOBUSY workaround).

Usage: run.bat scripts/play_craft.py --config configs/play_craft.yaml --episodes 1
"""
import argparse
import logging
import time
from pathlib import Path

import cv2
import imageio
import numpy as np
import torch
import yaml

logging.getLogger("minerl").setLevel(logging.CRITICAL)

from mine_jepa.ebwm.craft_wm import build_craft_wm_v4
from mine_jepa.ebwm.dataset import INV_SCALE
from mine_jepa.ebwm.planner import SwitchingCraftPlanner
from scripts.play import load_action_map, make_minerl_env


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/play_craft.yaml")
    p.add_argument("--episodes", type=int, default=None)
    return p.parse_args()


def load_craft_wm(ckpt_path: str, device):
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    cfg = ckpt["cfg"]
    items = ckpt["inventory_items"]
    wm = build_craft_wm_v4(cfg["model"], cfg["regularizer"], cfg["head"], n_items=len(items))
    wm.load_state_dict(ckpt["model_state"])
    wm.eval()
    return wm.to(device), items


def preprocess(pov: np.ndarray, device):
    """frame [H,W,3] uint8 → [1, 3, 1, 64, 64] float [0,1]."""
    frame = cv2.resize(pov, (64, 64))
    t = torch.from_numpy(frame).float() / 255.0
    return t.permute(2, 0, 1).unsqueeze(0).unsqueeze(2).to(device)


def inv_vector(obs_inv: dict, items: list, device) -> torch.Tensor:
    """MineRL inventory dict → normalised vector [K] in INV_ITEMS order."""
    vec = np.array([float(obs_inv.get(it, 0)) for it in items], dtype=np.float32)
    return torch.from_numpy(vec / INV_SCALE).to(device)


@torch.no_grad()
def build_chop_goal(wm, data_path: str, device, log_idx: int) -> torch.Tensor:
    """Visual-latent centroid of 'log obtained' frames → [1, D, H', W'] chop goal.

    Frames where the log count increased = "facing a tree, chopping" scenes. Steering
    the visual latent toward this centroid drives the lumberjack gesture (the Treechop
    trick), far better than the weak per-step inventory signal."""
    d = np.load(data_path)
    frames, inv, dones = d["frames"], d["inventory"], d["dones"].astype(bool)
    log = inv[:, log_idx].astype(np.int64)
    inc = np.zeros(len(frames), dtype=bool)
    inc[1:] = (log[1:] > log[:-1]) & (~dones[:-1])         # log went up, same episode
    good = frames[inc]
    if len(good) < 10:
        print(f"  ⚠️  only {len(good)} log-gain frames — using all frames for chop goal")
        good = frames
    print(f"  Chop goal: centroid of {len(good)} 'log obtained' frames")
    lat_sum, n = None, 0
    for i in range(0, len(good), 256):
        obs = torch.from_numpy(good[i:i + 256]).float() / 255.0
        obs = obs.permute(0, 3, 1, 2).unsqueeze(2).to(device)   # [B,3,1,64,64]
        lat = wm.encode(obs).squeeze(2)                          # [B,D,H',W']
        s = lat.sum(dim=0)
        lat_sum = s if lat_sum is None else lat_sum + s
        n += lat.size(0)
    return (lat_sum / n).unsqueeze(0)                            # [1,D,H',W']


def apply_action(env, action_int: int, action_map: list):
    a = env.action_space.noop()
    for k, v in action_map[action_int].items():
        if k == "camera":
            a["camera"] = np.array(v, dtype=np.float32)
        else:
            a[k] = v
    return env.step(a)


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}\nEnv: minerl (craft)")

    action_map = load_action_map(cfg.get("actions_config", "configs/minerl_actions_obtain.yaml"))

    print("\nLoading WM v4 (inventory-aware)...")
    wm, items = load_craft_wm(cfg["model"]["checkpoint"], device)
    print(f"  craft_wm_v4.pt loaded | items: {items}")
    planks_idx = items.index("planks")
    log_idx = items.index("log")

    print("\nBuilding chop goal...")
    chop_goal = build_chop_goal(wm, cfg["goal"]["data_path"], device, log_idx)

    p = cfg["planner"]
    item_weights = {log_idx: float(p.get("w_log", 1.0)), planks_idx: float(p.get("w_planks", 2.0))}
    planner = SwitchingCraftPlanner(
        wm, chop_goal=chop_goal, item_weights=item_weights, log_idx=log_idx,
        n_actions=p["n_actions"], horizon=p["horizon"], n_candidates=p["n_candidates"],
        log_threshold=float(p.get("log_threshold", 0.05)), device=device,
    )
    print(f"Planner: switching (no log→chop / log→craft), horizon={p['horizon']}, "
          f"candidates={p['n_candidates']}")

    a_cfg = cfg["agent"]
    n_episodes = args.episodes or a_cfg["episodes"]
    repeat = a_cfg.get("action_repeat", 4)
    env = make_minerl_env(cfg)
    label = cfg.get("minerl_env", "MineRLObtainIronPickaxeDense-v0")
    print(f"\n{'='*55}\nCraft agent — {n_episodes} ep in {label}\n{'='*55}")

    save_gif = cfg["logging"]["save_gif"]
    gif_budget = cfg["logging"].get("gif_episodes", 1)

    all_reward, all_logs, all_planks, all_steps = [], [], [], []
    for ep in range(1, n_episodes + 1):
        obs = env.reset()
        pov, inv = obs["pov"], obs["inventory"]
        # Measure GAIN vs the starting inventory — debug envs start with items, so
        # "planks > 0" would be trivially true. Success = crafted MORE than the start.
        start_log = int(inv.get("log", 0))
        start_planks = int(inv.get("planks", 0))
        max_log, max_planks = start_log, start_planks
        total_r = 0.0
        step = 0
        action_counts = [0] * p["n_actions"]
        mode_counts = {"chop": 0, "craft": 0}
        record = ep <= gif_budget and save_gif
        gif_frames = [pov] if record else []
        t0 = time.perf_counter()

        while step < a_cfg["max_steps"]:
            obs_t = preprocess(pov, device)
            inv_t = inv_vector(inv, items, device)
            action, mode = planner.plan(obs_t, inv_t)
            mode_counts[mode] += 1
            for _ in range(repeat):
                if step >= a_cfg["max_steps"]:
                    break
                action_counts[action] += 1
                obs, r, done, _info = apply_action(env, action, action_map)
                pov, inv = obs["pov"], obs["inventory"]
                total_r += r
                max_log = max(max_log, int(inv.get("log", 0)))
                max_planks = max(max_planks, int(inv.get("planks", 0)))
                step += 1
                if record:
                    gif_frames.append(pov)
                if done:
                    break
            if done:
                break

        fps = step / (time.perf_counter() - t0)
        log_gain = max_log - start_log
        planks_gain = max_planks - start_planks       # crafted = planks above the start
        got_planks = int(planks_gain > 0)
        ach = got_planks   # milestone = crafted planks (multi-process success_rate)
        top = sorted(range(p["n_actions"]), key=lambda i: -action_counts[i])[:3]
        acts = " ".join(f"a{i}={action_counts[i]/max(step,1)*100:.0f}%" for i in top)
        all_reward.append(total_r)
        all_logs.append(max(log_gain, 0))
        all_planks.append(planks_gain)
        all_steps.append(step)
        print(f"Ep {ep:4d}/{n_episodes} | reward={total_r:.3f}  achievements={ach:.2f}  "
              f"steps={step}  fps={fps:.1f}  [{acts}]")
        print(f"   start log={start_log} planks={start_planks}  |  planks crafted: "
              f"{'YES (+' + str(planks_gain) + ')' if got_planks else 'no'}"
              f"  |  plans: chop={mode_counts['chop']} craft={mode_counts['craft']}")

        if record and save_gif:
            gp = Path(cfg["logging"]["gif_path"])
            gp.parent.mkdir(exist_ok=True)
            imageio.mimsave(str(gp), gif_frames, fps=10, loop=0)
            print(f"  GIF saved -> {gp}")

    print(f"\n{'='*55}")
    print(f"  Mean reward       : {np.mean(all_reward):.4f}")
    print(f"  Logs chopped/ep   : {np.mean(all_logs):.2f}")
    print(f"  Planks crafted/ep : {np.mean(all_planks):.2f}")
    craft_rate = float(np.mean([pk > 0 for pk in all_planks]))
    print(f"  Success rate      : {craft_rate:.1%}  (episodes that crafted planks)")
    print(f"  Mean steps        : {np.mean(all_steps):.0f}")
    gate = craft_rate >= 0.3
    print(f"\n  Planks milestone  : {'PASSED' if gate else 'NOT PASSED'}  (>=30% craft planks)")


if __name__ == "__main__":
    main()

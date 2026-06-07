"""
Goal-directed MineRL collection to obtain goal frames (reward > 0).

Instead of uniformly random actions, we bias toward:
  - action 7: forward + attack (chops trees we walk through)
  - action 14: sprint + forward + attack
  - camera turns to avoid getting stuck against a wall

Goal: obtain at least N frames where reward > 0 (wood chopped).
These frames serve as goal embedding for the MPC planner.

Usage:
    run.bat scripts/collect_goal_directed.py
    run.bat scripts/collect_goal_directed.py --episodes 10 --out data/minerl_goal
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

# Probability per action (17 actions)
# Strong bias toward forward+attack (7) and sprint+attack (14)
ACTION_PROBS = np.array([
    0.00,  # 0 noop
    0.05,  # 1 forward
    0.00,  # 2 back
    0.01,  # 3 strafe left
    0.01,  # 4 strafe right
    0.02,  # 5 jump
    0.05,  # 6 attack only
    0.35,  # 7 forward + attack  ← primary
    0.03,  # 8 forward + jump
    0.05,  # 9 look up
    0.05,  # 10 look down
    0.07,  # 11 turn left
    0.07,  # 12 turn right
    0.05,  # 13 sprint
    0.15,  # 14 sprint + attack  ← secondary
    0.04,  # 15 forward + turn left
    0.04,  # 16 forward + turn right
], dtype=np.float64)
ACTION_PROBS /= ACTION_PROBS.sum()


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--episodes", type=int, default=5)
    p.add_argument("--max_steps", type=int, default=9000)
    p.add_argument("--out", default="data/minerl_goal")
    p.add_argument("--actions_config", default="configs/minerl_actions.yaml")
    p.add_argument("--env", default="MineRLTreechop-v0")
    return p.parse_args()


def kill_stray_java():
    subprocess.run(
        ["taskkill", "/F", "/IM", "java.exe", "/T"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def collect_one_episode(ep_idx: int, args) -> dict | None:
    """Run 1 MineRL episode with the goal-directed policy."""
    import yaml
    import cv2
    import gym
    import minerl  # noqa: F401

    with open(args.actions_config) as f:
        act_cfg = yaml.safe_load(f)
    action_map = [act_cfg["actions"].get(i, {}) for i in range(act_cfg["n_actions"])]

    env = gym.make(args.env)
    obs_dict = env.reset()
    obs = obs_dict["pov"]  # [64, 64, 3]

    frames, actions, rewards, dones = [], [], [], []
    n_reward = 0

    for step in range(args.max_steps):
        action_int = np.random.choice(len(action_map), p=ACTION_PROBS)
        action_dict = env.action_space.noop()
        overrides = action_map[action_int]
        for k, v in overrides.items():
            if k == "camera":
                action_dict["camera"] = np.array(v, dtype=np.float32)
            else:
                action_dict[k] = v

        next_obs_dict, reward, done, info = env.step(action_dict)
        frame = cv2.resize(obs, (64, 64))

        frames.append(frame)
        actions.append(action_int)
        rewards.append(float(reward))
        dones.append(done)

        if reward > 0:
            n_reward += 1
            print(f"  [ep {ep_idx} step {step}] REWARD +{reward:.0f}! Total wood: {n_reward}", flush=True)

        obs = next_obs_dict["pov"]
        if done:
            break

    env.close()

    print(f"[ep {ep_idx}] {len(frames)} steps — {n_reward} wood chopped", flush=True)
    return {
        "frames": np.array(frames, dtype=np.uint8),
        "actions": np.array(actions, dtype=np.int32),
        "rewards": np.array(rewards, dtype=np.float32),
        "dones": np.array(dones, dtype=bool),
    }


def main():
    args = parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_frames, all_actions, all_rewards, all_dones = [], [], [], []
    total_reward = 0.0

    for ep in range(args.episodes):
        print(f"\n{'='*60}", flush=True)
        print(f"Episode {ep+1}/{args.episodes} — goal-directed policy (70% forward+attack)", flush=True)
        print(f"{'='*60}", flush=True)

        try:
            data = collect_one_episode(ep + 1, args)
        except Exception as e:
            print(f"[ep {ep+1}] ERROR: {e}", flush=True)
            kill_stray_java()
            continue

        all_frames.append(data["frames"])
        all_actions.append(data["actions"])
        all_rewards.append(data["rewards"])
        all_dones.append(data["dones"])
        total_reward += data["rewards"].sum()
        kill_stray_java()

    if not all_frames:
        print("No data collected.", flush=True)
        return

    merged = {
        "frames":  np.concatenate(all_frames),
        "actions": np.concatenate(all_actions),
        "rewards": np.concatenate(all_rewards),
        "dones":   np.concatenate(all_dones),
    }
    n_pos = (merged["rewards"] > 0).sum()
    out_path = out_dir / "episodes.npz"
    np.savez_compressed(out_path, **merged)

    print(f"\n{'='*60}", flush=True)
    print(f"Saved → {out_path}", flush=True)
    print(f"  frames     : {merged['frames'].shape}", flush=True)
    print(f"  reward > 0 : {n_pos} frames ({n_pos/len(merged['rewards'])*100:.1f}%)", flush=True)
    print(f"  total wood : {total_reward:.0f}", flush=True)
    if n_pos == 0:
        print("\n  ⚠️  No tree chopped — re-run with a larger --episodes", flush=True)
    else:
        print(f"\n  ✅ Goal embedding built from {n_pos} success frames", flush=True)


if __name__ == "__main__":
    main()

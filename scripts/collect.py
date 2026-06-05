"""
Collect (frame, action) trajectories from Crafter using a random policy.

Output: data/crafter/
  episodes.npz  — dict of arrays: frames (N,H,W,3), actions (N,), dones (N,)
  random_agent.gif — short GIF of the first few episodes (for the README)

Usage:
    uv run python scripts/collect.py
    uv run python scripts/collect.py --episodes 500 --out data/crafter
"""
import argparse
import os
from pathlib import Path

import crafter
import imageio
import numpy as np
import yaml
from tqdm import tqdm


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/collect.yaml")
    p.add_argument("--episodes", type=int, default=None)
    p.add_argument("--out", type=str, default=None)
    p.add_argument("--seed", type=int, default=None)
    return p.parse_args()


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def collect(cfg: dict) -> None:
    out_dir = Path(cfg["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    env = crafter.Env(seed=cfg["seed"])
    frame_size = tuple(cfg["frame_size"])  # (H, W)

    all_frames, all_actions, all_dones = [], [], []
    all_health, all_food, all_drink, all_energy = [], [], [], []
    gif_frames = []
    gif_budget = cfg.get("gif_episodes", 3)

    for ep in tqdm(range(cfg["episodes"]), desc="Collecting"):
        obs = env.reset()
        done = False
        ep_frames, ep_actions, ep_dones = [], [], []
        ep_health, ep_food, ep_drink, ep_energy = [], [], [], []
        record_gif = ep < gif_budget

        while not done:
            # Random action — no policy, no labels, pure dynamics
            action = np.random.randint(env.action_space.n)
            next_obs, reward, done, info = env.step(action)

            # Resize frame for JEPA training (smaller = faster training)
            import cv2
            frame = cv2.resize(obs, (frame_size[1], frame_size[0]))

            inv = info.get("inventory", {})
            ep_frames.append(frame)
            ep_actions.append(action)
            ep_dones.append(done)
            ep_health.append(inv.get("health", 0))
            ep_food.append(inv.get("food", 0))
            ep_drink.append(inv.get("drink", 0))
            ep_energy.append(inv.get("energy", 0))

            if record_gif:
                gif_frames.append(obs)  # full-res for the GIF

            obs = next_obs

            if len(ep_frames) >= cfg.get("max_steps_per_episode", 500):
                break

        all_frames.extend(ep_frames)
        all_actions.extend(ep_actions)
        all_dones.extend(ep_dones)
        all_health.extend(ep_health)
        all_food.extend(ep_food)
        all_drink.extend(ep_drink)
        all_energy.extend(ep_energy)

    # Save dataset
    out_path = out_dir / "episodes.npz"
    np.savez_compressed(
        out_path,
        frames=np.array(all_frames, dtype=np.uint8),
        actions=np.array(all_actions, dtype=np.int32),
        dones=np.array(all_dones, dtype=bool),
        health=np.array(all_health, dtype=np.uint8),
        food=np.array(all_food, dtype=np.uint8),
        drink=np.array(all_drink, dtype=np.uint8),
        energy=np.array(all_energy, dtype=np.uint8),
    )

    n = len(all_frames)
    print(f"\nSaved {n} transitions → {out_path}")
    print(f"  frames shape : {np.array(all_frames).shape}")
    print(f"  action space : {env.action_space.n} discrete actions")

    # Save GIF (visible artifact for the README)
    if gif_frames:
        gif_path = Path("assets") / "random_agent.gif"
        gif_path.parent.mkdir(exist_ok=True)
        imageio.mimsave(str(gif_path), gif_frames, fps=10, loop=0)
        print(f"  GIF saved   → {gif_path}  ({len(gif_frames)} frames)")


def main():
    args = parse_args()
    cfg = load_config(args.config)
    if args.episodes is not None:
        cfg["episodes"] = args.episodes
    if args.out is not None:
        cfg["out_dir"] = args.out
    if args.seed is not None:
        cfg["seed"] = args.seed
    collect(cfg)


if __name__ == "__main__":
    main()

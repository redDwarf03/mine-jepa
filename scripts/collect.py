"""
Collect (frame, action) trajectories — Crafter or MineRL.

Output: data/<env>/
  episodes.npz  — frames (N,H,W,3), actions (N,), dones (N,), + health stats
  random_agent.gif — first episodes

Usage:
    run.bat scripts/collect.py                              # Crafter (default)
    run.bat scripts/collect.py --config configs/collect_minerl.yaml  # MineRL
    run.bat scripts/collect.py --env crafter --episodes 500
    run.bat scripts/collect.py --env minerl  --episodes 100
"""
import argparse
import os
from pathlib import Path

import cv2
import imageio
import numpy as np
import yaml
from tqdm import tqdm


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/collect.yaml")
    p.add_argument("--env", type=str, default=None, choices=["crafter", "minerl"])
    p.add_argument("--episodes", type=int, default=None)
    p.add_argument("--out", type=str, default=None)
    p.add_argument("--seed", type=int, default=None)
    return p.parse_args()


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Crafter
# ---------------------------------------------------------------------------

def make_crafter_env(cfg: dict):
    import crafter
    return crafter.Env(seed=cfg["seed"])


def crafter_step(env, action: int):
    obs, reward, done, info = env.step(action)
    inv = info.get("inventory", {})
    return obs, done, {
        "health": inv.get("health", 0),
        "food":   inv.get("food", 0),
        "drink":  inv.get("drink", 0),
        "energy": inv.get("energy", 0),
    }


def crafter_reset(env):
    return env.reset()


def crafter_n_actions(env) -> int:
    return env.action_space.n


# ---------------------------------------------------------------------------
# MineRL
# ---------------------------------------------------------------------------

def load_action_map(actions_cfg_path: str) -> list:
    """Returns a list of action dicts indexed by integer."""
    with open(actions_cfg_path) as f:
        cfg = yaml.safe_load(f)
    n = cfg["n_actions"]
    actions = cfg["actions"]
    return [actions.get(i, {}) for i in range(n)]


def make_minerl_env(cfg: dict):
    import gym
    import minerl  # noqa: F401 — registers MineRL envs in gym
    env_name = cfg.get("minerl_env", "MineRLTreechop-v0")
    env = gym.make(env_name)
    return env


def minerl_reset(env):
    obs = env.reset()
    return obs["pov"]  # [64, 64, 3] uint8


def minerl_step(env, action_int: int, action_map: list):
    action_dict = env.action_space.noop()
    overrides = action_map[action_int]
    for k, v in overrides.items():
        if k == "camera":
            action_dict["camera"] = np.array(v, dtype=np.float32)
        else:
            action_dict[k] = v
    obs, reward, done, info = env.step(action_dict)
    pov = obs["pov"]  # [64, 64, 3]
    life = obs.get("life_stats", {})
    return pov, reward, done, {
        "health": int(life.get("life", 20)),
        "food":   int(life.get("food", 20)),
        "drink":  0,
        "energy": 0,
    }


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def collect(cfg: dict) -> None:
    out_dir = Path(cfg["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    frame_size = tuple(cfg["frame_size"])
    env_type = cfg.get("env", "crafter")

    if env_type == "minerl":
        action_map = load_action_map(cfg["actions_config"])
        env = make_minerl_env(cfg)
        n_actions = cfg.get("n_actions", len(action_map))
        reset_fn  = lambda: minerl_reset(env)
        step_fn   = lambda a: minerl_step(env, a, action_map)
        print(f"Env: {cfg.get('minerl_env', 'MineRLTreechop-v0')}  ({n_actions} discrete actions)")
    else:
        env = make_crafter_env(cfg)
        n_actions = crafter_n_actions(env)
        reset_fn  = lambda: crafter_reset(env)
        step_fn   = lambda a: crafter_step(env, a)
        print(f"Env: Crafter  ({n_actions} actions)")

    all_frames, all_actions, all_dones = [], [], []
    all_health, all_food, all_drink, all_energy = [], [], [], []
    all_rewards = []
    gif_frames = []
    gif_budget = cfg.get("gif_episodes", 3)

    for ep in tqdm(range(cfg["episodes"]), desc="Collecting"):
        obs = reset_fn()
        done = False
        ep_frames, ep_actions, ep_dones = [], [], []
        ep_health, ep_food, ep_drink, ep_energy = [], [], [], []
        ep_rewards = []
        record_gif = ep < gif_budget

        while not done:
            action = np.random.randint(n_actions)
            if env_type == "minerl":
                next_obs, reward, done, stats = step_fn(action)
            else:
                next_obs, done, stats = step_fn(action)
                reward = 0.0

            frame = cv2.resize(obs, (frame_size[1], frame_size[0]))
            ep_frames.append(frame)
            ep_actions.append(action)
            ep_dones.append(done)
            ep_health.append(stats["health"])
            ep_food.append(stats["food"])
            ep_drink.append(stats["drink"])
            ep_energy.append(stats["energy"])
            ep_rewards.append(float(reward))

            if record_gif:
                gif_frames.append(obs)

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
        all_rewards.extend(ep_rewards)

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
        rewards=np.array(all_rewards, dtype=np.float32),
    )

    n = len(all_frames)
    print(f"\nSaved {n} transitions → {out_path}")
    print(f"  frames shape : {np.array(all_frames, dtype=np.uint8).shape}")
    print(f"  n_actions    : {n_actions}")

    if gif_frames and cfg.get("save_gif", True):
        gif_name = "random_agent_minerl.gif" if env_type == "minerl" else "random_agent.gif"
        gif_path = Path("assets") / gif_name
        gif_path.parent.mkdir(exist_ok=True)
        imageio.mimsave(str(gif_path), gif_frames, fps=10, loop=0)
        print(f"  GIF saved    → {gif_path}  ({len(gif_frames)} frames)")


def main():
    args = parse_args()
    cfg = load_config(args.config)
    if args.env is not None:
        cfg["env"] = args.env
        if args.env == "minerl" and "actions_config" not in cfg:
            cfg["actions_config"] = "configs/minerl_actions.yaml"
        if args.env == "minerl" and "minerl_env" not in cfg:
            cfg["minerl_env"] = "MineRLTreechop-v0"
        if args.env == "minerl" and "out_dir" not in cfg:
            cfg["out_dir"] = "data/minerl"
    if args.episodes is not None:
        cfg["episodes"] = args.episodes
    if args.out is not None:
        cfg["out_dir"] = args.out
    if args.seed is not None:
        cfg["seed"] = args.seed
    collect(cfg)


if __name__ == "__main__":
    main()

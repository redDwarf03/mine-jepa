"""
JEPA-MPC agent playing Crafter or real Minecraft (MineRL).

Pipeline:
  1. Load trained encoder + world model
  2. Build goal embedding (centroid of "good" latent states)
  3. For each episode:
     a. Reset env → initial frame
     b. Loop: encode frame → MPC planner → action → observe
  4. Report metrics vs random baseline

Usage:
    run.bat scripts/play.py                          # Crafter (Phase 3)
    run.bat scripts/play.py --config configs/play_minerl.yaml  # MineRL (Phase 4)
    run.bat scripts/play.py --episodes 20 --compare_random
"""
import argparse
import time
from pathlib import Path
from typing import Callable

import cv2
import imageio
import numpy as np
import torch
import yaml

from mine_jepa.encoder.crafter_encoder import CrafterJEPA
from mine_jepa.encoder.dataset import _load_npz, _to_float
from mine_jepa.planning import LatentMPCPlanner
from mine_jepa.policy import ActionHead, BCCNNPolicy, BCPolicy
from mine_jepa.predictor import ActionConditionedPredictor


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/play.yaml")
    p.add_argument("--env", type=str, default=None, choices=["crafter", "minerl"])
    p.add_argument("--episodes", type=int, default=None)
    p.add_argument("--compare_random", action="store_true")
    p.add_argument("--policy", type=str, default=None, choices=["mpc", "bc", "bc_cnn"])
    return p.parse_args()


def load_cfg(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_action_map(actions_cfg_path: str) -> list:
    with open(actions_cfg_path) as f:
        cfg = yaml.safe_load(f)
    n = cfg["n_actions"]
    return [cfg["actions"].get(i, {}) for i in range(n)]


def load_encoder(ckpt_path: str, device: torch.device) -> torch.nn.Module:
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    m = ckpt["cfg"]["model"]
    t = ckpt["cfg"]["training"]
    v = ckpt["cfg"]["vicreg"]
    jepa = CrafterJEPA(
        embed_dim=m["embed_dim"], hidden_dim=m["hidden_dim"],
        predictor_hidden=m["predictor_hidden"],
        ema_decay=t["ema_decay"], std_coeff=v["std_coeff"], cov_coeff=v["cov_coeff"],
    )
    jepa.load_state_dict(ckpt["model_state"])
    enc = jepa.encoder.to(device)
    for p in enc.parameters():
        p.requires_grad_(False)
    enc.eval()
    return enc


def load_predictor(ckpt_path: str, cfg: dict, device: torch.device) -> ActionConditionedPredictor:
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    m = cfg["world_model_cfg"]["model"]
    pred = ActionConditionedPredictor(
        embed_dim=m["embed_dim"], n_actions=m["n_actions"],
        action_dim=m["action_dim"], hidden_dim=m["hidden_dim"],
    ).to(device)
    pred.load_state_dict(ckpt["predictor_state"])
    for p in pred.parameters():
        p.requires_grad_(False)
    pred.eval()
    return pred


@torch.no_grad()
def build_goal_embedding(encoder: torch.nn.Module, cfg: dict, device: torch.device) -> torch.Tensor:
    g_cfg = cfg["goal"]
    data = _load_npz(g_cfg["data_path"])
    frames = _to_float(data["frames"])           # [N, 3, H, W]

    label_key = g_cfg.get("label")
    if label_key and label_key in data:
        labels = data[label_key].astype(np.int64)
        mask = labels >= g_cfg["threshold"]
        good_frames = frames[mask]
        if len(good_frames) < g_cfg["min_frames"]:
            print(f"  ⚠️  Only {len(good_frames)} 'goal' frames — using all frames")
            good_frames = frames
        else:
            print(f"  Goal embedding : {len(good_frames)} frames ({label_key} >= {g_cfg['threshold']})")
    else:
        # MineRL: no clear label → centroid over all frames
        good_frames = frames
        print(f"  Goal embedding: {len(good_frames)} frames (all, no label)")

    embeddings = []
    batch_size = 512
    for i in range(0, len(good_frames), batch_size):
        batch = good_frames[i : i + batch_size].to(device)
        embeddings.append(encoder(batch).cpu())

    goal = torch.cat(embeddings, dim=0).mean(dim=0)  # [D]
    print(f"  goal shape: {goal.shape}, norm: {goal.norm():.3f}")
    return goal


def preprocess_frame(obs: np.ndarray, size: int = 64) -> torch.Tensor:
    """obs [H, W, 3] uint8 → [1, 3, H, W] float32 [0,1]"""
    frame = cv2.resize(obs, (size, size))
    t = torch.from_numpy(frame).float() / 255.0
    return t.permute(2, 0, 1).unsqueeze(0)


# ---------------------------------------------------------------------------
# Crafter env wrappers
# ---------------------------------------------------------------------------

def make_crafter_env(cfg: dict):
    import crafter
    return crafter.Env(seed=cfg["agent"]["seed"])


def crafter_reset(env) -> np.ndarray:
    return env.reset()


def crafter_step(env, action_int: int, action_map=None):
    obs, reward, done, info = env.step(action_int)
    achievements = {k for k, v in info.get("achievements", {}).items() if v}
    return obs, reward, done, achievements


def crafter_n_actions(env) -> int:
    return env.action_space.n


def crafter_random_action(env, n_actions: int) -> int:
    return np.random.randint(env.action_space.n)


# ---------------------------------------------------------------------------
# MineRL env wrappers
# ---------------------------------------------------------------------------

def make_minerl_env(cfg: dict):
    import gym
    import minerl  # noqa: F401
    env_name = cfg.get("minerl_env", "MineRLTreechop-v0")
    return gym.make(env_name)


def minerl_reset(env) -> np.ndarray:
    return env.reset()["pov"]


def minerl_step(env, action_int: int, action_map: list):
    action_dict = env.action_space.noop()
    overrides = action_map[action_int]
    for k, v in overrides.items():
        if k == "camera":
            action_dict["camera"] = np.array(v, dtype=np.float32)
        else:
            action_dict[k] = v
    obs, reward, done, info = env.step(action_dict)
    pov = obs["pov"]
    achievements = {"log_chopped"} if reward > 0 else set()
    return pov, reward, done, achievements


# ---------------------------------------------------------------------------
# Episode runners
# ---------------------------------------------------------------------------

def run_episode(
    env,
    env_type: str,
    encoder: torch.nn.Module,
    planner: LatentMPCPlanner,
    goal: torch.Tensor,
    max_steps: int,
    device: torch.device,
    action_map: list = None,
    record_frames: bool = False,
) -> dict:
    if env_type == "minerl":
        obs = minerl_reset(env)
    else:
        obs = crafter_reset(env)

    done = False
    step = 0
    total_reward = 0.0
    all_achievements = set()
    frames = [obs] if record_frames else []
    action_counts = [0] * 17
    t_start = time.perf_counter()

    while not done and step < max_steps:
        frame_t = preprocess_frame(obs).to(device)

        if isinstance(planner, BCCNNPolicy):
            planner.set_frame(frame_t)
            s_t = frame_t   # not used by plan() but required as argument
        else:
            with torch.no_grad():
                s_t = encoder(frame_t)  # [1, D]

        action = planner.plan(s_t, goal)
        action_counts[action] += 1

        if env_type == "minerl":
            obs, reward, done, achievements = minerl_step(env, action, action_map)
        else:
            obs, reward, done, achievements = crafter_step(env, action)

        total_reward += reward
        step += 1
        all_achievements.update(achievements)

        if record_frames:
            frames.append(obs)

    elapsed = time.perf_counter() - t_start
    top3 = sorted(range(17), key=lambda i: -action_counts[i])[:3]
    action_summary = " ".join(f"a{i}={action_counts[i]/step*100:.0f}%" for i in top3) if step > 0 else ""
    return {
        "steps": step,
        "reward": total_reward,
        "achievements": all_achievements,
        "n_achievements": len(all_achievements),
        "fps": step / elapsed,
        "frames": frames,
        "action_summary": action_summary,
    }


def run_random_baseline(env, env_type: str, n_episodes: int, max_steps: int, action_map=None) -> dict:
    all_rewards, all_steps, all_achievements = [], [], []
    n_actions = len(action_map) if action_map else env.action_space.n
    for _ in range(n_episodes):
        if env_type == "minerl":
            obs = minerl_reset(env)
        else:
            obs = crafter_reset(env)
        done = False
        step = 0
        reward_sum = 0.0
        achievements = set()
        while not done and step < max_steps:
            action = np.random.randint(n_actions)
            if env_type == "minerl":
                obs, r, done, ach = minerl_step(env, action, action_map)
            else:
                obs, r, done, ach = crafter_step(env, action)
            reward_sum += r
            step += 1
            achievements.update(ach)
        all_rewards.append(reward_sum)
        all_steps.append(step)
        all_achievements.append(len(achievements))
    return {
        "mean_reward": np.mean(all_rewards),
        "mean_steps": np.mean(all_steps),
        "mean_achievements": np.mean(all_achievements),
        "success_rate": np.mean([a > 0 for a in all_achievements]),
    }


def main():
    args = parse_args()
    cfg = load_cfg(args.config)

    if args.env is not None:
        cfg["env"] = args.env

    env_type = cfg.get("env", "crafter")
    n_episodes = args.episodes or cfg["agent"]["episodes"]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"Env: {env_type}")

    action_map = None
    if env_type == "minerl":
        action_map = load_action_map(cfg.get("actions_config", "configs/minerl_actions.yaml"))

    # --- Load models ---
    print("\nLoading models...")
    policy_type = args.policy or cfg.get("policy", {}).get("type", "mpc")

    if policy_type == "bc_cnn":
        from mine_jepa.policy import BCNN
        bc_ckpt = torch.load(cfg["policy"]["checkpoint"], map_location=device, weights_only=False)
        cnn_model = BCNN(n_actions=bc_ckpt["cfg"]["model"]["n_actions"])
        cnn_model.load_state_dict(bc_ckpt["model_state"])
        planner = BCCNNPolicy(cnn=cnn_model, device=device)
        goal = torch.zeros(1, device=device)
        encoder = None
        print(f"BC-CNN policy loaded (val_acc={bc_ckpt.get('val_acc', 0):.1f}%)")
    elif policy_type == "bc":
        encoder = load_encoder(cfg["encoder"]["checkpoint"], device)
        bc_ckpt = torch.load(cfg["policy"]["checkpoint"], map_location=device, weights_only=False)
        bc_cfg = bc_ckpt["cfg"]["model"]
        head = ActionHead(
            input_dim=bc_cfg["input_dim"],
            hidden_dim=bc_cfg.get("hidden_dim", 128),
            n_actions=bc_cfg["n_actions"],
        )
        head.load_state_dict(bc_ckpt["head_state"])
        planner = BCPolicy(encoder=encoder, head=head, device=device)
        goal = torch.zeros(bc_cfg["input_dim"], device=device)
        print(f"BC policy loaded (val_acc={bc_ckpt.get('val_acc', 0):.1f}%)")
    else:
        encoder = load_encoder(cfg["encoder"]["checkpoint"], device)
        wm_ckpt_path = cfg["world_model"]["checkpoint"]
        wm_raw = torch.load(wm_ckpt_path, map_location=device, weights_only=False)
        cfg["world_model_cfg"] = wm_raw["cfg"]
        predictor = load_predictor(wm_ckpt_path, cfg, device)

        p_cfg = cfg["planner"]
        planner = LatentMPCPlanner(
            predictor=predictor,
            n_actions=p_cfg["n_actions"],
            horizon=p_cfg["horizon"],
            n_candidates=p_cfg["n_candidates"],
            device=device,
        )
        print(f"MPC planner: horizon={p_cfg['horizon']}, candidates={p_cfg['n_candidates']}")

        # --- Build goal embedding ---
        print("\nBuilding goal embedding...")
        goal = build_goal_embedding(encoder, cfg, device).to(device)

    # --- Create env ---
    a_cfg = cfg["agent"]
    if env_type == "minerl":
        env = make_minerl_env(cfg)
    else:
        env = make_crafter_env(cfg)

    # --- Random baseline (optional) ---
    if args.compare_random:
        print(f"\nRandom baseline ({n_episodes} episodes)...")
        if env_type == "minerl":
            env_rand = make_minerl_env(cfg)
        else:
            import crafter
            env_rand = crafter.Env(seed=a_cfg["seed"])
        baseline = run_random_baseline(env_rand, env_type, n_episodes, a_cfg["max_steps"], action_map)
        print(
            f"  reward={baseline['mean_reward']:.3f}  "
            f"steps={baseline['mean_steps']:.0f}  "
            f"achievements={baseline['mean_achievements']:.2f}  "
            f"success_rate={baseline['success_rate']:.1%}"
        )

    # --- Agent loop ---
    label = cfg.get("minerl_env", "Minecraft") if env_type == "minerl" else "Crafter"
    print(f"\n{'='*55}")
    print(f"JEPA-MPC agent — {n_episodes} episodes in {label}")
    print(f"{'='*55}")

    log_every = cfg["logging"]["print_every"]
    gif_budget = cfg["logging"]["gif_episodes"]
    all_rewards, all_steps, all_achievements_list = [], [], []
    gif_frames = []

    for ep in range(1, n_episodes + 1):
        record = ep <= gif_budget and cfg["logging"]["save_gif"]
        result = run_episode(
            env, env_type, encoder, planner, goal,
            max_steps=a_cfg["max_steps"],
            device=device,
            action_map=action_map,
            record_frames=record,
        )
        all_rewards.append(result["reward"])
        all_steps.append(result["steps"])
        all_achievements_list.append(result["n_achievements"])
        if record and result["frames"]:
            gif_frames.extend(result["frames"])

        if ep % log_every == 0 or ep == 1:
            avg_r = np.mean(all_rewards[-log_every:])
            avg_a = np.mean(all_achievements_list[-log_every:])
            fps = result["fps"]
            acts = result.get("action_summary", "")
            print(
                f"Ep {ep:4d}/{n_episodes} | "
                f"reward={avg_r:.3f}  achievements={avg_a:.2f}  "
                f"steps={result['steps']}  fps={fps:.1f}"
                + (f"  [{acts}]" if acts else "")
            )
            if result["achievements"]:
                print(f"           : {', '.join(result['achievements'])}")

    # --- Final results ---
    print(f"\n{'='*55}")
    mean_r = np.mean(all_rewards)
    mean_a = np.mean(all_achievements_list)
    success_rate = np.mean([a > 0 for a in all_achievements_list])
    print(f"  Mean reward       : {mean_r:.4f}")
    print(f"  Achievements/ep   : {mean_a:.2f}")
    print(f"  Success rate      : {success_rate:.1%}")
    print(f"  Mean steps        : {np.mean(all_steps):.0f}")

    gate_threshold = 0.3 if env_type == "minerl" else 0.5
    gate = success_rate >= gate_threshold
    print(f"\n  Phase 4 Gate      : {'PASSED' if gate else 'NOT PASSED'}  (success_rate >= {gate_threshold:.0%})")

    if args.compare_random:
        print(f"\n  vs Random : reward {mean_r:.3f} vs {baseline['mean_reward']:.3f}  "
              f"| achievements {mean_a:.2f} vs {baseline['mean_achievements']:.2f}")

    # --- GIF ---
    if gif_frames and cfg["logging"]["save_gif"]:
        gif_path = Path(cfg["logging"]["gif_path"])
        gif_path.parent.mkdir(exist_ok=True)
        imageio.mimsave(str(gif_path), gif_frames, fps=10, loop=0)
        print(f"\n  GIF saved → {gif_path}")


if __name__ == "__main__":
    main()

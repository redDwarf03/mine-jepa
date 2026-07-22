"""
Phase 4c step 4 — MPC agent with action-conditioned world model (eb_jepa).

Pipeline:
  1. Load ebwm.pt (encoder + predictor trained jointly)
  2. Build goal latent: centroid of latent maps from reward>0 frames
  3. MineRL loop: frame → random-shooting planner (latent rollout) → action

Prints metrics in the SAME format as play.py (parsed by play_minerl_multi.py).

Usage: run.bat scripts/play_ebwm.py --config configs/play_ebwm.yaml --episodes 1
"""
import argparse
import logging
import time
from pathlib import Path

import imageio
import numpy as np
import torch
import yaml

# Silence verbose MineRL/Malmo noise (asset downloads, Java watcher)
logging.getLogger("minerl").setLevel(logging.CRITICAL)

from mine_jepa.ebwm import build_ac_jepa
from mine_jepa.ebwm.curiosity import DisagreementEnsemble
from mine_jepa.ebwm.dataset import _load_npz
from mine_jepa.ebwm.planner import DiscreteLatentPlanner
from scripts.play import (
    load_action_map, make_minerl_env, minerl_reset, minerl_step,
)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/play_ebwm.yaml")
    p.add_argument("--episodes", type=int, default=None)
    return p.parse_args()


def load_cfg(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_model(ckpt_path: str, device: torch.device):
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    m = ckpt["cfg"]["model"]
    r = ckpt["cfg"]["regularizer"]
    model = build_ac_jepa(
        embed_dim=m["embed_dim"], encoder_hidden=m["encoder_hidden"],
        n_actions=m["n_actions"], action_embed_dim=m["action_embed_dim"],
        predictor_hidden=m["predictor_hidden"],
        std_coeff=r["std_coeff"], cov_coeff=r["cov_coeff"], sim_coeff_t=r["sim_coeff_t"],
    ).to(device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    return model, ckpt.get("ratio", float("nan"))


def preprocess(obs: np.ndarray, device: torch.device) -> torch.Tensor:
    """frame [H,W,3] uint8 → [1, 3, 1, 64, 64] float [0,1]."""
    import cv2
    frame = cv2.resize(obs, (64, 64))
    t = torch.from_numpy(frame).float() / 255.0
    return t.permute(2, 0, 1).unsqueeze(0).unsqueeze(2).to(device)  # [1,3,1,64,64]


@torch.no_grad()
def build_obtain_log_gain_goal(model, g: dict, device) -> torch.Tensor:
    """
    Cold-start attempt #11 (docs/10): centroid of 'log count increased' frames from
    a real MineRLObtainIronPickaxe demos npz (data/minerl_craft/episodes.npz),
    encoded by `model` (any frozen eb-JEPA world model, e.g. ebwm.pt) — the
    Obtain-domain analog of scripts/play_craft.py::build_chop_goal's default
    branch (same inventory-log-gain logic, different encoder). Used when
    goal.mode == "obtain_log_gain" so the two-brain chop planner's goal anchor is
    also Obtain-domain, matching what the paired DistanceProjector was trained
    against (attempt #10 found ebwm.pt's own scoring reverses direction on Obtain;
    a Treechop-only goal anchor would not fix that).
    """
    data = _load_npz(g["data_path"])
    frames, inv, dones = data["frames"], data["inventory"], data["dones"].astype(bool)
    items = [str(x) for x in data["inventory_items"]]
    log_idx = items.index(g.get("log_item", "log"))
    log = inv[:, log_idx].astype(np.int64)
    inc = np.zeros(len(frames), dtype=bool)
    inc[1:] = (log[1:] > log[:-1]) & (~dones[:-1])
    good = frames[inc]
    if len(good) < g.get("min_frames", 10):
        print(f"  ⚠️  only {len(good)} log-gain frames — using all frames for the goal")
        good = frames
    print(f"  Goal [obtain_log_gain]: centroid of {len(good)} 'log obtained' frames "
          f"({g['data_path']})")
    lat_sum, n = None, 0
    for i in range(0, len(good), 256):
        obs = torch.from_numpy(good[i:i + 256]).float() / 255.0
        obs = obs.permute(0, 3, 1, 2).unsqueeze(2).to(device)
        lat = model.encode(obs).squeeze(2)                     # [B,D,H',W']
        s = lat.sum(dim=0)
        lat_sum = s if lat_sum is None else lat_sum + s
        n += lat.size(0)
    goals = (lat_sum / n).unsqueeze(0)                          # [1,D,H',W']
    print(f"  goal latents: {tuple(goals.shape)}")
    return goals


@torch.no_grad()
def build_goal_latents(model, cfg, device) -> torch.Tensor:
    """
    Returns latent targets (success scenes, reward>0 frames) as [K, D, H', W'].

    Three modes (planner scores by distance to nearest of the K, so K=1 = centroid):
      - "centroid" (default): K=1, mean of all reward>0 frames. "Blurry" target
        never reached → forces permanent movement (empirically best: 50%).
      - "nearest": K sampled prototypes → nearest-neighbor. WARNING: tends to
        freeze the agent (a0/noop) because "stay near a success" minimizes distance.
      - "obtain_log_gain" (cold-start attempt #11): see build_obtain_log_gain_goal —
        an Obtain-domain goal anchor instead of a Treechop reward-frame one.
    """
    g = cfg["goal"]
    mode = g.get("mode", "centroid")
    if mode == "obtain_log_gain":
        return build_obtain_log_gain_goal(model, g, device)
    data = _load_npz(g["data_path"])
    frames = data["frames"]                                    # [N,H,W,3] uint8
    rewards = data["rewards"].astype(np.float32)
    mask = rewards >= g["threshold"]
    good = frames[mask]
    if len(good) < g["min_frames"]:
        print(f"  ⚠️  {len(good)} goal frames — falling back to all frames")
        good = frames

    if mode == "nearest":
        k = g.get("n_prototypes", 256)
        if len(good) > k:
            idx = np.random.RandomState(0).choice(len(good), k, replace=False)
            good = good[idx]
        print(f"  Goal [nearest]: {len(good)} prototypes (reward >= {g['threshold']})")
        lats = []
        for i in range(0, len(good), 256):
            obs = torch.from_numpy(good[i:i + 256]).float() / 255.0
            obs = obs.permute(0, 3, 1, 2).unsqueeze(2).to(device)
            lats.append(model.encode(obs).squeeze(2))
        goals = torch.cat(lats, dim=0)                         # [K,D,H',W']
    else:  # centroid
        print(f"  Goal [centroid]: mean of {len(good)} frames (reward >= {g['threshold']})")
        lat_sum, n = None, 0
        for i in range(0, len(good), 256):
            obs = torch.from_numpy(good[i:i + 256]).float() / 255.0
            obs = obs.permute(0, 3, 1, 2).unsqueeze(2).to(device)
            lat = model.encode(obs).squeeze(2)                 # [B,D,H',W']
            s = lat.sum(dim=0)
            lat_sum = s if lat_sum is None else lat_sum + s
            n += lat.size(0)
        goals = (lat_sum / n).unsqueeze(0)                     # [1,D,H',W']
    print(f"  goal latents: {tuple(goals.shape)}")
    return goals


def main():
    args = parse_args()
    cfg = load_cfg(args.config)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print("Env: minerl")

    action_map = load_action_map(cfg.get("actions_config", "configs/minerl_actions.yaml"))

    print("\nLoading action-conditioned world model...")
    model, ratio = load_model(cfg["model"]["checkpoint"], device)
    print(f"  ebwm.pt loaded (training ratio={ratio:.3f})")

    p_cfg = cfg["planner"]
    novelty_coeff = float(p_cfg.get("novelty_coeff", 0.0))
    ensemble = None
    ens_path = p_cfg.get("ensemble_checkpoint", "")
    if novelty_coeff > 0.0 and ens_path:
        print(f"\nLoading curiosity ensemble from {ens_path}...")
        ensemble = DisagreementEnsemble.load(ens_path, device=device)
        ensemble.eval()
        print(f"  Ensemble loaded ({ensemble.n_heads} heads, novelty_coeff={novelty_coeff})")
    elif novelty_coeff > 0.0:
        print("  WARNING: novelty_coeff > 0 but no ensemble_checkpoint — curiosity disabled.")
        novelty_coeff = 0.0

    cem_cfg = p_cfg.get("cem", {}) or {}
    planner = DiscreteLatentPlanner(
        model, n_actions=p_cfg["n_actions"], horizon=p_cfg["horizon"],
        n_candidates=p_cfg["n_candidates"],
        novelty_coeff=novelty_coeff, ensemble=ensemble,
        sticky_prob=float(p_cfg.get("sticky_prob", 0.0)),
        commit_length=int(p_cfg.get("commit_length", 1)),
        cem_iters=int(cem_cfg.get("iters", 1)),
        cem_elite_frac=float(cem_cfg.get("elite_frac", 0.1)),
        cem_smoothing=float(cem_cfg.get("smoothing", 0.01)),
        device=device,
    )
    mode_label = f"novelty λ={novelty_coeff}" if novelty_coeff > 0.0 else "goal-centroid only"
    print(f"Planner: horizon={p_cfg['horizon']}, candidates={p_cfg['n_candidates']}, "
          f"mode={mode_label}, sticky_prob={planner.sticky_prob}, commit_length={planner.commit_length}, "
          f"cem_iters={planner.cem_iters}")

    scan_cfg = cfg.get("scan", {}) or {}
    scan_enabled = bool(scan_cfg.get("enabled", False))
    if scan_enabled:
        print(f"Scan macro: ON (flat_threshold={scan_cfg['flat_threshold']}, "
              f"patience={scan_cfg.get('patience', 3)}, "
              f"turn_action=a{scan_cfg.get('turn_action', 12)}, "
              f"max_replans={scan_cfg.get('max_replans', 40)})")

    print("\nBuilding goal prototypes...")
    goal = build_goal_latents(model, cfg, device)

    a_cfg = cfg["agent"]
    n_episodes = args.episodes or a_cfg["episodes"]
    env = make_minerl_env(cfg)

    label = cfg.get("minerl_env", "MineRLTreechop-v0")
    print(f"\n{'='*55}\neb-JEPA MPC agent — {n_episodes} episodes in {label}\n{'='*55}")

    all_rewards, all_steps, all_ach = [], [], []
    gif_frames = []
    save_gif = cfg["logging"]["save_gif"]
    gif_budget = cfg["logging"]["gif_episodes"]

    for ep in range(1, n_episodes + 1):
        obs = minerl_reset(env)
        done, step, total_r = False, 0, 0.0
        ach = set()
        action_counts = [0] * 17
        record = ep <= gif_budget and save_gif
        if record:
            gif_frames.append(obs)
        t0 = time.perf_counter()

        # action_repeat: re-plan every K steps and repeat the chosen action.
        # Double benefit: ~K× faster AND produces the SUSTAINED attack needed
        # to break a log (a human holds "attack" for multiple ticks).
        repeat = a_cfg.get("action_repeat", 1)

        # Scan macro state (docs/10): goal_score_std ≈ 0 across candidates means
        # "no tree in view, the planner is choosing among lottery tickets" → force
        # a camera-yaw sweep until the std recovers (a goal entered the frame).
        # One scan replan turns 10° × action_repeat.
        flat_count, scanning, scan_replans, scan_triggers = 0, False, 0, 0
        while not done and step < a_cfg["max_steps"]:
            obs_t = preprocess(obs, device)
            action, info = planner.plan(obs_t, goal, return_info=True)
            std = info["goal_score_std"]
            if scan_cfg.get("log_std", False):
                print(f"    [scan] step={step:4d} goal_score_std={std:.6f}"
                      f"{'  SCANNING' if scanning else ''}")
            # commit_length>1 (docs/10 sustained-plan experiment): plan() returns the
            # first M actions of the winning sequence instead of only the first, so
            # they execute as a block before the next replan. commit_length=1
            # (default) makes `action` a single int and `committed` its 1-element
            # list — the loop below is then identical to the original single-action
            # execution, bit-for-bit.
            committed = action if isinstance(action, list) else [action]
            if scan_enabled:
                flat = std < float(scan_cfg["flat_threshold"])
                if not scanning:
                    flat_count = flat_count + 1 if flat else 0
                    if flat_count >= int(scan_cfg.get("patience", 3)):
                        scanning, scan_replans = True, 0
                        scan_triggers += 1
                if scanning:
                    if not flat or scan_replans >= int(scan_cfg.get("max_replans", 40)):
                        scanning, flat_count = False, 0
                    else:
                        committed = [int(scan_cfg.get("turn_action", 12))] * len(committed)
                        scan_replans += 1
            for act in committed:
                if done or step >= a_cfg["max_steps"]:
                    break
                for _ in range(repeat):
                    if done or step >= a_cfg["max_steps"]:
                        break
                    action_counts[act] += 1
                    obs, r, done, a = minerl_step(env, act, action_map)
                    total_r += r
                    ach.update(a)
                    step += 1
                    if record:
                        gif_frames.append(obs)

        fps = step / (time.perf_counter() - t0)
        top3 = sorted(range(17), key=lambda i: -action_counts[i])[:3]
        acts = " ".join(f"a{i}={action_counts[i]/max(step,1)*100:.0f}%" for i in top3)
        all_rewards.append(total_r)
        all_steps.append(step)
        all_ach.append(len(ach))
        print(f"Ep {ep:4d}/{n_episodes} | reward={total_r:.3f}  achievements={len(ach):.2f}  "
              f"steps={step}  fps={fps:.1f}  [{acts}]")
        if scan_enabled:
            # Separate line: the Ep line format is parsed by play_minerl_multi.py.
            print(f"   scan triggers={scan_triggers}")

    print(f"\n{'='*55}")
    mean_r = float(np.mean(all_rewards))
    success = float(np.mean([a > 0 for a in all_ach]))
    print(f"  Mean reward       : {mean_r:.4f}")
    print(f"  Achievements/ep   : {np.mean(all_ach):.2f}")
    print(f"  Success rate      : {success:.1%}")
    print(f"  Mean steps        : {np.mean(all_steps):.0f}")
    gate = success >= 0.3
    print(f"\n  Phase 4 Gate      : {'PASSED' if gate else 'NOT PASSED'}  (success_rate >= 30%)")

    if gif_frames and save_gif:
        gp = Path(cfg["logging"]["gif_path"])
        gp.parent.mkdir(exist_ok=True)
        imageio.mimsave(str(gp), gif_frames, fps=10, loop=0)
        print(f"  GIF saved → {gp}")


if __name__ == "__main__":
    main()

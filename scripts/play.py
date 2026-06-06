"""
Phase 3 — Agent JEPA qui joue à Crafter par MPC en espace latent.

Pipeline :
  1. Construire le goal embedding : centroïde des états latents "bon état"
     (frames où food >= seuil, issus du dataset Phase 0).
  2. Pour chaque épisode :
     a. Reset Crafter → frame initiale
     b. Boucle de jeu :
        - Encoder la frame courante → s_t
        - Planner : imaginer 512 séquences × 12 pas dans le WM → best action
        - Exécuter l'action, observer
        - Vérifier les achievements Crafter
  3. Reporter le taux de succès vs baseline random.

Gate Phase 3 :
  - ≥ 1 achievement par épisode plus fréquemment qu'une politique aléatoire

Usage :
    run.bat scripts/play.py
    run.bat scripts/play.py --episodes 100
    run.bat scripts/play.py --compare_random   (ajoute baseline aléatoire)
"""
import argparse
import time
from pathlib import Path

import cv2
import crafter
import imageio
import numpy as np
import torch
import yaml

from mine_jepa.encoder.crafter_encoder import CrafterJEPA
from mine_jepa.encoder.dataset import _load_npz, _to_float
from mine_jepa.planning import LatentMPCPlanner
from mine_jepa.predictor import ActionConditionedPredictor


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/play.yaml")
    p.add_argument("--episodes", type=int, default=None)
    p.add_argument("--compare_random", action="store_true")
    return p.parse_args()


def load_cfg(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


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
    """
    Construit le goal embedding = centroïde des états latents 'bons'.
    'Bon' = food >= threshold dans le dataset.
    """
    g_cfg = cfg["goal"]
    data = _load_npz(g_cfg["data_path"])
    frames = _to_float(data["frames"])           # [N, 3, H, W]
    food = data[g_cfg["label"]].astype(np.int64) # [N]

    mask = food >= g_cfg["threshold"]
    good_frames = frames[mask]

    if len(good_frames) < g_cfg["min_frames"]:
        print(f"  ⚠️  Seulement {len(good_frames)} frames 'goal' (< {g_cfg['min_frames']})")
        print(f"  → Utilisation de toutes les frames comme goal (exploration générique)")
        good_frames = frames

    print(f"  Goal embedding : {len(good_frames)} frames ({g_cfg['label']} >= {g_cfg['threshold']})")

    # Encoder par batchs
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


def run_episode(
    env: crafter.Env,
    encoder: torch.nn.Module,
    planner: LatentMPCPlanner,
    goal: torch.Tensor,
    max_steps: int,
    device: torch.device,
    record_frames: bool = False,
) -> dict:
    obs = env.reset()
    done = False
    step = 0
    total_reward = 0.0
    achievements = {}
    frames = [obs] if record_frames else []
    t_start = time.perf_counter()

    while not done and step < max_steps:
        frame_t = preprocess_frame(obs).to(device)
        with torch.no_grad():
            s_t = encoder(frame_t)  # [1, D]

        action = planner.plan(s_t, goal)
        obs, reward, done, info = env.step(action)

        total_reward += reward
        step += 1

        # Fusionner les achievements (Crafter les accumule sur l'épisode)
        for k, v in info.get("achievements", {}).items():
            if v:
                achievements[k] = True

        if record_frames:
            frames.append(obs)

    elapsed = time.perf_counter() - t_start
    return {
        "steps": step,
        "reward": total_reward,
        "achievements": achievements,
        "n_achievements": len(achievements),
        "fps": step / elapsed,
        "frames": frames,
    }


def run_random_baseline(env: crafter.Env, n_episodes: int, max_steps: int) -> dict:
    """Baseline : politique aléatoire uniforme."""
    all_rewards, all_steps, all_achievements = [], [], []
    for _ in range(n_episodes):
        env.reset()
        done = False
        step = 0
        reward_sum = 0.0
        achievements = {}
        while not done and step < max_steps:
            action = np.random.randint(env.action_space.n)
            _, r, done, info = env.step(action)
            reward_sum += r
            step += 1
            for k, v in info.get("achievements", {}).items():
                if v:
                    achievements[k] = True
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
    n_episodes = args.episodes or cfg["agent"]["episodes"]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # --- Charger les modèles ---
    print("\nChargement des modèles...")
    encoder = load_encoder(cfg["encoder"]["checkpoint"], device)

    # Charger la config du WM depuis son checkpoint pour reconstruire le predictor
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
    print(f"Planner : horizon={p_cfg['horizon']}, candidates={p_cfg['n_candidates']}")

    # --- Construire le goal embedding ---
    print("\nConstruction du goal embedding...")
    goal = build_goal_embedding(encoder, cfg, device).to(device)

    # --- Baseline random (optionnel) ---
    a_cfg = cfg["agent"]
    if args.compare_random:
        print(f"\nBaseline random ({n_episodes} épisodes)...")
        env_rand = crafter.Env(seed=a_cfg["seed"])
        baseline = run_random_baseline(env_rand, n_episodes, a_cfg["max_steps"])
        print(
            f"  reward={baseline['mean_reward']:.3f}  "
            f"steps={baseline['mean_steps']:.0f}  "
            f"achievements={baseline['mean_achievements']:.2f}  "
            f"success_rate={baseline['success_rate']:.1%}"
        )

    # --- Boucle agent ---
    print(f"\n{'='*55}")
    print(f"Agent JEPA-MPC — {n_episodes} épisodes dans Crafter")
    print(f"{'='*55}")

    env = crafter.Env(seed=a_cfg["seed"])
    log_every = cfg["logging"]["print_every"]
    gif_budget = cfg["logging"]["gif_episodes"]
    all_rewards, all_steps, all_achievements = [], [], []
    gif_frames = []

    for ep in range(1, n_episodes + 1):
        record = ep <= gif_budget and cfg["logging"]["save_gif"]
        result = run_episode(
            env, encoder, planner, goal,
            max_steps=a_cfg["max_steps"],
            device=device,
            record_frames=record,
        )
        all_rewards.append(result["reward"])
        all_steps.append(result["steps"])
        all_achievements.append(result["n_achievements"])
        if record and result["frames"]:
            gif_frames.extend(result["frames"])

        if ep % log_every == 0 or ep == 1:
            avg_r = np.mean(all_rewards[-log_every:])
            avg_a = np.mean(all_achievements[-log_every:])
            fps = result["fps"]
            print(
                f"Ep {ep:4d}/{n_episodes} | "
                f"reward={avg_r:.3f}  achievements={avg_a:.2f}  "
                f"steps={result['steps']}  fps={fps:.1f}"
            )
            if result["achievements"]:
                print(f"           Achievements : {', '.join(result['achievements'].keys())}")

    # --- Résultats finaux ---
    print(f"\n{'='*55}")
    print(f"Résultats finaux — Agent JEPA-MPC ({n_episodes} épisodes)")
    print(f"{'='*55}")
    mean_r = np.mean(all_rewards)
    mean_a = np.mean(all_achievements)
    success_rate = np.mean([a > 0 for a in all_achievements])
    print(f"  Reward moyen      : {mean_r:.4f}")
    print(f"  Achievements/ep   : {mean_a:.2f}")
    print(f"  Success rate      : {success_rate:.1%}  (≥1 achievement/épisode)")
    print(f"  Steps moyen       : {np.mean(all_steps):.0f}")

    gate = mean_a >= 0.5  # au moins 1 achievement toutes les 2 épisodes
    print(f"\n  Gate Phase 3      : {'✅ PASSÉ' if gate else '❌ NON PASSÉ'}")
    if not gate:
        print("  → Augmenter horizon ou n_candidates dans configs/play.yaml")

    if args.compare_random:
        print(f"\n  vs Random : reward {mean_r:.3f} vs {baseline['mean_reward']:.3f}  "
              f"| achievements {mean_a:.2f} vs {baseline['mean_achievements']:.2f}")

    # --- GIF ---
    if gif_frames and cfg["logging"]["save_gif"]:
        gif_path = Path(cfg["logging"]["gif_path"])
        gif_path.parent.mkdir(exist_ok=True)
        imageio.mimsave(str(gif_path), gif_frames, fps=10, loop=0)
        print(f"\n  GIF sauvegardé → {gif_path}")


if __name__ == "__main__":
    main()

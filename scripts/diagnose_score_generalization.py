"""
Cold-start attempt #10 (docs/10_coldstart_engineering.md) — offline diagnostic for
the standing hypothesis raised after attempt #9: with every action-generation-side
confound checked and ruled out on a genuinely diverse, non-collapsed BC-actor
candidate pool over confirmed-viable, confirmed-diverse Obtain spawns (0/8, no
lock-in, no unwinnable-spawn excuse), what is left standing "by elimination" is
ebwm.pt's OWN goal-centroid scoring — trained exclusively on MineRLTreechop-v0's
forest-guaranteed spawns, never exercised end-to-end on
MineRLObtainIronPickaxeDense-v0's free-spawn visual distribution.

This script tests that DIRECTLY, offline, with no MineRL/Java process and no
training: ebwm.pt is loaded frozen (eval, no grad), and for a set of saved
starting frames from both distributions, it reuses the EXACT candidate-sampling
(_sample_actions) and scoring (_score) code from
mine_jepa/ebwm/planner.py::DiscreteLatentPlanner — the same computation the live
scan/spawn_diag machinery already runs every replan — to compute the goal-score
spread (std and max-min range) across the same 512-candidate pool the live
planner would consider from that exact frame.

Frame sources:
  - Treechop: data/minerl_goal/episodes.npz (the data ebwm.pt itself trained on),
    sampled episodes at several within-episode offsets (varying tree distance).
  - Obtain: assets/spawn_thumbs/*.png (attempt #9's real MineRLObtainIronPickaxeDense
    cold-start spawn frames, already spot-checked non-degenerate) PLUS
    data/minerl_coverage/episodes.npz (attempt #3's random-policy coverage episodes
    on the SAME Obtain env, more Obtain-sourced frames at varying offsets).

No checkpoint is written or modified. Seed 0 (candidate sampling is stochastic).

Usage: run.bat scripts/diagnose_score_generalization.py --config configs/diagnose_score_generalization.yaml
"""
import argparse
import random
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import torch
import yaml

from mine_jepa.ebwm.dataset import _load_npz
from mine_jepa.ebwm.planner import DiscreteLatentPlanner, _sample_actions
from scripts.play_ebwm import build_goal_latents, load_model, preprocess


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/diagnose_score_generalization.yaml")
    return p.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def episode_ranges(dones: np.ndarray, chunk_size: int | None = None) -> list[tuple[int, int]]:
    """
    [start, end) index ranges, one per episode, split at dones==True. Fallback: if
    `dones` is entirely False and `chunk_size` is given, segment into fixed-length
    chunks instead — same fallback as scripts/train_value_projector.py's
    episode_ranges, needed because data/minerl_coverage/episodes.npz's dones array
    is all-False (collect_minerl_multi.py's shard-merge bug, docs/10 attempt #7).
    """
    if chunk_size and not dones.any():
        n = len(dones)
        return [(s, min(s + chunk_size, n)) for s in range(0, n, chunk_size)]
    idx = np.where(dones)[0]
    starts = np.concatenate(([0], idx + 1))
    ends = np.concatenate((idx + 1, [len(dones)]))
    return [(int(s), int(e)) for s, e in zip(starts, ends) if e > s]


def gather_treechop_frames(cfg: dict, rng: np.random.RandomState) -> list[dict]:
    d = _load_npz(cfg["data_path"])
    ranges = episode_ranges(d["dones"].astype(bool))
    n_ep = min(int(cfg["n_episodes"]), len(ranges))
    chosen = rng.choice(len(ranges), size=n_ep, replace=False)
    chosen.sort()
    rows = []
    for rank, ei in enumerate(chosen):
        s, e = ranges[ei]
        length = e - s - 1
        for off in cfg["offsets"]:
            idx = s + int(round(float(off) * length))
            rows.append({
                "group": "treechop", "episode": int(ei), "offset": float(off),
                "frame_idx": int(idx), "frame": d["frames"][idx],
                "thumb": rank < int(cfg.get("n_thumbs", 0)) and float(off) == 0.0,
            })
    return rows


def gather_obtain_frames(cfg: dict) -> list[dict]:
    rows = []
    thumb_dir = Path(cfg["spawn_thumb_dir"])
    for path in sorted(thumb_dir.glob("*.png")):
        frame = imageio.imread(str(path))[:, :, :3]
        rows.append({
            "group": "obtain_spawn", "episode": path.stem, "offset": 0.0,
            "frame_idx": 0, "frame": frame, "thumb": True, "path": str(path),
        })

    d = _load_npz(cfg["coverage_data_path"])
    ranges = episode_ranges(d["dones"].astype(bool), chunk_size=int(cfg["coverage_chunk_size"]))
    n_ch = min(int(cfg["coverage_n_chunks"]), len(ranges))
    for ci in range(n_ch):
        s, e = ranges[ci]
        length = e - s - 1
        for off in cfg["coverage_offsets"]:
            idx = s + int(round(float(off) * length))
            rows.append({
                "group": "obtain_coverage", "episode": int(ci), "offset": float(off),
                "frame_idx": int(idx), "frame": d["frames"][idx],
                "thumb": ci < 8 and float(off) == 0.0,
            })
    return rows


@torch.no_grad()
def score_frame(planner: DiscreteLatentPlanner, goal_latents: torch.Tensor,
                 frame: np.ndarray, device) -> tuple[float, float]:
    """
    Reuses DiscreteLatentPlanner's own _sample_actions + _score directly (the exact
    live code path, not a reimplementation). Returns (goal_score_std, score_range)
    over the same 512-candidate pool the live planner would consider from this frame.
    """
    obs = preprocess(frame, device)                                     # [1,3,1,64,64]
    obs_n = obs.expand(planner.n_candidates, -1, -1, -1, -1).contiguous()
    actions = _sample_actions(
        planner.n_candidates, planner.horizon, planner.n_actions,
        planner.sticky_prob, device,
    )
    scores, goal_score_std, _ = planner._score(obs_n, goal_latents, actions)
    score_range = float((scores.max() - scores.min()).item())
    return goal_score_std, score_range


def summarize(values: np.ndarray) -> dict:
    return {
        "n": len(values),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "std": float(np.std(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "p10": float(np.percentile(values, 10)),
        "p90": float(np.percentile(values, 90)),
    }


def print_summary(title: str, values: np.ndarray) -> None:
    s = summarize(values)
    print(f"  {title:<28} n={s['n']:>4}  mean={s['mean']:.6f}  median={s['median']:.6f}  "
          f"std={s['std']:.6f}  min={s['min']:.6f}  max={s['max']:.6f}  "
          f"p10={s['p10']:.6f}  p90={s['p90']:.6f}")


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    seed = int(cfg.get("seed", 0))
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}  |  seed: {seed}")

    print("\nLoading ebwm.pt frozen (read-only, no gradient, no checkpoint write)...")
    model, ratio = load_model(cfg["model"]["checkpoint"], device)
    model.requires_grad_(False)
    for p in model.parameters():
        assert not p.requires_grad
    print(f"  ebwm.pt loaded (ratio={ratio:.3f}), requires_grad_(False) verified")

    print("\nBuilding goal centroid (same construction as the live two-brain chop planner)...")
    goal_latents = build_goal_latents(model, {"goal": cfg["goal"]}, device)

    p_cfg = cfg["planner"]
    planner = DiscreteLatentPlanner(
        model, n_actions=int(p_cfg["n_actions"]), horizon=int(p_cfg["horizon"]),
        n_candidates=int(p_cfg["n_candidates"]), sticky_prob=float(p_cfg["sticky_prob"]),
        device=device,
    )
    print(f"Planner: horizon={planner.horizon} candidates={planner.n_candidates} "
          f"sticky_prob={planner.sticky_prob}")

    rng = np.random.RandomState(seed)
    print("\nGathering Treechop frames (data ebwm.pt trained on)...")
    treechop_rows = gather_treechop_frames(cfg["treechop"], rng)
    print(f"  {len(treechop_rows)} frames from "
          f"{len(set(r['episode'] for r in treechop_rows))} episodes")

    print("Gathering Obtain frames (cold-start spawn thumbnails + coverage episodes)...")
    obtain_rows = gather_obtain_frames(cfg["obtain"])
    n_spawn = sum(1 for r in obtain_rows if r["group"] == "obtain_spawn")
    n_cov = sum(1 for r in obtain_rows if r["group"] == "obtain_coverage")
    print(f"  {n_spawn} real cold-start spawn frames (attempt #9) + "
          f"{n_cov} coverage-episode frames")

    out_dir = Path(cfg["output"]["dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir = out_dir / "treechop_thumbs"
    thumb_dir.mkdir(exist_ok=True)
    cov_thumb_dir = out_dir / "obtain_coverage_thumbs"
    cov_thumb_dir.mkdir(exist_ok=True)

    all_rows = treechop_rows + obtain_rows
    print(f"\nScoring {len(all_rows)} frames through DiscreteLatentPlanner._sample_actions "
          f"+ _score (the exact live scan/spawn_diag computation)...")
    for i, row in enumerate(all_rows):
        std, rng_score = score_frame(planner, goal_latents, row["frame"], device)
        row["goal_score_std"] = std
        row["score_range"] = rng_score
        if row.get("thumb") and row["group"] == "treechop":
            imageio.imwrite(str(thumb_dir / f"ep{row['episode']:03d}.png"), row["frame"])
        if row.get("thumb") and row["group"] == "obtain_coverage":
            imageio.imwrite(str(cov_thumb_dir / f"chunk{row['episode']:03d}.png"), row["frame"])
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(all_rows)}", flush=True)

    csv_path = out_dir / cfg["output"]["csv_name"]
    with open(csv_path, "w") as f:
        f.write("group,episode,offset,frame_idx,goal_score_std,score_range\n")
        for row in all_rows:
            f.write(f"{row['group']},{row['episode']},{row['offset']},{row['frame_idx']},"
                    f"{row['goal_score_std']:.8f},{row['score_range']:.8f}\n")
    print(f"\nCSV saved -> {csv_path}")

    print(f"\n{'=' * 78}\nSCORE-SPREAD SUMMARY (goal_score_std across the same 512-candidate pool)\n{'=' * 78}")
    groups = {
        "treechop": np.array([r["goal_score_std"] for r in all_rows if r["group"] == "treechop"]),
        "obtain_spawn": np.array([r["goal_score_std"] for r in all_rows if r["group"] == "obtain_spawn"]),
        "obtain_coverage": np.array([r["goal_score_std"] for r in all_rows if r["group"] == "obtain_coverage"]),
    }
    for name, vals in groups.items():
        if len(vals):
            print_summary(name, vals)
    obtain_all = np.concatenate([groups["obtain_spawn"], groups["obtain_coverage"]])
    print_summary("obtain (spawn+coverage)", obtain_all)

    tc_median = float(np.median(groups["treechop"]))
    ob_median = float(np.median(obtain_all))
    print(f"\n  Treechop median / Obtain median = {tc_median / max(ob_median, 1e-12):.3f}x")
    print(f"  Treechop p90 / Obtain p90       = "
          f"{np.percentile(groups['treechop'], 90) / max(np.percentile(obtain_all, 90), 1e-12):.3f}x")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
        data = [groups["treechop"], groups["obtain_spawn"], groups["obtain_coverage"]]
        labels = [f"treechop\n(n={len(groups['treechop'])})",
                  f"obtain_spawn\n(n={len(groups['obtain_spawn'])})",
                  f"obtain_coverage\n(n={len(groups['obtain_coverage'])})"]
        axes[0].boxplot(data, labels=labels, showmeans=True)
        axes[0].set_ylabel("goal_score_std")
        axes[0].set_title("Score spread by source (linear)")
        axes[1].boxplot(data, labels=labels, showmeans=True)
        axes[1].set_yscale("log")
        axes[1].set_ylabel("goal_score_std (log scale)")
        axes[1].set_title("Score spread by source (log)")
        fig.suptitle("Cold-start attempt #10 — ebwm.pt goal-score spread, "
                      "Treechop (training distribution) vs Obtain (deployment distribution)")
        fig.tight_layout()
        plot_path = out_dir / cfg["output"]["plot_name"]
        fig.savefig(plot_path, dpi=130)
        print(f"\nPlot saved -> {plot_path}")
    except ImportError:
        print("\nmatplotlib not available — skipping plot (CSV has the full data).")

    print(f"\nTreechop spawn thumbnails (for manual tree-visible eyeballing) -> {thumb_dir}")
    print(f"Obtain coverage spawn thumbnails -> {cov_thumb_dir}")
    print(f"Obtain real cold-start spawn thumbnails (attempt #9, pre-existing) -> "
          f"{cfg['obtain']['spawn_thumb_dir']}")


if __name__ == "__main__":
    main()

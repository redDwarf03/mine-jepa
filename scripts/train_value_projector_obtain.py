"""
Cold-start attempt #11 (docs/10_coldstart_engineering.md, candidate direction #1 from
the post-attempt-#10 menu) — train a DistanceProjector with supervision sourced
ENTIRELY from MineRLObtainIronPickaxe(Dense), not from Treechop.

Attempt #10 found that ebwm.pt's own raw-latent goal-centroid scoring REVERSES
direction on Obtain's free-spawn distribution (closer trees score LOWER than open/
treeless views). Attempt #7's trained DistanceProjector discriminated near/far
convincingly offline (7.9x) but keyed off a lighting confound live, root-caused to
BOTH its training pools (Treechop demos + coverage) and its goal anchor (a Treechop
reward-frame centroid) sharing the same narrow, daytime, forest-guaranteed visual
distribution — the projector was never shown genuine Obtain-domain near/far pairs.

This script targets that gap directly: same censored/hinge protocol as
scripts/train_value_projector.py (near = within-episode temporal distance, far =
cross-episode / beyond-k_max / vs-goal), but BOTH pools are Obtain-domain:
  - data/minerl_craft/episodes.npz   : 40 real MineRLObtainIronPickaxe-v0 expert
    demos (84,902 frames) — genuine search+approach+chop trajectories on the actual
    deployment env, not Treechop's forest-guaranteed one.
  - data/minerl_coverage/episodes.npz: attempt #3's ~20 short random-policy
    Obtain-env episodes (8,000 frames) — the "genuinely lost" region.
The goal anchor is also rebuilt from Obtain data: the centroid of "log count
increased" frames from the demos, encoded by ebwm.pt (mirrors
scripts/play_craft.py::build_chop_goal's default branch, but with ebwm.pt as the
encoder instead of craft_wm_v4 — ebwm.pt is the model this projector, and the live
two-brain chop planner, both actually run on).

All the pair-sampling/loss/photometric-augmentation/brightness-check machinery is
IMPORTED from scripts/train_value_projector.py, not reimplemented — only the data
pools and the goal-building function differ (both are otherwise-generic functions
that never assumed Treechop specifically, verified by inspection: PairPool,
sample_near, sample_far_cross, sample_far_beyond, sample_coverage_vs_goal,
encode_flat, compute_brightness_correlation all take arbitrary npz paths and an
arbitrary goal_flat).

A FIXED holdout of 4 coverage chunks (config `data.holdout_coverage_chunks`) is
excluded from BOTH train and val pairs — reserved exclusively for the mandatory
gate-2 check below, so that check is never contaminated by pairs the projector was
actually trained on.

Mandatory gates (refuses to write the checkpoint if either fails, same
refusal-to-save discipline as train_craft_wm_v4.py / train_value_projector.py):
  1. Held-out near/far separation ratio (attempt #7's original check) >= min_separation_ratio.
  2. NEW — Obtain-specific DIRECTION check: on a small hand-labeled set of real
     MineRLObtainIronPickaxeDense cold-start spawn frames (assets/spawn_thumbs/,
     attempt #9) and held-out coverage chunks (the 4 excluded above), does the
     projector predict tree-close frames as NEARER than open/treeless frames — the
     correct direction, which attempt #10 showed ebwm.pt's own raw scoring gets
     backwards? This is the check attempt #7's gate structurally could not run (its
     near/far validation pairs were all same-distribution-as-training).
Brightness confound (reused from train_value_projector.py, attempt #7's own blind
spot) is measured and reported but is NOT a hard gate here (same as attempt #7) —
a large |r| is grounds to call this a NO-GO in the write-up even if the two gates
above pass, per the ColorJitter follow-up's own lesson.

Usage: run.bat scripts/train_value_projector_obtain.py --config configs/train_value_projector_obtain.yaml
"""
import argparse
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import torch
import yaml

from mine_jepa.ebwm.dataset import _load_npz
from mine_jepa.ebwm.value_head import DistanceProjector
from scripts.train_value_projector import (
    PairPool,
    compute_batch_losses,
    compute_brightness_correlation,
    encode_flat,
    load_frozen_model,
    sample_coverage_vs_goal,
    sample_near,
    seed_everything,
)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/train_value_projector_obtain.yaml")
    return p.parse_args()


@torch.no_grad()
def build_obtain_goal_flat(model, demos_path: str, device, log_item: str = "log",
                            min_frames: int = 10) -> tuple[torch.Tensor, int]:
    """
    Centroid of 'log count increased' frames from real Obtain demos, encoded by
    `model` (ebwm.pt, frozen) — the Obtain-domain analog of
    scripts/play_craft.py::build_chop_goal's default branch (which uses the SAME
    inventory-log-gain logic but encodes with craft_wm_v4 instead). Returns
    (goal_flat [1,F], n_frames_used).
    """
    d = _load_npz(demos_path)
    frames, inv, dones = d["frames"], d["inventory"], d["dones"].astype(bool)
    items = [str(x) for x in d["inventory_items"]]
    log_idx = items.index(log_item)
    log = inv[:, log_idx].astype(np.int64)
    inc = np.zeros(len(frames), dtype=bool)
    inc[1:] = (log[1:] > log[:-1]) & (~dones[:-1])
    good = frames[inc]
    if len(good) < min_frames:
        print(f"  WARNING: only {len(good)} log-gain frames — using all {len(frames)} frames")
        good = frames

    lat_sum, n = None, 0
    for i in range(0, len(good), 256):
        obs = torch.from_numpy(good[i:i + 256]).float() / 255.0
        obs = obs.permute(0, 3, 1, 2).unsqueeze(2).to(device)
        lat = model.encode(obs).squeeze(2)                          # [B,D,H',W']
        s = lat.sum(dim=0)
        lat_sum = s if lat_sum is None else lat_sum + s
        n += lat.size(0)
    goal = (lat_sum / n).unsqueeze(0)                                # [1,D,H',W']
    return goal.reshape(1, -1), len(good)


def exclude_coverage_chunks(pool: PairPool, chunk_size: int, holdout_chunks: list[int]) -> int:
    """
    Drops the given coverage-dataset (di==1) chunk indices from pool.episodes IN
    PLACE, so they never enter a training or validation PAIR — reserved exclusively
    for evaluate_obtain_direction's hand-labeled spot-check. Returns the number of
    episode ranges removed (sanity-printed by the caller, not just assumed).
    """
    holdout = set(int(c) for c in holdout_chunks)
    kept, removed = [], 0
    for (di, s, e) in pool.episodes:
        if di == 1 and (s // chunk_size) in holdout:
            removed += 1
            continue
        kept.append((di, s, e))
    pool.episodes[:] = kept
    return removed


@torch.no_grad()
def evaluate_obtain_direction(model, projector, goal_flat, dc_cfg: dict,
                               coverage_frames: np.ndarray, device):
    """
    The gate attempt #7 could not run: on a small, hand-labeled set of REAL
    MineRLObtainIronPickaxeDense frames (independently sourced, never in any
    training pair — spawn thumbnails are live-play captures, coverage chunks are
    the holdout reserved by exclude_coverage_chunks), does the projector score
    tree-close frames as NEARER to the goal than open/treeless frames?

    Labels below were assigned by visually inspecting each PNG referenced (not
    guessed from the numbers) — see the dispatch report for the per-file read.
    Returns (d_tree [n_tree], d_notree [n_notree]) predicted distances.
    """
    thumb_dir = Path(dc_cfg["spawn_thumb_dir"])

    def load_spawn(fname: str) -> np.ndarray:
        return imageio.imread(str(thumb_dir / fname))[:, :, :3]

    tree_frames = [load_spawn(f) for f in dc_cfg["tree_close_files"]]
    notree_frames = [load_spawn(f) for f in dc_cfg["no_tree_files"]]
    tree_frames += [coverage_frames[int(i)] for i in dc_cfg["coverage_tree_close_idx"]]
    notree_frames += [coverage_frames[int(i)] for i in dc_cfg["coverage_no_tree_idx"]]

    z_tree = encode_flat(model, tree_frames, device)
    z_notree = encode_flat(model, notree_frames, device)
    goal = goal_flat[0:1]
    d_tree = projector.dist(z_tree, goal.expand(z_tree.shape[0], -1)).cpu().numpy()
    d_notree = projector.dist(z_notree, goal.expand(z_notree.shape[0], -1)).cpu().numpy()
    return d_tree, d_notree


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    seed = int(cfg.get("seed", 0))
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}  |  seed: {seed}")

    print("\nLoading ebwm.pt (frozen — only DistanceProjector trains)...")
    model = load_frozen_model(cfg, device)
    print(f"  ebwm.pt loaded, requires_grad_(False) verified on all {sum(1 for _ in model.parameters())} params")

    aug_cfg = cfg.get("augmentation")
    cj = (aug_cfg or {}).get("color_jitter", {})
    if cj.get("enabled", False):
        print(f"\nPhotometric augmentation ENABLED (training frames only): "
              f"brightness={cj.get('brightness')} contrast={cj.get('contrast')} "
              f"saturation={cj.get('saturation')} gamma_range={cj.get('gamma_range')}")
    else:
        print("\nPhotometric augmentation disabled (default).")

    d_cfg = cfg["data"]
    k_max = int(d_cfg["k_max"])
    chunk_size = int(d_cfg.get("coverage_chunk_size", 400))
    print(f"\nLoading pair pool: {d_cfg['demos_path']} (Obtain demos) + "
          f"{d_cfg['coverage_path']} (Obtain coverage), K_max={k_max}")
    pool = PairPool(d_cfg["demos_path"], d_cfg["coverage_path"], coverage_chunk_size=chunk_size)

    holdout_chunks = d_cfg.get("holdout_coverage_chunks", [])
    n_removed = exclude_coverage_chunks(pool, chunk_size, holdout_chunks)
    print(f"  Held out {n_removed} coverage chunk(s) {holdout_chunks} from ALL train/val pairs "
          f"(reserved for the direction-check gate below)")

    train_eps, val_eps = pool.split(float(d_cfg.get("val_fraction", 0.1)), seed)
    print(f"  Episodes: train {len(train_eps)}  val {len(val_eps)}")

    print("\nBuilding Obtain-domain chop-goal latent (centroid of ebwm.pt-encoded "
          "'log count increased' frames from real Obtain demos)...")
    goal_cfg = cfg["goal"]
    goal_flat, n_goal_frames = build_obtain_goal_flat(
        model, d_cfg["demos_path"], device,
        log_item=goal_cfg.get("log_item", "log"), min_frames=int(goal_cfg.get("min_frames", 10)),
    )
    print(f"  goal_flat: {tuple(goal_flat.shape)} (from {n_goal_frames} log-gain frames)")

    with torch.no_grad():
        probe = encode_flat(model, [pool.frame(0, 0)], device)
    in_dim = probe.shape[1]
    print(f"\nFlattened latent dim F = {in_dim}")

    proj_cfg = cfg["projector"]
    projector = DistanceProjector(
        in_dim=in_dim, hidden_dim=int(proj_cfg.get("hidden_dim", 256)),
        proj_dim=int(proj_cfg.get("proj_dim", 32)),
    ).to(device)
    n_params = sum(p.numel() for p in projector.parameters())
    print(f"DistanceProjector params: {n_params:,}")

    t_cfg = cfg["training"]
    opt = torch.optim.Adam(projector.parameters(), lr=float(t_cfg["lr"]),
                            weight_decay=float(t_cfg.get("weight_decay", 0.0)))
    epochs = int(t_cfg["epochs"])
    steps_per_epoch = int(t_cfg["steps_per_epoch"])
    bs = int(t_cfg["batch_size"])
    near_w = float(t_cfg.get("near_weight", 1.0))
    far_w = float(t_cfg.get("far_weight", 1.0))
    batch_sizes = {
        "near": bs,
        "far_cross": max(1, bs // 3),
        "far_beyond": max(1, bs // 3),
        "far_coverage": max(1, bs // 3),
    }
    rng = np.random.default_rng(seed)

    print(f"\n{'Epoch':>5}  {'near_loss':>10}  {'far_loss':>9}  "
          f"{'near_pred':>9}  {'near_k':>7}  {'far_pred':>9}")
    for epoch in range(1, epochs + 1):
        projector.train()
        tot_near, tot_far, nb = 0.0, 0.0, 0
        last_stats = {}
        for _ in range(steps_per_epoch):
            near_loss, far_loss, stats = compute_batch_losses(
                model, projector, pool, train_eps, k_max, goal_flat, batch_sizes, rng, device,
                aug_cfg=aug_cfg,
            )
            loss = near_w * near_loss + far_w * far_loss
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot_near += float(near_loss.item())
            tot_far += float(far_loss.item())
            last_stats = stats
            nb += 1
        print(f"{epoch:>5}  {tot_near/nb:>10.4f}  {tot_far/nb:>9.4f}  "
              f"{last_stats['near_mean_pred']:>9.3f}  {last_stats['near_mean_k']:>7.3f}  "
              f"{last_stats['far_mean_pred']:>9.3f}", flush=True)

    # ------------------------------------------------------------------
    # Mandatory offline validation gate #1: held-out near/far separation
    # (attempt #7's original check, unchanged protocol).
    # ------------------------------------------------------------------
    projector.eval()
    val_batches = int(t_cfg.get("val_batches", 20))
    val_near_preds, val_near_ks, val_far_preds = [], [], []
    with torch.no_grad():
        for _ in range(val_batches):
            fa, fb, ks = sample_near(pool, val_eps, bs, min(5, k_max), rng)
            za, zb = encode_flat(model, fa, device), encode_flat(model, fb, device)
            val_near_preds.append(projector.dist(za, zb).cpu())
            val_near_ks.append(torch.from_numpy(ks))

            fa = sample_coverage_vs_goal(pool, bs, rng)
            za = encode_flat(model, fa, device)
            zb = goal_flat[0:1].expand(za.shape[0], -1)
            val_far_preds.append(projector.dist(za, zb).cpu())

    near_preds = torch.cat(val_near_preds)
    near_ks = torch.cat(val_near_ks)
    far_preds = torch.cat(val_far_preds)
    near_mean, near_std = float(near_preds.mean()), float(near_preds.std())
    far_mean, far_std = float(far_preds.mean()), float(far_preds.std())
    sep_ratio = far_mean / max(near_mean, 1e-6)

    print(f"\n{'='*70}")
    print("GATE 1 — OFFLINE NEAR/FAR SEPARATION (held-out Obtain-domain episodes)")
    print(f"  Near pairs (true k<={min(5, k_max)}, n={len(near_preds)}): "
          f"pred_dist mean={near_mean:.3f} std={near_std:.3f}  (true k mean={float(near_ks.mean()):.2f})")
    print(f"  Far/coverage-vs-goal pairs (n={len(far_preds)}): "
          f"pred_dist mean={far_mean:.3f} std={far_std:.3f}")
    print(f"  Separation ratio (far_mean / near_mean): {sep_ratio:.3f}")
    min_sep = float(cfg["checkpoint"].get("min_separation_ratio", 1.3))
    gate1 = sep_ratio >= min_sep and far_mean > near_mean
    print(f"  Gate 1: separation ratio >= {min_sep} required -> {'PASS' if gate1 else 'FAIL'}")

    # ------------------------------------------------------------------
    # Mandatory offline validation gate #2 (NEW, this attempt): does the
    # projector get the DIRECTION right on real Obtain frames specifically?
    # ------------------------------------------------------------------
    dc_cfg = cfg["direction_check"]
    coverage_frames = _load_npz(d_cfg["coverage_path"])["frames"]
    d_tree, d_notree = evaluate_obtain_direction(model, projector, goal_flat, dc_cfg, coverage_frames, device)
    tree_mean, notree_mean = float(d_tree.mean()), float(d_notree.mean())
    direction_ratio = notree_mean / max(tree_mean, 1e-6)
    n_correct_pairs = int(sum(1 for dt in d_tree for dn in d_notree if dt < dn))
    n_pairs = len(d_tree) * len(d_notree)

    print(f"\n{'='*70}")
    print("GATE 2 — OBTAIN-SPECIFIC DIRECTION CHECK (hand-labeled, held-out real frames)")
    print(f"  Tree-close frames  (n={len(d_tree)}): pred_dist = "
          f"{np.array2string(d_tree, precision=3)}  mean={tree_mean:.3f}")
    print(f"  No-tree/open frames (n={len(d_notree)}): pred_dist = "
          f"{np.array2string(d_notree, precision=3)}  mean={notree_mean:.3f}")
    print(f"  Direction ratio (no_tree_mean / tree_mean): {direction_ratio:.3f} "
          f"(>1 = correct direction, tree scores nearer)")
    print(f"  Pairwise correct-direction rate: {n_correct_pairs}/{n_pairs} "
          f"({100.0 * n_correct_pairs / n_pairs:.1f}%)")
    min_dir = float(cfg["checkpoint"].get("min_direction_ratio", 1.1))
    gate2 = direction_ratio >= min_dir and tree_mean < notree_mean
    print(f"  Gate 2: direction ratio >= {min_dir} required -> {'PASS' if gate2 else 'FAIL'}")

    # ------------------------------------------------------------------
    # Brightness confound check (reused verbatim from train_value_projector.py /
    # the ColorJitter follow-up) — measured and reported, not a hard gate here,
    # same as attempt #7's own script, but never skipped (attempt #7's blind spot).
    # ------------------------------------------------------------------
    n_bright = int(t_cfg.get("brightness_corr_samples", 500))
    bright_r, n_bright_used = compute_brightness_correlation(
        model, projector, pool, val_eps, goal_flat, device, n_bright, rng,
    )
    print(f"\n{'='*70}")
    print("BRIGHTNESS CONFOUND CHECK (held-out, UNAUGMENTED)")
    print(f"  pred dist-to-goal vs. mean pixel brightness, n={n_bright_used}: r={bright_r:.4f}")
    print(f"  (attempt #7 baseline, live-play metric: r=-0.57; attempt #7 offline: "
          f"r=0.117; ColorJitter-augmented offline: r=0.498)")
    print(f"{'='*70}")

    if not (gate1 and gate2):
        print("\nVALIDATION FAILED: gate 1 (separation) and/or gate 2 (Obtain direction) "
              "did not pass. Refusing to write the checkpoint (anti-collapse-style "
              "guardrail, same discipline as train_craft_wm_v4.py's refusal-to-save). "
              "Do NOT proceed to a live MineRL run with this metric.")
        return

    ckpt_dir = Path(cfg["checkpoint"]["dir"])
    ckpt_dir.mkdir(exist_ok=True)
    ckpt_path = ckpt_dir / cfg["checkpoint"]["name"]
    projector.save(str(ckpt_path))
    print(f"\nBoth gates passed (sep_ratio={sep_ratio:.3f}, direction_ratio={direction_ratio:.3f}) "
          f"-> checkpoint saved: {ckpt_path}")


if __name__ == "__main__":
    main()

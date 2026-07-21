"""
Cold-start attempt #7 (docs/10_coldstart_engineering.md, arXiv:2601.00844) — train
a DistanceProjector so Euclidean distance in a projected space approximates the true
action-count-to-goal, instead of using ebwm.pt's raw-latent squared-L2 (attempts
#1-#6 all worked around that raw distance going flat with no tree in view, never
retrained it).

ebwm.pt is loaded FROZEN (requires_grad_(False), eval()) — only DistanceProjector's
parameters ever receive a gradient. Training data = Treechop demos (the same
data/minerl_goal/episodes.npz ebwm.pt itself trained on) PLUS the coverage episodes
gathered for cold-start attempt #3 (data/minerl_coverage/episodes.npz) — random-spawn,
often-treeless frames that anchor the metric's behaviour in the "genuinely lost"
region Treechop demos barely contain.

Targets (censored/capped regression):
  - near pairs   (x_t, x_{t+k}), k in [1, K_max], same episode: MSE(pred_dist, k)
  - far pairs    cross-episode / within-episode beyond K_max / coverage-vs-chop-goal:
                 only a LOWER BOUND (>= K_max) is known -> one-sided hinge,
                 loss = max(0, K_max - pred_dist)^2 (never penalises "too far").

Mandatory validation (run before ANY live MineRL time, same discipline as
smoke_test_rnd.py): on held-out episodes, compare predicted distance for near pairs
(small true k) vs far/coverage pairs. Refuse to write checkpoints/value_projector.pt
if the separation isn't clear (mirrors train_craft_wm_v4.py's collapse-refusal gate).

Usage: run.bat scripts/train_value_projector.py --config configs/train_value_projector.yaml
"""
import argparse
import random
from pathlib import Path

import numpy as np
import torch
import yaml

from mine_jepa.ebwm import build_ac_jepa
from mine_jepa.ebwm.dataset import _load_npz
from mine_jepa.ebwm.value_head import DistanceProjector


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/train_value_projector.yaml")
    return p.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def episode_ranges(dones: np.ndarray, chunk_size: int | None = None) -> list[tuple[int, int]]:
    """
    [start, end) index ranges, one per episode, split at dones==True.

    Fallback: if `dones` is entirely False and `chunk_size` is given, segment into
    fixed-length chunks instead. This covers a real bug found while building this
    script: scripts/collect_minerl_multi.py's merge_shards() concatenates per-episode
    shards WITHOUT forcing a done=True at each shard boundary (the exact same class of
    bug scripts/merge_craft_coverage.py explicitly patches at the demos/coverage
    junction, `dones[n_demo-1] = True`) — data/minerl_coverage/episodes.npz's dones
    array is all-False, so without this fallback its 8000 frames would be treated as
    ONE 8000-step episode instead of the ~20 independent 400-step random-spawn
    episodes it actually is, letting near-pair sampling falsely bridge two unrelated
    spawns as a small-k pair.
    """
    if chunk_size and not dones.any():
        n = len(dones)
        return [(s, min(s + chunk_size, n)) for s in range(0, n, chunk_size)]
    idx = np.where(dones)[0]
    starts = np.concatenate(([0], idx + 1))
    ends = np.concatenate((idx + 1, [len(dones)]))
    return [(int(s), int(e)) for s, e in zip(starts, ends) if e > s]


class PairPool:
    """
    Frame pools from Treechop demos + coverage episodes, tagged by dataset so
    frames are always fetched from the correct source array.

    self.episodes: list of (dataset_idx, start, end) — index ranges into
    self.datasets[dataset_idx]["frames"].
    """

    def __init__(self, treechop_path: str, coverage_path: str, coverage_chunk_size: int = 400):
        self.datasets = [_load_npz(treechop_path), _load_npz(coverage_path)]
        self.episodes = []
        for di, d in enumerate(self.datasets):
            # chunk_size fallback only matters for the coverage dataset (di==1) —
            # see episode_ranges() docstring for the shard-merge bug it works around.
            chunk = coverage_chunk_size if di == 1 else None
            for s, e in episode_ranges(d["dones"].astype(bool), chunk_size=chunk):
                self.episodes.append((di, s, e))
        n_frames = [len(d["frames"]) for d in self.datasets]
        print(f"  PairPool: treechop {n_frames[0]:,} frames "
              f"({sum(1 for e in self.episodes if e[0] == 0)} episodes), "
              f"coverage {n_frames[1]:,} frames "
              f"({sum(1 for e in self.episodes if e[0] == 1)} episodes)")

    def frame(self, di: int, idx: int) -> np.ndarray:
        return self.datasets[di]["frames"][idx]

    def coverage_frame(self, idx: int) -> np.ndarray:
        return self.datasets[1]["frames"][idx]

    def n_coverage_frames(self) -> int:
        return len(self.datasets[1]["frames"])

    def split(self, val_fraction: float, seed: int) -> tuple[list, list]:
        """Split self.episodes into train/val by EPISODE (no frame leakage)."""
        eps = list(self.episodes)
        rng = np.random.RandomState(seed)
        rng.shuffle(eps)
        n_val = max(1, int(len(eps) * val_fraction))
        return eps[n_val:], eps[:n_val]


def sample_near(pool: PairPool, episodes: list, batch_size: int, k_max: int,
                 rng: np.random.Generator):
    eligible = [e for e in episodes if e[2] - e[1] >= 2]
    frames_a, frames_b, ks = [], [], []
    for _ in range(batch_size):
        di, s, e = eligible[rng.integers(len(eligible))]
        t = int(rng.integers(s, e - 1))
        k_local = min(k_max, e - 1 - t)
        k = int(rng.integers(1, k_local + 1))
        frames_a.append(pool.frame(di, t))
        frames_b.append(pool.frame(di, t + k))
        ks.append(k)
    return frames_a, frames_b, np.array(ks, dtype=np.float32)


def sample_far_cross(pool: PairPool, episodes: list, batch_size: int,
                      rng: np.random.Generator):
    frames_a, frames_b = [], []
    n = len(episodes)
    for _ in range(batch_size):
        i1, i2 = rng.integers(n), rng.integers(n)
        while i2 == i1:
            i2 = int(rng.integers(n))
        d1, s1, e1 = episodes[i1]
        d2, s2, e2 = episodes[i2]
        t1 = int(rng.integers(s1, e1))
        t2 = int(rng.integers(s2, e2))
        frames_a.append(pool.frame(d1, t1))
        frames_b.append(pool.frame(d2, t2))
    return frames_a, frames_b


def sample_far_beyond(pool: PairPool, episodes: list, batch_size: int, k_max: int,
                       rng: np.random.Generator):
    eligible = [e for e in episodes if e[2] - e[1] > k_max + 1]
    frames_a, frames_b = [], []
    for _ in range(batch_size):
        di, s, e = eligible[rng.integers(len(eligible))]
        max_t = e - 2 - k_max
        t = int(rng.integers(s, max_t + 1))
        t2 = int(rng.integers(t + k_max + 1, e))
        frames_a.append(pool.frame(di, t))
        frames_b.append(pool.frame(di, t2))
    return frames_a, frames_b


def sample_coverage_vs_goal(pool: PairPool, batch_size: int, rng: np.random.Generator):
    n = pool.n_coverage_frames()
    idx = rng.integers(0, n, size=batch_size)
    return [pool.coverage_frame(int(i)) for i in idx]


def frames_to_tensor(frames: list, device) -> torch.Tensor:
    """list of [H,W,3] uint8 -> [B,3,1,64,64] float [0,1]."""
    arr = np.stack(frames, axis=0)                             # [B,H,W,3]
    t = torch.from_numpy(arr).float() / 255.0
    return t.permute(0, 3, 1, 2).unsqueeze(2).to(device)        # [B,3,1,64,64]


def photometric_augment(x: torch.Tensor, aug_cfg: dict, rng: np.random.Generator) -> torch.Tensor:
    """
    Aggressive per-sample brightness/contrast/saturation/gamma jitter, applied to
    raw [B,3,T,H,W] float [0,1] frames BEFORE the frozen encoder — training-time
    only (see encode_flat's `aug_cfg` argument; validation and the goal-centroid
    build always pass aug_cfg=None so the mandatory gate still measures real,
    unmodified-frame behaviour).

    Custom implementation rather than torchvision.transforms.ColorJitter: each of
    the B*T frames in the batch draws its OWN random factors (ColorJitter's default
    __call__ draws one shared factor per call), so a single training batch spans a
    wide mix of lighting conditions rather than being uniformly re-lit. Targets
    cold-start attempt #7's finding that the projector shortcuts on scene
    brightness (day vs. dusk/night) instead of tree-proximity, by making that
    shortcut unusable — it must vary near/far pairs that share a brightness level
    and share brightness across frames at different true distances.
    """
    cj = aug_cfg.get("color_jitter", {}) if aug_cfg else {}
    if not cj.get("enabled", False):
        return x
    b, c, t, h, w = x.shape
    device = x.device
    n = b * t
    flat = x.permute(0, 2, 1, 3, 4).reshape(n, c, h, w)  # [B*T,3,H,W]

    def jitter(strength: float) -> torch.Tensor:
        lo, hi = 1.0 - strength, 1.0 + strength
        return torch.from_numpy(rng.uniform(lo, hi, size=n).astype(np.float32)).to(device)

    brightness = jitter(float(cj.get("brightness", 0.0))).view(n, 1, 1, 1)
    contrast = jitter(float(cj.get("contrast", 0.0))).view(n, 1, 1, 1)
    saturation = jitter(float(cj.get("saturation", 0.0))).view(n, 1, 1, 1)
    g_lo, g_hi = cj.get("gamma_range", [1.0, 1.0])
    gamma = torch.from_numpy(
        rng.uniform(float(g_lo), float(g_hi), size=n).astype(np.float32)
    ).to(device).view(n, 1, 1, 1)

    flat = (flat * brightness).clamp(0.0, 1.0)

    gray = flat.mean(dim=1, keepdim=True)                       # [n,1,h,w]
    img_mean = gray.mean(dim=(2, 3), keepdim=True)               # [n,1,1,1]
    flat = ((flat - img_mean) * contrast + img_mean).clamp(0.0, 1.0)

    gray = flat.mean(dim=1, keepdim=True)
    flat = (gray + (flat - gray) * saturation).clamp(0.0, 1.0)

    flat = flat.clamp(min=1e-4).pow(gamma).clamp(0.0, 1.0)

    return flat.reshape(b, t, c, h, w).permute(0, 2, 1, 3, 4)


@torch.no_grad()
def encode_flat(model, frames: list, device, aug_cfg: dict | None = None,
                 rng: np.random.Generator | None = None) -> torch.Tensor:
    obs = frames_to_tensor(frames, device)
    if aug_cfg is not None:
        obs = photometric_augment(obs, aug_cfg, rng)
    z = model.encode(obs).squeeze(2)                            # [B,D,H',W']
    return z.reshape(z.shape[0], -1)                             # [B,F]


def load_frozen_model(cfg: dict, device) -> torch.nn.Module:
    """Load ebwm.pt frozen (shared by main() and scripts/eval_distance_brightness_correlation.py
    so both ever load the checkpoint the same way)."""
    ckpt = torch.load(cfg["model"]["ebwm_checkpoint"], map_location=device, weights_only=False)
    m, r = ckpt["cfg"]["model"], ckpt["cfg"]["regularizer"]
    model = build_ac_jepa(
        embed_dim=m["embed_dim"], encoder_hidden=m["encoder_hidden"],
        n_actions=m["n_actions"], action_embed_dim=m["action_embed_dim"],
        predictor_hidden=m["predictor_hidden"],
        std_coeff=r["std_coeff"], cov_coeff=r["cov_coeff"], sim_coeff_t=r["sim_coeff_t"],
    ).to(device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    model.requires_grad_(False)
    for p in model.parameters():
        assert not p.requires_grad
    return model


def sample_flat_frames(pool: "PairPool", episodes: list, n: int,
                        rng: np.random.Generator) -> list:
    """n single frames drawn uniformly from the given episode ranges (for the
    brightness-confound check, not for near/far pair losses)."""
    frames = []
    for _ in range(n):
        di, s, e = episodes[rng.integers(len(episodes))]
        t = int(rng.integers(s, e))
        frames.append(pool.frame(di, t))
    return frames


def brightness_of(frames: list) -> np.ndarray:
    """Mean pixel intensity in [0,1] per frame, [H,W,3] uint8 -> scalar."""
    return np.array([f.astype(np.float32).mean() / 255.0 for f in frames], dtype=np.float32)


@torch.no_grad()
def compute_brightness_correlation(model, projector, pool, episodes, goal_flat, device,
                                    n_samples: int, rng: np.random.Generator) -> tuple[float, int]:
    """
    Offline analog of cold-start attempt #7's live brightness-confound finding
    (goal_score_std correlated with scene brightness at r=-0.57 during play, rather
    than tree-proximity). Here: predicted distance-to-goal for n_samples held-out
    single frames vs. each frame's mean pixel brightness, Pearson r. Always
    UNAUGMENTED (encode_flat's aug_cfg left at its default None) — this measures the
    model's real deployed behaviour, matching the validation gate's discipline.
    """
    frames = sample_flat_frames(pool, episodes, n_samples, rng)
    z = encode_flat(model, frames, device)
    dist = projector.dist(z, goal_flat[0:1].expand(z.shape[0], -1)).cpu().numpy()
    bright = brightness_of(frames)
    r = float(np.corrcoef(dist, bright)[0, 1])
    return r, len(frames)


@torch.no_grad()
def build_chop_goal_flat(model, goal_cfg: dict, device) -> torch.Tensor:
    """
    Exact same construction as scripts/play_ebwm.py::build_goal_latents (centroid
    of reward>=threshold frames), reused rather than reimplemented so the eventual
    live eval is apples-to-apples with what the two-brain planner uses at play time.
    """
    from scripts.play_ebwm import build_goal_latents
    goals = build_goal_latents(model, {"goal": goal_cfg}, device)   # [K,D,H',W']
    return goals.reshape(goals.shape[0], -1)                        # [K,F]


def compute_batch_losses(model, projector, pool, episodes, k_max, goal_flat,
                          batch_sizes, rng, device, aug_cfg: dict | None = None):
    """One step's worth of near + far losses. Returns (near_loss, far_loss, stats dict).

    `aug_cfg` is only ever passed at training time (see main()); the mandatory
    validation gate below always calls encode_flat with aug_cfg=None so it measures
    the model's behaviour on real, unmodified frames.
    """
    fa, fb, ks = sample_near(pool, episodes, batch_sizes["near"], k_max, rng)
    za, zb = encode_flat(model, fa, device, aug_cfg, rng), encode_flat(model, fb, device, aug_cfg, rng)
    pred_near = projector.dist(za, zb)
    target_near = torch.from_numpy(ks).to(device)
    near_loss = ((pred_near - target_near) ** 2).mean()

    far_preds = []

    fa, fb = sample_far_cross(pool, episodes, batch_sizes["far_cross"], rng)
    za, zb = encode_flat(model, fa, device, aug_cfg, rng), encode_flat(model, fb, device, aug_cfg, rng)
    far_preds.append(projector.dist(za, zb))

    fa, fb = sample_far_beyond(pool, episodes, batch_sizes["far_beyond"], k_max, rng)
    za, zb = encode_flat(model, fa, device, aug_cfg, rng), encode_flat(model, fb, device, aug_cfg, rng)
    far_preds.append(projector.dist(za, zb))

    fa = sample_coverage_vs_goal(pool, batch_sizes["far_coverage"], rng)
    za = encode_flat(model, fa, device, aug_cfg, rng)
    zb = goal_flat[0:1].expand(za.shape[0], -1)   # goal centroid stays the canonical, unaugmented anchor
    far_preds.append(projector.dist(za, zb))

    pred_far = torch.cat(far_preds, dim=0)
    far_loss = torch.clamp(k_max - pred_far, min=0.0).pow(2).mean()

    stats = {
        "near_mean_pred": float(pred_near.mean().item()),
        "near_mean_k": float(target_near.mean().item()),
        "far_mean_pred": float(pred_far.mean().item()),
    }
    return near_loss, far_loss, stats


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    seed = int(cfg.get("seed", 42))
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
        print("\nPhotometric augmentation disabled (default — bit-for-bit attempt #7 behaviour).")

    d_cfg = cfg["data"]
    k_max = int(d_cfg["k_max"])
    print(f"\nLoading pair pool: {d_cfg['treechop_path']} + {d_cfg['coverage_path']} (K_max={k_max})")
    pool = PairPool(d_cfg["treechop_path"], d_cfg["coverage_path"],
                     coverage_chunk_size=int(d_cfg.get("coverage_chunk_size", 400)))
    train_eps, val_eps = pool.split(float(d_cfg.get("val_fraction", 0.1)), seed)
    print(f"  Episodes: train {len(train_eps)}  val {len(val_eps)}")

    print("\nBuilding chop-goal latent (Treechop reward-frame centroid, "
          "same construction as scripts/play_ebwm.py::build_goal_latents)...")
    goal_flat = build_chop_goal_flat(model, cfg["goal"], device)
    print(f"  goal_flat: {tuple(goal_flat.shape)}")

    with torch.no_grad():
        probe = encode_flat(model, [pool.frame(0, 0)], device)
    in_dim = probe.shape[1]
    print(f"\nFlattened latent dim F = {in_dim} (D*H'*W' of ebwm.pt's encode() output)")

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
    # Mandatory offline validation (docs/10 attempt #7 gate) — held-out episodes,
    # NEVER seen during training. Must show real near/far separation before ANY
    # live MineRL time is spent, mirroring smoke_test_rnd.py's discipline.
    # ------------------------------------------------------------------
    projector.eval()
    val_batches = int(t_cfg.get("val_batches", 20))
    val_near_preds, val_near_ks, val_far_preds = [], [], []
    with torch.no_grad():
        for _ in range(val_batches):
            fa, fb, ks = sample_near(pool, val_eps, bs, min(5, k_max), rng)  # SMALL true k
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

    print(f"\n{'='*60}")
    print("OFFLINE VALIDATION (held-out episodes, mandatory gate)")
    print(f"  Near pairs (true k<={min(5, k_max)}, n={len(near_preds)}): "
          f"pred_dist mean={near_mean:.3f} std={near_std:.3f}  (true k mean={float(near_ks.mean()):.2f})")
    print(f"  Far/coverage-vs-goal pairs (n={len(far_preds)}): "
          f"pred_dist mean={far_mean:.3f} std={far_std:.3f}")
    print(f"  Separation ratio (far_mean / near_mean): {sep_ratio:.3f}")

    n_bright = int(t_cfg.get("brightness_corr_samples", 500))
    bright_r, n_bright_used = compute_brightness_correlation(
        model, projector, pool, val_eps, goal_flat, device, n_bright, rng,
    )
    print(f"  Brightness confound check (pred dist-to-goal vs. mean pixel brightness, "
          f"held-out, UNAUGMENTED, n={n_bright_used}): r={bright_r:.4f} "
          f"(attempt #7 baseline, live-play metric: r=-0.57)")

    min_sep = float(cfg["checkpoint"].get("min_separation_ratio", 1.3))
    discriminates = sep_ratio >= min_sep and far_mean > near_mean
    print(f"  Gate: separation ratio {'>=':<3} {min_sep} required -> "
          f"{'PASS' if discriminates else 'FAIL'}")
    print(f"{'='*60}")

    if not discriminates:
        print("\nVALIDATION FAILED: the projector does not clearly discriminate "
              "near-goal frames from far/lost frames on held-out data. Refusing to "
              "write checkpoints/value_projector.pt (anti-collapse-style guardrail — "
              "same discipline as train_craft_wm_v4.py's refusal-to-save). "
              "Do NOT proceed to a live MineRL run with this metric.")
        return

    ckpt_dir = Path(cfg["checkpoint"]["dir"])
    ckpt_dir.mkdir(exist_ok=True)
    ckpt_path = ckpt_dir / cfg["checkpoint"]["name"]
    projector.save(str(ckpt_path))
    print(f"\nValidation passed (ratio {sep_ratio:.3f} >= {min_sep}) -> checkpoint saved: {ckpt_path}")


if __name__ == "__main__":
    main()

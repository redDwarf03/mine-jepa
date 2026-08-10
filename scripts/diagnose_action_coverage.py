"""
Cold-start attempt #18, Diagnostic 2 of 2 (docs/10_coldstart_engineering.md) —
offline action-coverage / distribution-shift check between ebwm.pt's Treechop
training data and the Obtain-domain data the cold-start campaign has been
testing it against.

Motivation: every attempt since #10 (which confirmed ebwm.pt's own
goal-centroid score REVERSES direction on MineRLObtainIronPickaxeDense) has
assumed a purely photometric cause -- 6 independent mechanisms (attempts #7,
#11, #14 Phase1/Phase2, #15, #17) all converged on a brightness/scene-
composition confound in the frozen visual encoder. None of them examined the
ACTION side. Zhang, Guan, Zhang, Zhang, Li, "On the Identifiability of
Controlled World Models" (arXiv:2607.22430, docs/references/index.md) proves
that an action-conditioned JEPA -- ebwm.pt's exact architecture family --
only recovers a reliable state/dynamics model when the training data's action
distribution has adequate coverage/variation. This script tests whether
ebwm.pt's Treechop training data actually covers the action distribution the
Obtain domain exercises.

Method, no training, no GPU strictly required (action-array statistics only),
no checkpoint modified (ebwm.pt loaded read-only, cpu, only to read
cfg["model"]["n_actions"]):

  Metric 1 -- out-of-vocabulary (OOV) fraction: of all Obtain-domain action
    instances (data/minerl_craft + data/minerl_coverage, pooled without
    oversampling), what fraction have an action index >= ebwm.pt's trained
    action-vocabulary size (its action-embedding table has exactly this many
    rows; any index at or above it was never seen as a training example and
    has an arbitrary, unconditioned embedding).

  Metric 2 -- distributional overlap on the SHARED action indices (the ones
    both domains can express): Jensen-Shannon divergence (base-2, bounded
    [0, 1], symmetric) between the normalized action-usage histograms of
    Treechop vs. pooled Obtain, restricted to indices < the trained
    vocabulary size.

  Self-calibration (this campaign's convention since attempt #13's detector
    calibration and attempt #16's tie-break-bug fix -- never invent a pass bar
    from nothing): the SAME JSD computed between two random, disjoint,
    episode-level halves of Treechop's OWN data (seeded split) as a "no real
    difference" null baseline. Treechop-vs-Obtain JSD is compared against this
    null, not against an arbitrary threshold.

Usage: run.bat scripts/diagnose_action_coverage.py --config configs/diagnose_action_coverage.yaml
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
import yaml

from mine_jepa.ebwm.dataset import _load_npz


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/diagnose_action_coverage.yaml")
    return p.parse_args()


def seed_everything(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)


def load_trained_n_actions(checkpoint_path: str) -> int:
    """ebwm.pt's action-embedding table size (rows never sampled during
    training still exist but were never gradient-updated by a real
    transition) -- read-only cpu load, cfg dict only, no forward pass."""
    ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    return int(ckpt["cfg"]["model"]["n_actions"])


def load_actions_dones(data_path: str) -> tuple[np.ndarray, np.ndarray]:
    d = _load_npz(data_path)
    return d["actions"].astype(np.int64), d["dones"].astype(bool)


def episode_ranges(dones: np.ndarray) -> list[tuple[int, int]]:
    """[start, end] inclusive index ranges, one per episode, split on
    done=True (does not assume a done marks every episode's true end --
    the final range, if the array doesn't end on a done, is kept as a
    possibly-truncated episode rather than dropped)."""
    ranges, start = [], 0
    for i, done in enumerate(dones):
        if done:
            ranges.append((start, i))
            start = i + 1
    if start < len(dones):
        ranges.append((start, len(dones) - 1))
    return ranges


def split_by_episode_half(actions: np.ndarray, dones: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray, int]:
    """Randomly assigns whole episodes (never split mid-episode) to two
    disjoint halves -- the null-baseline comparison for Metric 2's JSD."""
    ranges = episode_ranges(dones)
    rng = np.random.RandomState(seed)
    order = rng.permutation(len(ranges))
    half = len(ranges) // 2
    a_ranges = [ranges[i] for i in order[:half]]
    b_ranges = [ranges[i] for i in order[half:]]
    a = np.concatenate([actions[s:e + 1] for s, e in a_ranges])
    b = np.concatenate([actions[s:e + 1] for s, e in b_ranges])
    return a, b, len(ranges)


def action_histogram(actions: np.ndarray, indices: list[int]) -> np.ndarray:
    """Normalized frequency per action index, restricted to `indices` -- any
    action outside `indices` (e.g. an out-of-vocabulary craft action) simply
    doesn't contribute to the count or the normalizing total."""
    counts = np.array([np.sum(actions == i) for i in indices], dtype=np.float64)
    total = counts.sum()
    return counts / total if total > 0 else counts


def jensen_shannon_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """Base-2 JSD in [0, 1]. Uses scipy if available (jensenshannon returns
    sqrt(JSD) by default, squared back here), else a direct implementation
    of JSD = 0.5*KL(P||M) + 0.5*KL(Q||M), M=(P+Q)/2."""
    p = p / p.sum()
    q = q / q.sum()
    try:
        from scipy.spatial.distance import jensenshannon
        return float(jensenshannon(p, q, base=2) ** 2)
    except ImportError:
        m = 0.5 * (p + q)

        def kl(a: np.ndarray, b: np.ndarray) -> float:
            mask = a > 0
            return float(np.sum(a[mask] * np.log2(a[mask] / b[mask])))

        return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def print_hist(title: str, hist: np.ndarray) -> None:
    parts = " ".join(f"a{i}={v * 100:4.1f}%" for i, v in enumerate(hist) if v > 0.005)
    print(f"  {title:<28} {parts}")


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    seed = int(cfg.get("seed", 0))
    seed_everything(seed)
    print(f"Seed: {seed}")

    print("\nLoading ebwm.pt's cfg (read-only cpu, no forward pass)...")
    n_trained = load_trained_n_actions(cfg["model"]["checkpoint"])
    print(f"  ebwm.pt action-embedding table size (trained vocabulary): {n_trained}")

    treechop_cfg_actions = int(yaml.safe_load(open("configs/minerl_actions.yaml"))["n_actions"])
    obtain_cfg_actions = int(yaml.safe_load(open("configs/minerl_actions_obtain.yaml"))["n_actions"])
    print(f"  Cross-check: configs/minerl_actions.yaml n_actions={treechop_cfg_actions} "
          f"(should match ebwm.pt), configs/minerl_actions_obtain.yaml n_actions={obtain_cfg_actions} "
          f"(the full Obtain action space it's a subset of)")
    assert treechop_cfg_actions == n_trained, "ebwm.pt's action table size no longer matches its action config"

    print(f"\nLoading actions...")
    actions_tc, dones_tc = load_actions_dones(cfg["treechop"]["data_path"])
    actions_craft, dones_craft = load_actions_dones(cfg["obtain"]["craft_data_path"])
    actions_cov, dones_cov = load_actions_dones(cfg["obtain"]["coverage_data_path"])
    print(f"  Treechop  ({cfg['treechop']['data_path']}): {len(actions_tc)} transitions, "
          f"{dones_tc.sum()} episodes, action range [{actions_tc.min()}, {actions_tc.max()}]")
    print(f"  Craft     ({cfg['obtain']['craft_data_path']}): {len(actions_craft)} transitions, "
          f"{dones_craft.sum()} episodes, action range [{actions_craft.min()}, {actions_craft.max()}]")
    print(f"  Coverage  ({cfg['obtain']['coverage_data_path']}): {len(actions_cov)} transitions, "
          f"{dones_cov.sum()} episodes (0 is expected -- attempt #3's coverage collection "
          f"does not mark done boundaries), action range [{actions_cov.min()}, {actions_cov.max()}]")

    actions_obtain = np.concatenate([actions_craft, actions_cov])
    print(f"  Pooled Obtain (craft + coverage, no oversampling): {len(actions_obtain)} transitions")

    print(f"\n{'=' * 78}\nMETRIC 1 -- OUT-OF-VOCABULARY FRACTION\n{'=' * 78}")
    oov_mask = actions_obtain >= n_trained
    oov_craft_mask = actions_craft >= n_trained
    oov_cov_mask = actions_cov >= n_trained
    oov_frac = float(oov_mask.mean())
    print(f"  ebwm.pt trained vocabulary: indices [0, {n_trained - 1}]  "
          f"(Obtain's full action space goes up to {obtain_cfg_actions - 1})")
    print(f"  Craft-only OOV fraction    : {oov_craft_mask.mean() * 100:.2f}% "
          f"({oov_craft_mask.sum()}/{len(actions_craft)})")
    print(f"  Coverage-only OOV fraction : {oov_cov_mask.mean() * 100:.2f}% "
          f"({oov_cov_mask.sum()}/{len(actions_cov)})")
    print(f"  Pooled Obtain OOV fraction : {oov_frac * 100:.2f}% "
          f"({int(oov_mask.sum())}/{len(actions_obtain)} transitions use an action index "
          f"ebwm.pt's action embedding was never trained on)")

    shared = list(range(n_trained))
    hist_tc = action_histogram(actions_tc, shared)
    hist_obtain_shared = action_histogram(actions_obtain, shared)
    hist_craft_shared = action_histogram(actions_craft, shared)
    hist_cov_shared = action_histogram(actions_cov, shared)

    print(f"\n{'=' * 78}\nMETRIC 2 -- DISTRIBUTIONAL OVERLAP ON SHARED INDICES "
          f"[0, {n_trained - 1}]\n{'=' * 78}")
    print_hist("Treechop", hist_tc)
    print_hist("Obtain (craft+coverage)", hist_obtain_shared)
    print_hist("  Obtain/craft only", hist_craft_shared)
    print_hist("  Obtain/coverage only", hist_cov_shared)

    jsd_obtain = jensen_shannon_divergence(hist_tc, hist_obtain_shared)
    jsd_craft = jensen_shannon_divergence(hist_tc, hist_craft_shared)
    jsd_cov = jensen_shannon_divergence(hist_tc, hist_cov_shared)
    print(f"\n  JSD(Treechop, pooled Obtain)   = {jsd_obtain:.4f}")
    print(f"  JSD(Treechop, craft only)      = {jsd_craft:.4f}")
    print(f"  JSD(Treechop, coverage only)   = {jsd_cov:.4f}")

    print(f"\n{'=' * 78}\nSELF-CALIBRATION -- Treechop-vs-Treechop split-half null baseline\n{'=' * 78}")
    half_a, half_b, n_ep = split_by_episode_half(actions_tc, dones_tc, seed)
    print(f"  {n_ep} Treechop episodes split into two disjoint random halves "
          f"(seed={seed}): {len(half_a)} vs {len(half_b)} transitions")
    hist_a = action_histogram(half_a, shared)
    hist_b = action_histogram(half_b, shared)
    jsd_null = jensen_shannon_divergence(hist_a, hist_b)
    print(f"  JSD(Treechop half A, Treechop half B) = {jsd_null:.4f}  (null: no real "
          f"distributional difference, same underlying policy/data source)")

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}")
    ratio = jsd_obtain / max(jsd_null, 1e-9)
    print(f"  JSD(Treechop, Obtain) = {jsd_obtain:.4f}")
    print(f"  JSD(null split-half)  = {jsd_null:.4f}")
    print(f"  Ratio                 = {ratio:.1f}x")
    # Reasoning, not an arbitrary bar: the null baseline is itself sampling
    # noise from splitting ONE homogeneous source in half -- any real,
    # reproducible domain difference should clear it by a wide, not marginal,
    # margin (this campaign's convention, e.g. attempt #17's OOD gate used
    # 1.2-1.3x bars for effects with a much noisier per-frame signal; a clean
    # aggregate action-histogram comparison should show a starker gap if the
    # gap is real, not an artifact of splitting).
    if jsd_null < 1e-4:
        print("  Null baseline is numerically ~0 (Treechop's own two halves have "
              "an essentially identical action distribution) -- ANY non-trivial "
              f"JSD(Treechop, Obtain) is then meaningful on its own; observed "
              f"{jsd_obtain:.4f} vs ~0 supports a REAL action-distribution shift.")
    elif ratio >= 5.0:
        print(f"  {ratio:.1f}x the null -- a wide margin, supports a REAL action-coverage/"
              f"distribution gap between Treechop and Obtain, not sampling noise.")
    elif ratio >= 2.0:
        print(f"  {ratio:.1f}x the null -- a real but moderate gap; some support for an "
              f"action-distribution shift, weaker than the campaign's other 5-10x-plus signals.")
    else:
        print(f"  {ratio:.1f}x the null -- comparable to within-Treechop sampling variation; "
              f"the action distributions are NOT meaningfully different at this resolution, "
              f"this alternative explanation gets no support from Metric 2.")

    out_dir = Path(cfg["output"]["dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / cfg["output"]["json_name"]
    summary = {
        "seed": seed,
        "n_actions_trained": n_trained,
        "n_actions_obtain_full": obtain_cfg_actions,
        "n_transitions": {
            "treechop": int(len(actions_tc)), "craft": int(len(actions_craft)),
            "coverage": int(len(actions_cov)), "obtain_pooled": int(len(actions_obtain)),
        },
        "n_episodes": {
            "treechop": int(dones_tc.sum()), "craft": int(dones_craft.sum()),
            "coverage": int(dones_cov.sum()),
        },
        "oov_fraction": {
            "craft": float(oov_craft_mask.mean()), "coverage": float(oov_cov_mask.mean()),
            "pooled_obtain": oov_frac,
        },
        "shared_indices": shared,
        "histograms": {
            "treechop": hist_tc.tolist(), "obtain_pooled": hist_obtain_shared.tolist(),
            "craft_only": hist_craft_shared.tolist(), "coverage_only": hist_cov_shared.tolist(),
            "treechop_half_a": hist_a.tolist(), "treechop_half_b": hist_b.tolist(),
        },
        "jsd": {
            "treechop_vs_obtain_pooled": jsd_obtain, "treechop_vs_craft": jsd_craft,
            "treechop_vs_coverage": jsd_cov, "null_treechop_split_half": jsd_null,
            "ratio_vs_null": ratio,
        },
    }
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary saved -> {out_path}")


if __name__ == "__main__":
    main()

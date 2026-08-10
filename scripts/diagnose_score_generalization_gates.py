"""
Cold-start attempt #19, Run A, step 4 — re-run of the central attempt #10 gate
(scripts/diagnose_score_generalization.py's goal_score_std computation, the
same DiscreteLatentPlanner._sample_actions/_score code path the live
scan/spawn_diag machinery uses every replan) against ebwm.pt AND the 5
action-coverage-fix fine-tune snapshots, formalized into the same PASS/FAIL
Gate A/Gate B shape attempts #17/#18 introduced (scripts/diagnose_ood_gate.py,
scripts/diagnose_depth_gate.py) — plus a Treechop non-regression gate that has
never been checked before (attempt #14 Phase 2's own self-flagged gap: "only
bulk score-distribution statistics were checked... neither confirmed fine nor
confirmed broken on Treechop specifically").

Reuses, verbatim, not reimplemented:
  - gather_treechop_frames / gather_obtain_frames / score_frame
    (scripts/diagnose_score_generalization.py)
  - load_model / build_goal_latents / preprocess (scripts/play_ebwm.py)
  - DiscreteLatentPlanner / _sample_actions (mine_jepa/ebwm/planner.py)
  - label_row's tree_close/no_tree matching rule (scripts/diagnose_depth_gate.py)
  - brightness_of (scripts/train_value_projector.py)

Frame set: identical 251-frame population, identical hand-labeled subset
(configs/diagnose_depth_gate.yaml's EXPANDED direction_check block, tree_close
n=10, no_tree n=17 — attempt #18's larger, non-small-sample-artifact set, not
the original n=4/6 set that produced a false GO on Diagnostic 1).

Three gates, evaluated per checkpoint:
  Gate A (separation)      : mean goal_score_std, tree_close vs no_tree,
                              correct direction + ratio >= min_separation_ratio.
  Gate B (brightness-indep): |Pearson r(goal_score_std, brightness)| < max_brightness_corr,
                              over all 251 frames.
  Gate C (Treechop non-regression, NEW): median(treechop goal_score_std) stays
                              within [treechop_median_band_lo, treechop_median_band_hi]
                              of the FIRST checkpoint listed (intended to be the
                              unmodified checkpoints/ebwm.pt baseline) AND the
                              offset 0.0-vs-0.5 near/far direction check on
                              Treechop's own data stays correct with the same
                              min_separation_ratio bar.

No checkpoint is written or modified anywhere in this script (every model is
loaded read-only, eval(), requires_grad_(False) verified).

Usage: run.bat scripts/diagnose_score_generalization_gates.py --config configs/diagnose_score_generalization_gates.yaml
"""
import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
import yaml

from scripts.diagnose_depth_gate import label_row
from scripts.diagnose_score_generalization import gather_obtain_frames, gather_treechop_frames, score_frame
from scripts.play_ebwm import build_goal_latents, load_model
from scripts.train_value_projector import brightness_of
from mine_jepa.ebwm.planner import DiscreteLatentPlanner


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/diagnose_score_generalization_gates.yaml")
    return p.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def score_checkpoint(ckpt_path: str, all_rows: list, cfg: dict, seed: int, device) -> np.ndarray:
    """Loads one checkpoint frozen, builds its own goal centroid + planner
    (exactly like the live two-brain chop planner would for that checkpoint),
    scores every row in `all_rows` (same frames for every checkpoint, only the
    model differs). Reseeded per checkpoint so the stochastic candidate
    sampling (_sample_actions) is identical across checkpoints, not a
    confounding source of noise between them."""
    seed_everything(seed)
    model, ratio = load_model(ckpt_path, device)
    model.requires_grad_(False)
    for p in model.parameters():
        assert not p.requires_grad
    print(f"  Loaded {ckpt_path} (ratio={ratio:.4f}), requires_grad_(False) verified")

    goal_latents = build_goal_latents(model, {"goal": cfg["goal"]}, device)
    p_cfg = cfg["planner"]
    planner = DiscreteLatentPlanner(
        model, n_actions=int(p_cfg["n_actions"]), horizon=int(p_cfg["horizon"]),
        n_candidates=int(p_cfg["n_candidates"]), sticky_prob=float(p_cfg["sticky_prob"]),
        device=device,
    )
    scores = np.zeros(len(all_rows), dtype=np.float64)
    for i, row in enumerate(all_rows):
        std, _ = score_frame(planner, goal_latents, row["frame"], device)
        scores[i] = std
        if (i + 1) % 100 == 0:
            print(f"    {i + 1}/{len(all_rows)}", flush=True)
    return scores


def gate_a_separation(obtain_rows: list, scores_obtain: np.ndarray, dc: dict, min_sep: float) -> dict:
    labels = [label_row(r, dc) for r in obtain_rows]
    tree = scores_obtain[np.array([l == "tree_close" for l in labels])]
    notree = scores_obtain[np.array([l == "no_tree" for l in labels])]
    tree_mean, notree_mean = float(tree.mean()), float(notree.mean())
    correct_direction = tree_mean > notree_mean
    if abs(notree_mean) > 1e-9:
        ratio = tree_mean / notree_mean if notree_mean > 0 else tree_mean / abs(notree_mean)
    else:
        ratio = float("inf") if tree_mean > 0 else float("-inf")
    passed = correct_direction and ratio >= min_sep
    return {
        "n_tree_close": int(len(tree)), "n_no_tree": int(len(notree)),
        "tree_close_mean": tree_mean, "no_tree_mean": notree_mean,
        "correct_direction": bool(correct_direction), "ratio": float(ratio),
        "pass": bool(passed),
    }


def gate_b_brightness(all_scores: np.ndarray, bright: np.ndarray, max_bright: float) -> dict:
    r = float(np.corrcoef(all_scores, bright)[0, 1])
    passed = abs(r) < max_bright
    return {"pearson_r": r, "pass": bool(passed)}


def gate_c_treechop_regression(treechop_rows: list, scores_treechop: np.ndarray,
                                baseline_median: float, band: list, offsets: list,
                                min_sep: float, check_direction: bool = True) -> dict:
    """
    check_direction=True (default) reproduces attempt #19 Run A's Gate C exactly
    (band + near/far direction sub-test both required to pass).
    check_direction=False (Run B's own diagnose_score_generalization_gates_sigreg.yaml)
    drops the direction sub-test from the pass/fail verdict — Run A's diagnostic
    found the baseline itself already failed that sub-test (invalidated premise,
    see CLAUDE.md attempt #19 Run A write-up) — magnitude/band only. The
    direction numbers are still computed and returned for visibility either way,
    just not used to gate pass/fail when check_direction=False.
    """
    median = float(np.median(scores_treechop))
    ratio_vs_baseline = median / max(baseline_median, 1e-12)
    band_pass = band[0] <= ratio_vs_baseline <= band[1]

    off_lo, off_hi = float(offsets[0]), float(offsets[1])
    offs = np.array([float(r["offset"]) for r in treechop_rows])
    lo_scores = scores_treechop[np.isclose(offs, off_lo)]
    hi_scores = scores_treechop[np.isclose(offs, off_hi)]
    lo_mean, hi_mean = float(lo_scores.mean()), float(hi_scores.mean())
    correct_direction = hi_mean > lo_mean
    dir_ratio = hi_mean / lo_mean if lo_mean > 1e-12 else float("inf")
    direction_pass = correct_direction and dir_ratio >= min_sep

    passed = band_pass and (direction_pass if check_direction else True)
    return {
        "median": median, "baseline_median": baseline_median,
        "ratio_vs_baseline": ratio_vs_baseline, "band": band, "band_pass": bool(band_pass),
        "offset_lo": off_lo, "offset_hi": off_hi, "offset_lo_mean": lo_mean, "offset_hi_mean": hi_mean,
        "direction_correct": bool(correct_direction), "direction_ratio": float(dir_ratio),
        "direction_pass": bool(direction_pass), "direction_checked": bool(check_direction),
        "pass": bool(passed),
    }


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    seed = int(cfg.get("seed", 0))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}  |  seed: {seed}")

    seed_everything(seed)
    rng = np.random.RandomState(seed)
    print("\nGathering the 251-frame diagnostic set (verbatim from "
          "scripts/diagnose_score_generalization.py)...")
    treechop_rows = gather_treechop_frames(cfg["treechop"], rng)
    obtain_rows = gather_obtain_frames(cfg["obtain"])
    all_rows = treechop_rows + obtain_rows
    n_spawn = sum(1 for r in obtain_rows if r["group"] == "obtain_spawn")
    n_cov = sum(1 for r in obtain_rows if r["group"] == "obtain_coverage")
    print(f"  {len(treechop_rows)} treechop, {n_spawn} obtain_spawn, {n_cov} obtain_coverage "
          f"= {len(all_rows)} total")

    frames = [r["frame"] for r in all_rows]
    bright = brightness_of(frames)

    dc = cfg["direction_check"]
    gates_cfg = cfg["gates"]
    min_sep = float(gates_cfg["min_separation_ratio"])
    max_bright = float(gates_cfg["max_brightness_corr"])
    band = [float(x) for x in gates_cfg["treechop_regression_band"]]
    offsets = gates_cfg["treechop_direction_offsets"]
    check_direction = bool(gates_cfg.get("treechop_direction_check_enabled", True))

    checkpoints = cfg["checkpoints"]
    baseline_name = cfg["baseline_name"]
    assert baseline_name in checkpoints, f"baseline_name={baseline_name} not in checkpoints"

    out_dir = Path(cfg["output"]["dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / cfg["output"]["csv_name"]

    results = {}
    baseline_treechop_median = None
    csv_rows = []

    ordered_names = [baseline_name] + [n for n in checkpoints if n != baseline_name]
    for name in ordered_names:
        ckpt_path = checkpoints[name]
        print(f"\n{'=' * 78}\nCHECKPOINT: {name} ({ckpt_path})\n{'=' * 78}")
        scores = score_checkpoint(ckpt_path, all_rows, cfg, seed, device)
        for row, s in zip(all_rows, scores):
            csv_rows.append((name, row["group"], row["episode"], row["offset"], row["frame_idx"], float(s)))

        scores_treechop = scores[np.array([r["group"] == "treechop" for r in all_rows])]
        scores_obtain_mask = np.array([r["group"] != "treechop" for r in all_rows])
        scores_obtain = scores[scores_obtain_mask]

        ga = gate_a_separation(obtain_rows, scores_obtain, dc, min_sep)
        gb = gate_b_brightness(scores, bright, max_bright)

        if name == baseline_name:
            baseline_treechop_median = float(np.median(scores_treechop))
            gc = {"note": "baseline checkpoint — regression gate not applicable to itself",
                  "median": baseline_treechop_median, "pass": True}
        else:
            gc = gate_c_treechop_regression(treechop_rows, scores_treechop,
                                            baseline_treechop_median, band, offsets, min_sep,
                                            check_direction=check_direction)

        overall = ga["pass"] and gb["pass"] and gc["pass"]
        results[name] = {"checkpoint": ckpt_path, "gate_a": ga, "gate_b": gb, "gate_c": gc,
                          "all_gates_pass": bool(overall)}

        print(f"  Gate A (separation)        : {'PASS' if ga['pass'] else 'FAIL'} "
              f"(ratio={ga['ratio']:.3f}x, correct_direction={ga['correct_direction']}, "
              f"tree_close_mean={ga['tree_close_mean']:.6f}, no_tree_mean={ga['no_tree_mean']:.6f})")
        print(f"  Gate B (brightness-indep)  : {'PASS' if gb['pass'] else 'FAIL'} (r={gb['pearson_r']:.4f})")
        if name == baseline_name:
            print(f"  Gate C (Treechop regression): N/A (this IS the baseline, "
                  f"median={gc['median']:.6f})")
        else:
            dir_note = "" if check_direction else " [direction sub-test NOT gated — informational only]"
            print(f"  Gate C (Treechop regression): {'PASS' if gc['pass'] else 'FAIL'} "
                  f"(median_ratio_vs_baseline={gc['ratio_vs_baseline']:.3f}x, band={band}, "
                  f"band_pass={gc['band_pass']}; offset0.0={gc['offset_lo_mean']:.6f} vs "
                  f"offset0.5={gc['offset_hi_mean']:.6f}, dir_ratio={gc['direction_ratio']:.3f}x, "
                  f"direction_pass={gc['direction_pass']}{dir_note})")
        print(f"  ALL GATES: {'PASS' if overall else 'FAIL'}")

    with open(csv_path, "w") as f:
        f.write("checkpoint,group,episode,offset,frame_idx,goal_score_std\n")
        for row in csv_rows:
            f.write(",".join(str(x) for x in row) + "\n")
    print(f"\nCSV saved -> {csv_path}")

    json_path = out_dir / cfg["output"]["json_name"]
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Summary saved -> {json_path}")

    print(f"\n{'=' * 78}\nOVERALL VERDICT ACROSS ALL CHECKPOINTS\n{'=' * 78}")
    any_full_pass = False
    for name in ordered_names:
        r = results[name]
        tag = "BASELINE" if name == baseline_name else ""
        print(f"  {name:<10} {tag:<9} gate_a={'P' if r['gate_a']['pass'] else 'F'}  "
              f"gate_b={'P' if r['gate_b']['pass'] else 'F'}  "
              f"gate_c={'P' if r['gate_c']['pass'] else 'F'}  "
              f"ALL={'PASS' if r['all_gates_pass'] else 'FAIL'}")
        if name != baseline_name and r["all_gates_pass"]:
            any_full_pass = True
    print(f"\n  At least one non-baseline snapshot passes all 3 gates: {any_full_pass}")


if __name__ == "__main__":
    main()

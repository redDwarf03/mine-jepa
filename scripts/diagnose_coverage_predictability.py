"""
Cold-start attempt #16 candidate — Coverage-Value Predictor (CVP), offline
validation gate ONLY (docs/10_coldstart_engineering.md). This does NOT build or
train the actual predictor (no mine_jepa/ebwm/coverage_predictor.py, no training
script here — deliberately out of scope for this dispatch) — it decides whether
the geometric target (realized Δunique_cells over ~scan.frontier.log_transitions_k
ticks after a scan-macro trigger) is worth building a predictor for at all, and
whether the cheap non-learned flow-summary feature carries independent signal
beyond a plain scene-brightness confound — the same shortcut 5 independent
prior attempts (#7, #11, #14 Phase1/Phase2, #15) each found a frozen-encoder-
adjacent head reaching for on this exact domain.

Reads the CSV produced by scripts/play_craft.py's scan.frontier.log_transitions
instrumentation: one row per scan-macro trigger tick, containing the chosen
frontier heading + target cell + its visit count, the full 12-heading local
visitation histogram, a classical per-quadrant frame-difference flow summary
over the 8 POV frames preceding the trigger, mean frame brightness
(scripts/train_value_projector.py's brightness_of, reused verbatim upstream in
play_craft.py), and the REALIZED Δunique_cells measured k ticks later (or at
episode end if the episode ended first).

No MineRL, no Java, no training, no checkpoint touched — pure CSV analysis.

Usage: run.bat scripts/diagnose_coverage_predictability.py --csv logs/coverage_transitions.csv
"""
import argparse
import csv

import numpy as np


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default="logs/coverage_transitions.csv")
    p.add_argument("--range_gate_ratio", type=float, default=2.0)
    return p.parse_args()


def load_rows(path: str) -> list[dict]:
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return [{k: float(v) for k, v in row.items()} for row in reader]


def pearson(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 2 or np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def partial_corr(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> float:
    """Partial correlation of x and y controlling for z, standard first-order
    formula: r_xy.z = (r_xy - r_xz*r_yz) / sqrt((1-r_xz^2)(1-r_yz^2))."""
    r_xy, r_xz, r_yz = pearson(x, y), pearson(x, z), pearson(y, z)
    denom = np.sqrt(max((1 - r_xz ** 2) * (1 - r_yz ** 2), 1e-12))
    return float((r_xy - r_xz * r_yz) / denom)


def dynamic_range_gate(rows: list[dict], ratio_bar: float) -> bool | None:
    print(f"\n{'='*70}\nGATE 1 - dynamic range of realized delta_unique_cells by chosen heading\n{'='*70}")
    by_heading: dict[float, list[float]] = {}
    for r in rows:
        by_heading.setdefault(r["chosen_heading_deg"], []).append(r["realized_delta_unique_cells"])
    means = {h: float(np.mean(v)) for h, v in by_heading.items()}
    for h in sorted(means):
        print(f"  heading={h:6.1f}deg  n={len(by_heading[h]):3d}  "
              f"mean_delta_unique_cells={means[h]:7.3f}")
    if len(means) < 2:
        print("  Only one distinct heading chosen across the whole batch - cannot compute a ratio.")
        return None
    top, bottom = max(means.values()), min(means.values())
    eps = 1e-6
    ratio = (top + eps) / (max(bottom, 0.0) + eps)
    print(f"\n  top heading mean = {top:.3f}, bottom heading mean = {bottom:.3f}, "
          f"ratio = {ratio:.2f}x (bar: >= {ratio_bar}x)")
    verdict = ratio >= ratio_bar
    print(f"  GATE 1 verdict: {'PASS' if verdict else 'FAIL'}")
    return verdict


def brightness_partial_correlation_gate(rows: list[dict]) -> bool:
    print(f"\n{'='*70}\nGATE 2 - brightness-partial-correlation (the critical gate)\n{'='*70}")
    delta = np.array([r["realized_delta_unique_cells"] for r in rows])
    brightness = np.array([r["brightness"] for r in rows])
    flow_means = np.array([
        [r["flow_tl_mean"], r["flow_tr_mean"], r["flow_bl_mean"], r["flow_br_mean"]]
        for r in rows
    ])
    flow_magnitude = flow_means.mean(axis=1)

    r_bright_delta = pearson(brightness, delta)
    r_flow_delta = pearson(flow_magnitude, delta)
    partial_flow_delta = partial_corr(flow_magnitude, delta, brightness)

    print(f"  r(brightness, delta_unique_cells)              = {r_bright_delta:+.4f}")
    print(f"  r(flow_magnitude, delta_unique_cells)  [raw]    = {r_flow_delta:+.4f}")
    print(f"  partial r(flow_magnitude, delta | brightness)   = {partial_flow_delta:+.4f}")

    print("\n  Per-quadrant-feature detail (raw r, partial r | brightness):")
    for q in ("tl", "tr", "bl", "br"):
        for stat in ("mean", "var"):
            col = f"flow_{q}_{stat}"
            x = np.array([r[col] for r in rows])
            r_raw = pearson(x, delta)
            r_partial = partial_corr(x, delta, brightness)
            print(f"    {col:16s}  raw={r_raw:+.4f}  partial|brightness={r_partial:+.4f}")

    # Hard-stop condition, per the dispatch's own design: brightness has a
    # non-negligible raw relationship with the target AND the flow feature's
    # correlation with the target is mostly explained BY brightness (collapses
    # once brightness is controlled for) -> the shortcut a trained predictor
    # would find is "avoid/seek dark scenes" (== forests in this domain), not
    # genuine motion/coverage geometry.
    brightness_nonneg = abs(r_bright_delta) >= 0.15
    flow_explained_by_brightness = abs(partial_flow_delta) < 0.5 * max(abs(r_flow_delta), 1e-6)
    hard_stop = brightness_nonneg and flow_explained_by_brightness
    print(f"\n  Hard-stop condition (|r_brightness| >= 0.15 AND partial r drops "
          f"below half its raw value): {'TRIGGERED -- NO-GO' if hard_stop else 'not triggered'}")
    return not hard_stop


def main():
    args = parse_args()
    rows = load_rows(args.csv)
    print(f"Loaded {len(rows)} scan-trigger rows from {args.csv}")
    if not rows:
        print("No rows - cannot run either gate. Re-run the collection batch "
              "(configs/play_craft_commit4_hazard.yaml with scan.frontier.log_transitions: true).")
        return

    gate1 = dynamic_range_gate(rows, args.range_gate_ratio)
    gate2 = brightness_partial_correlation_gate(rows)

    print(f"\n{'='*70}\nSUMMARY\n{'='*70}")
    print(f"  Gate 1 (dynamic range >= {args.range_gate_ratio}x) : "
          f"{'PASS' if gate1 else ('FAIL' if gate1 is not None else 'INCONCLUSIVE (single heading)')}")
    print(f"  Gate 2 (brightness does not dominate)   : {'PASS' if gate2 else 'FAIL (hard-stop)'}")
    if gate1 and gate2:
        print("\n  Both gates PASS -> building the trained Coverage-Value Predictor is justified.")
    else:
        print("\n  At least one gate did not pass -> do NOT build the trained CVP model on this "
              "signal as designed. See the gate detail above for which one and why.")


if __name__ == "__main__":
    main()

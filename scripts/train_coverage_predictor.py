"""
Train the Coverage-Value Predictor (CVP) — cold-start attempt #16
(docs/10_coldstart_engineering.md, mine_jepa/ebwm/coverage_predictor.py).

Reads the scan.frontier.log_transitions CSVs (scripts/diagnose_coverage_predictability.py's
own load_rows/feature columns, reused verbatim here rather than re-derived) and
trains a small MLP regressor: (flow summary, brightness, local visitation
histogram, candidate-heading identity) -> realized Δunique_cells for that
heading.

Mandatory k-fold cross-validation (no single train/val split — the combined
dataset is only ~100 rows): reports REAL out-of-fold MAE against a trivial
"always predict the fold's own training mean" baseline. Only trains + saves a
final full-data checkpoint if the CV comparison in the printed report shows a
meaningful improvement over that baseline — this script always prints the
comparison; a human (or the calling agent) reads the printed verdict to decide
whether to trust the resulting checkpoint before wiring it into play_craft.py.

Usage: run.bat scripts/train_coverage_predictor.py --csvs logs/coverage_transitions.csv logs/coverage_transitions_tiebreak.csv
"""
import argparse
import random

import numpy as np
import torch
import torch.nn as nn
from sklearn.model_selection import KFold

from mine_jepa.ebwm.coverage_predictor import CoveragePredictor, build_feature_vector, feature_dim
from scripts.diagnose_coverage_predictability import load_rows


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--csvs", nargs="+", default=[
        "logs/coverage_transitions.csv", "logs/coverage_transitions_tiebreak.csv",
    ])
    p.add_argument("--n_headings", type=int, default=12)
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--hidden_dim", type=int, default=32)
    p.add_argument("--epochs", type=int, default=300)
    p.add_argument("--lr", type=float, default=1e-2)
    p.add_argument("--weight_decay", type=float, default=1e-3)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--min_improvement_ratio", type=float, default=0.85,
                    help="GO only if mean OOF MAE(model) <= this * MAE(baseline)")
    p.add_argument("--out", default="checkpoints/coverage_predictor.pt")
    return p.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def load_dataset(csv_paths: list[str], n_headings: int) -> tuple[np.ndarray, np.ndarray]:
    """One (features, target) pair per row: the row's CHOSEN heading's own
    feature vector -> the row's realized Δunique_cells. chosen_heading_deg is
    snapped to the nearest of the n_headings candidate slots (it was sampled
    from exactly that grid by FrontierTracker.frontier_heading_deg(), so this
    is an exact match modulo floating point, not a lossy approximation)."""
    xs, ys = [], []
    for path in csv_paths:
        rows = load_rows(path)
        print(f"  {path}: {len(rows)} rows")
        for row in rows:
            hist = [row[f"hist_heading{i}_visits"] for i in range(n_headings)]
            flow = {k: row[k] for k in [
                f"flow_{q}_{stat}" for q in ("tl", "tr", "bl", "br") for stat in ("mean", "var")
            ]}
            step = 360.0 / n_headings
            heading_idx = int(round(row["chosen_heading_deg"] / step)) % n_headings
            feat = build_feature_vector(hist, flow, row["brightness"], heading_idx, n_headings)
            xs.append(feat)
            ys.append(row["realized_delta_unique_cells"])
    return np.stack(xs), np.array(ys, dtype=np.float32)


def train_one_model(
    x_train: np.ndarray, y_train: np.ndarray, hidden_dim: int, n_headings: int,
    epochs: int, lr: float, weight_decay: float, seed: int, device: torch.device,
) -> CoveragePredictor:
    seed_everything(seed)
    mean, std = x_train.mean(axis=0), x_train.std(axis=0)
    model = CoveragePredictor(in_dim=x_train.shape[1], hidden_dim=hidden_dim, n_headings=n_headings)
    model.set_normalization(mean, std)
    model = model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    xt = torch.from_numpy(x_train).float().to(device)
    yt = torch.from_numpy(y_train).float().to(device)
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        pred = model(xt)
        loss = nn.functional.mse_loss(pred, yt)
        loss.backward()
        opt.step()
    model.eval()
    return model


def cross_validate(x: np.ndarray, y: np.ndarray, args, n_headings: int, device: torch.device):
    kf = KFold(n_splits=args.folds, shuffle=True, random_state=args.seed)
    oof_pred = np.zeros_like(y)
    oof_baseline = np.zeros_like(y)
    fold_model_mae, fold_baseline_mae = [], []
    for fold, (tr_idx, va_idx) in enumerate(kf.split(x)):
        x_tr, y_tr = x[tr_idx], y[tr_idx]
        x_va, y_va = x[va_idx], y[va_idx]
        model = train_one_model(
            x_tr, y_tr, args.hidden_dim, n_headings, args.epochs, args.lr,
            args.weight_decay, args.seed + fold, device,
        )
        with torch.no_grad():
            pred_va = model(torch.from_numpy(x_va).float().to(device)).cpu().numpy()
        train_mean = float(y_tr.mean())
        baseline_va = np.full_like(y_va, train_mean)
        oof_pred[va_idx] = pred_va
        oof_baseline[va_idx] = baseline_va
        model_mae = float(np.mean(np.abs(pred_va - y_va)))
        baseline_mae = float(np.mean(np.abs(baseline_va - y_va)))
        fold_model_mae.append(model_mae)
        fold_baseline_mae.append(baseline_mae)
        print(f"  fold {fold+1}/{args.folds}: n_val={len(va_idx):3d}  "
              f"model_MAE={model_mae:.3f}  baseline_MAE={baseline_mae:.3f}  "
              f"train_mean_target={train_mean:.3f}")
    return oof_pred, oof_baseline, fold_model_mae, fold_baseline_mae


def r_squared(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    return 1.0 - ss_res / max(ss_tot, 1e-12)


def main():
    args = parse_args()
    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    n_headings = args.n_headings

    print("Loading combined dataset:")
    x, y = load_dataset(args.csvs, n_headings)
    print(f"  Combined: {len(y)} rows, feature_dim={x.shape[1]} "
          f"(expected {feature_dim(n_headings)})")
    print(f"  target realized_delta_unique_cells: mean={y.mean():.3f} std={y.std():.3f} "
          f"min={y.min():.3f} max={y.max():.3f}")

    print(f"\n{'='*70}\n{args.folds}-fold cross-validation (seeded, out-of-fold error only)\n{'='*70}")
    oof_pred, oof_baseline, fold_model_mae, fold_baseline_mae = cross_validate(
        x, y, args, n_headings, device
    )
    mean_model_mae = float(np.mean(fold_model_mae))
    mean_baseline_mae = float(np.mean(fold_baseline_mae))
    oof_model_r2 = r_squared(y, oof_pred)
    oof_baseline_r2 = r_squared(y, oof_baseline)

    print(f"\n{'='*70}\nCross-validation summary\n{'='*70}")
    print(f"  mean OOF MAE  — model:    {mean_model_mae:.4f}")
    print(f"  mean OOF MAE  — baseline: {mean_baseline_mae:.4f}")
    print(f"  pooled OOF R^2 — model:    {oof_model_r2:+.4f}")
    print(f"  pooled OOF R^2 — baseline: {oof_baseline_r2:+.4f}  (should be ~0 or negative by construction)")
    ratio = mean_model_mae / max(mean_baseline_mae, 1e-9)
    go = ratio <= args.min_improvement_ratio
    print(f"\n  model_MAE / baseline_MAE = {ratio:.3f}  (GO bar: <= {args.min_improvement_ratio})")
    print(f"  VERDICT: {'GO — real signal, training + saving the final checkpoint' if go else 'NO-GO — no meaningful signal over the trivial baseline, NOT saving a checkpoint'}")

    if not go:
        print("\n  Stopping here per the dispatch's own instructions: a non-functional model "
              "should not be wired into play_craft.py. checkpoints/coverage_predictor.pt NOT written.")
        return

    print(f"\nTraining final model on ALL {len(y)} rows for deployment...")
    final_model = train_one_model(
        x, y, args.hidden_dim, n_headings, args.epochs, args.lr,
        args.weight_decay, args.seed, device,
    )
    final_model.to("cpu").save(args.out)
    print(f"Saved -> {args.out}")


if __name__ == "__main__":
    main()

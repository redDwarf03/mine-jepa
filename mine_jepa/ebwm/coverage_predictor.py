"""
Coverage-Value Predictor (CVP) — cold-start attempt #16, docs/10_coldstart_engineering.md.

A small MLP that predicts the exploration payoff (realized Δunique_cells over
~scan.frontier.log_transitions_k ticks) of steering toward one of
FrontierTracker's n_headings candidate directions, from features that are
DELIBERATELY non-photometric-scoring: a classical per-quadrant frame-difference
flow summary (scripts/play_craft.py::quadrant_flow_stats) plus the local
visitation histogram FrontierTracker.all_headings_visits() already computes for
free, plus raw scene brightness (kept as an input, not the target, specifically
so the training/CV step can show whether the model leans on it — see
scripts/train_coverage_predictor.py). This avoids the single-frame frozen-
encoder goal-centroid shortcut 5 independent prior attempts (#7, #11, #14
Phase1/Phase2, #15) all found reaching for brightness on this exact domain.

Training data is one row per scan-macro trigger tick, i.e. one (features,
realized outcome) pair for the ONE heading actually chosen that tick — not a
12-output-at-once model. At inference (scripts/play_craft.py, scan.macro:
"learned_frontier") the same small model is run once per candidate heading
(12 forward passes total, negligible cost) by swapping which heading's index
the feature vector encodes while holding the shared scene features (flow,
brightness, full histogram) fixed — see build_feature_vector below.
"""
from __future__ import annotations

import math

import numpy as np
import torch
import torch.nn as nn

FLOW_KEYS = [f"flow_{q}_{stat}" for q in ("tl", "tr", "bl", "br") for stat in ("mean", "var")]


def feature_dim(n_headings: int = 12) -> int:
    """8 flow stats + 1 brightness + n_headings histogram + sin/cos(heading) + own visit count."""
    return len(FLOW_KEYS) + 1 + n_headings + 3


def build_feature_vector(
    hist_counts: list[float], flow: dict, brightness: float, heading_idx: int, n_headings: int = 12,
) -> np.ndarray:
    """One feature vector describing "the payoff of choosing candidate heading
    `heading_idx`" given the CURRENT scene (flow, brightness) and the CURRENT
    local visitation histogram (`hist_counts`, length n_headings, same order as
    FrontierTracker.all_headings_visits()/frontier_heading_deg()'s enumeration:
    heading_deg = 360*i/n_headings).

    flow/brightness are the SAME across all n_headings queries at one decision
    tick (they describe the current frame, not a specific direction) — only the
    sin/cos(heading) + own_visit_count entries change per query, which is what
    lets a single small MLP be queried n_headings times to rank all candidates.
    """
    heading_deg = 360.0 * heading_idx / n_headings
    rad = math.radians(heading_deg)
    own_visits = float(hist_counts[heading_idx])
    vec = (
        [float(flow[k]) for k in FLOW_KEYS]
        + [float(brightness)]
        + [float(c) for c in hist_counts]
        + [math.sin(rad), math.cos(rad), own_visits]
    )
    return np.array(vec, dtype=np.float32)


class CoveragePredictor(nn.Module):
    """Small MLP regressor: feature_dim(n_headings) -> scalar predicted
    Δunique_cells. Feature normalization (mean/std, fit on the training set)
    is baked in as buffers so a saved checkpoint is self-contained — no
    separate stats file to keep in sync at inference time."""

    def __init__(self, in_dim: int, hidden_dim: int = 32, n_headings: int = 12):
        super().__init__()
        self.in_dim = in_dim
        self.hidden_dim = hidden_dim
        self.n_headings = n_headings
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Linear(hidden_dim, 1),
        )
        self.register_buffer("feat_mean", torch.zeros(in_dim), persistent=True)
        self.register_buffer("feat_std", torch.ones(in_dim), persistent=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = (x - self.feat_mean) / self.feat_std
        return self.net(x).squeeze(-1)

    def set_normalization(self, mean: np.ndarray, std: np.ndarray) -> None:
        self.feat_mean.copy_(torch.as_tensor(mean, dtype=torch.float32))
        self.feat_std.copy_(torch.as_tensor(std, dtype=torch.float32).clamp_min(1e-6))

    @torch.no_grad()
    def predict_headings(self, hist_counts: list[float], flow: dict, brightness: float) -> np.ndarray:
        """Score all n_headings candidates for one decision tick. Returns a
        [n_headings] numpy array of predicted Δunique_cells."""
        feats = np.stack([
            build_feature_vector(hist_counts, flow, brightness, i, self.n_headings)
            for i in range(self.n_headings)
        ])
        device = self.feat_mean.device
        x = torch.from_numpy(feats).to(device)
        return self.forward(x).cpu().numpy()

    def save(self, path: str) -> None:
        torch.save({
            "state_dict": self.state_dict(),
            "cfg": {"in_dim": self.in_dim, "hidden_dim": self.hidden_dim, "n_headings": self.n_headings},
        }, path)

    @classmethod
    def load(cls, path: str, device: torch.device | str | None = None) -> "CoveragePredictor":
        ckpt = torch.load(path, map_location=device or "cpu", weights_only=False)
        model = cls(**ckpt["cfg"])
        model.load_state_dict(ckpt["state_dict"])
        if device is not None:
            model = model.to(device)
        model.eval()
        return model

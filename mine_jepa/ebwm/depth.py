"""
Monocular depth (MiDaS_small, off-the-shelf, intel-isl/MiDaS via torch.hub) as
a NAVIGATION heading signal for the scan macro's cold-start recovery reflex
(docs/10_coldstart_engineering.md, cold-start attempt #18 follow-up).

Cold-start attempt #18's offline diagnostic (scripts/diagnose_depth_gate.py,
Task A of this follow-up dispatch, not touched here) found MiDaS_small is the
first signal in 7 independent tries on MineRLObtainIronPickaxeDense-v0 to
separate "tree close" from "no tree" while staying near-independent of raw
brightness (ratio 1.304x, r=0.045 -- the campaign's best by a wide margin).
This module factors out that diagnostic's model-loading/scoring logic (same
shape, not literally imported since diagnose_depth_gate.py is off-limits for
this dispatch) for reuse LIVE in scripts/play_craft.py's new "depth" scan
macro.

CRITICAL constraint (from reading mine_jepa/ebwm/planner.py): depth can only
be computed on a REAL rendered frame (actual RGB pixels from obs_init). The
world model's unroll() produces IMAGINED future LATENTS with no pixels at all
-- there is no decoder back to pixel space in this project. This module is
therefore never called from CraftPlannerV4/SwitchingCraftPlanner's _score();
it is called exactly once per replan, on the single CURRENT observed frame,
purely to choose a scan-macro heading.

LIMITATION, stated once here and repeated at every call site: depth cannot
distinguish a tree trunk from a wall, a hill, or the ground -- it only answers
"is something close in this direction", not "is that something choppable".
This is a heading proposal for the scan macro's forward-cruise recovery
reflex, not a scoring signal for the chop/craft planner itself.
"""
from __future__ import annotations

import numpy as np
import torch


def load_depth_model(repo: str, model_type: str, device):
    """Off-the-shelf MiDaS_small, zero Minecraft-specific training. Loaded
    read-only: eval() + requires_grad_(False), the same convention as every
    checkpoint-touching script in this campaign, even though nothing here is
    actually a project checkpoint. trust_repo=True bypasses torch.hub's
    interactive y/N confirmation for a non-built-in-trusted repo -- fatal
    under a non-interactive/Tee'd run, the same bypass
    scripts/diagnose_depth_gate.py uses (official documented torch.hub
    mechanism, not a security weakening beyond what running arbitrary hub
    code already implies)."""
    model = torch.hub.load(repo, model_type, trust_repo=True)
    model = model.to(device).eval()
    model.requires_grad_(False)
    for p in model.parameters():
        assert not p.requires_grad
    transforms = torch.hub.load(repo, "transforms", trust_repo=True)
    transform = transforms.small_transform
    return model, transform


@torch.no_grad()
def column_depth_scores(
    model, transform, frame: np.ndarray, device, n_columns: int, top_frac: float,
) -> np.ndarray:
    """Splits the frame into n_columns equal-width VERTICAL strips and returns
    one "nearest salient object" scalar per column: the mean of the closest
    (numerically LARGEST -- MiDaS outputs relative INVERSE depth/disparity,
    higher = closer, per the official repo's documented convention) top_frac
    of pixels WITHIN that column only. Same statistic as
    diagnose_depth_gate.py's depth_score(), computed once per column instead
    of once for the whole frame -- gives directional resolution instead of a
    single whole-frame scalar. MiDaS itself still sees the FULL frame (not
    column crops) so its receptive field keeps full-frame context; only the
    pixel-selection mask for the top-frac statistic is columnar.

    n_columns is a resolution/cost trade-off, not a measured claim about
    Minecraft's field of view: at this project's 64x64 encoding resolution, 4
    columns (16px each) is roughly the finest split that still leaves each
    column enough pixels for a non-degenerate top-10% statistic.
    """
    img = frame[:, :, :3]
    inp = transform(img).to(device)
    pred = model(inp)
    pred = torch.nn.functional.interpolate(
        pred.unsqueeze(1), size=img.shape[:2], mode="bicubic", align_corners=False,
    ).squeeze()
    depth = pred.cpu().numpy()   # [H, W]
    h, w = depth.shape
    col_w = w // n_columns
    scores = np.zeros(n_columns, dtype=np.float32)
    for c in range(n_columns):
        x0 = c * col_w
        x1 = w if c == n_columns - 1 else (c + 1) * col_w
        col = depth[:, x0:x1].reshape(-1)
        k = max(1, int(len(col) * top_frac))
        top_vals = np.partition(col, -k)[-k:]
        scores[c] = float(top_vals.mean())
    return scores


def column_heading_offsets_deg(n_columns: int, fov_deg: float) -> np.ndarray:
    """Camera-relative bearing (degrees, + = right, matching MineRL's
    camera[1] convention) of each column's CENTER, assuming the frame spans
    fov_deg of horizontal field of view split evenly into n_columns strips.
    fov_deg is a configured APPROXIMATION (Minecraft's in-game FOV slider
    defaults to ~70deg; this project has never independently measured the
    actual horizontal angle subtended by the POV array MineRL hands back) --
    not a precisely calibrated optical constant. Column 0 is leftmost
    (negative offset), the last column is rightmost (positive)."""
    idx = np.arange(n_columns, dtype=np.float64)
    centered = idx - (n_columns - 1) / 2.0
    return centered * (fov_deg / n_columns)


def best_heading_delta_deg(scores: np.ndarray, offsets_deg: np.ndarray) -> tuple[float, int]:
    """Returns (delta_deg, column_index) for the column with the HIGHEST
    near-object score (closest thing in view) -- delta_deg is directly the
    camera-relative bearing to steer toward. Unlike FrontierTracker/hazard's
    world-position deltas, this needs no dead-reckoned position at all: it is
    re-derived fresh from the CURRENT frame every call, with no persistent
    cross-replan target (the object judged "closest" can be a different real
    object next replan, once the view has rotated)."""
    idx = int(np.argmax(scores))
    return float(offsets_deg[idx]), idx

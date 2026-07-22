"""
Topological/episodic frontier memory — a coverage-based "where have I not been"
signal for the scan macro's cold-start recovery reflex (docs/10_coldstart_engineering.md,
proposal 2 of the post-attempt-#10 research menu, CLAUDE.md).

Deliberately NOT built on ebwm.pt's latent space or goal-centroid distance: attempt
#10 confirmed that distance actively REVERSES direction off the Treechop training
distribution (closer trees score as LESS promising than open, treeless scenes) on
MineRLObtainIronPickaxeDense's free-spawn visual distribution — any frontier
mechanism built on that same metric would inherit the same backwards signal by
construction. Also deliberately NOT built on RNDModule (mine_jepa/ebwm/rnd.py):
attempt #4's instrumented re-run found its online predictor converges within ~150
ticks on whatever narrow visual distribution one episode happens to wander through,
so "novelty" tracked elapsed ticks, not scene content, in exactly this deployment —
reusing that mechanism in a new role would not fix what made it fail in the old one.

Instead: dead-reckoned (x, y, yaw) position estimate, integrated directly from the
SAME discrete action indices already being executed each tick (forward/back/strafe
deltas + cumulative camera yaw, read once from the action map that already defines
what each action does — MineRLObtainIronPickaxeDense exposes no GPS/compass
observation to read this from directly, unlike the Navigate envs), binned into a
coarse visitation-count grid. "Visited" means "dead-reckoning has passed through this
coarse cell before" — a pure integer count table with no learned component and
therefore no way to collapse the way a trained predictor (RND) or a frozen encoder
(goal-centroid distance) can: there is no gradient step anywhere in this module, only
addition.

This is deliberately approximate — no real physics simulation, no collision
detection, a constant configured sprint/no-sprint speed ratio, no correction for
Minecraft's actual movement model. The grid only needs to be self-consistent WITHIN
one episode (has this dead-reckoned position area been visited before, relative to
this episode's own path) to distinguish "probably explored" from "probably fresh
ground," not to reproduce Minecraft's real coordinate system.
"""
from __future__ import annotations

import math

import numpy as np


def build_action_deltas(
    action_map: list[dict], move_step: float = 1.0, sprint_mult: float = 1.6,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Reads the SAME action_map dicts already used to drive the env (configs/
    minerl_actions*.yaml) and derives, for every discrete action index, its
    (forward_delta, strafe_delta, yaw_delta) contribution per real tick — a single
    source of truth shared with the actual env.step() calls, instead of a second,
    independently hardcoded table that could silently drift out of sync.

    Returns three [n_actions] float arrays: d_forward (+ = forward, - = back),
    d_strafe (+ = right, - = left), d_yaw (degrees, + = turn right, matching
    MineRL's camera[1] convention).
    """
    n = len(action_map)
    d_forward = np.zeros(n, dtype=np.float64)
    d_strafe = np.zeros(n, dtype=np.float64)
    d_yaw = np.zeros(n, dtype=np.float64)
    for i, a in enumerate(action_map):
        mult = sprint_mult if a.get("sprint") else 1.0
        if a.get("forward"):
            d_forward[i] += move_step * mult
        if a.get("back"):
            d_forward[i] -= move_step * mult
        if a.get("right"):
            d_strafe[i] += move_step * mult
        if a.get("left"):
            d_strafe[i] -= move_step * mult
        cam = a.get("camera")
        if cam is not None:
            d_yaw[i] += float(cam[1])
    return d_forward, d_strafe, d_yaw


class FrontierTracker:
    """
    Per-episode dead-reckoning + coarse visitation grid.

    update(action) must be called once per REAL environment tick with the applied
    MineRL action dict (the same dict passed to env.step) — camera/movement deltas
    accumulate correctly only at that cadence, not once per `action_repeat` group.

    frontier_heading_deg() / heading_delta_deg() answer "which direction has this
    episode dead-reckoned through the least" — the signal the frontier scan macro
    steers toward when goal_score_std is flat.
    """

    def __init__(
        self, cell_size: float = 4.0, move_step: float = 1.0,
        sprint_mult: float = 1.6, lookahead_cells: float = 2.0,
        n_headings: int = 12,
    ):
        self.cell_size = cell_size
        self.move_step = move_step
        self.sprint_mult = sprint_mult
        self.lookahead_cells = lookahead_cells
        self.n_headings = n_headings
        self.x = 0.0
        self.y = 0.0
        self.yaw_deg = 0.0
        self.visits: dict[tuple[int, int], int] = {}
        self._visit_current()

    def reset(self) -> None:
        """Call at the start of every episode — the grid is per-episode memory,
        not cross-episode (a fresh spawn has no relationship to the last one)."""
        self.x = self.y = self.yaw_deg = 0.0
        self.visits = {}
        self._visit_current()

    def _cell(self, x: float, y: float) -> tuple[int, int]:
        return (int(math.floor(x / self.cell_size)), int(math.floor(y / self.cell_size)))

    def _visit_current(self) -> None:
        c = self._cell(self.x, self.y)
        self.visits[c] = self.visits.get(c, 0) + 1

    @property
    def n_unique_cells(self) -> int:
        return len(self.visits)

    def update(self, action: dict) -> None:
        """Dead-reckon one real environment tick given the applied action dict."""
        cam = action.get("camera")
        if cam is not None:
            self.yaw_deg = (self.yaw_deg + float(cam[1])) % 360.0
        mult = self.sprint_mult if action.get("sprint") else 1.0
        fwd = 0.0
        if action.get("forward"):
            fwd += self.move_step * mult
        if action.get("back"):
            fwd -= self.move_step * mult
        strafe = 0.0
        if action.get("right"):
            strafe += self.move_step * mult
        if action.get("left"):
            strafe -= self.move_step * mult
        if fwd or strafe:
            rad = math.radians(self.yaw_deg)
            self.x += fwd * math.sin(rad) + strafe * math.cos(rad)
            self.y += fwd * math.cos(rad) - strafe * math.sin(rad)
        self._visit_current()

    def frontier_heading_deg(self) -> tuple[float, tuple[int, int], int]:
        """
        Samples n_headings candidate directions around the full circle, each
        projected lookahead_cells*cell_size ahead of the CURRENT dead-reckoned
        position, and returns the one whose target cell has been visited least
        (ties broken by the first checked, i.e. the smallest heading angle).

        Returns (heading_deg, target_cell, target_visit_count).
        """
        best_heading = self.yaw_deg
        best_cell = self._cell(self.x, self.y)
        best_count = None
        look = self.lookahead_cells * self.cell_size
        for i in range(self.n_headings):
            heading = 360.0 * i / self.n_headings
            rad = math.radians(heading)
            tx = self.x + look * math.sin(rad)
            ty = self.y + look * math.cos(rad)
            cell = self._cell(tx, ty)
            count = self.visits.get(cell, 0)
            if best_count is None or count < best_count:
                best_heading, best_cell, best_count = heading, cell, count
        return best_heading, best_cell, best_count if best_count is not None else 0

    def heading_delta_deg(self) -> float:
        """Signed shortest turn (degrees, in [-180, 180]) from the current yaw to
        the current frontier heading. Positive = turn right (MineRL action 12),
        negative = turn left (MineRL action 11)."""
        heading, _, _ = self.frontier_heading_deg()
        return (heading - self.yaw_deg + 180.0) % 360.0 - 180.0

    def heading_to(self, tx: float, ty: float) -> float:
        """Bearing (degrees, same x=sin/y=cos convention as the rest of this
        class) from the CURRENT dead-reckoned position toward an arbitrary
        (tx, ty) point — e.g. the last dead-reckoned position at which the
        hazard reflex (mine_jepa/ebwm/hazard.py) last saw dry ground, so the
        escape can steer toward a remembered point instead of a fixed frontier
        cell. Falls back to the current yaw (no turn) if already there."""
        dx, dy = tx - self.x, ty - self.y
        if dx == 0.0 and dy == 0.0:
            return self.yaw_deg
        return math.degrees(math.atan2(dx, dy)) % 360.0

    def heading_delta_to(self, tx: float, ty: float) -> float:
        """Signed shortest turn (degrees, in [-180, 180]) from the current yaw
        to the bearing toward (tx, ty) — same sign convention as
        heading_delta_deg() (positive = turn right / action 12, negative =
        turn left / action 11)."""
        heading = self.heading_to(tx, ty)
        return (heading - self.yaw_deg + 180.0) % 360.0 - 180.0

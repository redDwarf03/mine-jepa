"""Smoke test (CPU, no MineRL needed) for the cold-start planner changes (docs/10).

Checks:
  1. _sample_actions(sticky=0) is bit-for-bit the original torch.randint draw.
  2. sticky=0.7 produces temporally correlated sequences (repeat rate ~0.72).
  3. DiscreteLatentPlanner.plan: default return unchanged (int), return_info=True
     returns (int, {"goal_score_std": float}), sticky path runs.
  4. SwitchingCraftPlanner.plan: (action, mode) default, (action, mode, info) with
     return_info=True, in both chop and craft modes.

Usage: uv run python scripts/smoke_planner_coldstart.py   (or run.bat on the PC)
"""
import torch

from mine_jepa.ebwm.planner import (
    DiscreteLatentPlanner, SwitchingCraftPlanner, _sample_actions,
)

N, H, A, D, HW = 64, 12, 17, 4, 8

# --- 1. sticky=0 == original i.i.d. draw, same RNG consumption -----------------
torch.manual_seed(123)
a_new = _sample_actions(N, H, A, 0.0, torch.device("cpu"))
torch.manual_seed(123)
a_old = torch.randint(0, A, (N, 1, H))
assert a_new.shape == (N, 1, H) and a_new.dtype == torch.long
assert torch.equal(a_new, a_old), "sticky=0 must be bit-for-bit the original draw"
print("1. sticky_prob=0.0 == original torch.randint     OK")

# --- 2. sticky=0.7 → correlated sequences --------------------------------------
torch.manual_seed(0)
a_sticky = _sample_actions(4096, H, A, 0.7, torch.device("cpu"))
rep = (a_sticky[:, 0, 1:] == a_sticky[:, 0, :-1]).float().mean().item()
# expected repeat rate = sticky + (1-sticky)/A = 0.7 + 0.3/17 ≈ 0.72
assert 0.68 < rep < 0.76, f"repeat rate {rep:.3f} outside expected ~0.72"
iid_rep = (a_old[:, 0, 1:] == a_old[:, 0, :-1]).float().mean().item()
print(f"2. sticky_prob=0.7 repeat rate={rep:.3f} (i.i.d.={iid_rep:.3f})   OK")


# --- 3. DiscreteLatentPlanner ---------------------------------------------------
class StubJepa(torch.nn.Module):
    """Minimal stand-in exposing the interfaces the planners call."""

    def __init__(self):
        super().__init__()
        self.dummy = torch.nn.Parameter(torch.zeros(1))

    def unroll(self, obs, actions, nsteps, unroll_mode, ctxt_window_time, compute_loss):
        n = obs.shape[0]
        g = torch.Generator().manual_seed(0)
        return torch.randn(n, D, 1 + nsteps, HW, HW, generator=g), None


stub = StubJepa()
goal = torch.randn(1, D, HW, HW)
obs = torch.rand(1, 3, 1, 64, 64)

planner = DiscreteLatentPlanner(stub, n_actions=A, horizon=H, n_candidates=N)
a = planner.plan(obs, goal)
assert isinstance(a, int) and 0 <= a < A
a2, info = planner.plan(obs, goal, return_info=True)
assert isinstance(a2, int) and isinstance(info["goal_score_std"], float)
assert info["goal_score_std"] > 0.0
sticky_planner = DiscreteLatentPlanner(stub, n_actions=A, horizon=H,
                                       n_candidates=N, sticky_prob=0.7)
a3 = sticky_planner.plan(obs, goal)
assert isinstance(a3, int) and 0 <= a3 < A
print(f"3. DiscreteLatentPlanner: default=int, info std={info['goal_score_std']:.4f}, "
      f"sticky path runs   OK")


# --- 4. SwitchingCraftPlanner ---------------------------------------------------
class StubCraftWM(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.jepa = StubJepa()
        self.dummy = torch.nn.Parameter(torch.zeros(1))

    def step_inventory(self, inv, action, visual):
        return inv + 0.01 * (action == 17).float().unsqueeze(1)


craft_wm = StubCraftWM()
sw = SwitchingCraftPlanner(craft_wm, chop_goal=goal, item_weights={1: 1.0},
                           log_idx=0, n_actions=22, horizon=H, n_candidates=N,
                           sticky_prob=0.6)
inv_empty = torch.zeros(4)                    # no log → chop
inv_log = torch.zeros(4)
inv_log[0] = 0.5                              # has log → craft
a, mode = sw.plan(obs, inv_empty)
assert mode == "chop" and isinstance(a, int)
a, mode, info = sw.plan(obs, inv_empty, return_info=True)
assert mode == "chop" and isinstance(info["goal_score_std"], float)
a, mode, info = sw.plan(obs, inv_log, return_info=True)
assert mode == "craft" and isinstance(info["goal_score_std"], float)
print("4. SwitchingCraftPlanner: chop/craft, default & return_info   OK")

print("\nALL SMOKE TESTS PASSED")

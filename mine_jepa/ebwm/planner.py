"""
Discrete planner for the action-conditioned world model (Phase 4c).

eb_jepa provides *continuous* CEM/MPPI planners — ill-suited to our 17 discrete
actions. We write a random-shooting MPC that:
  1. samples N discrete action sequences (horizon H)
  2. unrolls them via model.unroll(autoregressive) in SPATIAL latent space
  3. scores each sequence: -MSE(final_latent_state, goal_latent)
  4. returns the 1st action of the best sequence (re-plans every step)

Key difference vs the old LatentMPCPlanner: here states are spatial maps
[D, H', W'] (not a vector), and the WM is action-conditioned and jointly trained
→ the rollout genuinely reflects the effect of actions.
"""
from __future__ import annotations

import torch


class DiscreteLatentPlanner:
    def __init__(self, model, n_actions=17, horizon=12, n_candidates=512, device=None):
        self.model = model
        self.n_actions = n_actions
        self.horizon = horizon
        self.n_candidates = n_candidates
        self.device = device or next(model.parameters()).device

    @torch.no_grad()
    def plan(self, obs_init: torch.Tensor, goal_latents: torch.Tensor) -> int:
        """
        Args:
            obs_init     : [1, 3, 1, 64, 64] — current frame (T=1 context)
            goal_latents : [K, D, H', W'] — K success-scene prototypes (reward>0 frames)
        Returns:
            action (int) — 1st action of the best sequence

        Nearest-neighbor scoring: each sequence is scored by its distance to the
        CLOSEST success prototype (min over K), not a blurry average centroid. The
        planner thus seeks "the most reachable success scene" → more reactive behavior
        (orienting/stopping toward a specific trunk).
        """
        N, H = self.n_candidates, self.horizon
        obs = obs_init.expand(N, -1, -1, -1, -1).contiguous()       # [N,3,1,64,64]
        actions = torch.randint(0, self.n_actions, (N, 1, H), device=self.device)  # [N,1,H]

        # Autoregressive rollout: unroll H steps, keep final state
        predicted, _ = self.model.unroll(
            obs, actions, nsteps=H, unroll_mode="autoregressive",
            ctxt_window_time=1, compute_loss=False,
        )                                                            # [N, D, 1+H, H', W']
        final = predicted[:, :, -1]                                 # [N, D, H', W']

        # MSE distance to each prototype via ||a-b||² = |a|² - 2a·b + |b|² (efficient)
        F = final.shape[1] * final.shape[2] * final.shape[3]
        final_flat = final.reshape(N, F)                            # [N, F]
        goals_flat = goal_latents.reshape(goal_latents.shape[0], F)  # [K, F]
        final_sq = (final_flat ** 2).sum(dim=1, keepdim=True)        # [N, 1]
        goals_sq = (goals_flat ** 2).sum(dim=1).unsqueeze(0)         # [1, K]
        cross = final_flat @ goals_flat.t()                         # [N, K]
        dist = (final_sq - 2 * cross + goals_sq) / F                # [N, K]
        scores = -dist.min(dim=1).values                           # [N]: distance to nearest
        best = scores.argmax()
        return int(actions[best, 0, 0].item())

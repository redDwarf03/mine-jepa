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

Phase 5 novelty extension (Plan2Explore):
  DiscreteLatentPlanner accepts an optional DisagreementEnsemble and a
  novelty_coeff λ.  Score = goal_score + λ · novelty_score, where
  novelty_score = mean disagreement over the H rollout steps.
  novelty_coeff=0.0 (default) reproduces the original behaviour exactly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import torch

if TYPE_CHECKING:
    from mine_jepa.ebwm.curiosity import DisagreementEnsemble


class DiscreteLatentPlanner:
    def __init__(
        self,
        model,
        n_actions: int = 17,
        horizon: int = 12,
        n_candidates: int = 512,
        novelty_coeff: float = 0.0,
        ensemble: "DisagreementEnsemble | None" = None,
        device=None,
    ):
        self.model = model
        self.n_actions = n_actions
        self.horizon = horizon
        self.n_candidates = n_candidates
        self.novelty_coeff = novelty_coeff
        self.ensemble = ensemble
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

        When novelty_coeff > 0 and an ensemble is supplied, the score blends in
        Plan2Explore disagreement:  score = goal_score + λ · novelty_score
        Both terms are z-score normalised across candidates before blending so
        that the relative weight is controlled by λ alone (not by raw magnitudes).
        """
        N, H = self.n_candidates, self.horizon
        obs = obs_init.expand(N, -1, -1, -1, -1).contiguous()       # [N,3,1,64,64]
        actions = torch.randint(0, self.n_actions, (N, 1, H), device=self.device)  # [N,1,H]

        # Autoregressive rollout: unroll H steps, keep all predicted states
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
        goal_scores = -dist.min(dim=1).values                       # [N]: dist to nearest

        if self.novelty_coeff > 0.0 and self.ensemble is not None:
            # Compute disagreement over the H predicted steps (skip context step 0)
            # predicted: [N, D, 1+H, H', W'] → rollout states [N, D, H, H', W']
            rollout_states = predicted[:, :, 1:]                    # [N, D, H, H', W']
            # action_enc: [N, E, H]
            action_enc = self.model.action_encoder(actions)
            # disagreement: [N, H] → mean over H → [N]
            dis = self.ensemble.disagreement(rollout_states, action_enc)  # [N, H]
            novelty_scores = dis.mean(dim=1)                        # [N]

            # z-score normalise both terms (std-safe: add 1e-8)
            g_mu, g_std = goal_scores.mean(), goal_scores.std().clamp(min=1e-8)
            n_mu, n_std = novelty_scores.mean(), novelty_scores.std().clamp(min=1e-8)
            scores = (goal_scores - g_mu) / g_std + self.novelty_coeff * (novelty_scores - n_mu) / n_std
        else:
            scores = goal_scores

        best = scores.argmax()
        return int(actions[best, 0, 0].item())


class CraftPlanner:
    """
    Goal-directed MPC for the inventory/reward-aware WM v3 (CraftWorldModel).

    Instead of steering toward a visual goal latent, it scores each candidate action
    sequence by what the WM PREDICTS will happen to the game state:

        score = w_item * (predicted gain of the target item, e.g. planks)
              + w_reward * (predicted cumulative reward over the rollout)

    The reward/inventory heads turn the latent rollout into a task-grounded objective,
    so MPC naturally selects "craft planks" once the agent holds a log.

    Note on curiosity: true intrinsic motivation (reward = WM prediction error on the
    transitions actually experienced) belongs in the self-play collection loop, not in
    open-loop MPC scoring. This planner is the goal-directed half of the hybrid.
    """

    def __init__(self, model, n_actions=22, horizon=12, n_candidates=512,
                 target_item=1, w_item=1.0, w_reward=0.2, device=None):
        self.model = model                      # CraftWorldModel
        self.n_actions = n_actions
        self.horizon = horizon
        self.n_candidates = n_candidates
        self.target_item = target_item          # index into inventory_items (1 = planks)
        self.w_item = w_item
        self.w_reward = w_reward
        self.device = device or next(model.parameters()).device

    @torch.no_grad()
    def plan(self, obs_init: torch.Tensor) -> int:
        """obs_init: [1, 3, 1, 64, 64]. Returns the 1st action of the best sequence."""
        N, H = self.n_candidates, self.horizon
        obs = obs_init.expand(N, -1, -1, -1, -1).contiguous()       # [N,3,1,64,64]
        actions = torch.randint(0, self.n_actions, (N, 1, H), device=self.device)

        predicted, _ = self.model.jepa.unroll(
            obs, actions, nsteps=H, unroll_mode="autoregressive",
            ctxt_window_time=1, compute_loss=False,
        )                                                            # [N, D, 1+H, H', W']

        rew = self.model.predict_reward(predicted)                   # [N, 1+H]
        inv = self.model.predict_inventory(predicted)                # [N, 1+H, K]

        cum_reward = rew[:, 1:].sum(dim=1)                           # [N] predicted return
        item_gain = inv[:, -1, self.target_item] - inv[:, 0, self.target_item]  # [N]
        scores = self.w_item * item_gain + self.w_reward * cum_reward
        best = scores.argmax()
        return int(actions[best, 0, 0].item())


class CraftPlannerV4:
    """
    MPC for WM v4 (CraftWorldModelV4), where inventory is a real state variable.

    For each candidate action sequence:
      1. unroll the VISUAL latent (eb-JEPA predictor) → perception at each step
      2. roll the INVENTORY forward from the REAL current inventory, using the learned
         dynamics g(inv, action, visual) → predicted inventory at the horizon
      3. score = predicted gain of the target item (e.g. planks)

    Starting the inventory rollout from the agent's TRUE current inventory (known from
    the MineRL obs) makes planning grounded: "if I attack here then craft, do I gain
    planks?" — exactly the question the milestone needs.
    """

    def __init__(self, model, n_actions=22, horizon=12, n_candidates=512,
                 item_weights=None, device=None):
        self.model = model                      # CraftWorldModelV4
        self.n_actions = n_actions
        self.horizon = horizon
        self.n_candidates = n_candidates
        # item_weights: {item_idx: weight}. Default targets planks only. Tech-tree-aware
        # weighting (e.g. {log:1, planks:2}) makes the planner value chopping wood as a
        # stepping stone — without it the planner ignores the hard "get a log" subtask.
        self.item_weights = item_weights or {1: 1.0}
        self.device = device or next(model.parameters()).device

    @torch.no_grad()
    def plan(self, obs_init: torch.Tensor, inv_init: torch.Tensor) -> int:
        """obs_init [1,3,1,64,64]; inv_init [K] normalised current inventory.
        Returns the 1st action of the best sequence."""
        N, H = self.n_candidates, self.horizon
        obs = obs_init.expand(N, -1, -1, -1, -1).contiguous()
        actions = torch.randint(0, self.n_actions, (N, 1, H), device=self.device)

        predicted, _ = self.model.jepa.unroll(
            obs, actions, nsteps=H, unroll_mode="autoregressive",
            ctxt_window_time=1, compute_loss=False,
        )                                                            # [N,D,1+H,H',W']
        vpool = predicted.mean(dim=(3, 4)).permute(0, 2, 1)          # [N, 1+H, D]

        inv = inv_init.to(self.device).unsqueeze(0).expand(N, -1).contiguous()  # [N,K]
        inv0 = inv.clone()
        for h in range(H):
            a = actions[:, 0, h]                                     # [N]
            v = vpool[:, h]                                          # [N,D] (before action h)
            inv = self.model.step_inventory(inv, a, v)              # [N,K]

        gain = inv - inv0                                           # [N,K]
        scores = sum(w * gain[:, idx] for idx, w in self.item_weights.items())
        best = scores.argmax()
        return int(actions[best, 0, 0].item())


class SwitchingCraftPlanner:
    """
    Hierarchical MPC that switches objective by inventory state:

      • NO log   → CHOP objective: steer the visual latent toward a goal-centroid of
                   "log obtained" scenes (the Treechop trick that drives the lumberjack
                   gesture — far more effective at chopping than the weak inventory signal).
      • HAS log  → CRAFT objective: score by predicted inventory gain (Δlog, Δplanks)
                   via the learned dynamics — the model knows craft+log → +planks.

    Combines two validated pieces: chopping (goal-centroid, ~25-50% in Treechop) and
    crafting (WM v4, dPlanks=+4). The planks milestone is then bounded by chopping.
    """

    def __init__(self, model, chop_goal, item_weights, log_idx, n_actions=22,
                 horizon=12, n_candidates=512, log_threshold=0.05, device=None):
        self.model = model
        self.chop_goal = chop_goal              # [1, D, H', W'] visual latent centroid
        self.item_weights = item_weights        # {idx: weight} for the craft objective
        self.log_idx = log_idx
        self.n_actions = n_actions
        self.horizon = horizon
        self.n_candidates = n_candidates
        self.log_threshold = log_threshold      # normalised; 0.05 ≈ 0.5 raw logs
        self.device = device or next(model.parameters()).device

    @torch.no_grad()
    def plan(self, obs_init: torch.Tensor, inv_init: torch.Tensor) -> tuple[int, str]:
        """Returns (action, mode) where mode ∈ {'chop','craft'}."""
        N, H = self.n_candidates, self.horizon
        obs = obs_init.expand(N, -1, -1, -1, -1).contiguous()
        actions = torch.randint(0, self.n_actions, (N, 1, H), device=self.device)
        predicted, _ = self.model.jepa.unroll(
            obs, actions, nsteps=H, unroll_mode="autoregressive",
            ctxt_window_time=1, compute_loss=False,
        )                                                            # [N,D,1+H,H',W']

        has_log = float(inv_init[self.log_idx]) >= self.log_threshold
        if not has_log:
            # CHOP: minimise distance of the final visual latent to the chop-goal centroid
            final = predicted[:, :, -1]                              # [N,D,H',W']
            Fdim = final.shape[1] * final.shape[2] * final.shape[3]
            ff = final.reshape(N, Fdim)
            gf = self.chop_goal.reshape(1, Fdim)
            dist = ((ff - gf) ** 2).mean(dim=1)                      # [N]
            best = (-dist).argmax()
            return int(actions[best, 0, 0].item()), "chop"

        # CRAFT: maximise predicted inventory gain
        vpool = predicted.mean(dim=(3, 4)).permute(0, 2, 1)          # [N,1+H,D]
        inv = inv_init.to(self.device).unsqueeze(0).expand(N, -1).contiguous()
        inv0 = inv.clone()
        for h in range(H):
            inv = self.model.step_inventory(inv, actions[:, 0, h], vpool[:, h])
        gain = inv - inv0
        scores = sum(w * gain[:, idx] for idx, w in self.item_weights.items())
        best = scores.argmax()
        return int(actions[best, 0, 0].item()), "craft"

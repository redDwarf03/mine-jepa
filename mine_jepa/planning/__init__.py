"""
Mine-JEPA — Phase 3: planning in latent space (discrete actions).

LatentMPCPlanner — random-shooting MPC:
  1. Sample N random action sequences (horizon H)
  2. Unroll the world model for each sequence → final latent state
  3. Score: -MSE(final_state, goal_embedding)
  4. Return the first action of the best sequence

This is simplified "open-loop" MPC. At each step we re-plan from the
current state → robustness to world model errors.

Why not full CEM? For 17 discrete actions of Crafter, random shooting
with N=512 sequences is sufficient and < 5ms/step on GPU.

Pedagogy: docs/05_planning.md
"""
import torch
import torch.nn as nn


class LatentMPCPlanner:
    """
    Latent-space random-shooting MPC.

    Each call to plan() samples n_candidates action sequences, unrolls
    them through the world model, and returns the first action of the
    sequence whose final state is closest to the goal_embedding.
    """

    def __init__(
        self,
        predictor: nn.Module,
        n_actions: int = 17,
        horizon: int = 12,
        n_candidates: int = 512,
        device: torch.device = None,
    ):
        self.predictor = predictor
        self.n_actions = n_actions
        self.horizon = horizon
        self.n_candidates = n_candidates
        if device is not None:
            self.device = device
        else:
            # Infer from the predictor to avoid device mismatches
            try:
                self.device = next(predictor.parameters()).device
            except StopIteration:
                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    @torch.no_grad()
    def plan(self, s_current: torch.Tensor, s_goal: torch.Tensor) -> int:
        """
        Args:
            s_current : [1, D] or [D] — current latent state
            s_goal    : [1, D] or [D] — target latent state
        Returns:
            action (int) — index of the best first action
        """
        s_current = s_current.view(1, -1).to(self.device)
        s_goal = s_goal.view(1, -1).to(self.device)

        # [N, D]: N copies of the current state
        s = s_current.expand(self.n_candidates, -1).clone()

        # [N, H]: random action sequences
        actions = torch.randint(
            0, self.n_actions,
            (self.n_candidates, self.horizon),
            device=self.device,
        )

        # Rollout
        for h in range(self.horizon):
            a = actions[:, h]          # [N]
            s = self.predictor(s, a)   # [N, D]

        # Score: -MSE(final_state, goal). Higher is better.
        scores = -(s - s_goal).pow(2).mean(dim=1)  # [N]

        best = scores.argmax()
        return actions[best, 0].item()

    @torch.no_grad()
    def rollout(self, s_start: torch.Tensor, action_seq: torch.Tensor) -> list:
        """
        Unroll an action sequence from s_start.
        Used for world model "imagination" visualization.

        Args:
            s_start    : [D]
            action_seq : [H] int64
        Returns:
            list of H tensors [D] — imagined latent states
        """
        s = s_start.view(1, -1).to(self.device)
        states = []
        for a in action_seq:
            s = self.predictor(s, a.unsqueeze(0).to(self.device))
            states.append(s.squeeze(0).cpu())
        return states

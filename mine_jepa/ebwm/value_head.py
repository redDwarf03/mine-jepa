"""
Distance projector for goal-conditioned MPC (Destrade et al., arXiv:2601.00844).

Cold-start attempts #1-#6 (docs/10_coldstart_engineering.md) all worked AROUND the
same flatness: the raw-latent goal score (untrained L2/cosine on ebwm.pt's latent
maps) goes flat/undiscriminating whenever no tree is in view, and every downstream
mechanism (search macro, novelty bonus, elite-refit) either does nothing or makes
things worse against that flatness. This module targets the flatness itself.

Architecture (matches the cited paper, NOT an MLP(z_t, z_goal)->scalar regressor):
  A small shared projector P maps a flattened visual latent -> a lower-dim vector,
  applied INDEPENDENTLY to z_t and z_goal (same weights). Euclidean distance in the
  projected space, ||P(z_t) - P(z_goal)||, is trained to approximate the number of
  actions between the two states (a temporal-distance / cost-to-go metric). This
  keeps the planner's existing multi-goal-centroid batched scoring pattern
  (pairwise [N,K] distances) and, unlike an unconstrained scalar regressor, stays a
  constrained METRIC (triangle inequality, non-negativity) — the property that
  should extrapolate more predictably to out-of-distribution "lost" states, which is
  the actual failure mode this module exists to fix.

ebwm.pt is always frozen upstream of this module: DistanceProjector only ever
consumes flattened latents that were already produced with no_grad/detach by the
caller (mirrors mine_jepa/ebwm/rnd.py and curiosity.py's isolation discipline).
"""
from __future__ import annotations

import torch
import torch.nn as nn


class DistanceProjector(nn.Module):
    """
    P: flattened visual latent [*, F] -> projected vector [*, proj_dim].

    Args:
        in_dim     : F, flattened latent dimension (D * H' * W' of the frozen WM's
                     encode() output — read at training time from an actual encode
                     call, never hardcoded).
        hidden_dim : hidden width of the 2-layer MLP.
        proj_dim   : output projection dimension.
    """

    def __init__(self, in_dim: int, hidden_dim: int = 256, proj_dim: int = 32):
        super().__init__()
        self.in_dim = in_dim
        self.hidden_dim = hidden_dim
        self.proj_dim = proj_dim
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Linear(hidden_dim, proj_dim),
        )

    def project(self, z_flat: torch.Tensor) -> torch.Tensor:
        """[*, in_dim] -> [*, proj_dim]."""
        return self.net(z_flat)

    def dist(self, z_a_flat: torch.Tensor, z_b_flat: torch.Tensor) -> torch.Tensor:
        """Elementwise (paired) Euclidean distance. [N, F], [N, F] -> [N]."""
        pa, pb = self.project(z_a_flat), self.project(z_b_flat)
        return (pa - pb).norm(dim=-1)

    def pairwise_dist(self, z_a_flat: torch.Tensor, z_b_flat: torch.Tensor) -> torch.Tensor:
        """
        Batched Euclidean distance, [N, F] vs [K, F] -> [N, K]. Matches the
        multi-goal-centroid pattern already used by DiscreteLatentPlanner._score()
        (nearest-goal scoring via min over K), just fed a trained metric instead
        of raw-latent squared L2.
        """
        pa, pb = self.project(z_a_flat), self.project(z_b_flat)
        return torch.cdist(pa, pb, p=2)

    def save(self, path: str) -> None:
        torch.save({
            "state_dict": self.state_dict(),
            "cfg": {"in_dim": self.in_dim, "hidden_dim": self.hidden_dim, "proj_dim": self.proj_dim},
        }, path)

    @classmethod
    def load(cls, path: str, device: torch.device | str | None = None) -> "DistanceProjector":
        ckpt = torch.load(path, map_location=device or "cpu", weights_only=False)
        cfg = ckpt["cfg"]
        proj = cls(in_dim=cfg["in_dim"], hidden_dim=cfg["hidden_dim"], proj_dim=cfg["proj_dim"])
        proj.load_state_dict(ckpt["state_dict"])
        if device is not None:
            proj = proj.to(device)
        proj.eval()
        return proj

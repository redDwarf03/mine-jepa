"""
BC actor — a learned prior over next actions, used to PROPOSE MPC candidates
(docs/10_coldstart_engineering.md, cold-start attempt #8, Proposal B).

Attempts #4-#7 diagnosed the cold-start wall as BEHAVIOURAL, not perceptual: the
world model already scores situations correctly (attempt #7's own offline gate
proves that), but the 512 i.i.d./sticky-sampled candidate sequences the MPC
evaluates essentially never contain the right sustained gesture in the first
place. Proposal A (mine_jepa/ebwm/planner.py::_build_primed_macros) put a
handful of hand-authored macros directly into the candidate pool; this module
replaces "hand-authored" with "learned from expert demonstrations + coverage
episodes": a small classifier on frozen ebwm.pt latents, trained by
behavioural cloning, whose per-action probabilities seed a slice of the
candidate pool (see planner.py::_sample_actor_macros).

This is NOT a repeat of Phase 4's failed pure-BC approach (reward 0, covariate
shift): there, BC was the FINAL policy, executed open-loop with no correction.
Here the actor only PROPOSES action sequences — DiscreteLatentPlanner /
SwitchingCraftPlanner's own world-model-based MPC scoring still evaluates
every candidate (actor-proposed AND sticky/i.i.d./primed) and re-plans every
step, which is the mechanism that corrects for the actor's drift.

ebwm.pt is always frozen upstream of this module: BCActor only ever consumes
flattened latents produced with no_grad/detach by the caller — same isolation
discipline as rnd.py, curiosity.py, and value_head.py.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class BCActor(nn.Module):
    """
    A small MLP classifier: flattened visual latent [*, in_dim] -> logits over
    n_actions. Trained on the 17 shared movement-action indices (0-16,
    identical in configs/minerl_actions.yaml and minerl_actions_obtain.yaml).

    Args:
        in_dim     : F, flattened latent dim (D*H'*W' of the frozen WM's
                     encode() output — read at training time from an actual
                     encode call, never hardcoded).
        n_actions  : number of discrete actions the actor predicts over.
        hidden_dim : hidden width of the 3-layer MLP.
    """

    def __init__(self, in_dim: int, n_actions: int = 17, hidden_dim: int = 256):
        super().__init__()
        self.in_dim = in_dim
        self.n_actions = n_actions
        self.hidden_dim = hidden_dim
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Linear(hidden_dim, n_actions),
        )

    def forward(self, z_flat: torch.Tensor) -> torch.Tensor:
        """[*, in_dim] -> [*, n_actions] logits (unnormalised)."""
        return self.net(z_flat)

    @torch.no_grad()
    def action_probs(self, z_flat: torch.Tensor, temperature: float = 1.0) -> torch.Tensor:
        """[*, in_dim] -> [*, n_actions] softmax probabilities at `temperature`."""
        logits = self.forward(z_flat) / max(float(temperature), 1e-6)
        return torch.softmax(logits, dim=-1)

    def save(self, path: str) -> None:
        torch.save({
            "state_dict": self.state_dict(),
            "cfg": {"in_dim": self.in_dim, "n_actions": self.n_actions, "hidden_dim": self.hidden_dim},
        }, path)

    @classmethod
    def load(cls, path: str, device: torch.device | str | None = None) -> "BCActor":
        ckpt = torch.load(path, map_location=device or "cpu", weights_only=False)
        cfg = ckpt["cfg"]
        actor = cls(in_dim=cfg["in_dim"], n_actions=cfg["n_actions"], hidden_dim=cfg["hidden_dim"])
        actor.load_state_dict(ckpt["state_dict"])
        if device is not None:
            actor = actor.to(device)
        actor.eval()
        return actor

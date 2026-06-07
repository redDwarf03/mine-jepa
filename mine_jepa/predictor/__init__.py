"""
Mine-JEPA — Phase 2: action-conditioned predictor.

The predictor takes (s_t, a_t) and predicts ŝ_{t+1} in latent space.
This is the core of the world model: it "imagines" the consequence of an
action without ever touching the real environment.

Architecture: action-embedding + MLP (ESANN 2025 recipe).
  a_t  → Embedding(17, action_dim) → a_emb [B, action_dim]
  s_t  ──────────────────────────────────── [B, embed_dim]
  concat([s_t, a_emb])  →  MLP(3 layers)  →  ŝ_{t+1} [B, embed_dim]

Pedagogy: see docs/04_world_model.md.
"""
import torch
import torch.nn as nn


class ActionConditionedPredictor(nn.Module):
    """
    Predicts the next latent state ŝ_{t+1} = f(s_t, a_t).

    Deliberately small (< 1M params): information should live in the
    ENCODER (Phase 1), not the predictor. An oversized predictor would
    compensate for a poor encoder.
    """

    def __init__(
        self,
        embed_dim: int = 128,
        n_actions: int = 17,
        action_dim: int = 32,
        hidden_dim: int = 256,
    ):
        super().__init__()
        self.action_embed = nn.Embedding(n_actions, action_dim)
        self.net = nn.Sequential(
            nn.Linear(embed_dim + action_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, embed_dim),
        )

    def forward(self, s: torch.Tensor, a: torch.Tensor) -> torch.Tensor:
        """
        Args:
            s : [B, embed_dim]  — current latent state (frozen encoder)
            a : [B]             — discrete action (int64)
        Returns:
            ŝ_{t+1} : [B, embed_dim]
        """
        a_emb = self.action_embed(a)          # [B, action_dim]
        x = torch.cat([s, a_emb], dim=-1)    # [B, embed_dim + action_dim]
        return self.net(x)                    # [B, embed_dim]

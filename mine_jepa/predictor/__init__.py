"""
Mine-JEPA — Phase 2 : predictor action-conditionné.

Le predictor reçoit (s_t, a_t) et prédit ŝ_{t+1} dans l'espace latent.
C'est le cœur du world model : il "imagine" la conséquence d'une action
sans jamais toucher l'environnement réel.

Architecture : action-embedding + MLP (recette ESANN 2025).
  a_t  → Embedding(17, action_dim) → a_emb [B, action_dim]
  s_t  ──────────────────────────────────── [B, embed_dim]
  concat([s_t, a_emb])  →  MLP(3 couches)  →  ŝ_{t+1} [B, embed_dim]

Pédagogie : voir docs/04_world_model.md.
"""
import torch
import torch.nn as nn


class ActionConditionedPredictor(nn.Module):
    """
    Prédit le prochain état latent ŝ_{t+1} = f(s_t, a_t).

    Délibérément petit (< 1M params) : on veut que l'information soit
    dans l'ENCODEUR (Phase 1), pas dans le predictor. Un predictor
    surdimensionné compenserait un mauvais encodeur.
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
            s : [B, embed_dim]  — état latent courant (encodeur gelé)
            a : [B]             — action discrète (int64)
        Returns:
            ŝ_{t+1} : [B, embed_dim]
        """
        a_emb = self.action_embed(a)          # [B, action_dim]
        x = torch.cat([s, a_emb], dim=-1)    # [B, embed_dim + action_dim]
        return self.net(x)                    # [B, embed_dim]

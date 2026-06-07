"""
Mine-JEPA — Phase 1: JEPA encoder for Crafter.

Architecture:
  CrafterEncoder      — ResNet5 → avgpool → latent vector [B, D]
  EMATargetEncoder    — EMA copy of CrafterEncoder, no gradient
  FramePredictor      — 2-layer MLP: [B, D] → [B, D]
  CrafterJEPA         — loss = L_JEPA + VICReg (variance + covariance)

Pedagogy: see docs/01_jepa.md and docs/03_representation_collapse.md.
"""
import copy

import torch
import torch.nn as nn
import torch.nn.functional as F

from mine_jepa.eb_jepa.architectures import ResNet5
from mine_jepa.eb_jepa.losses import CovarianceLoss, HingeStdLoss


class CrafterEncoder(nn.Module):
    """
    Encodes a Crafter frame (64×64 RGB) into a latent vector [B, D].

    Uses ResNet5 (eb_jepa) followed by global avg-pool.
    The avg-pool is crucial: it produces a *flat* vector on which
    VICReg regularization and linear-probe can be applied directly.
    """

    def __init__(self, embed_dim: int = 128, hidden_dim: int = 64):
        super().__init__()
        self.net = ResNet5(
            in_d=3,
            h_d=hidden_dim,
            out_d=embed_dim,
            s1=2,
            s2=2,
            s3=2,
            avg_pool=True,  # → output [B, embed_dim] (no spatial dims)
        )
        self.embed_dim = embed_dim

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [B, 3, H, W] float32 dans [0, 1]
        Returns:
            [B, embed_dim]
        """
        return self.net(x)


class EMATargetEncoder(nn.Module):
    """
    EMA (Exponential Moving Average) copy of the context encoder.

    Weights are NEVER updated by backprop — only via update().
    This is countermeasure #1 against collapse: if target weights move
    slowly, the prediction target remains non-trivial.

    EMA formula: θ̄ ← decay · θ̄ + (1 - decay) · θ
    """

    def __init__(self, source: CrafterEncoder, decay: float = 0.99):
        super().__init__()
        self.decay = decay
        self.net = copy.deepcopy(source)
        # No gradient: target encoder is frozen between EMA updates
        for p in self.net.parameters():
            p.requires_grad_(False)

    @torch.no_grad()
    def update(self, source: CrafterEncoder) -> None:
        """Updates EMA weights from the context encoder."""
        for ema_p, src_p in zip(self.net.parameters(), source.parameters()):
            ema_p.data.mul_(self.decay).add_(src_p.data, alpha=1.0 - self.decay)

    @torch.no_grad()
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class FramePredictor(nn.Module):
    """
    2-layer MLP that predicts the next frame's embedding.

    Receives s_x (current frame embedding) → predicts ŝ_{t+1}.
    Intentionally small: information should be in the encoder, not the
    predictor. (An oversized predictor can compensate for a weak encoder.)
    """

    def __init__(self, embed_dim: int = 128, hidden_dim: int = 256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(embed_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, embed_dim),
        )

    def forward(self, s: torch.Tensor) -> torch.Tensor:
        return self.net(s)


class CrafterJEPA(nn.Module):
    """
    Complete JEPA model for Phase 1 (no action conditioning).

    Total loss = L_JEPA + λ_std · L_std + λ_cov · L_cov

    - L_JEPA: MSE between prediction and EMA target (stop-gradient)
    - L_std : penalizes too-low embedding variance (anti-collapse)
    - L_cov : penalizes inter-dimension correlations (decorrelation)

    Call update_ema() after each batch to propagate weights.
    """

    def __init__(
        self,
        embed_dim: int = 128,
        hidden_dim: int = 64,
        predictor_hidden: int = 256,
        ema_decay: float = 0.99,
        std_coeff: float = 1.0,
        cov_coeff: float = 0.04,
    ):
        super().__init__()
        self.encoder = CrafterEncoder(embed_dim, hidden_dim)
        self.target_encoder = EMATargetEncoder(self.encoder, decay=ema_decay)
        self.predictor = FramePredictor(embed_dim, predictor_hidden)

        # Anti-collapse: variance + covariance on embeddings
        self.std_loss_fn = HingeStdLoss(std_margin=1.0)
        self.cov_loss_fn = CovarianceLoss()
        self.std_coeff = std_coeff
        self.cov_coeff = cov_coeff

    def update_ema(self) -> None:
        """Call after each optimization step."""
        self.target_encoder.update(self.encoder)

    def forward(
        self, x_context: torch.Tensor, x_target: torch.Tensor
    ) -> dict[str, torch.Tensor]:
        """
        Args:
            x_context : [B, 3, H, W] — current frame, float [0,1]
            x_target  : [B, 3, H, W] — next frame (target)
        Returns:
            dict with total_loss, jepa_loss, std_loss, cov_loss, batch_var
        """
        # Encode current frame (gradient flows through)
        s_x = self.encoder(x_context)  # [B, D]

        # Encode next frame via EMA (no gradient)
        s_y = self.target_encoder(x_target)  # [B, D]

        # Predict next state in latent space
        s_hat = self.predictor(s_x)  # [B, D]

        # L_JEPA: predicts s_y, but s_y is stop-gradient
        # (target encoder NEVER receives direct gradient)
        jepa_loss = F.mse_loss(s_hat, s_y.detach())

        # VICReg: anti-collapse on context encoder embeddings
        std_loss = self.std_loss_fn(s_x)  # penalizes var < 1
        cov_loss = self.cov_loss_fn(s_x)  # penalizes correlations

        total_loss = jepa_loss + self.std_coeff * std_loss + self.cov_coeff * cov_loss

        # Collapse indicator: if batch_var < 1e-6, model is collapsing
        batch_var = s_x.var(dim=0).mean().item()

        return {
            "total": total_loss,
            "jepa": jepa_loss,
            "std": std_loss,
            "cov": cov_loss,
            "batch_var": batch_var,
        }

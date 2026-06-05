"""
Mine-JEPA — Phase 1 : encodeur JEPA pour Crafter.

Architecture :
  CrafterEncoder      — ResNet5 → avgpool → vecteur latent [B, D]
  EMATargetEncoder    — copie EMA de CrafterEncoder, aucun gradient
  FramePredictor      — MLP 2-couches : [B, D] → [B, D]
  CrafterJEPA         — loss = L_JEPA + VICReg (variance + covariance)

Pédagogie : voir docs/01_jepa.md et docs/03_representation_collapse.md.
"""
import copy

import torch
import torch.nn as nn
import torch.nn.functional as F

from mine_jepa.eb_jepa.architectures import ResNet5
from mine_jepa.eb_jepa.losses import CovarianceLoss, HingeStdLoss


class CrafterEncoder(nn.Module):
    """
    Encode une frame Crafter (64×64 RGB) en vecteur latent [B, D].

    Utilise ResNet5 (eb_jepa) suivi d'un avg-pool global.
    L'avg-pool est crucial : il produit un vecteur *plat* sur lequel
    la régularisation VICReg et le linear-probe sont applicables directement.
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
            avg_pool=True,  # → sortie [B, embed_dim] (pas de dims spatiales)
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
    Copie EMA (Exponential Moving Average) de l'encodeur de contexte.

    Les poids ne sont JAMAIS mis à jour par backprop — seulement via update().
    C'est la parade n°1 contre le collapse : si les poids du target bougent
    doucement, la cible de prédiction reste non-triviale.

    Formule EMA : θ̄ ← decay · θ̄ + (1 - decay) · θ
    """

    def __init__(self, source: CrafterEncoder, decay: float = 0.99):
        super().__init__()
        self.decay = decay
        self.net = copy.deepcopy(source)
        # Aucun gradient : le target encoder est gelé entre les updates EMA
        for p in self.net.parameters():
            p.requires_grad_(False)

    @torch.no_grad()
    def update(self, source: CrafterEncoder) -> None:
        """Met à jour les poids EMA depuis l'encodeur de contexte."""
        for ema_p, src_p in zip(self.net.parameters(), source.parameters()):
            ema_p.data.mul_(self.decay).add_(src_p.data, alpha=1.0 - self.decay)

    @torch.no_grad()
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class FramePredictor(nn.Module):
    """
    MLP 2-couches qui prédit l'embedding de la frame suivante.

    Reçoit s_x (embedding de la frame courante) → prédit ŝ_{t+1}.
    Volontairement petit : on veut que l'information soit dans l'encodeur,
    pas dans le predictor. (Si le predictor est trop gros, il peut compenser
    un mauvais encodeur.)
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
    Modèle JEPA complet pour Phase 1 (sans action conditioning).

    Loss totale = L_JEPA + λ_std · L_std + λ_cov · L_cov

    - L_JEPA : MSE entre prédiction et cible EMA (stop-gradient)
    - L_std  : pénalise la variance trop faible des embeddings (anti-collapse)
    - L_cov  : pénalise les corrélations entre dimensions (décorrélation)

    Après chaque batch, appeler update_ema() pour propager les poids.
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

        # Anti-collapse : variance + covariance sur les embeddings
        self.std_loss_fn = HingeStdLoss(std_margin=1.0)
        self.cov_loss_fn = CovarianceLoss()
        self.std_coeff = std_coeff
        self.cov_coeff = cov_coeff

    def update_ema(self) -> None:
        """À appeler après chaque step d'optimisation."""
        self.target_encoder.update(self.encoder)

    def forward(
        self, x_context: torch.Tensor, x_target: torch.Tensor
    ) -> dict[str, torch.Tensor]:
        """
        Args:
            x_context : [B, 3, H, W] — frame courante, float [0,1]
            x_target  : [B, 3, H, W] — frame suivante (cible)
        Returns:
            dict avec total_loss, jepa_loss, std_loss, cov_loss, batch_var
        """
        # Encode la frame courante (gradient propagé)
        s_x = self.encoder(x_context)  # [B, D]

        # Encode la frame suivante via EMA (pas de gradient)
        s_y = self.target_encoder(x_target)  # [B, D]

        # Prédit l'état suivant en latent
        s_hat = self.predictor(s_x)  # [B, D]

        # L_JEPA : on prédit s_y, mais s_y est stop-gradient
        # (le target encoder ne reçoit JAMAIS de gradient direct)
        jepa_loss = F.mse_loss(s_hat, s_y.detach())

        # VICReg : anti-collapse sur les embeddings du context encoder
        std_loss = self.std_loss_fn(s_x)  # pénalise var < 1
        cov_loss = self.cov_loss_fn(s_x)  # pénalise corrélations

        total_loss = jepa_loss + self.std_coeff * std_loss + self.cov_coeff * cov_loss

        # Indicateur de collapse : si batch_var < 1e-6, le modèle collapse
        batch_var = s_x.var(dim=0).mean().item()

        return {
            "total": total_loss,
            "jepa": jepa_loss,
            "std": std_loss,
            "cov": cov_loss,
            "batch_var": batch_var,
        }

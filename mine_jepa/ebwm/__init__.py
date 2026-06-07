"""
Mine-JEPA — Phase 4c: action-conditioned world model (Meta's eb_jepa).

Why this approach (vs previous failures):
  - The old JEPA encoder produced a flat 128-d VECTOR → lost spatial info
    ("where is the trunk"). Here: latent maps [D, 8, 8] that preserve it.
  - The old WM was trained ON a frozen frame→frame encoder (non action-aware)
    → ratio 0.959 useless. Here: encoder + predictor trained JOINTLY,
    conditioned on action → latent is structured around action consequences.

This module assembles Meta building blocks (ResNet5, JEPA, anti-collapse regularizer)
with two custom pieces for our 17 discrete actions (eb_jepa targets continuous):
  - DiscreteActionEncoder: indices → embedding
  - ACConvPredictor: concatenates latent state + action (spatially broadcast)

Risk #1 = collapse (see CLAUDE.md) → VC_IDM_Sim_Regularizer always enabled.
"""
from __future__ import annotations

import torch
import torch.nn as nn

from mine_jepa.eb_jepa.architectures import ResidualBlock, ResNet5
from mine_jepa.eb_jepa.jepa import JEPA
from mine_jepa.eb_jepa.losses import SquareLossSeq, VC_IDM_Sim_Regularizer
from mine_jepa.eb_jepa.nn_utils import TemporalBatchMixin


class DiscreteActionEncoder(nn.Module):
    """
    17 discrete actions → continuous embedding.

    JEPA.unroll calls action_encoder(actions) with actions [B, 1, T] (long indices).
    Output: [B, embed_dim, T] — spatially broadcast by the predictor.
    """

    def __init__(self, n_actions: int = 17, embed_dim: int = 16):
        super().__init__()
        self.embed = nn.Embedding(n_actions, embed_dim)
        self.embed_dim = embed_dim

    def forward(self, actions: torch.Tensor) -> torch.Tensor:
        # actions: [B, 1, T] long → [B, T] → embed → [B, T, E] → [B, E, T]
        idx = actions.squeeze(1).long()
        emb = self.embed(idx)                  # [B, T, E]
        return emb.permute(0, 2, 1)            # [B, E, T]


class _PerFrameConv(TemporalBatchMixin, nn.Module):
    """Conv backbone applied frame-by-frame (T folded into B via the mixin), H/W preserved."""

    def __init__(self, in_d: int, h_d: int, out_d: int):
        super().__init__()
        self.conv1 = nn.Conv2d(in_d, h_d, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(h_d)
        self.relu = nn.ReLU(inplace=True)
        self.block1 = ResidualBlock(h_d, h_d, stride=1)
        self.block2 = ResidualBlock(h_d, out_d, stride=1)

    def _forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.block1(out)
        out = self.block2(out)
        return out


class ACConvPredictor(nn.Module):
    """
    Action-conditioned predictor: (latent_state_t, action_t) → latent_state_{t+1}.

    Concatenates state [B,D,T,H,W] and embedded action [B,E,T] (broadcast over H,W)
    on the channel axis, then passes through a conv backbone that preserves T, H, W.

    Residual connection: predicts the latent DELTA (state_{t+1} - state_t), not the
    absolute state. So "do nothing" = copy the state → ratio ≤ 1 guaranteed,
    and the backbone only learns the action-induced correction. This is the standard
    trick that unlocks latent world models.

    Interface expected by JEPA.unroll:
      - is_rnn attribute (False) and context_length (1)
      - forward(state, action_enc) → [B, D, T, H, W]
    """

    is_rnn = False

    def __init__(self, state_dim: int, action_embed_dim: int, hidden_dim: int = 128, context_length: int = 1):
        super().__init__()
        self.context_length = context_length
        self.action_embed_dim = action_embed_dim
        self.backbone = _PerFrameConv(state_dim + action_embed_dim, hidden_dim, state_dim)

    def forward(self, state: torch.Tensor, action_enc: torch.Tensor | None) -> torch.Tensor:
        b, d, t, h, w = state.shape
        if action_enc is None:
            a = torch.zeros(b, self.action_embed_dim, t, h, w, device=state.device, dtype=state.dtype)
        else:
            a = action_enc.view(b, self.action_embed_dim, t, 1, 1).expand(-1, -1, -1, h, w)
        x = torch.cat([state, a], dim=1)       # [B, D+E, T, H, W]
        delta = self.backbone(x)               # [B, D, T, H, W]
        return state + delta                   # residual: copy + correction


def build_ac_jepa(
    embed_dim: int = 64,
    encoder_hidden: int = 32,
    n_actions: int = 17,
    action_embed_dim: int = 16,
    predictor_hidden: int = 128,
    std_coeff: float = 10.0,
    cov_coeff: float = 1.0,
    sim_coeff_t: float = 0.0,
) -> JEPA:
    """
    Assembles a ready-to-train action-conditioned JEPA.

    encoder    : ResNet5 → latent maps [B, embed_dim, T, 8, 8] (64×64 input)
    aencoder   : DiscreteActionEncoder (17 actions → embedding)
    predictor  : ACConvPredictor (single-step latent, context_length=1)
    regularizer: VC_IDM_Sim_Regularizer (anti-collapse VICReg + temporal similarity)
    predcost   : SquareLossSeq (latent MSE)
    """
    encoder = ResNet5(
        in_d=3, h_d=encoder_hidden, out_d=embed_dim,
        s1=2, s2=2, s3=2, avg_pool=False,
    )
    aencoder = DiscreteActionEncoder(n_actions=n_actions, embed_dim=action_embed_dim)
    predictor = ACConvPredictor(
        state_dim=embed_dim, action_embed_dim=action_embed_dim,
        hidden_dim=predictor_hidden, context_length=1,
    )
    # spatial_as_samples=False: variance is measured BETWEEN batch samples
    # (x_for_vc = [B*T, C*H*W]) — that's the collapse that matters. With True, the
    # regularizer only saw inter-pixel variance (blind to batch collapse).
    regularizer = VC_IDM_Sim_Regularizer(
        cov_coeff=cov_coeff, std_coeff=std_coeff, sim_coeff_t=sim_coeff_t,
        idm_coeff=0.0, idm=None, first_t_only=False, spatial_as_samples=False,
    )
    predcost = SquareLossSeq()
    return JEPA(encoder, aencoder, predictor, regularizer, predcost)

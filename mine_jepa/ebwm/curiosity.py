"""
Plan2Explore-style disagreement ensemble for open-loop novelty bonuses.

Mirrors the architecture of ACConvPredictor (the main WM predictor) but wraps
k independent small heads that each predict the *next* latent [D, H', W'] given
(state_t, action_t).  Novelty = variance across heads = epistemic uncertainty.

Key design constraints:
  - Trained on FROZEN eb-JEPA latents only → SEPARATE optimizer, never touches
    the main WM or its checkpoint (ebwm.pt).
  - Detached latents everywhere → cannot corrupt the main WM's anti-collapse
    safeguards (VICReg / EMA target).
  - Lightweight: k heads × a small 3-layer conv stack → ~k×0.3M params total.
  - Operates on latent maps [D, H', W'] (spatial, same as DiscreteLatentPlanner),
    NOT on flattened vectors, so H'/W' structure is preserved.

Usage (plan-time):
    ens = DisagreementEnsemble.load("checkpoints/curiosity_ensemble.pt", device)
    novelty = ens.disagreement(latents, actions)   # [N, T] variance per step
"""
from __future__ import annotations

import torch
import torch.nn as nn


class _EnsHead(nn.Module):
    """
    One ensemble member: (state [B,D,T,H,W], action_enc [B,E,T]) → next_state [B,D,T,H,W].

    Architecture mirrors ACConvPredictor (3×3 conv + BN + ReLU + two residual conv
    blocks), but with a smaller hidden dim so the ensemble stays cheap.
    Residual connection (predict delta) keeps training stable.
    """

    def __init__(self, state_dim: int, action_embed_dim: int, hidden_dim: int = 64):
        super().__init__()
        in_ch = state_dim + action_embed_dim
        self.stem = nn.Sequential(
            nn.Conv2d(in_ch, hidden_dim, 3, padding=1, bias=False),
            nn.BatchNorm2d(hidden_dim),
            nn.ReLU(inplace=True),
        )
        self.res1 = nn.Sequential(
            nn.Conv2d(hidden_dim, hidden_dim, 3, padding=1, bias=False),
            nn.BatchNorm2d(hidden_dim),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden_dim, hidden_dim, 3, padding=1, bias=False),
            nn.BatchNorm2d(hidden_dim),
        )
        self.res2 = nn.Sequential(
            nn.Conv2d(hidden_dim, state_dim, 3, padding=1, bias=False),
            nn.BatchNorm2d(state_dim),
        )
        self.relu = nn.ReLU(inplace=True)

    def forward(self, state: torch.Tensor, action_enc: torch.Tensor) -> torch.Tensor:
        """
        state      : [B, D, T, H, W]
        action_enc : [B, E, T]
        Returns    : [B, D, T, H, W] — predicted next state (residual + state)
        """
        b, d, t, h, w = state.shape
        e = action_enc.shape[1]
        a = action_enc.view(b, e, t, 1, 1).expand(-1, -1, -1, h, w)  # [B,E,T,H,W]
        x = torch.cat([state, a], dim=1)           # [B, D+E, T, H, W]
        # fold T into B for the 2-D conv backbone
        x = x.permute(0, 2, 1, 3, 4).reshape(b * t, d + e, h, w)

        y = self.stem(x)
        r1 = y + self.relu(self.res1(y))           # residual block 1
        delta = self.res2(r1)                       # [B*T, D, H, W]

        state_bt = state.permute(0, 2, 1, 3, 4).reshape(b * t, d, h, w)
        out = state_bt + delta
        return out.reshape(b, t, d, h, w).permute(0, 2, 1, 3, 4)  # [B, D, T, H, W]


class DisagreementEnsemble(nn.Module):
    """
    k independent one-step predictors trained on frozen JEPA latents.
    Novelty at step t = variance of k heads' predictions of latent_{t+1}.

    Args:
        state_dim        : D (latent channel dimension from build_ac_jepa)
        action_embed_dim : E (must match DiscreteActionEncoder.embed_dim)
        n_heads          : k, number of ensemble members (default 5)
        head_hidden      : hidden channels inside each _EnsHead (default 64)
    """

    def __init__(
        self,
        state_dim: int = 64,
        action_embed_dim: int = 16,
        n_heads: int = 5,
        head_hidden: int = 64,
    ):
        super().__init__()
        self.state_dim = state_dim
        self.action_embed_dim = action_embed_dim
        self.n_heads = n_heads
        self.heads = nn.ModuleList([
            _EnsHead(state_dim, action_embed_dim, head_hidden)
            for _ in range(n_heads)
        ])

    def forward(
        self, state: torch.Tensor, action_enc: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute all k predictions.

        state      : [B, D, T, H, W]
        action_enc : [B, E, T]
        Returns    : [k, B, D, T, H, W]
        """
        preds = [h(state, action_enc) for h in self.heads]
        return torch.stack(preds, dim=0)            # [k, B, D, T, H, W]

    @torch.no_grad()
    def disagreement(
        self,
        latents: torch.Tensor,
        action_enc: torch.Tensor,
    ) -> torch.Tensor:
        """
        Epistemic uncertainty = variance of k head predictions, averaged over
        (D, H', W') spatial dims, leaving one scalar per (batch, step).

        latents    : [B, D, T, H, W] — sequence of latent states (from model.encode
                     followed by concatenation, or from model.unroll output)
        action_enc : [B, E, T] — encoded actions (output of model.action_encoder)
        Returns    : [B, T] — disagreement score, higher = more novel
        """
        preds = self(latents, action_enc)           # [k, B, D, T, H, W]
        # variance across heads, then mean over spatial dims
        var = preds.var(dim=0)                       # [B, D, T, H, W]
        return var.mean(dim=(1, 3, 4))              # [B, T]

    # ------------------------------------------------------------------
    # Convenience: save / load the ensemble checkpoint
    # ------------------------------------------------------------------
    def save(self, path: str) -> None:
        torch.save({"state_dict": self.state_dict(), "cfg": {
            "state_dim": self.state_dim,
            "action_embed_dim": self.action_embed_dim,
            "n_heads": self.n_heads,
            "head_hidden": self.heads[0].res2[0].out_channels
            if hasattr(self.heads[0].res2[0], "out_channels") else 64,
        }}, path)

    @classmethod
    def load(cls, path: str, device: torch.device | str | None = None) -> "DisagreementEnsemble":
        ckpt = torch.load(path, map_location=device or "cpu", weights_only=False)
        cfg = ckpt["cfg"]
        ens = cls(
            state_dim=cfg["state_dim"],
            action_embed_dim=cfg["action_embed_dim"],
            n_heads=cfg["n_heads"],
            head_hidden=cfg.get("head_hidden", 64),
        )
        ens.load_state_dict(ckpt["state_dict"])
        if device is not None:
            ens = ens.to(device)
        ens.eval()
        return ens

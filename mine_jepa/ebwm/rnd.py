"""
RND (Random Network Distillation, arXiv:1810.12894) — online novelty signal.

Why RND over the offline Plan2Explore ensemble (docs/09_curiosity_coldstart.md):
the ensemble's degenerate solution is "all heads agree" (collapse), which is exactly
what happened when trained offline on frozen, narrow expert-demo latents (heads
converge because the training distribution never forces them apart). RND has no such
degenerate solution: predictor == target only if it has genuinely learned to
reproduce a FIXED RANDOM function, which requires seeing the corresponding states.
Novelty = predictor's regression error against the untouched random target, and it is
trained ONLINE (continuously, on the states actually visited), so novelty decays as
a state is revisited and stays high for anything the predictor has not seen — the
mechanism this module exists to test (`scripts/smoke_test_rnd.py`).

No BatchNorm2d in either net: online updates use small, temporally-correlated batches
(a ring buffer of recent states), and BatchNorm's running mean/var would itself drift
with that non-stationary, narrow batch composition — indistinguishable from genuine
novelty drift. Plain conv + ReLU (no normalisation) keeps the signal attributable only
to the predictor/target weights, not to a moving statistic.

Contract (matches DisagreementEnsemble.disagreement, mine_jepa/ebwm/curiosity.py,
so a future planner integration is a drop-in swap):
    latents    : [B, D, T, H, W] — sequence of latent states
    action_enc : ignored (RND is state-only; kept for signature compatibility)
    Returns    : [B, T] — per-(batch, step) novelty score, higher = more novel
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


def _make_net(state_dim: int, hidden_dim: int, feat_dim: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(state_dim, hidden_dim, 3, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(hidden_dim, hidden_dim, 3, padding=1),
        nn.ReLU(inplace=True),
        nn.Conv2d(hidden_dim, feat_dim, 3, padding=1),
    )


class RNDModule(nn.Module):
    """
    target    : frozen, fixed-random-init conv net — never updated, never .train()'d.
    predictor : architecturally identical conv net, trained online to match target.

    Args:
        state_dim  : D, latent channel dimension (e.g. 64 for craft_wm_v4).
        hidden_dim : hidden channels inside both nets (default 32, keeps params small).
        feat_dim   : output feature channels (default 32).
    """

    def __init__(self, state_dim: int = 64, hidden_dim: int = 32, feat_dim: int = 32):
        super().__init__()
        self.state_dim = state_dim
        self.target = _make_net(state_dim, hidden_dim, feat_dim)
        self.predictor = _make_net(state_dim, hidden_dim, feat_dim)
        self.target.requires_grad_(False)
        self.target.eval()

    def train(self, mode: bool = True) -> "RNDModule":
        # Keep target frozen in eval mode regardless of the module-wide train()/eval()
        # calls a caller might issue (e.g. as part of a larger model.train()).
        super().train(mode)
        self.target.eval()
        return self

    @staticmethod
    def _to_bdhw(x: torch.Tensor) -> tuple[torch.Tensor, tuple[int, ...]]:
        """
        Normalise input to [N, D, H, W] for the conv nets, remembering the leading
        shape so the output can be reshaped back.

        Accepts either [B, D, T, H, W] (the DisagreementEnsemble contract) or
        [B, D, H, W] (a single time step, e.g. one probe latent per ring-buffer tick).
        """
        if x.dim() == 5:
            b, d, t, h, w = x.shape
            return x.permute(0, 2, 1, 3, 4).reshape(b * t, d, h, w), (b, t)
        elif x.dim() == 4:
            b, d, h, w = x.shape
            return x, (b,)
        else:
            raise ValueError(f"RNDModule expects 4D or 5D latents, got shape {tuple(x.shape)}")

    @torch.no_grad()
    def disagreement(self, latents: torch.Tensor, action_enc: torch.Tensor | None = None) -> torch.Tensor:
        """
        No-grad novelty score. action_enc is accepted (and ignored) only to match
        DisagreementEnsemble's call signature — RND depends on state alone.

        Returns [B, T] if latents is 5D, or [B] if latents is 4D.
        """
        x, lead = self._to_bdhw(latents)
        tgt = self.target(x)
        pred = self.predictor(x)
        mse = (pred - tgt).pow(2).mean(dim=(1, 2, 3))   # [N]
        return mse.reshape(*lead)

    def update(self, z_batch: torch.Tensor, opt: torch.optim.Optimizer) -> float:
        """
        One gradient step: train predictor to regress target(z_batch).detach().
        z_batch: [N, D, H, W] (or [B, D, T, H, W], flattened internally).
        Returns the scalar MSE loss (float, post-step value from this batch).
        """
        x, _ = self._to_bdhw(z_batch)
        with torch.no_grad():
            tgt = self.target(x)
        pred = self.predictor(x)
        loss = F.mse_loss(pred, tgt)
        opt.zero_grad()
        loss.backward()
        opt.step()
        return float(loss.item())

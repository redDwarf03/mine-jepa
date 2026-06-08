"""
WM v3 — inventory- and reward-aware action-conditioned world model.

Extends the eb-JEPA world model (build_ac_jepa) with two auxiliary heads that read
the latent and predict the structured game state:

    latent [B, D, T, 8, 8] ──mean over H,W──► [B, T, D] ──┬─► reward_head    → [B, T]   (per-step reward)
                                                          └─► inventory_head → [B, T, K] (item counts / INV_SCALE)

Why: the bare JEPA latent only encodes "what the scene looks like next". Forcing it to
also predict reward and inventory makes it encode the MECHANICS ("craft action when
log>=1 → planks +1, reward +2"). The MPC planner can then score candidate action
sequences by PREDICTED reward / inventory gain, instead of a blurry visual centroid.

Trained jointly: total = jepa_loss (latent MSE + VICReg) + rew_coeff·reward_MSE
+ inv_coeff·inventory_MSE. The heads backprop into the encoder (that is the point —
they shape the latent), so we call the encoder WITH gradients (not the no-grad encode()).
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from mine_jepa.ebwm import build_ac_jepa


class LatentHead(nn.Module):
    """[B, D, T, H, W] → spatial mean → [B, T, out_dim] via a small MLP."""

    def __init__(self, state_dim: int, out_dim: int, hidden_dim: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Linear(hidden_dim, out_dim),
        )

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        # state [B, D, T, H, W] → mean over H,W → [B, D, T] → [B, T, D]
        pooled = state.mean(dim=(3, 4)).permute(0, 2, 1)
        return self.net(pooled)                           # [B, T, out_dim]


class CraftWorldModel(nn.Module):
    """eb-JEPA + reward/inventory heads. One module, one combined loss."""

    def __init__(
        self,
        n_items: int,
        embed_dim: int = 64,
        encoder_hidden: int = 32,
        n_actions: int = 22,
        action_embed_dim: int = 16,
        predictor_hidden: int = 128,
        std_coeff: float = 10.0,
        cov_coeff: float = 1.0,
        sim_coeff_t: float = 0.0,
        rew_coeff: float = 1.0,
        inv_coeff: float = 1.0,
        head_hidden: int = 64,
    ):
        super().__init__()
        self.jepa = build_ac_jepa(
            embed_dim=embed_dim, encoder_hidden=encoder_hidden, n_actions=n_actions,
            action_embed_dim=action_embed_dim, predictor_hidden=predictor_hidden,
            std_coeff=std_coeff, cov_coeff=cov_coeff, sim_coeff_t=sim_coeff_t,
        )
        self.reward_head = LatentHead(embed_dim, out_dim=1, hidden_dim=head_hidden)
        self.inventory_head = LatentHead(embed_dim, out_dim=n_items, hidden_dim=head_hidden)
        self.rew_coeff = rew_coeff
        self.inv_coeff = inv_coeff

    # --- training ---
    def loss(self, obs, actions, rewards, inventory):
        """obs [B,3,T,H,W], actions [B,1,T], rewards [B,T], inventory [B,T,K].
        Returns (total, dict of components)."""
        _, jepa_losses = self.jepa.unroll(
            obs, actions, nsteps=1, unroll_mode="parallel", compute_loss=True
        )
        jepa_loss, rloss, _, _, ploss = jepa_losses

        state = self.jepa.encoder(obs)                    # [B,D,T,H,W] WITH grad
        rew_pred = self.reward_head(state).squeeze(-1)    # [B, T]
        inv_pred = self.inventory_head(state)             # [B, T, K]

        rew_mse = F.mse_loss(rew_pred, rewards)
        inv_mse = F.mse_loss(inv_pred, inventory)
        total = jepa_loss + self.rew_coeff * rew_mse + self.inv_coeff * inv_mse

        def _f(x):
            return x.detach().item() if torch.is_tensor(x) else float(x)

        return total, {
            "jepa": _f(jepa_loss), "pred": _f(ploss), "reg": _f(rloss),
            "reward": _f(rew_mse), "inv": _f(inv_mse),
        }

    # --- planning / inference ---
    @torch.no_grad()
    def encode(self, obs):
        return self.jepa.encoder(obs)

    @torch.no_grad()
    def predict_reward(self, state):
        return self.reward_head(state).squeeze(-1)

    @torch.no_grad()
    def predict_inventory(self, state):
        return self.inventory_head(state)


def build_craft_wm(cfg_model: dict, cfg_reg: dict, cfg_head: dict, n_items: int) -> CraftWorldModel:
    """Assemble a CraftWorldModel from config dicts."""
    return CraftWorldModel(
        n_items=n_items,
        embed_dim=cfg_model["embed_dim"], encoder_hidden=cfg_model["encoder_hidden"],
        n_actions=cfg_model["n_actions"], action_embed_dim=cfg_model["action_embed_dim"],
        predictor_hidden=cfg_model["predictor_hidden"],
        std_coeff=cfg_reg["std_coeff"], cov_coeff=cfg_reg["cov_coeff"],
        sim_coeff_t=cfg_reg["sim_coeff_t"],
        rew_coeff=cfg_head["rew_coeff"], inv_coeff=cfg_head["inv_coeff"],
        head_hidden=cfg_head.get("head_hidden", 64),
    )


# ============================================================================
# WM v4 — inventory as a STATE variable (not a prediction head)
# ============================================================================
# Why v4: the POV frame does not contain the inventory count, so a head reading the
# visual latent can only learn scene-stage correlations, never the craft mechanic.
# v4 makes the inventory a real state variable with its own learned dynamics:
#   inv_{t+1} = inv_t + g(inv_t, action_t, visual_latent_t)
# The visual latent (perception: "tree ahead?", "near a table?") conditions g, so g
# learns BOTH chopping (attack + tree → log+1) and crafting (craft + log≥1 → planks+4).
# Crafting rules are near-deterministic → easy to learn once inventory is in the state.


class InventoryDynamics(nn.Module):
    """Predicts the inventory change from (inventory, action, pooled visual latent).

    Residual: inv_{t+1} = inv_t + MLP([inv_t, action_emb, visual_pooled]).
    Fully vectorised over time — accepts [B, T, *] and applies per timestep.
    """

    def __init__(self, n_items: int, n_actions: int, visual_dim: int,
                 action_embed_dim: int = 16, hidden_dim: int = 128):
        super().__init__()
        self.action_embed = nn.Embedding(n_actions, action_embed_dim)
        in_dim = n_items + action_embed_dim + visual_dim
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim), nn.ReLU(inplace=True),
            nn.Linear(hidden_dim, hidden_dim), nn.ReLU(inplace=True),
            nn.Linear(hidden_dim, n_items),
        )

    def forward(self, inv, action, visual_pooled):
        """inv [B,T,K], action [B,T] long, visual_pooled [B,T,D] → inv_pred [B,T,K]."""
        a = self.action_embed(action)                         # [B,T,A]
        x = torch.cat([inv, a, visual_pooled], dim=-1)        # [B,T,K+A+D]
        return inv + self.net(x)                              # residual


class CraftWorldModelV4(nn.Module):
    """Visual eb-JEPA (perception) + InventoryDynamics (discrete crafting state)."""

    # craft actions in configs/minerl_actions_obtain.yaml (17=planks .. 21=pickaxe)
    CRAFT_ACTIONS_FROM = 17

    def __init__(self, n_items, embed_dim=64, encoder_hidden=32, n_actions=22,
                 action_embed_dim=16, predictor_hidden=128, std_coeff=10.0,
                 cov_coeff=1.0, sim_coeff_t=0.0, inv_coeff=1.0, inv_hidden=128,
                 precond_coeff=1.0, craft_weight=30.0):
        super().__init__()
        self.jepa = build_ac_jepa(
            embed_dim=embed_dim, encoder_hidden=encoder_hidden, n_actions=n_actions,
            action_embed_dim=action_embed_dim, predictor_hidden=predictor_hidden,
            std_coeff=std_coeff, cov_coeff=cov_coeff, sim_coeff_t=sim_coeff_t,
        )
        self.inv_dyn = InventoryDynamics(
            n_items=n_items, n_actions=n_actions, visual_dim=embed_dim,
            action_embed_dim=action_embed_dim, hidden_dim=inv_hidden,
        )
        self.inv_coeff = inv_coeff
        self.precond_coeff = precond_coeff
        self.craft_weight = craft_weight

    @staticmethod
    def _pool(visual):
        # [B,D,T,H,W] → [B,T,D]
        return visual.mean(dim=(3, 4)).permute(0, 2, 1)

    def loss(self, obs, actions, inventory):
        """obs [B,3,T,H,W], actions [B,1,T], inventory [B,T,K]. Returns (total, parts)."""
        _, jepa_losses = self.jepa.unroll(
            obs, actions, nsteps=1, unroll_mode="parallel", compute_loss=True
        )
        jepa_loss, rloss, _, _, ploss = jepa_losses

        visual = self.jepa.encoder(obs)                       # [B,D,T,H,W] with grad
        vpool = self._pool(visual)                            # [B,T,D]
        act = actions.squeeze(1)                              # [B,T]

        act_in = act[:, :-1]                                   # [B,T-1]
        craft_mask = act_in >= self.CRAFT_ACTIONS_FROM         # [B,T-1]

        # Predict inv[t+1] from (inv[t], action[t], visual[t]) for t = 0..T-2.
        # Craft transitions are rare (~144/85k) but carry the whole signal → upweight
        # them so "craft+log → +4 planks" is not drowned by the no-change majority.
        inv_pred = self.inv_dyn(inventory[:, :-1], act_in, vpool[:, :-1])  # [B,T-1,K]
        per = ((inv_pred - inventory[:, 1:]) ** 2).mean(dim=-1)            # [B,T-1]
        w = torch.where(craft_mask, per.new_full((), self.craft_weight), per.new_ones(()))
        inv_loss = (per * w).sum() / w.sum()

        # Precondition negative: crafting with an EMPTY inventory produces nothing.
        # Demos never show failed crafts, so without this the model thinks craft→+item
        # unconditionally and the agent crafts on an empty inventory forever. We assert:
        # at craft-action steps, g(zeros, craft, visual) must stay ~0 (no item created).
        if craft_mask.any():
            zero_inv = torch.zeros_like(inventory[:, :-1])
            inv_pred_zero = self.inv_dyn(zero_inv, act_in, vpool[:, :-1].detach())
            precond_loss = (inv_pred_zero[craft_mask] ** 2).mean()
        else:
            precond_loss = torch.zeros((), device=obs.device)

        total = jepa_loss + self.inv_coeff * inv_loss + self.precond_coeff * precond_loss

        def _f(x):
            return x.detach().item() if torch.is_tensor(x) else float(x)

        return total, {"jepa": _f(jepa_loss), "pred": _f(ploss), "reg": _f(rloss),
                       "inv": _f(inv_loss), "precond": _f(precond_loss)}

    @torch.no_grad()
    def encode(self, obs):
        return self.jepa.encoder(obs)

    @torch.no_grad()
    def step_inventory(self, inv, action, visual_pooled):
        """One-step inventory transition for planning. inv [N,K], action [N], vpool [N,D]."""
        return self.inv_dyn(inv.unsqueeze(1), action.unsqueeze(1),
                            visual_pooled.unsqueeze(1)).squeeze(1)


def build_craft_wm_v4(cfg_model: dict, cfg_reg: dict, cfg_head: dict, n_items: int) -> CraftWorldModelV4:
    return CraftWorldModelV4(
        n_items=n_items,
        embed_dim=cfg_model["embed_dim"], encoder_hidden=cfg_model["encoder_hidden"],
        n_actions=cfg_model["n_actions"], action_embed_dim=cfg_model["action_embed_dim"],
        predictor_hidden=cfg_model["predictor_hidden"],
        std_coeff=cfg_reg["std_coeff"], cov_coeff=cfg_reg["cov_coeff"],
        sim_coeff_t=cfg_reg["sim_coeff_t"],
        inv_coeff=cfg_head["inv_coeff"], inv_hidden=cfg_head.get("inv_hidden", 128),
        precond_coeff=cfg_head.get("precond_coeff", 1.0),
        craft_weight=cfg_head.get("craft_weight", 30.0),
    )

"""
Discrete planner for the action-conditioned world model (Phase 4c).

eb_jepa provides *continuous* CEM/MPPI planners — ill-suited to our 17 discrete
actions. We write a random-shooting MPC that:
  1. samples N discrete action sequences (horizon H)
  2. unrolls them via model.unroll(autoregressive) in SPATIAL latent space
  3. scores each sequence: -MSE(final_latent_state, goal_latent)
  4. returns the 1st action of the best sequence (re-plans every step)

Key difference vs the old LatentMPCPlanner: here states are spatial maps
[D, H', W'] (not a vector), and the WM is action-conditioned and jointly trained
→ the rollout genuinely reflects the effect of actions.

Phase 5 novelty extension (Plan2Explore):
  DiscreteLatentPlanner accepts an optional DisagreementEnsemble and a
  novelty_coeff λ.  Score = goal_score + λ · novelty_score, where
  novelty_score = mean disagreement over the H rollout steps.
  novelty_coeff=0.0 (default) reproduces the original behaviour exactly.

Phase 5+ cold-start extension (docs/10_coldstart_engineering.md):
  - sticky_prob: temporally correlated candidate sampling (see _sample_actions).
  - plan(..., return_info=True): exposes the goal-score std across candidates,
    the "am I lost?" signal driving the scan macro in the play scripts.
  Defaults (sticky_prob=0.0, return_info=False) reproduce the original
  behaviour exactly.

Phase 5+ cold-start attempt #4 (commit_length): plan() picks the best H-step
sequence but historically returned only its first action — every replan drew a
fresh independent 512-candidate sample, so any sustained direction proposed for
steps 2..H was discarded. commit_length>1 returns the first M actions of the
winning sequence instead of 1, so the caller can execute several before
replanning. commit_length=1 (default) is the exact original code path: same
scoring, same argmax, same single-int return.

Phase 5+ cold-start attempt #6 (CEM, arXiv:2512.24497): plan() was single-generation
random/sticky-shooting — sample N candidates ONCE, score, argmax. cem_iters>1 turns
this into iterative refinement (iCEM-lite for DISCRETE/categorical actions, not the
classical continuous-Gaussian CEM): generation 1 uses the existing _sample_actions()
(so sticky_prob still seeds a temporally-correlated starting pool); the top
cem_elite_frac fraction by score become the elite set; a [horizon, n_actions]
categorical table is refit from the elite's empirical per-timestep action
frequencies (+cem_smoothing Laplace floor, renormalised) so a low-probability
action never hits exactly 0 (premature degenerate convergence); generations 2..
cem_iters sample fresh candidates independently per timestep from that table
(the temporal correlation now comes from the refit distribution itself, not from
sticky repetition). The single best-scoring sequence seen across ALL generations
(not just the last) is what gets returned. cem_iters=1 (default) skips the refit
loop entirely and is bit-for-bit the original single-generation code path — the
scoring/rollout logic itself (_score) is unchanged, refactored out of plan() only
so both code paths call it instead of duplicating it.

Phase 5+ cold-start attempt #7 (trained distance metric, arXiv:2601.00844,
mine_jepa/ebwm/value_head.py): _score()'s goal distance was always an UNTRAINED
raw-latent squared-L2 — attempts #1-#6 all worked around it going flat/
undiscriminating with no tree in view, never at the metric itself. distance_projector
(optional, default None) swaps that raw distance for DistanceProjector.pairwise_dist,
a small MLP trained (frozen ebwm.pt latents only, see scripts/train_value_projector.py)
so Euclidean distance in its projection space approximates true action-count-to-goal.
distance_projector=None (default) is bit-for-bit the original raw-L2 scoring path —
verified with a fixed-seed comparison, same discipline as every other change here.

Phase 5+ cold-start attempt #8, Proposal A (action-pool priming, docs/10): attempts
#4-#7 diagnosed the wall as BEHAVIOURAL, not perceptual — the world model already
scores situations correctly, but the 512 i.i.d./sticky-sampled candidate sequences
essentially never contain a sustained "clean" gesture (sprint-forward-attack for
~12 steps, a continuous camera sweep, walking backward) for the argmax to select in
the first place. action_pool_priming (optional dict, default None/disabled) has
_sample_actions() overwrite a fixed leading slice of the SAME N candidates it would
have produced anyway with hand-authored full-horizon macros built from the 17 shared
movement-action indices (see _build_primed_macros) — same shape, same downstream
_score() call, no bonus/weighting on them. Disabled (no dict, or enabled: false) is
bit-for-bit the original sticky/i.i.d. sampling — verified with a fixed-seed
comparison, same discipline as sticky_prob/commit_length/cem_iters/distance_projector.

Phase 5+ cold-start attempt #8, Proposal B (BC actor prior, mine_jepa/ebwm/actor.py):
Proposal A's macros are hand-authored; this swaps "hand-authored" for "learned from
demonstrations + coverage episodes" — a small BCActor classifier on the SAME frozen
model's latents proposes a further leading slice of the candidate pool, drawn i.i.d.
per-timestep from its predicted action distribution conditioned on the CURRENT
observation (see _sample_actor_macros). NOT a repeat of Phase 4's failed pure-BC
policy: the actor only proposes here, _score()'s world-model-based MPC still
evaluates and re-plans every step. actor=None / actor_n_samples<=0 (default) never
calls the actor and is bit-for-bit the original/Proposal-A sampling — verified with
a fixed-seed comparison, same discipline as every prior config-gated change here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import torch

if TYPE_CHECKING:
    from mine_jepa.ebwm.actor import BCActor
    from mine_jepa.ebwm.curiosity import DisagreementEnsemble
    from mine_jepa.ebwm.value_head import DistanceProjector


def _build_primed_macros(cfg: dict, horizon: int, device) -> torch.Tensor:
    """
    Hand-authored 'clean' macro sequences for action-pool priming (docs/10 attempt
    #8, Proposal A). Each row is a FULL-horizon repeated-action gesture built from
    the 17 shared movement-action indices (configs/minerl_actions_obtain.yaml /
    minerl_actions.yaml, identical 0-16 in both):
      - forward+attack (n_forward_attack): half a14 (sprint+forward+attack, the
        lumberjack gesture), half a7 (forward+attack, no sprint) for variety.
      - camera-turn (n_turn): a third pure a12 (turn right) for the full horizon,
        a third pure a11 (turn left), a third half-right-then-half-left (a scan
        that sweeps both ways within one sequence) — collectively covering the
        yaw range in both directions rather than betting on one.
      - backward (n_backward): pure a2 (back) for the full horizon.
    Returns [M, H] (M = sum of the three counts, possibly 0 rows). These go through
    the exact same _score() rollout/argmax as every other candidate — no scoring
    change, only what's in the menu.
    """
    n_fa = int(cfg.get("n_forward_attack", 30))
    n_turn = int(cfg.get("n_turn", 30))
    n_back = int(cfg.get("n_backward", 30))
    rows = []
    if n_fa > 0:
        half = n_fa // 2
        rows.append(torch.full((half, horizon), 14, dtype=torch.long, device=device))
        rows.append(torch.full((n_fa - half, horizon), 7, dtype=torch.long, device=device))
    if n_turn > 0:
        third = n_turn // 3
        rem = n_turn - 2 * third
        rows.append(torch.full((third, horizon), 12, dtype=torch.long, device=device))
        rows.append(torch.full((third, horizon), 11, dtype=torch.long, device=device))
        half_h = horizon // 2
        if rem > 0:
            scan = torch.cat([
                torch.full((rem, half_h), 12, dtype=torch.long, device=device),
                torch.full((rem, horizon - half_h), 11, dtype=torch.long, device=device),
            ], dim=1)
            rows.append(scan)
    if n_back > 0:
        rows.append(torch.full((n_back, horizon), 2, dtype=torch.long, device=device))
    if not rows:
        return torch.empty(0, horizon, dtype=torch.long, device=device)
    return torch.cat(rows, dim=0)


def _sample_actor_macros(
    actor: "BCActor", obs_latent_flat: torch.Tensor, n_samples: int,
    horizon: int, temperature: float, device,
) -> torch.Tensor:
    """
    [n_samples, H] action sequences (docs/10 attempt #8, Proposal B) drawn i.i.d.
    per-timestep from a frozen BCActor's predicted action distribution, conditioned
    on the CURRENT observation's flattened latent `obs_latent_flat` [1, F] — a
    LEARNED prior over what to propose, in the same role as _build_primed_macros'
    hand-authored macros. The actor is a single-step classifier, not a sequence
    model: the SAME per-action distribution is reused at every timestep and every
    row here — combining this with sticky_prob's temporal correlation (holding a
    sampled action for several steps in a row) is a natural follow-up, kept out of
    scope for the first live sanity pass to keep the mechanism auditable.
    """
    if n_samples <= 0:
        return torch.empty(0, horizon, dtype=torch.long, device=device)
    probs = actor.action_probs(obs_latent_flat, temperature=temperature).squeeze(0)  # [n_actions]
    flat = torch.multinomial(probs, n_samples * horizon, replacement=True)
    return flat.reshape(n_samples, horizon)


def _sample_actions(
    n_candidates: int, horizon: int, n_actions: int,
    sticky_prob: float, device,
    action_pool_priming: dict | None = None,
    actor: "BCActor | None" = None,
    actor_n_samples: int = 0,
    actor_temperature: float = 1.0,
    obs_latent_flat: torch.Tensor | None = None,
) -> torch.Tensor:
    """
    Sample [N, 1, H] candidate action sequences.

    sticky_prob=0.0 → i.i.d. uniform (the original behaviour, bit-for-bit).
    sticky_prob>0.0 → temporally correlated (iCEM-lite, arXiv:2008.06389): at each
    step the previous action is repeated with probability sticky_prob, else a fresh
    uniform draw. I.i.d. sequences almost never contain sustained gestures like
    "turn for 6 steps then walk" — sticky sampling puts them in the candidate pool,
    which is what lets MPC *consider* searching/approaching behaviours at all.

    action_pool_priming (docs/10 attempt #8, Proposal A): optional dict, default
    None/disabled. When {"enabled": True, ...}, overwrites a fixed LEADING slice of
    the sticky/i.i.d. pool above (same total N, same shape) with the hand-authored
    macros from _build_primed_macros — so the argmax has a chance to pick a genuine
    sustained gesture instead of only i.i.d./sticky noise. Disabled (None, or
    enabled: false) never touches the tensor below this point — bit-for-bit the
    original sampling.

    actor / actor_n_samples (docs/10 attempt #8, Proposal B): when actor is not
    None and actor_n_samples > 0, a FURTHER leading slice (placed right after
    action_pool_priming's, so both can coexist) is overwritten with sequences
    drawn from _sample_actor_macros — a learned prior instead of hand-authored
    macros. actor=None / actor_n_samples<=0 (default) never touches the tensor
    here either — bit-for-bit the original/Proposal-A sampling.
    """
    if sticky_prob <= 0.0:
        actions = torch.randint(0, n_actions, (n_candidates, 1, horizon), device=device)
    else:
        actions = torch.empty(n_candidates, 1, horizon, dtype=torch.long, device=device)
        actions[:, 0, 0] = torch.randint(0, n_actions, (n_candidates,), device=device)
        for h in range(1, horizon):
            fresh = torch.randint(0, n_actions, (n_candidates,), device=device)
            keep = torch.rand(n_candidates, device=device) < sticky_prob
            actions[:, 0, h] = torch.where(keep, actions[:, 0, h - 1], fresh)

    m = 0
    if action_pool_priming and action_pool_priming.get("enabled", False):
        macros = _build_primed_macros(action_pool_priming, horizon, device)  # [M,H]
        m = min(macros.shape[0], n_candidates)
        if m > 0:
            actions[:m, 0] = macros[:m]

    if actor is not None and actor_n_samples > 0 and obs_latent_flat is not None:
        budget = max(0, n_candidates - m)
        macros2 = _sample_actor_macros(
            actor, obs_latent_flat, min(actor_n_samples, budget), horizon,
            actor_temperature, device,
        )
        m2 = macros2.shape[0]
        if m2 > 0:
            actions[m:m + m2, 0] = macros2

    return actions


class DiscreteLatentPlanner:
    def __init__(
        self,
        model,
        n_actions: int = 17,
        horizon: int = 12,
        n_candidates: int = 512,
        novelty_coeff: float = 0.0,
        ensemble: "DisagreementEnsemble | None" = None,
        sticky_prob: float = 0.0,
        commit_length: int = 1,
        cem_iters: int = 1,
        cem_elite_frac: float = 0.1,
        cem_smoothing: float = 0.01,
        distance_projector: "DistanceProjector | None" = None,
        action_pool_priming: dict | None = None,
        actor: "BCActor | None" = None,
        actor_n_samples: int = 0,
        actor_temperature: float = 1.0,
        device=None,
    ):
        self.model = model
        self.n_actions = n_actions
        self.horizon = horizon
        self.n_candidates = n_candidates
        self.novelty_coeff = novelty_coeff
        self.ensemble = ensemble
        self.sticky_prob = sticky_prob
        self.commit_length = commit_length
        # None/disabled (default): _sample_actions() is bit-for-bit the original
        # sticky/i.i.d. pool (docs/10 attempt #8, Proposal A).
        self.action_pool_priming = action_pool_priming
        # None/0 (default): _sample_actions() never calls the actor (docs/10
        # attempt #8, Proposal B) — bit-for-bit the original/Proposal-A sampling.
        self.actor = actor
        self.actor_n_samples = int(actor_n_samples)
        self.actor_temperature = float(actor_temperature)
        # cem_iters<=1: exact original single-generation code path (verified
        # bit-for-bit, docs/10 attempt #6). >1: iCEM-lite refit loop below.
        self.cem_iters = max(1, int(cem_iters))
        self.cem_elite_frac = cem_elite_frac
        self.cem_smoothing = cem_smoothing
        # None (default): _score() uses the original raw-latent squared-L2 goal
        # distance, bit-for-bit (docs/10 attempt #7). Set: a trained DistanceProjector
        # replaces that distance with a learned cost-to-goal metric.
        self.distance_projector = distance_projector
        self.device = device or next(model.parameters()).device

    def _score(self, obs: torch.Tensor, goal_latents: torch.Tensor, actions: torch.Tensor):
        """
        Unrolls `actions` [N,1,H] through the world model and scores each sequence.
        Returns (scores [N], goal_score_std: float, novelty_mean: float or None).
        Exact scoring/rollout block from the original single-generation plan(),
        factored out so the CEM refit loop can call it once per generation
        instead of duplicating it.
        """
        N, H = actions.shape[0], self.horizon
        predicted, _ = self.model.unroll(
            obs, actions, nsteps=H, unroll_mode="autoregressive",
            ctxt_window_time=1, compute_loss=False,
        )
        final = predicted[:, :, -1]

        F = final.shape[1] * final.shape[2] * final.shape[3]
        final_flat = final.reshape(N, F)
        goals_flat = goal_latents.reshape(goal_latents.shape[0], F)
        if self.distance_projector is not None:
            # Trained cost-to-goal metric (docs/10 attempt #7): pairwise_dist
            # already returns [N, K] Euclidean distances in projection space.
            dist = self.distance_projector.pairwise_dist(final_flat, goals_flat)
        else:
            # Original path (bit-for-bit): mean-squared-L2 in raw latent space.
            final_sq = (final_flat ** 2).sum(dim=1, keepdim=True)
            goals_sq = (goals_flat ** 2).sum(dim=1).unsqueeze(0)
            cross = final_flat @ goals_flat.t()
            dist = (final_sq - 2 * cross + goals_sq) / F
        goal_scores = -dist.min(dim=1).values
        goal_score_std = float(goal_scores.std().item())

        if self.novelty_coeff > 0.0 and self.ensemble is not None:
            rollout_states = predicted[:, :, 1:]
            action_enc = self.model.action_encoder(actions)
            dis = self.ensemble.disagreement(rollout_states, action_enc)
            novelty_scores = dis.mean(dim=1)

            g_mu, g_std = goal_scores.mean(), goal_scores.std().clamp(min=1e-8)
            n_mu, n_std = novelty_scores.mean(), novelty_scores.std().clamp(min=1e-8)
            scores = (goal_scores - g_mu) / g_std + self.novelty_coeff * (novelty_scores - n_mu) / n_std
            novelty_mean = float(novelty_scores.mean().item())
        else:
            scores = goal_scores
            novelty_mean = None

        return scores, goal_score_std, novelty_mean

    def _refit_categorical(self, actions: torch.Tensor, scores: torch.Tensor) -> torch.Tensor:
        """
        Elite-frequency categorical table [H, n_actions] for the next CEM generation:
        top cem_elite_frac fraction of `actions` [N,1,H] by `scores`, per-timestep
        action-frequency counts among the elite, +cem_smoothing Laplace floor (no
        action's probability collapses to exactly 0 after one generation), each
        timestep row renormalised to sum to 1.
        """
        n_elite = max(1, int(actions.shape[0] * self.cem_elite_frac))
        elite_idx = torch.topk(scores, n_elite).indices
        elite_actions = actions[elite_idx, 0]
        table = torch.zeros(self.horizon, self.n_actions, device=self.device)
        for h in range(self.horizon):
            table[h] = torch.bincount(elite_actions[:, h], minlength=self.n_actions).float()
        table = table + self.cem_smoothing
        return table / table.sum(dim=1, keepdim=True)

    @torch.no_grad()
    def plan(self, obs_init: torch.Tensor, goal_latents: torch.Tensor,
             return_info: bool = False):
        """
        Args:
            obs_init     : [1, 3, 1, 64, 64] — current frame (T=1 context)
            goal_latents : [K, D, H', W'] — K success-scene prototypes (reward>0 frames)
            return_info  : if True, also return {"goal_score_std": float} — the std of
                           the goal scores across the N generation-1 candidates. Near-zero
                           std means every imagined future looks equally (un)promising,
                           i.e. no goal is in view — the signal the scan macro triggers on.
        Returns (self.commit_length == 1, the default — original contract, unchanged):
            action (int) — 1st action of the best sequence found
            (action, info) when return_info=True
        Returns (self.commit_length > 1):
            actions (list[int], length min(commit_length, horizon)) — the first M
            actions of the best sequence, letting the caller execute a sustained
            gesture before replanning instead of discarding steps 2..H every time.
            (actions, info) when return_info=True

        Nearest-neighbor scoring: each sequence is scored by its distance to the
        CLOSEST success prototype (min over K), not a blurry average centroid. The
        planner thus seeks "the most reachable success scene" -> more reactive behavior
        (orienting/stopping toward a specific trunk).

        When novelty_coeff > 0 and an ensemble is supplied, the score blends in
        Plan2Explore disagreement:  score = goal_score + lambda * novelty_score
        Both terms are z-score normalised across candidates before blending so
        that the relative weight is controlled by lambda alone (not by raw magnitudes).

        CEM (cem_iters > 1, docs/10 attempt #6): generation 1 samples via
        _sample_actions() (sticky_prob still applies here); the top cem_elite_frac
        sequences by score refit a per-timestep categorical table
        (_refit_categorical); generations 2..cem_iters sample fresh, independent-
        per-timestep candidates from that table and repeat score -> elite -> refit.
        The single best-scoring sequence across ALL generations is returned
        (tracked, not just the last generation's argmax). cem_iters=1 (default)
        skips this loop entirely -> bit-for-bit the original behaviour.
        """
        N, H = self.n_candidates, self.horizon
        obs = obs_init.expand(N, -1, -1, -1, -1).contiguous()       # [N,3,1,64,64]
        # docs/10 attempt #8, Proposal B: the actor needs the CURRENT frame's
        # latent, not the expanded [N,...] batch — one cheap single-frame encode,
        # skipped entirely when no actor is attached (self.actor is None).
        obs_latent_flat = None
        if self.actor is not None and self.actor_n_samples > 0:
            z0 = self.model.encode(obs_init).squeeze(2)              # [1,D,H',W']
            obs_latent_flat = z0.reshape(1, -1)
        actions = _sample_actions(
            N, H, self.n_actions, self.sticky_prob, self.device, self.action_pool_priming,
            actor=self.actor, actor_n_samples=self.actor_n_samples,
            actor_temperature=self.actor_temperature, obs_latent_flat=obs_latent_flat,
        )

        scores, goal_score_std, novelty_mean = self._score(obs, goal_latents, actions)
        best = scores.argmax()
        best_score = scores[best]
        best_seq = actions[best, 0].clone()                        # [H]

        for _ in range(1, self.cem_iters):
            table = self._refit_categorical(actions, scores)        # [H, n_actions]
            samples = torch.multinomial(table, N, replacement=True)  # [H, N]
            actions = samples.t().unsqueeze(1)                       # [N, 1, H]
            scores, _, _ = self._score(obs, goal_latents, actions)
            gen_best = scores.argmax()
            if scores[gen_best] > best_score:
                best_score = scores[gen_best]
                best_seq = actions[gen_best, 0].clone()

        info = {"goal_score_std": goal_score_std}
        if novelty_mean is not None:
            info["novelty_mean"] = novelty_mean
        if self.commit_length <= 1:
            action = int(best_seq[0].item())
            if return_info:
                return action, info
            return action
        M = min(self.commit_length, H)
        committed = best_seq[:M].tolist()
        if return_info:
            return committed, info
        return committed


class CraftPlanner:
    """
    Goal-directed MPC for the inventory/reward-aware WM v3 (CraftWorldModel).

    Instead of steering toward a visual goal latent, it scores each candidate action
    sequence by what the WM PREDICTS will happen to the game state:

        score = w_item * (predicted gain of the target item, e.g. planks)
              + w_reward * (predicted cumulative reward over the rollout)

    The reward/inventory heads turn the latent rollout into a task-grounded objective,
    so MPC naturally selects "craft planks" once the agent holds a log.

    Note on curiosity: true intrinsic motivation (reward = WM prediction error on the
    transitions actually experienced) belongs in the self-play collection loop, not in
    open-loop MPC scoring. This planner is the goal-directed half of the hybrid.
    """

    def __init__(self, model, n_actions=22, horizon=12, n_candidates=512,
                 target_item=1, w_item=1.0, w_reward=0.2, device=None):
        self.model = model                      # CraftWorldModel
        self.n_actions = n_actions
        self.horizon = horizon
        self.n_candidates = n_candidates
        self.target_item = target_item          # index into inventory_items (1 = planks)
        self.w_item = w_item
        self.w_reward = w_reward
        self.device = device or next(model.parameters()).device

    @torch.no_grad()
    def plan(self, obs_init: torch.Tensor) -> int:
        """obs_init: [1, 3, 1, 64, 64]. Returns the 1st action of the best sequence."""
        N, H = self.n_candidates, self.horizon
        obs = obs_init.expand(N, -1, -1, -1, -1).contiguous()       # [N,3,1,64,64]
        actions = torch.randint(0, self.n_actions, (N, 1, H), device=self.device)

        predicted, _ = self.model.jepa.unroll(
            obs, actions, nsteps=H, unroll_mode="autoregressive",
            ctxt_window_time=1, compute_loss=False,
        )                                                            # [N, D, 1+H, H', W']

        rew = self.model.predict_reward(predicted)                   # [N, 1+H]
        inv = self.model.predict_inventory(predicted)                # [N, 1+H, K]

        cum_reward = rew[:, 1:].sum(dim=1)                           # [N] predicted return
        item_gain = inv[:, -1, self.target_item] - inv[:, 0, self.target_item]  # [N]
        scores = self.w_item * item_gain + self.w_reward * cum_reward
        best = scores.argmax()
        return int(actions[best, 0, 0].item())


class CraftPlannerV4:
    """
    MPC for WM v4 (CraftWorldModelV4), where inventory is a real state variable.

    For each candidate action sequence:
      1. unroll the VISUAL latent (eb-JEPA predictor) → perception at each step
      2. roll the INVENTORY forward from the REAL current inventory, using the learned
         dynamics g(inv, action, visual) → predicted inventory at the horizon
      3. score = predicted gain of the target item (e.g. planks)

    Starting the inventory rollout from the agent's TRUE current inventory (known from
    the MineRL obs) makes planning grounded: "if I attack here then craft, do I gain
    planks?" — exactly the question the milestone needs.
    """

    def __init__(self, model, n_actions=22, horizon=12, n_candidates=512,
                 item_weights=None, device=None):
        self.model = model                      # CraftWorldModelV4
        self.n_actions = n_actions
        self.horizon = horizon
        self.n_candidates = n_candidates
        # item_weights: {item_idx: weight}. Default targets planks only. Tech-tree-aware
        # weighting (e.g. {log:1, planks:2}) makes the planner value chopping wood as a
        # stepping stone — without it the planner ignores the hard "get a log" subtask.
        self.item_weights = item_weights or {1: 1.0}
        self.device = device or next(model.parameters()).device

    @torch.no_grad()
    def plan(self, obs_init: torch.Tensor, inv_init: torch.Tensor) -> int:
        """obs_init [1,3,1,64,64]; inv_init [K] normalised current inventory.
        Returns the 1st action of the best sequence."""
        N, H = self.n_candidates, self.horizon
        obs = obs_init.expand(N, -1, -1, -1, -1).contiguous()
        actions = torch.randint(0, self.n_actions, (N, 1, H), device=self.device)

        predicted, _ = self.model.jepa.unroll(
            obs, actions, nsteps=H, unroll_mode="autoregressive",
            ctxt_window_time=1, compute_loss=False,
        )                                                            # [N,D,1+H,H',W']
        vpool = predicted.mean(dim=(3, 4)).permute(0, 2, 1)          # [N, 1+H, D]

        inv = inv_init.to(self.device).unsqueeze(0).expand(N, -1).contiguous()  # [N,K]
        inv0 = inv.clone()
        for h in range(H):
            a = actions[:, 0, h]                                     # [N]
            v = vpool[:, h]                                          # [N,D] (before action h)
            inv = self.model.step_inventory(inv, a, v)              # [N,K]

        gain = inv - inv0                                           # [N,K]
        scores = sum(w * gain[:, idx] for idx, w in self.item_weights.items())
        best = scores.argmax()
        return int(actions[best, 0, 0].item())


class SwitchingCraftPlanner:
    """
    Hierarchical MPC that switches objective by inventory state:

      • NO log   → CHOP objective: steer the visual latent toward a goal-centroid of
                   "log obtained" scenes (the Treechop trick that drives the lumberjack
                   gesture — far more effective at chopping than the weak inventory signal).
      • HAS log  → CRAFT objective: score by predicted inventory gain (Δlog, Δplanks)
                   via the learned dynamics — the model knows craft+log → +planks.

    Combines two validated pieces: chopping (goal-centroid, ~25-50% in Treechop) and
    crafting (WM v4, dPlanks=+4). The planks milestone is then bounded by chopping.
    """

    def __init__(self, model, chop_goal, item_weights, log_idx, n_actions=22,
                 horizon=12, n_candidates=512, log_threshold=0.05,
                 sticky_prob=0.0, commit_length: int = 1,
                 action_pool_priming: dict | None = None,
                 actor: "BCActor | None" = None, actor_n_samples: int = 0,
                 actor_temperature: float = 1.0, device=None):
        self.model = model
        self.chop_goal = chop_goal              # [1, D, H', W'] visual latent centroid
        self.item_weights = item_weights        # {idx: weight} for the craft objective
        self.log_idx = log_idx
        self.n_actions = n_actions
        self.horizon = horizon
        self.n_candidates = n_candidates
        self.log_threshold = log_threshold      # normalised; 0.05 ≈ 0.5 raw logs
        self.sticky_prob = sticky_prob
        self.commit_length = commit_length
        # None/disabled (default): _sample_actions() is bit-for-bit the original
        # sticky/i.i.d. pool (docs/10 attempt #8, Proposal A).
        self.action_pool_priming = action_pool_priming
        # None/0 (default): _sample_actions() never calls the actor (docs/10
        # attempt #8, Proposal B) — bit-for-bit the original/Proposal-A sampling.
        # NB: only attach an actor trained on THIS planner's own model's latent
        # space (e.g. an ebwm.pt-trained actor must not be attached here when
        # `model` is craft_wm_v4 — different encoder, same shape, different geometry).
        self.actor = actor
        self.actor_n_samples = int(actor_n_samples)
        self.actor_temperature = float(actor_temperature)
        self.device = device or next(model.parameters()).device

    @torch.no_grad()
    def plan(self, obs_init: torch.Tensor, inv_init: torch.Tensor,
             return_info: bool = False):
        """Returns (action, mode) where mode ∈ {'chop','craft'} —
        or (action, mode, {"goal_score_std": float}) when return_info=True.
        The std is only meaningful for the scan macro in chop mode.
        commit_length > 1 (default 1, original contract): `action` becomes a
        list of the first min(commit_length, horizon) actions of the winning
        sequence instead of a single int."""
        N, H = self.n_candidates, self.horizon
        obs = obs_init.expand(N, -1, -1, -1, -1).contiguous()
        obs_latent_flat = None
        if self.actor is not None and self.actor_n_samples > 0:
            z0 = self.model.encode(obs_init).squeeze(2)               # [1,D,H',W']
            obs_latent_flat = z0.reshape(1, -1)
        actions = _sample_actions(
            N, H, self.n_actions, self.sticky_prob, self.device, self.action_pool_priming,
            actor=self.actor, actor_n_samples=self.actor_n_samples,
            actor_temperature=self.actor_temperature, obs_latent_flat=obs_latent_flat,
        )
        predicted, _ = self.model.jepa.unroll(
            obs, actions, nsteps=H, unroll_mode="autoregressive",
            ctxt_window_time=1, compute_loss=False,
        )                                                            # [N,D,1+H,H',W']

        has_log = float(inv_init[self.log_idx]) >= self.log_threshold
        if not has_log:
            # CHOP: minimise distance of the final visual latent to the chop-goal centroid
            final = predicted[:, :, -1]                              # [N,D,H',W']
            Fdim = final.shape[1] * final.shape[2] * final.shape[3]
            ff = final.reshape(N, Fdim)
            gf = self.chop_goal.reshape(1, Fdim)
            dist = ((ff - gf) ** 2).mean(dim=1)                      # [N]
            scores = -dist
        else:
            # CRAFT: maximise predicted inventory gain
            vpool = predicted.mean(dim=(3, 4)).permute(0, 2, 1)      # [N,1+H,D]
            inv = inv_init.to(self.device).unsqueeze(0).expand(N, -1).contiguous()
            inv0 = inv.clone()
            for h in range(H):
                inv = self.model.step_inventory(inv, actions[:, 0, h], vpool[:, h])
            gain = inv - inv0
            scores = sum(w * gain[:, idx] for idx, w in self.item_weights.items())

        best = scores.argmax()
        mode = "chop" if not has_log else "craft"
        if self.commit_length <= 1:
            action = int(actions[best, 0, 0].item())
            if return_info:
                return action, mode, {"goal_score_std": float(scores.std().item())}
            return action, mode
        M = min(self.commit_length, H)
        committed = actions[best, 0, :M].tolist()
        if return_info:
            return committed, mode, {"goal_score_std": float(scores.std().item())}
        return committed, mode

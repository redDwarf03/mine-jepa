"""
Cold-start attempt #20 (docs/10_coldstart_engineering.md) — offline Context Collapse
diagnostic on ebwm.pt.

Motivation: Gan et al., "ActSWM: Action-Sensitive World Models for Long-Horizon
Planning in Open-World Games", arXiv:2607.26712 (2026), whose baseline is LeWM —
the same architecture family as mine_jepa/ebwm. They name a failure mode called
CONTEXT COLLAPSE: an autoregressive latent predictor keeps high cosine similarity
to the true future while producing nearly indistinguishable futures under
different action sequences. A model in that state has a healthy prediction `ratio`
and a blind planner, because MPC can only rank action sequences by the differences
their rollouts produce.

That is a candidate mechanical explanation for this campaign's standing diagnosis
(attempts #4-#19): every score/search fix failed, `commit_length` (an execution
fix) was the only lever that ever worked, and attempt #10 confirmed the goal
score itself points backwards on Obtain. None of those attempts ever measured
whether the world model's rollouts respond to actions AT ALL.

Protocol (ActSWM Eq. 10, adapted): from one encoded context frame, roll out K
steps twice from the SAME context and compare each against the encoded true
future z_{t+k}:
    s_gt_k   = cos(z_hat_gt_{t+k},   z_{t+k})     # recorded actions
    s_zero_k = cos(z_hat_zero_{t+k}, z_{t+k})     # all-noop counterfactual
    delta_k  = s_gt_k - s_zero_k                  # the action gap
Context Collapse = high s_gt_k with small delta_k.

Two deliberate departures from ActSWM, both reported separately rather than
blended into their number:
  * A RANDOM-action arm alongside their all-noop arm. The planner never compares
    "recorded vs. noop"; it compares many non-noop candidate sequences against each
    other. delta_rand is the planner-matched version of the same question.
  * A planner-matched SPREAD arm: the std, across candidate action sequences, of
    the exact final-step latent distance mine_jepa/ebwm/planner.py::_score ranks on.
    This is the offline counterpart of the live `goal_score_std` the campaign has
    logged since attempt #2, measured here without MineRL.

Treechop is its own positive control: ebwm.pt demonstrably supports planning there
(Phase 4, 25-50% chop success), so a healthy delta on Treechop and a collapsed one
on Obtain is interpretable without needing an externally established threshold —
which this project does not have, since this quantity has never been measured here.

Negative control: Pearson r between per-window delta and raw mean frame brightness.
Every mechanism this campaign has tested (attempts #7/#11/#14x2/#15/#17) landed
between r=0.117 and r=0.947 on that check; this is the 7th.

ebwm.pt is loaded frozen and never written. No MineRL, no Java, no GPU required
beyond what encoding a few hundred windows needs.

Usage:
  run.bat scripts/diagnose_context_collapse.py --config configs/diagnose_context_collapse.yaml
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
import torch
import yaml

from mine_jepa.ebwm.dataset import MineRLSeqDataset
from scripts.play_ebwm import load_model


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/diagnose_context_collapse.yaml")
    return p.parse_args()


@torch.no_grad()
def rollout(model, obs_ctx: torch.Tensor, actions: torch.Tensor, horizon: int) -> torch.Tensor:
    """
    obs_ctx: [B, 3, 1, H, W] single context frame.
    actions: [B, 1, horizon] discrete action indices.
    Returns the predicted latents for steps 1..horizon: [B, D, horizon, h, w].
    """
    predicted, _ = model.unroll(
        obs_ctx, actions, nsteps=horizon, unroll_mode="autoregressive",
        ctxt_window_time=1, compute_loss=False,
    )
    return predicted[:, :, 1:]


def cosine_per_step(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Cosine similarity per (batch, step) over the flattened latent map: [B, K]."""
    b, _, k = pred.shape[0], pred.shape[1], pred.shape[2]
    p = pred.permute(0, 2, 1, 3, 4).reshape(b, k, -1)
    t = target.permute(0, 2, 1, 3, 4).reshape(b, k, -1)
    return torch.nn.functional.cosine_similarity(p, t, dim=-1)


@torch.no_grad()
def planner_spread(model, obs_ctx: torch.Tensor, horizon: int, n_candidates: int,
                   n_actions: int, generator: torch.Generator) -> torch.Tensor:
    """
    Std, across `n_candidates` random action sequences from the same context, of the
    final-step mean-squared-L2 latent distance planner.py::_score ranks candidates on.
    Returns [B] — one spread per window, in the planner's own units.
    """
    b = obs_ctx.shape[0]
    device = obs_ctx.device
    cand = torch.randint(
        0, n_actions, (b, n_candidates, horizon), generator=generator, device=device
    )
    spreads = torch.empty(b, device=device)
    for i in range(b):
        ctx = obs_ctx[i : i + 1].expand(n_candidates, -1, -1, -1, -1)
        pred = rollout(model, ctx, cand[i].unsqueeze(1), horizon)
        final = pred[:, :, -1]
        flat = final.reshape(n_candidates, -1)
        f = flat.shape[1]
        # Pairwise distance to the candidate set's own centroid, in _score's units
        # (squared L2 divided by feature count) — the quantity whose collapse makes
        # every candidate look equally good to the planner.
        centroid = flat.mean(dim=0, keepdim=True)
        dist = ((flat - centroid) ** 2).sum(dim=1) / f
        spreads[i] = dist.std()
    return spreads


@torch.no_grad()
def action_response(model, obs_ctx: torch.Tensor, n_actions: int) -> tuple[float, float]:
    """
    Two scale checks that separate "the predictor ignores actions" from "the predictor
    responds to actions, but not usefully" — a distinction ActSWM's delta alone cannot
    make, because a delta near zero is consistent with both.

    Returns (action_spread, real_move):
      action_spread: mean L2 spread of the 1-step prediction across all n_actions
                     choices from the same frame — how much the action pathway moves
                     the prediction at all.
      real_move:     ||z_{t+1} - z_t||, the true 1-step latent change the predictor is
                     trying to explain — the denominator that makes the spread meaningful.
    """
    ctx = obs_ctx[:, :, :1].expand(n_actions, -1, -1, -1, -1)
    acts = torch.arange(n_actions, device=obs_ctx.device).view(n_actions, 1, 1)
    pred = rollout(model, ctx, acts, 1)[:, :, -1].reshape(n_actions, -1)
    z = model.encode(obs_ctx[:, :, :2])
    z0, z1 = z[:, :, 0].reshape(1, -1), z[:, :, 1].reshape(1, -1)
    spread = float((pred - pred.mean(dim=0, keepdim=True)).norm(dim=1).mean().item())
    return spread, float((z1 - z0).norm().item())


@torch.no_grad()
def evaluate_domain(model, path: str, max_action: int | None, horizon: int,
                    n_windows: int, n_candidates: int, noop_action: int,
                    n_actions: int, device: torch.device, seed: int) -> dict:
    ds = MineRLSeqDataset(path, num_frames=horizon + 1, subsample=1, max_action=max_action)
    if len(ds) == 0:
        raise ValueError(f"{path}: no valid windows at horizon={horizon}, max_action={max_action}")

    rng = np.random.default_rng(seed)
    idx = rng.choice(len(ds), size=min(n_windows, len(ds)), replace=False)
    generator = torch.Generator(device=device).manual_seed(seed)

    s_gt, s_zero, s_rand, spreads, brightness = [], [], [], [], []
    act_spreads, real_moves = [], []

    for j in idx:
        obs, actions, _ = ds[int(j)]
        obs = obs.unsqueeze(0).to(device)                 # [1, 3, T, H, W]
        actions = actions.unsqueeze(0).to(device)         # [1, 1, T]

        ctx = obs[:, :, :1]
        a_gt = actions[:, :, :horizon]
        a_zero = torch.full_like(a_gt, noop_action)
        a_rand = torch.randint(
            0, n_actions, a_gt.shape, generator=generator, device=device
        )

        target = model.encode(obs[:, :, 1:])              # [1, D, K, h, w]
        s_gt.append(cosine_per_step(rollout(model, ctx, a_gt, horizon), target)[0].cpu().numpy())
        s_zero.append(cosine_per_step(rollout(model, ctx, a_zero, horizon), target)[0].cpu().numpy())
        s_rand.append(cosine_per_step(rollout(model, ctx, a_rand, horizon), target)[0].cpu().numpy())

        spreads.append(float(planner_spread(
            model, ctx, horizon, n_candidates, n_actions, generator
        )[0].item()))
        brightness.append(float(obs[0, :, 0].mean().item()))

        a_sp, r_mv = action_response(model, obs, n_actions)
        act_spreads.append(a_sp)
        real_moves.append(r_mv)

    s_gt = np.stack(s_gt)       # [W, K]
    s_zero = np.stack(s_zero)
    s_rand = np.stack(s_rand)
    delta_zero = s_gt - s_zero
    delta_rand = s_gt - s_rand

    r_brightness = float(np.corrcoef(np.array(brightness), delta_zero[:, -1])[0, 1])

    from scipy import stats

    # Step 1 is the regime ebwm.pt was actually trained on (train_eb_jepa.py uses
    # nsteps=1), so a deficit there cannot be blamed on multi-step rollout drift.
    d1 = delta_zero[:, 0]
    t_stat, p_value = stats.ttest_1samp(d1, 0.0)
    act_spread_mean = float(np.mean(act_spreads))
    real_move_mean = float(np.mean(real_moves))

    return {
        "n_windows": int(len(idx)),
        "n_valid_windows_available": int(len(ds)),
        "s_gt_per_step": s_gt.mean(axis=0).tolist(),
        "s_zero_per_step": s_zero.mean(axis=0).tolist(),
        "s_rand_per_step": s_rand.mean(axis=0).tolist(),
        "delta_zero_per_step": delta_zero.mean(axis=0).tolist(),
        "delta_rand_per_step": delta_rand.mean(axis=0).tolist(),
        "s_gt_final": float(s_gt[:, -1].mean()),
        "delta_zero_final": float(delta_zero[:, -1].mean()),
        "delta_zero_final_std": float(delta_zero[:, -1].std()),
        "delta_rand_final": float(delta_rand[:, -1].mean()),
        "delta_rand_final_std": float(delta_rand[:, -1].std()),
        "planner_spread_mean": float(np.mean(spreads)),
        "planner_spread_std": float(np.std(spreads)),
        "brightness_mean": float(np.mean(brightness)),
        "corr_delta_brightness": r_brightness,
        "delta_zero_step1_mean": float(d1.mean()),
        "delta_zero_step1_sem": float(d1.std() / np.sqrt(len(d1))),
        "delta_zero_step1_t": float(t_stat),
        "delta_zero_step1_p": float(p_value),
        "delta_zero_step1_win_frac": float((d1 > 0).mean()),
        "action_spread_mean": act_spread_mean,
        "real_1step_move_mean": real_move_mean,
        "action_share_of_real_move": act_spread_mean / real_move_mean,
    }


def main() -> None:
    args = parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt_path = cfg["checkpoint"]
    model, ratio = load_model(ckpt_path, device)
    for p in model.parameters():
        p.requires_grad_(False)
    n_actions = model.action_encoder.embed.num_embeddings

    print(f"[context-collapse] checkpoint={ckpt_path} ratio={ratio:.4f} "
          f"n_actions={n_actions} device={device}")

    r = cfg["rollout"]
    horizon, n_windows, n_candidates = r["horizon"], r["windows_per_domain"], r["n_candidates"]
    print(f"[context-collapse] horizon={horizon} windows/domain={n_windows} "
          f"candidates/window={n_candidates}")

    results = {}
    for name, d in cfg["domains"].items():
        if not Path(d["path"]).exists():
            print(f"[context-collapse] SKIP {name}: {d['path']} not found")
            continue
        print(f"[context-collapse] evaluating {name} ({d['path']}) ...", flush=True)
        results[name] = evaluate_domain(
            model, d["path"], d["max_action"], horizon, n_windows, n_candidates,
            cfg["noop_action"], n_actions, device, cfg["seed"],
        )
        m = results[name]
        print(f"    windows={m['n_windows']}/{m['n_valid_windows_available']}  "
              f"s_gt@K={m['s_gt_final']:.4f}  "
              f"delta_zero@K={m['delta_zero_final']:.5f}  "
              f"delta_rand@K={m['delta_rand_final']:.5f}  "
              f"planner_spread={m['planner_spread_mean']:.3e}  "
              f"r(delta,brightness)={m['corr_delta_brightness']:+.3f}")

    print("\n" + "=" * 78)
    print("GATES")
    print("=" * 78)

    if "treechop" in results:
        tc = results["treechop"]
        print(f"\nPositive control — Treechop (ebwm.pt's home domain, 25-50% chop in Phase 4):")
        print(f"  s_gt@K       = {tc['s_gt_final']:.4f}")
        print(f"  delta_zero@K = {tc['delta_zero_final']:.5f} (ActSWM protocol)")
        print(f"  delta_rand@K = {tc['delta_rand_final']:.5f} (planner-matched)")
        collapse_tc = tc["s_gt_final"] > 0.5 and abs(tc["delta_rand_final"]) < 0.01
        print(f"  Context Collapse on Treechop itself: "
              f"{'YES — high fidelity, no action gap' if collapse_tc else 'no'}")

    print("\nWhich failure is it? A near-zero delta is consistent with TWO different")
    print("models, and ActSWM's delta alone cannot tell them apart:")
    print("  (a) the predictor ignores the action  -> action_share ~ 0")
    print("  (b) it responds, but not usefully     -> action_share > 0, delta still ~ 0")
    for name, m in results.items():
        verdict = "(a) ignores actions" if m["action_share_of_real_move"] < 0.01 else \
                  "(b) responds, but the response does not predict the true future"
        print(f"\n  {name}:")
        print(f"    action-induced spread   = {m['action_spread_mean']:.4f}")
        print(f"    real 1-step latent move = {m['real_1step_move_mean']:.4f}")
        print(f"    action share of real move = {100 * m['action_share_of_real_move']:.1f}%  -> {verdict}")
        print(f"    delta_zero at step 1 (the trained regime): "
              f"{m['delta_zero_step1_mean']:+.6f} +/- {m['delta_zero_step1_sem']:.6f} "
              f"(t={m['delta_zero_step1_t']:.2f}, p={m['delta_zero_step1_p']:.4f})")
        print(f"    windows where the TRUE action beats noop: "
              f"{100 * m['delta_zero_step1_win_frac']:.1f}%  (chance = 50%)")

    # Ratios are deliberately NOT reported here: delta_zero is negative in every
    # domain, so a ratio of two negatives reads as "larger is better" while it
    # actually means "more negative". Absolute values, side by side, with the
    # ordering spelled out instead.
    print("\nBaseline ordering per domain (which rollout best matches the true future)")
    print("  delta_zero = s_gt - s_noop  (>0: the true action beats assuming noop)")
    print("  delta_rand = s_gt - s_random(>0: the true action beats a random action)")
    print(f"\n  {'domain':18s} {'real 1-step move':>17s} {'delta_zero@K':>13s} {'delta_rand@K':>13s}  ordering")
    for name, m in results.items():
        beats_noop = m["delta_zero_final"] > 0
        beats_rand = m["delta_rand_final"] > 0
        if not beats_noop and beats_rand:
            ordering = "noop > true > random"
        elif beats_noop and beats_rand:
            ordering = "true > noop, true > random"
        elif not beats_noop and not beats_rand:
            ordering = "noop > true, random > true"
        else:
            ordering = "true > noop, random > true"
        print(f"  {name:18s} {m['real_1step_move_mean']:17.4f} "
              f"{m['delta_zero_final']:13.5f} {m['delta_rand_final']:13.5f}  {ordering}")

    print("\nNegative control — corr(delta_zero@K, frame brightness) per domain")
    print("  (campaign range for every prior mechanism: 0.117 to 0.947)")
    for name, m in results.items():
        print(f"  {name:18s} r = {m['corr_delta_brightness']:+.3f}")

    out = cfg["output"]
    Path(out["json"]).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "checkpoint": ckpt_path,
        "ratio": ratio,
        "horizon": horizon,
        "n_actions": n_actions,
        "seed": cfg["seed"],
        "domains": results,
    }
    Path(out["json"]).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with open(out["csv"], "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["domain", "step", "s_gt", "s_zero", "s_rand", "delta_zero", "delta_rand"])
        for name, m in results.items():
            for k in range(horizon):
                w.writerow([
                    name, k + 1,
                    f"{m['s_gt_per_step'][k]:.6f}", f"{m['s_zero_per_step'][k]:.6f}",
                    f"{m['s_rand_per_step'][k]:.6f}", f"{m['delta_zero_per_step'][k]:.6f}",
                    f"{m['delta_rand_per_step'][k]:.6f}",
                ])
    print(f"\n[context-collapse] wrote {out['json']} and {out['csv']}")


if __name__ == "__main__":
    main()

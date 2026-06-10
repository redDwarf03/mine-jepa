# Phase 5+ — Curiosity for cold-start, attempt #1 (a documented negative result)

> The previous chapter (`docs/08_crafting.md`) ended on a promise: an agent driven by
> **intrinsic reward = world-model prediction error** should learn the craft precondition
> *and* explore toward trees from a cold start. This chapter is the first real attempt at
> the exploration half — and it **failed, cleanly and instructively.** A diagnosed negative
> result is worth more than a vague "future work" line.

---

## The setup: a 3-agent development loop

Before running experiments we built a small reusable harness (`.claude/`) so each
hypothesis is turned into a *refutable, executed* experiment rather than taken on faith:

| Agent | Role | Tools |
|-------|------|-------|
| `jepa-explorer` | Read-only. Proposes ONE concrete experiment grounded in the verified bibliography (`docs/references/index.md` §3). | read + web |
| `jepa-developer` | Implements the proposal (config-gated), respects the guardrails (never overwrite a good checkpoint, seed, keep anti-collapse), runs training. Fixes from test feedback. | read/edit/bash |
| `jepa-tester` | Runs the gates + the cold-start play test, reports PASS/FAIL with the **actual numbers**, honest about variance. Never edits code. | read/bash |

Orchestrated by `/jepa-loop` (explore → develop → test → route on the verdict). The
north-star: *a JEPA agent that plays Minecraft*, currently blocked on cold-start chopping.

---

## Proposal #1 — Plan2Explore open-loop novelty

**Idea** (grounded in Plan2Explore, [arXiv:2005.05960](https://arxiv.org/abs/2005.05960)):
the goal-centroid chopper has no direction when **no tree is in view** — every candidate
action sequence is equally far from the "tree" prototype, so the score is flat. Add an
**intrinsic novelty bonus** so the planner steers toward *expected future novelty* until a
tree enters view, then the existing chopper takes over.

```
score = goal_score + λ · novelty_score        (λ = novelty_coeff, default 0 = OFF)
novelty_score = disagreement of an ensemble of one-step latent predictors
```

**Implementation** (config-gated, the main WM untouched):
- `mine_jepa/ebwm/curiosity.py` — `DisagreementEnsemble`, k=5 action-conditioned one-step
  heads on the spatial latent `[D,8,8]`; `.disagreement()` = variance across heads.
- `scripts/train_curiosity.py` — trains the ensemble on **frozen** eb-JEPA latents
  (separate optimizer, seeded, saves to `checkpoints/curiosity_ensemble.pt`, never touches
  `ebwm.pt`). Anti-collapse of the main WM is therefore structurally safe.
- `mine_jepa/ebwm/planner.py` — `DiscreteLatentPlanner` blends the z-scored novelty into
  the score when `novelty_coeff > 0`; default `0.0` = the original behaviour, bit-for-bit.
- `configs/play_explore.yaml` — `novelty_coeff: 1.0` for the ON condition.

---

## The result: ON ≈ OFF (in fact slightly worse), at 2.5× the cost

A/B on `MineRLTreechop-v0`, 20 episodes each, same frozen `ebwm.pt` (ratio 0.927):

| Condition | Success (reward>0) | Mean reward | Logs total | fps |
|-----------|--------------------|-------------|-----------|-----|
| **OFF** (goal-centroid only) | **6/20 = 30%** | **0.40** | 8 (two 2-log eps) | 63 |
| **ON** (novelty λ=1.0) | 5/20 = 25% | 0.25 | 5 (all single) | **25** |

The 30% vs 25% gap is **not** a real effect at N=20 given Treechop's documented 25–50%
variance. The honest reading: **curiosity added no signal, and cost 2.5× the compute** (the
ensemble runs over 512 candidates every planning step → fps 63 → 25).

`jepa-tester` verdict: **FAIL** (no cold-start improvement; speed penalty with zero gain).

---

## Root cause: the ensemble collapsed *during training*

The training log told the story before the play test even ran:

```
epoch 1: val_disagree = 0.0613   (healthy diversity)
epoch 2: val_disagree = 0.0122
epoch 3: val_disagree = 0.0017   (collapsed)
epoch 4–15: val_disagree ≈ 0.0005   (dead, never recovers)
```

By epoch 3 the **5 heads had converged to the same function** → disagreement ≈ 0
everywhere → the novelty bonus was uniformly zero → the planner saw exactly the
goal-centroid score → identical 25–30% chop rate, just slower.

### Why it collapsed — the deep lesson

> **We reproduced the *form* of Plan2Explore without the *condition* that makes it work.**

Plan2Explore trains its ensemble **online, on data the agent gathers while exploring** —
that stream is diverse, so the heads keep disagreeing on the frontier. We trained on a
**fixed, narrow set of Treechop demos** (mostly the same lumberjack gesture, same tree
type, same camera). On data that homogeneous, every head finds the *same* trivial low-loss
solution → diversity dies. An ensemble's novelty signal is only as good as the diversity of
what it was trained on, and **offline frozen-latent training on expert demos actively
destroys that diversity.**

This rhymes with the Phase 5 precondition lesson: expert demos are too clean. There, they
lacked *failed crafts*; here, they lack *exploratory diversity*. Both gaps point at the
same missing ingredient — **self-generated experience.**

---

## What the next iteration should try

In order of fit (the `jepa-explorer`'s candidates for cycle #2):

1. **Force diversity** — explicit inter-head disagreement regularizer, or bootstrap each
   head on a disjoint data shard. Cheapest patch to the current module.
2. **RND** ([arXiv:1810.12894](https://arxiv.org/abs/1810.12894)) — novelty = error against
   a *fixed random* target network. **Structurally immune to this collapse**: the target
   never moves, so it cannot homogenize. Strong next candidate.
3. **Online self-play** — collect curiosity-driven data *first*, then (re)train the
   ensemble on it. The actual Plan2Explore recipe; the heaviest but most faithful.

---

## Honest status

| Item | Status |
|------|--------|
| 3-agent loop (explore/develop/test) runs end-to-end | ✅ produced this experiment |
| Curiosity module (Plan2Explore offline ensemble) | ✅ implemented, config-gated, WM safe |
| Cold-start chopping improved by curiosity | ❌ no — ensemble collapsed, ON ≈ OFF |
| Diagnosis + next direction | ✅ ensemble-diversity collapse → RND / diversity reg / self-play |

**The wall still stands** — but we now know one specific thing that does *not* knock it
down, and exactly why. That is the point of the loop.

---

*Previous: `docs/08_crafting.md` (the cold-start wall). References: `docs/references/index.md` §3 (exploration).*

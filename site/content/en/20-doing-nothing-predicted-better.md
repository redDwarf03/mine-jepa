---
title: "Doing nothing predicted better: twenty attempts fixing the driver, when the problem was the engine"
slug: "20-doing-nothing-predicted-better"
lang: "en"
order: 20
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft", "07-broken-curiosity", "08-the-wall-is-behavioral", "09-next-directions", "10-the-cleanest-negative", "11-compass-points-backwards", "12-memory-of-visited-places", "13-blind-rescue", "14-a-web-giant-put-to-the-test", "15-fifth-confirmation-false-alarm", "16-predicting-the-future-not-the-image", "17-the-shortcut-is-in-the-eye", "18-the-victory-that-did-not-hold", "19-two-levers-two-understood-failures"]
source_docs: ["docs/10_coldstart_engineering.md#Attempt #20", "CLAUDE.md#Phase 5+ — Cold-start attempt #20"]
---

::: beginner

## Where we left off

Chapter 19 ended on a chosen pause. Two attempts to retrain the core of the main model had both
failed, each for a reason that was understood rather than guessed. Nineteen attempts, and the best
result the whole campaign had ever produced was still under 10% — one success in ten runs, at best.

This chapter is the last of the campaign. It contains its single most important finding, and that
finding arrived from an unexpected direction: not from another idea about how to search better, but
from a question nobody had ever thought to ask.

## A paper about our own architecture

A routine re-reading of recent scientific publications turned up a paper studying almost exactly
this project's setup: the same family of world model, planning in Minecraft, in closed loop. It
described a failure mode with a name: **context collapse**.

The idea is unsettling once you see it. A world model can be very good at predicting what the next
moment will look like — and yet produce *almost the same prediction whatever the agent decides to
do*. In that state, all the usual measurements look healthy. The model predicts well. Nothing seems
broken. But a planner built on top of it is blind, because planning consists entirely of comparing
"what happens if I do this" against "what happens if I do that". If those two imagined futures are
nearly identical, there is nothing to compare, and the choice is made on noise.

Nineteen attempts had been spent improving how the agent searches, how it scores what it sees, how
long it commits to a plan. **Not one had ever checked whether the world model reacts to the agent's
actions at all.**

## The measurement

The test is simple to describe. Take a real moment from a recorded game. From that single frame,
ask the model to imagine twelve steps into the future twice: once using the actions the player
really took, and once pretending the player did nothing at all. Then compare both imagined futures
against what actually happened.

If the model understands actions, the version using the real actions should be closer to reality.
That is the whole point of a world model.

The result, measured on 400 moments in each of three different settings:

**Using the real actions predicts the future slightly *worse* than pretending the agent did
nothing.**

Not equal. Worse — and reliably so, not by accident. In the crafting environment, the real action
beat "do nothing" in only 13% of the moments tested. Pure chance would give 50%.

## What is broken, precisely

It would be easy to conclude that the model simply ignores actions. It does not, and the difference
matters.

A second measurement checked this directly: from one frame, ask the model to imagine the next
moment under each of the seventeen possible actions, and see how far apart those seventeen
imaginings are. They are genuinely different from one another. The internal machinery that
represents actions is healthy and well-formed. The model does react.

But the reaction accounts for only about 4% of what really changes between two consecutive moments
in the game — and it pushes in a direction that does not match reality. The model has learned to
respond to actions; it has not learned to respond *correctly*.

An analogy: imagine a car whose steering wheel is definitely connected — turn it and the car does
change direction — but wired so the connection has almost nothing to do with where the road goes.
The wheel is not broken. It moves the car. It simply does not help you drive.

## A detail that makes the story hold together

One number was not planned for, and it is the most convincing part of the result.

The three settings tested differ in how much movement they contain. The crafting recordings are
mostly static — a lot of standing still, menus, small gestures. The tree-chopping recordings are
the most active. Ranked from most static to most active, the model's failure rate follows exactly:
the more static the footage, the more often "do nothing" wins.

That is precisely what you would expect if the problem is what we just described. When very little
moves, "assume nothing changes" is already an excellent guess, and any action-driven adjustment
that is even slightly miscalibrated does more harm than good. Nobody designed the test to produce
that pattern; it simply fell out of the data. When a result predicts something you were not looking
for, that is usually a sign it is real.

## The honest complication

There is a tension in this finding, and it will not be smoothed over.

The agent chops trees successfully 25 to 50% of the time in the simple tree-chopping environment
(Chapter 5) — **with this exact defect present**. If a world model that misunderstands actions made
planning impossible, nothing would ever have worked. Something did work.

So this finding cannot, on its own, be the complete explanation of why the agent fails from a cold
start. Any account leaning on it has to explain the successes too, and this chapter does not offer
one. It would be a hypothesis, and this site has spent nineteen chapters distinguishing hypotheses
from measurements.

What the finding does explain is why nineteen attempts to improve the *planner* changed so little.
They were all refining how to choose between options that the model could not meaningfully tell
apart.

It also makes sense of the campaign's one real success. The single change that ever produced a
non-zero result (Chapter 8) was making the agent stick to its plan for longer instead of
reconsidering at every instant. If the information available at each instant is mostly noise, then
deciding less often and committing more is exactly the right response. The project found that by
trial and error, without knowing why it helped.

## Why the campaign closes here

After this measurement, the decision was taken to close the cold-start campaign rather than open a
twenty-first attempt.

The reasoning is not exhaustion. It is that the remaining option is a different kind of work. The
paper that prompted this chapter also proposes a fix — a way of training that forces the model to
keep action consequences distinguishable. Half the necessary machinery turns out to already exist
in this project's code, switched off since the beginning. But applying it properly would probably
also mean changing how much of the past the model can see at once: the published version looks at
thirty-two moments of history, ours at one. That is rebuilding the world model, not adjusting it.

And it is worth stating plainly what closing does **not** claim. It does not claim that a JEPA agent
cannot learn to find its first tree. The paper that started this chapter shows a model of the same
family planning successfully in Minecraft — mining stone in 19 attempts out of 20. The capability is
real for this kind of architecture, at a larger scale than this project's. What is claimed is much
narrower and much better supported: **this particular approach — repairing the planner around a
small, frozen world model — is finished, and we now know why.**

## What this project actually achieved

It is worth ending on an accurate ledger rather than a mood.

The agent learned to see without labels, without collapsing (Chapters 1-2). It learned to imagine
the consequences of its actions well enough to plan (Chapters 3-4). It plays real Minecraft and
chops real trees (Chapter 5). It crafts, end to end, given wood (Chapter 6). Every one of those was
verified against a stated numerical bar before being called a success.

And then twenty documented attempts at a problem that was not solved — including six independent
confirmations of a single confusing measurement error, a victory that was retracted the day it was
found, and a root-cause diagnosis at the very end. Most published work shows only the part that
worked. This site has shown the rest, at the same level of precision, because that is the part that
teaches something.

:::

::: expert

## Context

Chapter 19 (attempt #19) closed on a user-chosen pause: both concretely scoped core-objective
retraining levers had failed, each with a diagnosed cause. This chapter covers attempt #20 in
`docs/10_coldstart_engineering.md` and `CLAUDE.md#Phase 5+` — **the first measurement in the
campaign of whether `ebwm.pt`'s rollouts respond to actions at all**, and the campaign's closing
result.

Note that attempts #7-#19 were, with the exception of #19 itself, almost entirely *scoring-side* or
*search-side* interventions. The dynamics — whether the world model's imagined futures actually
depend on the actions being planned — had never been instrumented.

## Origin

A bibliography refresh (2026-08-10, covering 2026-07-27 onward, querying arXiv *and* Google Scholar
rather than arXiv alone) surfaced Gan, Zeng, Cheng, Song, Tang, Wang, "ActSWM: Action-Sensitive
World Models for Long-Horizon Planning in Open-World Games"
([arXiv:2607.26712](https://arxiv.org/abs/2607.26712), 2026) — **whose baseline is LeWM, this
project's own architecture family, evaluated on closed-loop Minecraft planning**.

It names **Context Collapse**: an autoregressive latent predictor that maintains high cosine
similarity to true future states while producing nearly indistinguishable futures under different
action sequences. A healthy prediction `ratio` with a blind planner — this project's exact Phase 4/5
symptom.

The paper was verified by reading its LaTeXML source directly (equations, Table 3 hyperparameters,
Table 8 counts), not via a summariser. That check mattered: it caught that the paper reports its
gains in two different conventions (percentage points in the introduction, relative in the results
section), corrected an attribution of its SigReg term to LeWM rather than LeJEPA, and surfaced a
detail no summary mentioned — see "the lever this opens" below.

## Method

`scripts/diagnose_context_collapse.py` + `configs/diagnose_context_collapse.yaml`. Fully offline: no
MineRL, no Java, `ebwm.pt` loaded frozen with `requires_grad_(False)` and md5-reverified
(`ac14e65361fbddeb057963362ea1382d`, unchanged).

ActSWM's Eq. 10, adapted: from one encoded context frame, roll out K=12 steps twice from the same
context, comparing each against the encoded true future `z_{t+k}`:

- `s_gt_k = cos(ẑ_gt, z)` — recorded actions
- `s_zero_k = cos(ẑ_zero, z)` — all-noop counterfactual (action index 0)
- `delta_k = s_gt_k − s_zero_k` — the action gap

Two deliberate departures from ActSWM, reported separately rather than blended into their number:

1. A **random-action arm**. The planner never compares "recorded vs. noop"; it compares many
   non-noop candidates against each other.
2. A **planner-matched spread arm**: the std, across 64 candidate sequences, of the exact final-step
   latent distance `planner.py::_score` ranks on — the offline counterpart of the live
   `goal_score_std` logged since attempt #2.

**Treechop serves as its own positive control.** This project has no established threshold for
`delta_k` (never measured before), but the agent demonstrably plans successfully on Treechop
(Phase 4, 25-50% chop), which makes a Treechop-vs-Obtain comparison interpretable without an
external bar.

**A near-zero delta is ambiguous** and ActSWM's metric alone cannot disambiguate it, so a second
measurement was added: the L2 spread of the 1-step prediction across all 17 action choices from the
same frame, divided by the true 1-step latent change `‖z_{t+1} − z_t‖`. This separates "the predictor
ignores the action" (share ≈ 0) from "it responds, but not usefully" (share > 0, delta still ≈ 0).

## Result

n=400 windows/domain (266 for `obtain_coverage` — the only windows surviving the `max_action=17`
filter, so that column is noisier and is not treated as equal evidence).

| domain | real 1-step move | action spread | action share | Δ@k=1 win-rate | Δ_zero@K | Δ_rand@K |
|---|---|---|---|---|---|---|
| treechop | 16.22 | 0.615 | 3.8% | 35.5% | −0.00028 | +0.00012 |
| obtain_craft | 4.82 | 0.520 | 10.8% | 13.0% | −0.00055 | +0.00204 |
| obtain_coverage | 11.31 | 0.703 | 6.2% | 28.2% | −0.00150 | +0.00011 |

**Not Context Collapse as literally defined.** The action pathway works: the 17 actions genuinely
move the prediction, and the action embedding table is healthy (near-orthogonal, mean pairwise
cosine −0.014).

**But the response is a net liability.** `delta_zero` is negative in every domain, and significantly
so **at k=1 — the exact regime `ebwm.pt` was trained on** (`train_eb_jepa.py` uses `nsteps=1`), so
this cannot be attributed to multi-step rollout drift:

- treechop: −0.000444 ± 0.000178, t=−2.49, p=0.0130, true action wins in **35.5%** of windows
- obtain_craft: −0.000113 ± 0.000026, t=−4.37, p<0.0001, wins in **13.0%**
- obtain_coverage: −0.000149 ± 0.000059, t=−2.51, p=0.0126, wins in **28.2%**

The consistent ordering across all three domains is **noop > true action > random action**. The model
learned something real (the true action beats a random one) but not enough to clear the trivial
copy-last baseline the noop rollout approximates — consistent with `ratio=0.9265`, i.e. prediction
beats copy-last by only ~7%.

**Unplanned internal consistency check**: the win-rate is perfectly monotone in how dynamic the
domain is (real 1-step move 4.82 → 13.0%, 11.31 → 28.2%, 16.22 → 35.5%). The more static the
footage, the stronger copy-last is as a baseline, and the more a miscalibrated action perturbation
costs. This is the expected signature if the action response is a net liability against a strong
copy baseline; it was not designed for and fell out of the data.

**Negative control**: corr(delta, frame brightness) = −0.048 / +0.031 / −0.225 — the first mechanism
in this campaign essentially uncorrelated with brightness (prior range 0.117-0.947). Expected by
construction, since delta is a difference between two rollouts from the *same* frame, so frame-level
confounds cancel — but worth stating after six prior mechanisms failed this check.

## What this establishes, and what it does not

**Established**: `ebwm.pt` is, for planning purposes, close to a copy-last predictor carrying an
action-dependent perturbation that does not track true consequences. This holds on **Treechop, its
own training domain** — so unlike attempt #10's score reversal, it is not a domain-shift effect. It
is a second, independent defect on the **dynamics** side, whereas attempts #7-#19 targeted the
**scoring** side almost exclusively.

**NOT established — a genuine tension, not a footnote**: this cannot by itself be the cause of the
cold-start wall, because the agent chops trees 25-50% on Treechop *with this exact deficit present*.
Any account leaning on this finding has to explain that too. None is offered here; it would be a
hypothesis, not a measurement.

**NOT established**: that ActSWM's fix transfers. Their predictor carries H=32 context and their
causal story ("long context lets the predictor extrapolate scene progression while ignoring the
action") cannot apply unchanged to `ACConvPredictor`'s `context_length=1`.

**What it reframes**: `commit_length=4` remains the only lever that ever produced a non-zero result
(9.7% pooled). If per-step action information is at noise level against copy-last, then committing
to a block of actions instead of re-ranking every tick on a noise-dominated score is exactly the
right compensation. The campaign found this empirically in attempt #4 without knowing why.

## The lever this opens — not taken

ActSWM's `L_readout` term (Eq. 8) enforces exactly the property measured broken here: that the
action associated with each local transition remain recoverable. **Half that machinery already
exists in this repository, disabled since day one**: `mine_jepa/eb_jepa/losses.py::InverseDynamicsLoss`
is `(state_t, state_t+1) → action`, wired into `VC_IDM_Sim_Regularizer`, but `build_ac_jepa` passes
`idm_coeff=0.0, idm=None` (`mine_jepa/ebwm/__init__.py:146`), so it has never been instantiated.
Missing versus ActSWM: parameter freezing (their `idm.stop_grad=true` excludes φ₀ from the optimizer
while still backpropagating through the latent inputs), application to rollout-predicted transitions
(Eq. 8b), and the hinge term (Eq. 5) entirely.

## Campaign closed on attempt #20

The cold-start campaign is **closed here**, by the user's decision (2026-08-10), with attempt #20 as
its concluding result rather than a 21st attempt. Stated plainly so a later reader does not mistake
it for exhaustion:

- **The campaign was working on the wrong layer.** Attempts #2-#19 tuned search, scoring and
  execution on top of a frozen `ebwm.pt`. Attempt #20 measured that `ebwm.pt`'s own action
  conditioning is a net liability against copy-last, so an MPC planner sitting on it ranks candidate
  action sequences by differences that do not track consequences. That retrospectively explains why
  three score fixes (#7, #11, #17), two search fixes (#5, #6) and two retrains (#19 Run A/B) each
  failed differently: none of them addressed the dynamics.
- **The remaining lever is a rebuild, not a patch** — the `L_readout`/hinge terms above, plausibly
  together with a context length greater than 1. That is a world-model rebuild, not another attempt
  in this campaign's idiom.
- **The project's stated purpose is already met**: Phases 0-4 validated against real gates, the
  agent chops trees in real Minecraft (25-50%), the live craft demo runs at 100% over 6+ episodes.

**NOT claimed by closing here**: not that cold-start chopping is impossible, and not that the
remaining lever would fail. ActSWM demonstrates a LeWM-family model planning successfully in
closed-loop Minecraft (mining 19/20 against LeWM's 10/20, at matched backbone, planner and action
library), so the capability is real for this architecture family at a larger scale. The narrower,
better-supported claim: **this campaign's approach — fixing the planner around a frozen
664K-parameter world model with `context_length=1` — is exhausted, and attempt #20 explains why.**

**Standing baseline if work ever resumes**: `commit_length=4` (9.7% pooled, the campaign's best
result), `FrontierTracker` coverage search (attempt #12), and the hazard-avoidance drowning fix
(attempt #13, confirmed at N=20: drowning 60% → 15%, fair-shot episodes 40% → 60%). Left open, not
resolved: attempt #18's deferred 2/6 `died_during_escape` signal, a possible regression of the #13
fix under the depth scan macro.

`ebwm.pt` and `craft_wm_v4.pt` untouched throughout this chapter; no checkpoint written.

## References

- Gan, Zeng, Cheng, Song, Tang, Wang, "ActSWM: Action-Sensitive World Models for Long-Horizon
  Planning in Open-World Games", [arXiv:2607.26712](https://arxiv.org/abs/2607.26712) (2026) —
  source of the Context Collapse definition, the Eq. 10 delta protocol adapted here, and the
  `L_readout`/hinge lever discussed above.

Verified in `docs/references/index.md`, along with eight further papers added in the same
bibliography pass.

:::

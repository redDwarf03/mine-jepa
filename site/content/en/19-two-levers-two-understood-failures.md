---
title: "The first real retraining of the model's core: two levers, two well-understood failures, one chosen pause"
slug: "19-two-levers-two-understood-failures"
lang: "en"
order: 19
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft", "07-broken-curiosity", "08-the-wall-is-behavioral", "09-next-directions", "10-the-cleanest-negative", "11-compass-points-backwards", "12-memory-of-visited-places", "13-blind-rescue", "14-a-web-giant-put-to-the-test", "15-fifth-confirmation-false-alarm", "16-predicting-the-future-not-the-image", "17-the-shortcut-is-in-the-eye", "18-the-victory-that-did-not-hold"]
source_docs: ["CLAUDE.md#Phase 5+ — Cold-start attempt #19"]
---

::: beginner

## Where we left off

Chapter 18 ended on a real decision, taken on 28 July 2026 by the project's owner: after
**eighteen attempts** to repair, from the outside, the way the main model (`ebwm.pt`) judges "is
there a tree close by?", all of them falling into the same brightness trap, it was time to try
something else — **to touch the very core of that model for the first time**, rather than keep
stacking crutches around it without ever opening the bonnet. Two precise, quantified ideas were on
the table, found in the previous chapter: widen the vocabulary of gestures the model has learned to
recognise, and change the anti-collapse ingredient that stops it "cheating" by learning to confuse
everything.

This chapter tells what happened when those two ideas were tried for real. Both failed — but
**each for a precise reason that was understood**, not left vague. And the decision that follows is
not an abandonment: it is a chosen pause.

## Lever 1: teaching the model more gestures

Recall from Chapter 18: a test had shown that in the runs where the expert chops trees, the model
has almost never seen certain gestures — jumping, strafing sideways, looking up or down. Out of
seventeen possible gestures, only eight really appeared in the original training data.

The fix was concrete: re-read the recorded runs and **recover** those gestures, which had been
there all along but which the data-preparation program did not yet know how to read correctly. Once
fixed, almost every gesture appears (fifteen out of seventeen instead of eight). The model was then
retrained, starting from its current weights — not from scratch — with a very cautious learning
rate (the equivalent of adjusting in small steps rather than rebuilding everything), across five
complete passes over the data.

**Result: it did not work.** The test measuring whether the model properly distinguishes "tree
close" from "no tree" failed both before AND after this retraining, with no gradual improvement
across the five passes. The gesture vocabulary did widen, but the way the model judges a scene did
not improve for it.

### Why? An investigation, not a guess

Faced with this failure, the team asked the right question before moving on: *why* did it not work?
A first, simple explanation came to mind — perhaps by adding the "jump" label, the program had
accidentally erased the "attack" label on the same frames (a bit like ticking a new box on a form
and mistakenly unticking one already filled in). **That explanation was checked twice, with exact
counts** — and it is false: the number of frames labelled "attack" stayed rigorously identical,
frame for frame, before and after.

What really changed: about 5 frames in 100 changed label, and the overwhelming majority of that
change is frames where the expert was moving forward AND jumping at the same time (a "bunny hop", a
genuinely real movement technique in Minecraft) — a real gesture finally being seen, not an error.

The most solid explanation (but **not yet proven**, and the team is honest about that): those rare
gestures accounted for roughly 1% of the model's training attention before the fix, and jumped
suddenly to around 4% after — up to nine times more on certain gesture combinations. It is a bit as
if a student who had barely ever practised the piano suddenly received nine times more lessons than
usual on that instrument: even if their other subjects do not change, the shock of that new learning
unbalances their general habits. A more cautious follow-up (introducing those gestures more
gradually) was considered but not attempted — the user preferred to move straight to the second
lever.

## Lever 2: changing the anti-collapse ingredient

The second lever touched something deeper: the ingredient that stops the model "cheating". Recall
from Chapter 2: a JEPA model can learn to represent *all* images the same way (a collapse) because
that artificially minimises its error without learning anything useful. This project has used an
ingredient called VICReg from the start to prevent that. Two recent scientific publications claim
that a newer ingredient, called **SIGReg**, is more reliable in theory.

Before writing any code, an examination of the existing code revealed a surprise: the version of
VICReg actually used in this project had, from the very beginning, only ever been **half** the full
recipe — just one of the two mechanisms the theory prescribes. That simplified the swap to SIGReg:
no need to rebuild an entire architecture, just to exchange one ingredient for another in the same
place.

The new ingredient was tested with the **most cautious recipe of the whole campaign**: an even
lower learning rate than Lever 1, a maximum of only three passes over the data, and above all — a
**new safeguard built specifically for this test**, able to detect a kind of collapse the old
monitoring tool cannot see.

### A different kind of collapse, caught before it did too much damage

Here is what that new danger is, with a simple picture. The project's old monitoring tool
(`batch_var`, used since Chapter 2) measures whether the model's representations have all become
*identical* — a collapse "in height", as if an entire class of students gave exactly the same answer
to every question. But there is a **second kind of collapse**, more insidious: the representations
do stay different from one another overall (so `batch_var` sees nothing wrong), but everything
making them different concentrates onto a handful of details, whereas the model previously had more
than four thousand different ways to vary. It is as if the whole class kept giving varied answers,
but those answers now only covered 4 or 5 topics instead of several thousand — an illusory richness.

**That is exactly what happened, from the very first pass over the data**, and the new safeguard
detected it and stopped training before continuing pointlessly: the effective number of "useful
directions" in the model's representations collapsed from 26.7 to 4.5 — an 83% drop — while the old
monitoring tool displayed a perfectly healthy figure, as good as any previous good training run.
Without that new safeguard, nobody would have noticed in time.

On that single model snapshot saved before the full shipwreck, the central test ("does it properly
distinguish tree-close from no-tree") gave a result **even worse** than Lever 1 — and the test on
the model's original task (chopping trees in the simple environment) very nearly collapsed too.
This new ingredient, as tried here, broke the model more broadly than it repaired it.

Important: that failure is **not** counted as a seventh confirmation of the famous brightness trap
from the previous chapters. It is a problem of a different nature — a collapse of the
representations, not a confusion between colour and distance. The two problems look alike in their
symptoms ("the model fails the test") but not in their cause.

## The decision: a pause, not an abandonment

Faced with two levers, two failures, each now well understood (not just "it did not work" but
"here is why"), the user chose to **pause the campaign** rather than immediately move on to a third
lever. This is an important decision not to misread: it does **not** mean that retraining the
model's core is impossible. It means that these two precise implementations, the cheapest available
for each idea, each failed for a reason that has now been identified — not for lack of trying, but
because of a real technical problem, spotted and explained.

What still stands and works, as the project's positive baseline: the rule preventing the agent from
abandoning its plan too soon, the search pushing the agent to explore the terrain rather than going
in circles, and the anti-drowning reflex. None of those three mechanisms was touched by this
attempt — nor was `ebwm.pt` itself, which remains identical to before, verified byte for byte.

:::

::: expert

## Context

Chapter 18 (attempt #18, `CLAUDE.md#Phase 5+`) closed on a user decision of 2026-07-28: after 18
attempts at *external* correction of `ebwm.pt`'s goal-centroid scoring (heads trained on frozen
latents, off-the-shelf models, hand-made features, closed-form statistics — 6 independent
confirmations of the same brightness/scene-composition confound), rework the training objective of
`ebwm.pt`'s **core** itself — never done in 18 attempts, always frozen or lightly nudged (attempt
#14 Phase 2). Two concrete levers, scoped by attempt #18's Diagnostic 2, were on the table:
(1) broaden Treechop's own action coverage and/or reweight toward Obtain's action mix (motivated by
Zhang et al., [arXiv:2607.22430](https://arxiv.org/abs/2607.22430)); (2) replace VICReg with SIGReg
(Balestriero & LeCun, [arXiv:2511.08544](https://arxiv.org/abs/2511.08544); Arnez & Gomez-Villa,
[arXiv:2607.13612](https://arxiv.org/abs/2607.13612)). This chapter covers attempt #19 as recorded
in `CLAUDE.md#Phase 5+`. **Not yet reflected in `docs/10_coldstart_engineering.md`** at the time of
writing — `CLAUDE.md` is the only source for this attempt.

## Run A — broaden Treechop's action coverage: NO-GO, diagnosed (not merely failed)

`scripts/prepare_demos.py::discretize_actions()` extended to read `action$jump/left/right/back` +
camera pitch — previously only forward/attack/sprint/yaw were read. Treechop's own action-index
coverage rises from 8/17 to 15/17. Fused with Obtain data exactly as in attempt #14 Phase 2,
fine-tuned 5 epochs from `ebwm.pt`'s current weights (LR=3e-5, VICReg intact, seed=0, snapshots
`ebwm_v3_actioncoverage_epoch{1..5}.pt`, `ebwm.pt` never touched, md5 re-verified).

| Gate | Result |
|---|---|
| A — separation (extended hand-labelled set tree_close n=10 / no_tree n=17, attempt #18's sample) | **FAIL on baseline (0.790x) AND all 5 epochs (0.531x-0.775x)**, non-monotone, never ≥1.3x |
| C — Treechop non-regression (new) | direction sub-test invalid by construction (the baseline itself fails it, 0.434x — not a fine-tune-caused regression) — removed from the verdict, magnitude band only retained |

JSD(Treechop, Obtain) barely moves: 0.1453 → 0.1585 (slightly worse) — raw index coverage improved
but distributional shape did not.

### Root-cause diagnostic (at the user's request, before deciding next steps)

Independently re-verified, **twice**, that the "jump masks attack in the if/elif priority order"
hypothesis is **FALSE**: "attack" frame counts are byte-identical between the old and new datasets
(265,454 / 265,454). What actually changed: 4.73% of frames relabelled, dominated by a genuine
`forward → forward+jump` reclassification (11,626 frames, an authentic bunny-hop, a correct relabel,
not corruption).

> **Best-supported explanation (not proven)**: those long-idle action indices (jump/strafe/pitch)
> went from roughly 1.2% to roughly 3.8% of the weighted training mass in a single step (~9x on the
> jump+forward index alone) — a sudden gradient injection onto near-untrained action embeddings,
> plausibly destabilising the predictor's shared weights, even though the frames of the
> already-well-trained indices did not themselves change.

A Run A-bis (warmup / frozen action-embedding table / lower LR) was scoped but not attempted — the
user chose to go straight to Run B.

## Run B — VICReg → SIGReg: NO-GO, more severely broken than Run A

Scoping revealed that `ebwm.pt`'s current "VICReg" is in reality only a
`HingeStdLoss+CovarianceLoss` on a single tensor (`state`) — `sim_coeff_t`/`idm_coeff` were already
inert at 0, and no paired-view/EMA-target mechanism exists in this pipeline. Implemented as a
~15-line `SIGRegRegularizer` calling the already-vendored `BCS(state, state)` (the same tensor
twice — the invariance term is neutral at 0 by construction, the anti-collapse role coming from the
Epps-Pulley marginal-gaussianity test alone, no EMA needed per LeJEPA's own "collapse-free without
stop-grad" claim).

Full replacement, not additive (`std_coeff=cov_coeff=0`, `sigreg_coeff=1.0`), original (non-`_v2`)
dataset, augmentation disabled to isolate the single variable under test, LR=1e-5 (10x more
cautious than Run A), 3-epoch cap with a **new effective-rank gate** (participation ratio on
`state`'s covariance), built specifically because `batch_var` cannot see *dimensional* (as opposed
to isotropic) collapse.

> **The new gate did exactly the job it was built for**: epoch 1 alone triggered early stop —
> effective rank collapsed from 26.69 to 4.50 (-83%) while `batch_var` stayed perfectly healthy
> (1.36, as high as any VICReg run) — a real collapse mode, invisible to the old metric, caught
> before wasting epochs 2-3.

Offline gates on that single snapshot: Gate A worse than Run A's baseline (0.367x against 0.790x,
more inverted, not less), Gate C severely failed (Treechop's own score falls to 5.7% of baseline — a
generically broken checkpoint, not a nuanced confound reading). Gate B passes nominally (r=0.131)
but is judged low-value here — a brightness-independence reading on a representation collapsed to
~4.5 effective dimensions is not measuring much. `ebwm.pt` never touched (md5 re-verified).

Explicitly **not** read as an 8th confirmation of the confound — the failure mode here (dimensional
collapse from a single-term anti-collapse loss with no covariance pressure) is mechanically distinct
from the brightness/composition confound established by the rest of the campaign. A mitigated Run
B-bis (`CovarianceLoss` partially retained alongside SIGReg, additive rather than full replacement)
was proposed as an option but not attempted.

## Decision

**User's decision, both levers having failed: pause and consolidate rather than immediately scope a
3rd lever.** Both of attempt #18 Diagnostic 2's concretely scoped fixes are now exhausted as
originally specified — this is not equivalent to "retraining `ebwm.pt`'s core objective is
impossible", only that these two specific, cheapest-available implementations each failed for two
distinct, now-diagnosed reasons: data-side gradient-injection instability (Run A); architecture-side
covariance under-constraint from a single-term anti-collapse loss (Run B). The non-photometric
mechanisms that already worked earlier in the campaign (`commit_length=4`, `FrontierTracker`
coverage search, the anti-drowning fix) remain the only validated positive results and constitute
the project's current baseline. No live MineRL/Java test was run for either Run A or Run B
(correctly withheld — neither passed its offline gate). `checkpoints/ebwm.pt` untouched throughout
attempt #19 (md5 `ac14e65361fbddeb057963362ea1382d`, re-verified after both runs);
`ebwm_v3_actioncoverage_epoch{1..5}.pt` and `ebwm_v3_sigreg_epoch1.pt` kept as comparison artefacts
only, neither promoted.

## References

- Zhang, Guan, Zhang, Zhang, Li, "On the Identifiability of Controlled World Models",
  [arXiv:2607.22430](https://arxiv.org/abs/2607.22430) (2026) — foundation of the Run A lever
  (action coverage/reweighting).
- Balestriero, LeCun, "LeJEPA: Provable and Scalable Self-Supervised Learning Without the
  Heuristics", [arXiv:2511.08544](https://arxiv.org/abs/2511.08544) (2025) — foundation of SIGReg
  (Run B), including the "collapse-free without stop-grad/EMA" claim.
- Arnez, Gomez-Villa, "The SIGReg Objective as Variational Free Energy: A Theoretical
  Active-Inference Account of JEPA World Models",
  [arXiv:2607.13612](https://arxiv.org/abs/2607.13612) (2026) — the theoretical critique of VICReg
  motivating Run B.

All three references are verified in `docs/references/index.md`.

:::

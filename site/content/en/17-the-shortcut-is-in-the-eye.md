---
title: "Even a detector that cannot learn anything falls into the same shortcut: the problem is in the eye, not in the learning"
slug: "17-the-shortcut-is-in-the-eye"
lang: "en"
order: 17
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft", "07-broken-curiosity", "08-the-wall-is-behavioral", "09-next-directions", "10-the-cleanest-negative", "11-compass-points-backwards", "12-memory-of-visited-places", "13-blind-rescue", "14-a-web-giant-put-to-the-test", "15-fifth-confirmation-false-alarm", "16-predicting-the-future-not-the-image"]
source_docs: ["docs/10_coldstart_engineering.md#Cold-start attempt #17", "CLAUDE.md#Phase 5+"]
---

::: beginner

## Where we left off

Since Chapter 11, an uncomfortable fact has been sitting at the centre of this whole campaign,
never repaired: the planner's compass — the one comparing an imagined story against a memory of
success — points **backwards** once it leaves its training ground. Every attempt since
(Chapters 12 to 16) has built something *around* that problem — a memory of visited places, an
anti-drowning reflex, an exploration prediction — without ever tackling the compass itself. This
chapter tells the story of the first two attempts aimed directly at the heart of the problem.
Neither works. But together, they teach something important about *where* this defect really
hides.

## First idea: don't repair the compass, learn not to trust it

Instead of correcting the compass's biased judgement, this first idea tries to route around it
differently: build a separate detector whose only job is to spot "this image looks like something
the model never saw properly during training" — and if so, ignore the compass and hand over to the
memory of visited places (Chapter 12), which has already proved itself.

What is distinctive about this detector is that it does not train at all, in the sense machine
learning usually means. No neural network, no gradient descent (the usual method by which a model
gradually adjusts its internal settings to improve a score). It simply measures, once and for all,
what the typical statistical shape — the average and the spread — of the training images looks
like in the compressed space (the **embedding**, the compact representation the model builds from
an image) that the model already uses. Then, for any new image, it simply computes how far that
image sits from this typical shape. Further away = more suspicious. It is a fixed mathematical
formula, not something that "learns" in a way a misleading shortcut could quietly slip into.

This detector was put through three tests, on the same frames already used in Chapter 11 to prove
the compass was inverted:

1. **Can it tell known ground from unknown ground?** Almost, but narrowly missed — the difference
   between the two categories was not sharp enough.
2. **Does it specifically spot the frames where the compass got it wrong**, rather than just "any
   somewhat different image"? Missed more clearly — the detector was reacting to "this is a
   different setting", not to "this is where the judgement is false".
3. **Does it get distracted by an unrelated detail, like the plain brightness of the image?**
   Clearly missed, and this is the most important of the three results: the detector tracked
   brightness almost as much as the previous failed attempts in Chapters 10, 14 and 15.

## Why this third failure matters more than the five before it

Here is this chapter's most important point. Five times before this one (Chapters 10, 11, 14
counting both its halves, and 15), a trained system was caught out by scene brightness instead of
genuinely judging whether a tree was present. One could have thought the problem came from the way
those systems *learned* — an easy shortcut that training would always end up finding, like a path
of least resistance. But this new detector **learns nothing at all**. It is a fixed formula, with
no adjustable settings, with no way to "cheat" by finding a shortcut during training — because
there is no training.

And yet it falls into exactly the same trap.

That completely changes the most likely explanation. The problem is probably not "our training
methods always find the same bad shortcut". The problem runs deeper: the confusion between "there
is a tree close by" and "this is dark" appears to be **already present in the very way the base
model compresses an image into a compact representation** — before any additional learning is
involved at all. Any calculation built on top of that representation, however careful, inherits the
same defect, because the defect is in the raw material, not in how it is worked.

## Second idea, more modest: does the problem come from a shortage of dark photos?

This chapter's second line revisits an old hypothesis never directly tested, dating back to the
very start of this investigation (the brightness shortcut fixed — unsuccessfully — in Chapter 10):
what if the model confuses darkness with the absence of a tree simply because it had almost never
seen dark scenes during its very first training?

The check is simple, with nothing trained: count, in the original training data, the proportion of
dark or underwater frames. Result: barely 1% — so the lack-of-diversity hypothesis was
well-founded, for that original model.

But Chapter 14 had already retrained a version of the model on a much broader data mixture,
including many scenes from the real crafting environment — and this check shows those data already
contained 16 to 22% dark or underwater frames, even counting generously. The odd frame spotted in
Chapter 14 (the one whose score got worse after retraining) was therefore not an extreme case never
encountered: it resembles many other frames already present in the training data. **Conclusion: for
this precise case, missing dark photos is no longer a plausible explanation.** If anyone ever picks
up repairing the base model, the most promising direction is probably not "more data", but
something in *the way training compares different scenes with one another* — a point nobody has
tested yet.

## What this changes for what follows

These two negative results, taken together, close one question and clarify another:

- **Sixth independent confirmation of the same brightness trap** — after a small trained module,
  that same module retrained, an artificial lighting variation, a giant off-the-shelf model, a
  hand-built colour calculation, and now a plain statistical formula with no learning at all. Six
  completely different ways of going about it, one and the same wall.
- **The "not enough dark data" direction is closed** for the precise case that motivated it — not
  because more data would never help in general, but because, in this precise case, there was
  already enough.
- The project therefore faces a clear choice, not yet settled: either retrain the very core of the
  model with a different training objective — a heavy piece of work, never attempted so far — or
  accept this defect as a known project limitation and keep building on what already works
  (executing plans for longer, the memory of visited places, the anti-drowning reflex). This is not
  yet decided, and this chapter does not decide it on anyone's behalf.

As with every chapter on this site: two real attempts, two honest failures, and a result that, even
though negative, teaches something solid about the nature of the problem.

:::

::: expert

## Context

Chapter 16 (attempt #16, CVP) closed without touching the central problem identified back in
Chapter 11 (attempt #10): `ebwm.pt`'s native goal-centroid scoring, still used live by the
two-brain chop planner as soon as the search finds something, inverts on Obtain's spawn
distribution. Every attempt from #11 to #16 worked around that fact rather than correcting it. This
chapter covers attempt #17 in `docs/10_coldstart_engineering.md`/`CLAUDE.md#Phase 5+`: two direct,
cheap attacks on that central mechanism, ahead of any more expensive commitment.

## Prong A — an OOD detector as a fallback, rather than a score repair

**Idea, orthogonal to "fix the score"**: if `ebwm.pt`'s frozen latent can be shown to be measurably
out of distribution on an Obtain frame, a later dispatch could fall back on the already-working
`FrontierTracker` coverage search (attempt #12) instead of trusting a compass confirmed inverted
there (attempt #10). No gradient, no loss function for a downstream head — a deliberate contrast
with every trained-head attempt (#7, #11, #14 Phase 2) that already fell into the brightness trap.

`scripts/diagnose_ood_gate.py` (`configs/diagnose_ood_gate.yaml`) fits a single Gaussian (mean,
covariance) over `ebwm.pt`'s pooled latents from 4,000 random Treechop frames — Lee, Lee, Lee &
Shin, "A Simple Unified Framework for Detecting Out-of-Distribution Samples and Adversarial
Attacks", arXiv:1807.03888 (NeurIPS 2018), closed-form statistics, no training loop — evaluated at
the exact `vpool` feature `CraftPlannerV4`/`SwitchingCraftPlanner` already compute every replan
(`mine_jepa/ebwm/planner.py`), then scores test frames by their Mahalanobis distance to that fit.
Three gates on the same 251-frame set as every prior attempt in the campaign (160 Treechop, 11 real
Obtain spawn thumbnails, 80 Obtain coverage frames).

| Gate | Bar | Result |
|---|---|---|
| A — separation (mean Mahalanobis distance, Obtain vs. Treechop) | ≥ 1.3x | **FAILED — 1.294x** (missed by a hair; re-verified directly from the raw CSV: obtain mean 9.905 vs. treechop 7.657, n=91/160) |
| B — specificity (elevated specifically on attempt #10's confirmed-wrong frames, not uniformly across all of Obtain) | ≥ 1.2x | **FAILED — 1.105x** |
| C — negative control (correlation with raw frame brightness) | \|r\| < 0.3 | **FAILED — r = 0.56** |

Gate A missed by a hair, meaning the detector barely distinguishes "this is Obtain" from "this is
Treechop". Gate B, failed more clearly, means that even the weak separation it does capture is not
concentrated on the frames where the score is confirmed wrong — it would flag "this is Obtain", a
markedly less useful signal for a fallback dispatch than "this particular score is unreliable
here". Gate C is the sharpest of the three:

> **LESSON: 6th independent confirmation of the brightness/scene-composition confound, and the most
> structurally decisive to date.** r=0.56 lands squarely inside the range of every trained-head
> attempt (0.117-0.947, attempts #7/#11/#14/#15) — but this detector **has no gradient, no loss
> function, and no way to "learn" a shortcut**: it is a closed-form Gaussian fit and a distance
> computation. That it still lands in the same confound range shows the shortcut is not something
> downstream heads learn to exploit — it is baked into the raw geometry of `ebwm.pt`'s frozen latent
> space itself, inherited by any statistic built on top without retraining the encoder's own
> objective.

**VERDICT: NO-GO on all three gates.** Not wired into `mine_jepa/ebwm/planner.py` or
`scripts/play_craft.py` — no live batch spent on a mechanism that failed its own offline gates.
`ebwm.pt` loaded frozen and verified `requires_grad_(False)` throughout; no checkpoint touched.
Artefacts kept as diagnostics only: `assets/diagnostics/ood_gate.csv`,
`assets/diagnostics/ood_mahalanobis_stats.npz`.

## Prong B — is attempt #14 Phase 2's anomaly a data-diversity gap?

Attempt #7's original hypothesis — never directly tested until now — was that `ebwm.pt`'s
brightness confound might come from a lack of lighting diversity in its training data
(dark/underwater/cave frames under-represented). Before collecting anything new, a read-only check:
what share of the data actually used already fits that description?

Using `mine_jepa/ebwm/hazard.py`'s calibrated underwater/cave detector (the lighting-invariant
channel-ratio heuristic validated in attempt #13 — preferred over raw brightness, a poor
discriminator here since Treechop is actually darker on average due to canopy shade):

- `ebwm.pt`'s **original** Treechop training data: only **1.0%** of frames flagged
  underwater/cave — the gap attempt #7 flagged was real, for the original model.
- Obtain-domain data actually used for attempt #14 Phase 2's fine-tune (`data/minerl_craft` +
  `data/minerl_coverage`, ~4x oversampled): **16-22%** of such frames, even after oversampling.

Attempt #14 Phase 2's specific anomalous frame (the dark cave/underwater frame whose score *got
worse*, 0.0130 → 0.025-0.031, after the fine-tune) was tentatively identified by visual and numeric
match — with one unreconciled discrepancy honestly flagged rather than papered over — and sits well
inside the range of already-present training examples, not as an extreme case never encountered.

> **LESSON: the gap that motivated Prong B is already closed for the data actually used in attempt
> #14 Phase 2.** Collecting new data is not well-supported as the next step for this precise
> anomaly. If the encoder-retraining direction is resumed, a reweighting or training-objective fix
> — nothing in the current VICReg + prediction loss explicitly rewards a **correct relative distance
> ordering across biomes**, only local prediction accuracy — is the better-motivated next question,
> not more data.

## Standing diagnosis, on its firmest footing yet

Six independent, mechanically diverse approaches now converge on the same brightness/scene-
composition confound: two heads trained on frozen latents (#7, #11), a 400M-image off-the-shelf
model never touched by this project (#14 Phase 1, CLIP), a direct fine-tune of the encoder itself
(#14 Phase 2), a hand-designed lighting-invariant feature (#15), and now an untrained closed-form
statistic (#17 Prong A). Combined with Prong B closing the "just needs more data" theory for the
precise case that raised it, the defect looks **structural** to `ebwm.pt`'s frozen representation
and/or its training objective — not fixable by anything built on top of the existing checkpoint
without retraining its core objective, a materially more expensive undertaking than anything tried
in attempts #7-#17.

**Not yet decided whether that is worth pursuing, or whether to consolidate around the mechanisms
that already work (`commit_length`, frontier coverage, hazard avoidance) and accept the central
score as a permanent known limitation — a question put to the user, not settled by this chapter.**

## References

- Lee, Lee, Lee & Shin, "A Simple Unified Framework for Detecting Out-of-Distribution Samples and
  Adversarial Attacks", [arXiv:1807.03888](https://arxiv.org/abs/1807.03888) (NeurIPS 2018) —
  foundation of Prong A (Gaussian fit + Mahalanobis distance on `ebwm.pt`'s pooled latent),
  verified in `docs/references/index.md`.

Prong B rests on no new reference: it reuses as-is the underwater/cave detector from
`mine_jepa/ebwm/hazard.py`, already motivated and calibrated in attempt #13 (Chapter 13).

:::

---
title: "The closest thing to H-JEPA yet predicts the future, not the image — and still loses to a plain average"
slug: "16-predicting-the-future-not-the-image"
lang: "en"
order: 16
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft", "07-broken-curiosity", "08-the-wall-is-behavioral", "09-next-directions", "10-the-cleanest-negative", "11-compass-points-backwards", "12-memory-of-visited-places", "13-blind-rescue", "14-a-web-giant-put-to-the-test", "15-fifth-confirmation-false-alarm"]
source_docs: ["CLAUDE.md#Phase 5+"]
---

::: beginner

## Where we left off

Chapter 15 closed, this time for good, an entire family of attempts: no calculation based on a
single image — learned, off-the-shelf, or hand-built to resist lighting changes — can cleanly
separate "this is a forest" from "this is dark", because in this game forests really are darker
than meadows. Five different attempts, five confirmations of the same wall. What remained on the
table, for picking the cold-start investigation back up: the memory of visited places (Chapter 12),
which has real but modest and fading results, and the heaviest, most ambitious idea on the menu —
a separate second brain, designed for long-range search. This chapter tells the story of the first
real attempt in that direction: not yet the full second brain, but a first, cheaper try, designed
specifically to dodge Chapter 15's trap from the outset.

## A different idea: predict the discovery, not the image

Until now, every attempt of this kind asked a small model to look at an image and judge: "does
this look like a promising scene?". That is exactly the type of question that always ended up
caught by brightness. This time the idea changes in nature: instead of judging an image, a small
model learns to predict, for each possible direction the agent could go, **how many new cells of
the explored grid would probably be discovered** — a bet on how useful it is to explore that way,
not an aesthetic judgement about what is on screen.

To place that bet, the small model **never** looks at the colour or texture of an image. It relies
on only two kinds of clue: a classical calculation of motion between two consecutive frames (is the
camera moving a lot or a little in a given direction?), and the history of already-visited zones,
inherited from the memory built in Chapter 12. This is, to date, the attempt closest to the real
idea behind **JEPA** — the project's very name: instead of predicting a future image pixel by
pixel, you predict a small useful quantity about the future (here, "how much new ground am I going
to discover"), from compact clues rather than raw pixel colour. It is exactly the kind of
prediction this project has always aimed to make, applied here to a new question.

## A real bug found along the way, not just a shortage of data

Before anything could even be trained, real examples had to be collected of "in this direction,
here is how much new ground was actually discovered". A first collection batch revealed a real
bug, invisible until then: when several directions are tied (which happens almost all the time
early in an exploration, when no neighbouring cell has been visited yet), the mechanism
systematically and unintentionally chose the same default direction — 54 times out of 57 triggers
in that first batch. So it was not a genuine exploratory choice each time, just a hidden reflex
always landing on the same spot. Fixed by adding a coin-toss option to break ties (the old
behaviour stays available and unchanged if you do not enable it), then re-collected: this time all
12 possible directions are properly represented in the data.

## Two good signs, before training anything at all

Two safety checks were run on this freshly re-collected data, before any training attempt:

1. **Is there a real difference between directions?** Clearly improved after the bug fix, but based
   on few examples per direction (between 1 and 7) — encouraging, not yet a solid confirmation.
2. **Does scene brightness still dominate the target we are trying to predict?** This test was run
   twice, on two independent collection batches, and both times the answer is clear: **no**,
   brightness has almost no link with the amount of newly discovered ground. This is the most
   solidly reproducible result in this entire long investigation into the absence of a
   brightness trap — at last, a direction that does not fall into the same hole as the previous
   five.

## The real test: can this small model predict one specific trial?

With those two good signs, a small model was actually trained — a tiny neural network, barely
1,900 internal settings. But this project has a strict rule, applied at every step: never judge a
model on its own training data. The honest way to check is to split the data into several piles,
train on some and test on the rest, several times over with different piles each time, so as not
to be fooled by a lucky or unlucky split — this is called cross-validation.

Measured with that rigorous method against the simplest possible benchmark — always guessing the
average of every value already seen, without even looking at the direction in question — the
learned model **does worse**, not better. A systematic trial of eight different variants (smaller
networks, more cautious settings against over-fitting) never once managed to beat that simple
average. And to be really sure this was not just a tuning problem with a neural network too
complicated for the task, an even simpler version was tested — a classical linear model, no neural
network at all, with an adjustable brake against over-fitting. Identical result: the harder you
apply that brake, the closer the model gets to guessing a nearly constant value — and it never
surpasses the simple average, even in that most cautious case.

## Why this is a failure of a different kind from the previous ones

It matters to distinguish this result clearly from Chapter 15's five failures. There, the problem
was that a model **was learning something misleading** — a shortcut that gave the illusion of
working while actually measuring something else (brightness). Here it is different: both safety
checks show a real, honest aggregate signal, not fooled by brightness. The problem lies elsewhere:
**guessing precisely the outcome of one particular trial, from only four coarse clues about the
scene, is a much harder task than spotting a general trend across all the trials** — and with only
about a hundred examples in total, that is simply not enough data for a model, however simple, to
learn to do it reliably. This is not proof that the original idea is bad. It is an honest finding
that the task probably needs a great deal more data (likely several hundred examples, rather than
better tuning) before we can say whether it is learnable at all with these clues.

Following this project's honesty rule, that small model was **not** wired into the real game: no
run was spent testing a model whose cross-validation check clearly says it does not work yet.

## Where the project stands, after 16 real attempts

At this stage of the cold-start investigation, an honest overall stocktake is useful, without
adding gloss in either direction:

- **The "fix the visual judgement" direction is now closed**, with five independent confirmations
  of the same brightness trap — a small learned module, that same module retrained on other data,
  an artificial lighting variation during training, a giant off-the-shelf model, and a hand-built
  colour calculation. None of those five ways of going about it worked, for the same underlying
  reason.
- **The "search and coverage" direction holds the only real positive results of the whole
  campaign** — executing a good plan for longer (Chapter 8), the memory of visited places
  (Chapter 12) — but with gains that are running out of steam: the anti-drowning rescue holds well
  at scale (Chapter 15) without lifting the chop rate, and this chapter shows that pushing further
  in that direction (predicting exploration rather than counting it afterwards) now runs into a
  data-quantity problem, not an idea problem.
- **One mechanism, named repeatedly since Chapter 11 but never directly repaired, remains the most
  important open thread**: the chop planner's very compass — the one comparing an imagined story
  against a memory of success — was confirmed **inverted** as early as Chapter 11, and every
  attempt since (search, rescue, coverage prediction) has worked around that problem rather than
  tackling it head-on. With the visual direction now closed and the coverage direction showing
  diminishing returns, this never-repaired mechanism becomes the most significant lever left on the
  table.

As with every chapter on this site since day one: this report dresses nothing up. A real signal was
found (brightness does not dominate this new model's target), a real bug was found and fixed along
the way, and the final result nonetheless remains an honest failure at this stage — not a disguised
victory, and not an abandonment either.

:::

::: expert

## Context

Chapter 15 closed candidate direction 1 from Chapter 11's menu (photometric score correction) with
a fifth independent confirmation of the brightness shortcut, under a new and stronger constraint
than before: **no single-frame photometric feature can, structurally, separate brightness from
scene composition in this domain.** This chapter covers attempt #16 in `CLAUDE.md#Phase 5+` (no
corresponding `docs/10` entry to date): the campaign's first mechanism built explicitly under the
"no single-frame photometric scoring" constraint, a first non-photometric, non-visual step towards
candidate direction 3 (H-JEPA) without paying its full cost.

## Design: the Coverage-Value Predictor (CVP)

An Explorer proposal, externally reviewed and refined: a small MLP predicting `Δunique_cells` (the
expected coverage payoff) per candidate heading, from **non-photometric features only** — a
classical per-quadrant frame-difference optical-flow proxy, plus the local visitation histogram
already maintained by `FrontierTracker` (Chapter 12). This is a genuinely JEPA-shaped predictor
(input + action → future state), but with the **target swapped**: from pixel reconstruction to a
compact geometric quantity. It feeds the already-validated frontier scan macro rather than
replacing its handoff to the chop planner.

## Instrumentation, collection, and a real bug found along the way

`scan.frontier.log_transitions` (config-gated, default off) added to `scripts/play_craft.py`; two
batches collected.

**First batch (N=12, 57 rows)** revealed a real, previously unnoticed bug:
`FrontierTracker.frontier_heading_deg()` breaks ties toward the smallest heading index, and since
cells in a still-sparse grid are almost always tied (0 visits each), 54/57 triggers "chose" heading
0.0° by construction, not by genuine preference. Gate 1 (dynamic range across headings) was
uncertifiable on that data.

**Fix**: config-gated `tie_break="random"` option (seeded), default `"first"` = old behaviour
verified unchanged. **Re-collection (N=14, 44 rows)**: all 12 possible headings now represented
(1-7 rows each).

## Offline gates on the re-collected data

- **Gate 2 (brightness does not dominate the target): PASSED on BOTH batches independently**
  (r ≈ 0.10, opposite signs) — the most reproducible non-confounded result in the campaign's
  entire history.
- **Gate 1 (dynamic range)**: substantially improved after the bug fix, but resting on small
  per-heading samples (1-7 rows) — assessed as "encouraging, not a rock-solid confirmation".

## The actual trained model — NO-GO, thoroughly checked, not just badly tuned

Both CSVs combined (~101 rows), a small MLP (~1.9K parameters) trained with mandatory 5-fold
cross-validation against a trivial "always predict the mean" baseline.

**Default configuration**: model MAE 1.590 against the baseline's 1.169 (worse).

**8-way hyperparameter sweep** (smaller nets, heavier regularisation): never beats the baseline,
best ratio 1.06 (still worse).

**From-scratch linear Ridge regression check**, to rule out an MLP-specific over-fitting artefact:
as regularisation strength increases, the model's error only approaches the baseline as it is
forced towards a near-constant prediction — it never surpasses it.

> **Diagnosis: predicting one specific noisy trial's outcome from 4 coarse scene-level features is
> a much harder task than the aggregate statistics checked by Gates 1-2, and is not learnable at
> N≈100 with this feature set — this is not evidence that the aggregate signal is fake, only that
> per-row prediction needs substantially more data (likely several hundred rows, not better
> tuning) to be learnable, if it is learnable at all with these features.**

In line with the dispatch's honesty discipline, the model was **not** wired into `play_craft.py`,
no `scan.macro: "learned_frontier"` was added, and no live episode was spent testing a model whose
cross-validation gate says it does not work. No checkpoint written
(`checkpoints/coverage_predictor.pt` does not exist). `ebwm.pt` and `craft_wm_v4.pt` untouched.

## Why this negative differs in nature from Chapters 11/12/14/15

The previous failures in the "brightness shortcut" family are cases where a model **learns
something real but misleading** — a shortcut producing a good gate score while actually measuring a
confounding variable (brightness). Here, both offline gates (Gate 2 twice, Gate 1 after the bug
fix) indicate a real, unconfounded aggregate signal — the problem is not the signal's validity, it
is the **intrinsic difficulty of the per-trial prediction task** combined with an **insufficient
sample size** (~100 rows). This is a failure of statistical power and task granularity, not a
failure of design principle like the previous five.

## Where this leaves the campaign — status after 16 numbered attempts

- **Direction #1 (encoder/scoring correction) closed, confirmed 5 times**: attempts #7, #11, #14
  (phase 1 CLIP + phase 2 direct fine-tune), and #15 (ratio chrominance) each independently hit a
  brightness/domain-composition confound. No single-frame photometric feature — learned,
  off-the-shelf, or hand-designed for invariance — repairs it.
- **Direction #2 (coverage/execution) holds the campaign's only real positive results**:
  `commit_length=4` alone (9.7% pooled), attempt #12's frontier search (1/20, later confirmed at
  N=20 with attempt #13's hazard fix layered on: drowning 60%→15%, fair-shot episodes 40%→60%, but
  chop rate stayed at 0/20 — diminishing returns from coverage alone, exactly the condition that
  justified trying direction #3). Attempt #16 (CVP) extends this line under the "no photometric
  scoring" constraint and finds a real aggregate signal (Gate 2, twice) but no learnable per-trial
  model at this sample size.
- **Direction #3 (H-JEPA proper) not built** — attempt #16 was the cheap, non-photometric first
  probe the standing diagnosis called for; it did not produce a deployable mechanism, but it also
  did not fail for a photometric reason, so the door is not closed the way direction #1 is.
  Cheapest version if resumed: collect substantially more transition rows (several hundred) before
  retraining, per the CVP dispatch's own recommendation.
- **The mechanism named but never directly repaired**: attempt #10 (Chapter 11) confirmed that
  `ebwm.pt`'s native goal-centroid scoring — used live by the two-brain chop planner as soon as the
  search finds something — inverts on Obtain's spawn distribution. Every attempt from #11 to #16 has
  worked around that problem (search mechanisms, hazard avoidance, coverage prediction) rather than
  fixing it directly. With direction #1 closed and directions #2/#3 both showing diminishing returns
  without touching it, this is now the campaign's most decisive unexamined mechanism — not yet
  decided whether, or how, to attack it directly.

## References

This chapter rests on no new bibliographic reference verified in `docs/references/index.md`. The
CVP design is described in `CLAUDE.md` as an internally refined Explorer proposal, in the general
spirit of a JEPA predictor with a swapped target (predicting a geometric quantity rather than
pixels) — a principle already motivated for this project by the JEPA architecture itself
(Chapter 1, LeCun, original JEPA concept) and by the latent-space prediction choice already made
for `mine_jepa/ebwm/` (Assran et al., I-JEPA, arXiv:2301.08243; Maes et al., LeWorldModel,
arXiv:2603.19312), without any of those references specifically describing exploration-coverage
prediction — so this precise component has no external reference of its own to cite.

:::

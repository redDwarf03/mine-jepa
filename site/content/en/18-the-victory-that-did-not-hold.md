---
title: "The campaign's first victory did not survive a larger sample — and it was the team itself that caught it"
slug: "18-the-victory-that-did-not-hold"
lang: "en"
order: 18
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft", "07-broken-curiosity", "08-the-wall-is-behavioral", "09-next-directions", "10-the-cleanest-negative", "11-compass-points-backwards", "12-memory-of-visited-places", "13-blind-rescue", "14-a-web-giant-put-to-the-test", "15-fifth-confirmation-false-alarm", "16-predicting-the-future-not-the-image", "17-the-shortcut-is-in-the-eye"]
source_docs: ["docs/10_coldstart_engineering.md#Cold-start attempt #18", "CLAUDE.md#Phase 5+"]
---

::: beginner

## Where we left off

Chapter 17 ended on a heavy number: **six** completely different ways of measuring "is there a
tree close by?" — two small trained modules, a web giant never touched by this project, a direct
retraining, a hand-built colour calculation, and even a plain statistical formula with no learning
at all — had all fallen into the same trap: they got distracted by the brightness of the scene
instead of genuinely judging whether a tree was present. The decision about what came next
(retrain the model's core, or accept this limit and continue with what already works) remained
with the user, unsettled.

Before settling it, a re-reading of the latest scientific publications on nearby topics surfaced
two new ideas, cheap to test ahead of any heavy commitment. This chapter tells what happened when
they were — and its most important event is not a result, but a **correction the team inflicted on
itself, within the same working session**, before anyone had time to declare victory too soon.

## Idea 1: what if we looked at distance rather than colour?

Every previous attempt tried to guess "there is a tree close by" from the colour and texture of the
image — exactly the kind of clue brightness can pollute. A recent scientific publication proposed
something else: add to a JEPA model a notion of **depth** — how far away each part of the image is,
a bit like a radar measuring distances rather than an eye looking at colours — and that publication
showed it helped a model generalise better to unfamiliar scenes.

The test is built exactly on Chapter 14's template: take an off-the-shelf vision model, never
trained on Minecraft, able to estimate how far away each zone of an image is from a single photo.
No setting is adjusted for Minecraft — it is an outside tool, used as is, precisely to prevent any
project-specific learning from reinventing the same brightness shortcut.

On the very small image sample already used by every previous chapter (4 images with a nearby tree,
6 without), this test passed **both** conditions that six previous attempts had never passed
together: it did distinguish scenes with trees from scenes without, AND it was almost entirely
undistracted by brightness — by far the best result on that second point since the campaign began.
At the time, it looked like the very first "yes" of this long investigation.

## But the team did not stop there — and was right not to

One figure immediately raised suspicion: on the first condition (distinguishing tree from no-tree),
the result cleared the passing bar by only a hair — the kind of margin that can vanish once you
look at more examples. Rather than publishing that result as a victory, the same team, in the same
working session, immediately widened the image sample: instead of settling for the usual 10 images,
it examined and hand-classified **all** the remaining images available for this test — not a
cherry-picked selection, the entire population — reaching 27 images in total (honestly setting
aside 4 images judged too ambiguous to classify).

**On that larger sample, the result collapsed.** The ability to distinguish tree from no-tree fell
back below the passing bar. The direction stayed correct — images with trees continued to score
slightly higher on average — but the gap had become too small to be a real discovery: it was the
kind of gap a small sample sometimes produces by pure chance, not a reliable property of the
signal.

That is the heart of this chapter: **the very first apparent victory of this eighteen-attempt
campaign did not survive a broader examination — and it was the same team, the same day, that
detected and corrected it**, rather than letting the first flattering result become the official
story. It is exactly the same honesty that, since this site's very first chapter, has made it say
"0/20", "not significant" or "this does not work" whenever that was the truth — applied here, for
the first time, to a result of the project itself rather than to someone else's.

One important thing not to conflate, however: **two different claims**, and only one of them
survived. "This signal is not distracted by brightness" — true, confirmed, and it is even the best
result of the whole campaign on that precise point. "This signal really detects a nearby tree" —
false, or at any rate not yet proven, as soon as you look at enough examples. Not being fooled by
brightness is not enough to be a good tree detector.

## Idea 2: what if the real problem were not visual at all?

A second scientific publication, on a different topic, inspired a question with nothing to do with
colours or light: has the agent learned to **move** differently enough across the two training sets
for that to be a problem in its own right?

The test counts, without training anything or running a GPU, which actions appear in the expert
runs used for each of the two tasks. Striking result: in the expert runs for the "chop a tree"
task (Treechop), the most frequent action by far is **attack** (58.5% of the time) — logically, the
expert spends its time logging. In the expert runs for the crafting task (Obtain), actions are much
more evenly split between "do nothing", "move forward" and "attack", with far less attacking. A
statistical calculation measuring how different two action distributions are gives a gap **104
times larger** than what you would get by pure chance comparing one half of an expert run against
the other half of the same run.

This proves nothing causal for now — it is a new fact, honestly presented as a lead rather than a
certainty. But it is the very first time, in eighteen attempts, that a test has surfaced a real and
important gap between the two training sets that has **nothing to do with colour or light**. It
opens a door nobody had opened yet: perhaps the model simply never trained enough on moving the way
an exploring agent moves, because its expert runs mostly showed it how to chop wood.

## A small live test: nothing spectacularly broken, but a signal to watch

A small live experiment (6 runs) tried to navigate the agent using this distance estimate rather
than the usual compass, whenever the agent seemed lost. The mechanism triggered only 3 times across
the 6 runs — too few to really judge whether it behaves well — and showed no severe lock-in on a
single direction, unlike several past failed attempts. No wood chopped, unsurprisingly; that was
not the question being asked.

A worrying signal did appear, however, and was reported honestly rather than hidden: in 2 runs out
of 6, the agent died **while** the anti-drowning reflex (repaired and confirmed in Chapter 13) was
actively trying to get it out of the water. Yet that reflex had survived 6 runs out of 6 with no
deaths at its last check. Nothing yet proves this new distance-based navigation causes the problem
— it could be chance across so few runs — but the most plausible explanation is interesting: models
that estimate distance from a single image often get water wrong, a surface that reflects light
deceptively. This point deserves a dedicated check before trusting the anti-drowning solution
alongside this new navigation mechanism.

## What this chapter changes, and what it does not

- Chapter 17's diagnosis (the brightness defect is deeply embedded in the way the base model
  compresses an image, not in one particular learning method) **still stands** — the "depth" test
  did not repair the central problem, only showed that a signal can escape that precise trap without
  thereby becoming a good tree detector.
- **One genuine novelty appears**: a gap in behaviour, not in perception, between the two training
  sets — never measured before, and with nothing to do with colour or light.
- **This chapter's most important moment remains the correction itself**: a result that looked like
  the first real victory in eighteen attempts turned out to be a mirage caused by too small a
  sample — and the team discovered and corrected it the same day, without letting the flattering
  version take hold. It is concrete proof that the "verify before believing" rule, applied since
  this site's first chapter, also works when it is applied to one's own work.
- The underlying decision (retrain the base model, or consolidate around what already works)
  remains, as in Chapter 17, an open question for the user — not settled by this chapter.

:::

::: expert

## Context

Chapter 17 (attempt #17) closed two direct attacks on `ebwm.pt`'s goal-centroid scoring (an OOD
Mahalanobis-distance fallback, and a check on the "not enough dark data" hypothesis) at a standstill:
6 independent confirmations of the same brightness/scene-composition confound, retrain-vs-consolidate
decision left to the user. This chapter covers attempt #18 in
`docs/10_coldstart_engineering.md`/`CLAUDE.md#Phase 5+`: a dedicated bibliography search pass
(2026-07-27, covering 2026-07-13 to 2026-07-27) surfaced 5 new JEPA papers (added to
`docs/references/index.md`), two of which reopened cheap sub-questions ahead of any retraining
commitment. This attempt's notable event is not a result but a **correction issued within the same
session**.

## Diagnostic 1 — pseudo-depth generalisation: an apparent first GO that did not survive a larger sample

Motivated by Khan, "Depth-Regularized JEPA World Models Learn More Transferable Representations from
Real Outdoor Robot Data" ([arXiv:2607.16314](https://arxiv.org/abs/2607.16314), 2026): an 18M-param
JEPA world model + SIGReg on real outdoor robot video, with a depth-supervision auxiliary term,
gains -33% error on a visual-odometry probe and better surprise-score separation in-domain AND
out-of-domain (TartanGround benchmark) under real domain shift, at no extra inference cost — the
first published instance of attempt #15's own conclusion: the brightness confound needs "a different
modality", not another photometric feature.

`scripts/diagnose_depth_gate.py` runs MiDaS_small (`torch.hub`, `intel-isl/MiDaS`, off-the-shelf, no
Minecraft-specific training — the same "outside model" logic as attempt #14 Phase 1's CLIP test)
over the campaign's standard 251-frame set, scoring each frame by the mean of its closest 10% of
MiDaS-predicted pixels (nearest-object proxy).

**First pass, the campaign's usual small sample (tree_close n=4, no_tree n=6):**

| Gate | Bar | Result |
|---|---|---|
| A — separation | ≥ 1.3x | **PASS — 1.304x** |
| B — brightness independence | \|r\| < 0.3 | **PASS — r = 0.0451** (the campaign's best by far; previous range 0.117-0.947) |

Read at face value, this was the first mechanism in 7 independent tests (#7, #11, #14
Phase1/Phase2, #15, #17 Prong A, and this one) to pass both established gates — flagged at the time
as "a thin margin on a small sample", not declared a victory, because that margin looked fragile on
inspection (Gate A cleared the 1.3x bar by only 0.004).

**Same-session follow-up: the hand-labelled sample was extended from 10 to 27 frames** (21 new
candidates visually inspected — the *entire* remaining population eligible for this gate in
`data/minerl_coverage/episodes.npz` and `assets/spawn_thumbs/`, not a cherry-picked subset; 4
discarded as genuinely ambiguous, a 19% exclusion rate, reported rather than hidden).

| Gate | n=10 (original) | n=27 (extended) |
|---|---|---|
| A — separation | 1.304x (PASS) | **1.086x (FAIL)** |
| B — brightness independence | r=0.0451 (PASS) | r=0.0451 (PASS, unchanged) |

> **LESSON: the first pass's 1.304x was a small-sample artefact, not a real, robust separation.**
> Tree-close frames still score higher on average than no-tree frames (644.3 versus 593.5) — the
> *direction* stays correct — but the margin collapsed well below the 1.3x bar once the sample was
> nearly tripled. Gate B's brightness-independence result is real and unaffected: depth genuinely is
> not a brightness shortcut, the best such result of any mechanism this campaign has tested. But
> independence from a confound is not the same thing as being a working tree detector.

**CORRECTED VERDICT: MIXED, not GO.** Attempt #17's standing diagnosis — no mechanism has yet
cleanly separated tree-close from open scenes while staying brightness-independent at a trustworthy
sample size — **still stands**. What genuinely changed: depth's brightness independence is confirmed
and reproducible (a non-photometric signal that is not itself a brightness shortcut, even if it is
not yet, alone, a working detector). Corrected in the same session it was found, not left standing
as a false first GO — the campaign's honesty discipline applied to itself, not only to each new
mechanism tested.

## Diagnostic 2 — Treechop/Obtain action-coverage overlap: a genuinely new, non-photometric factor that still stands

Motivated by Zhang, Guan, Zhang, Zhang, Li, "On the Identifiability of Controlled World Models"
([arXiv:2607.22430](https://arxiv.org/abs/2607.22430), 2026): an action-conditioned JEPA only
recovers reliable state/dynamics when the training action distribution has adequate coverage.
`scripts/diagnose_action_coverage.py` measures this directly — no GPU, pure action-array statistics,
seeded, self-calibrated against a Treechop-vs-Treechop split-half null rather than an invented bar.

- **Out-of-vocabulary fraction**: only **2.33%** of pooled Obtain actions use an index outside
  `ebwm.pt`'s trained 17-action vocabulary — far lower than the naive starting estimate of
  "5/22≈22.7%" (craft-heavy expert demos rarely invoke crafting relative to movement; the
  random-policy coverage set alone is 22.6% OOV).
- **Jensen-Shannon divergence on shared indices**: Treechop vs. pooled Obtain = **0.1453**, against
  a Treechop-vs-Treechop split-half null of **0.0014** — a **104x** ratio, not explainable by
  sampling noise. Treechop demos are 58.5% attack / 14.7% forward / 12.0% noop ("walk to a tree,
  hold attack"); Obtain is comparatively noop/forward-heavy and attack-light (33%/31%/25%).
- **Bonus finding, more specific than the question asked**: Treechop's own training data only ever
  exercises 8 of `ebwm.pt`'s 17 trained action indices — strafe, jump, and both camera tilt
  directions are never sampled during training, an internal coverage gap inside Treechop itself,
  independent of the Obtain domain.

> **LESSON, held to the campaign's "hypothesis vs. confirmed" discipline**: this establishes a real,
> large, non-photometric distributional gap — the first diagnostic in 18 attempts to surface a
> candidate factor outside the brightness/scene-composition family — but does NOT by itself prove
> that this mechanism causes attempt #10's score reversal. The paper's claim concerns
> state-action-next-state identifiability; this diagnostic only measured the marginal action-usage
> histogram. A plausible contributing factor, not a confirmed cause.

It reframes "retrain the core objective" from a vague, expensive idea into two concrete, scoped
candidates: broaden Treechop's own action coverage, and/or reweight training toward the actions
Obtain actually exercises. Unaffected by Diagnostic 1's correction.

## Live sanity test — `scan.macro: "depth"` (N=6): no chopping, mechanism barely exercised, one regression signal flagged not buried

Dispatched against Diagnostic 1's ORIGINAL (since corrected) result, before the larger sample came
back. Correctly reframed once the correction landed: read as "does a depth-driven heading behave
sanely", not as validating a fix. `mine_jepa/ebwm/depth.py` (new module — MiDaS loading,
per-column depth scoring, heading-delta computation) feeds a new scan-macro variant
(`configs/play_craft_commit4_depth.yaml`, built on the already-validated commit_length=4 + hazard
avoidance baseline). By construction it never touches `CraftPlannerV4`/`SwitchingCraftPlanner`'s
latent-space scoring — MiDaS needs real pixels, and the planner's candidate rollouts are imagined
latents with no pixels to decode, so depth can only inform a navigation heading from the real
current frame, not a rollout score.

- **0/6 logs, 0/6 planks, mean reward 0.000** (below MineRL's ~0.4 random-policy baseline) —
  expected, not the question this batch was asked.
- **The scan macro triggered only 3 times across the 6 episodes** — `goal_score_std` rarely dropped
  low enough to invoke it. The sanity question is only weakly answered by this batch, independent of
  the small-N caveat that already applies everywhere in this campaign.
- Across the 3 triggers: no severe lock-in (unlike attempt #6's CEM or attempt #8's action-pool
  priming, both >80% single-action concentration); one converged in 2 ticks; one held a consistent
  rightmost-column heading across 4 of 6 ticks with one detour; **one reversed completely from the
  rightmost column (delta +26.2°) to the leftmost (delta -26.2°) in a single 16-tick step** — not the
  campaign's classic ping-pong-every-replan bug (attempt #13's first steered-escape round), but a
  real, unexplained reversal on too small a sample (2 data points) to characterise further.
- **Regression signal, flagged rather than buried**: 2/6 episodes ended with
  `died_during_escape=True` (death while the hazard-avoidance reflex was actively trying to escape
  water) — exactly the failure mode attempt #13's final round (widened `align_deg` + debounced dry
  anchor) believed FIXED at 6/6 episodes survived, 0 deaths, same N=6. This batch reuses that
  identical hazard configuration, only adding the new depth scan macro alongside it. Not established
  as causal at this N (could be batch-to-batch noise recurring by chance), but plausible: monocular
  depth models are known to behave unpredictably on reflective/transparent surfaces like water, so a
  depth-driven heading could plausibly steer toward or linger near water in a way the previous
  `"turn"`/`"frontier"` macros did not. **Before trusting attempt #13's hazard fix as robust across
  scan-macro choices, this deserves a dedicated check — not asserted as a confirmed regression, but
  not dismissed either.**

GIF: `assets/agent_play_craft_commit4_depth.gif`. Full log:
`logs/coldstart_attempt18_depth_sanity_n6.log`.

## Standing diagnosis after attempt #18

Attempt #17's "the encoder/scoring confound is structural and unfixable short of retraining"
conclusion **still stands on the separation question** — no mechanism has yet cleanly separated
tree-close from open scenes while staying brightness-independent at a trustworthy sample size. What
genuinely changed: depth's brightness independence (Gate B, r=0.045, unchanged across both samples)
is real and reproducible — a non-photometric signal that is not itself a brightness shortcut, even
though it is not yet, alone, a working tree detector — and Diagnostic 2's action-coverage gap is a
separate, still-standing, genuinely new non-photometric factor. Neither is a proven live fix.
Diagnostic 2 reframes "retrain the core objective" into two concrete, scoped candidates
(action-coverage reweighting; SIGReg in place of VICReg, see
[arXiv:2607.13612](https://arxiv.org/abs/2607.13612)) rather than a vague, expensive idea. The live
sanity test's regression signal is a separate open question about mechanism interaction (scan macro
choice vs. hazard avoidance), unrelated to the central score. **The decision on how to proceed
(retrain `ebwm.pt`'s core objective vs. consolidate around the coverage/execution mechanisms that
already work) still belongs to the user — this attempt records results, not a commitment to any
next step.**

## References

- Khan, "Depth-Regularized JEPA World Models Learn More Transferable Representations from Real
  Outdoor Robot Data", [arXiv:2607.16314](https://arxiv.org/abs/2607.16314) (2026) — foundation of
  Diagnostic 1 (MiDaS_small, depth separation, brightness independence).
- Zhang, Guan, Zhang, Zhang, Li, "On the Identifiability of Controlled World Models",
  [arXiv:2607.22430](https://arxiv.org/abs/2607.22430) (2026) — foundation of Diagnostic 2
  (Treechop/Obtain action-coverage overlap).
- Arnez, Gomez-Villa, "The SIGReg Objective as Variational Free Energy: A Theoretical
  Active-Inference Account of JEPA World Models",
  [arXiv:2607.13612](https://arxiv.org/abs/2607.13612) (2026) — mentioned in the standing diagnosis
  as a second concrete candidate should core-objective retraining ever be undertaken; not tested in
  this chapter.

All three references are verified in `docs/references/index.md`.

:::

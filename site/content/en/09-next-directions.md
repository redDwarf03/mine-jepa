---
title: "After avenues A and C: the learned policy becomes the priority"
slug: "09-next-directions"
lang: "en"
order: 9
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft", "07-broken-curiosity", "08-the-wall-is-behavioral"]
source_docs: ["CLAUDE.md#Phase 5+"]
---

::: beginner

## Note: this chapter has changed since its first version

When this chapter was first written, avenues A and C described below were still just ideas, not results. That is no longer the case: they have since been tested together (Chapter 8 tells their full story, complete with real numbers). This chapter has therefore been updated to clearly distinguish **what has been done** (avenues A and C, yielding a negative yet instructive result) from **what remains a plan, not yet tested** (avenue B, promoted to top priority, plus two complementary ideas added after that latest result). If you return to this chapter later and the "not yet tested" section below still lists ideas without numbers, it means they haven't been tried yet.

## Quick summary: avenues A and C, tested together (see Chapter 8 for full details)

The two least expensive ideas in this plan — seeding pre-built good gestures into the planner's candidate list (avenue A) and replacing the "spin in place" reflex with a sprint-ahead cruising maneuver (avenue C) — were tested together, alongside the fix already in place since Chapter 8. Result across 8 episodes: still zero logs chopped. But both mechanisms worked as intended: the pre-built gesture was chosen by the planner in several episodes, and the cruising maneuver triggered at least once as well. The true takeaway is not the zero itself, but an unexpected behavior: across several episodes, the agent began repeating the exact same gesture almost all the time (up to 100% of episode steps) — a lock-in that recalls an issue previously seen with a more refined planning method tested in Chapter 8, though not yet confirmed as the exact same underlying mechanism.

This result sharpens the diagnosis: when the planner has no reliable clue to compare its options (because no tree is in view), feeding it pure noise makes it fidget without purpose; feeding it a concentrated choice of pre-built gestures makes it, instead, freeze blindly on one of them — because nothing ever comes along to make it change its mind. In both cases, the core problem remains: the planner has never *learned*, from real human gameplay, what a player actually does when nothing interesting is in sight.

## What remains to be tested: avenue B, promoted to priority, and two complementary ideas

### Avenue B: learning good gestures rather than hand-writing them

With avenues A and C tested and informative but insufficient, the track previously sitting in third place becomes the top priority: training a small function that learns, from the expert human gameplay recordings used elsewhere in the project, which actions a player typically chooses in a given situation. This function does not replace the planner — it serves only to *propose* better candidate futures among which the imagined world model (Chapter 3) continues to choose and correct at every step. This follows the exact same principle as renowned gaming algorithms (the ideas behind systems that defeated human champions in chess and Go): a learned intuition proposes moves, an explicit search verifies them.

A trap identified in advance, before even launching this experiment: the expert gameplay recordings used for training almost always show a player already near a tree — containing almost zero examples of "searching methodically when nothing is in view". To prevent this function from merely learning "always attack the visible tree" without ever learning to search — the same underlying weakness as avenues A and C on the search side —, the plan calls for blending the random coverage episodes collected in Chapter 7 (which do show true "lost, searching" situations).

**This avenue comes with the exact same important reminder as in the previous version of this chapter**: Chapter 5 had already tested a "copy a human player" approach that failed (zero reward), but that version used the copy as the *final decision*, with zero opportunity to self-correct during drift. Here, the learned function merely suggests — the planner retains final veto power at every timestep.

### Two complementary ideas, also not yet tested

- **Fixing the trained distance metric with lighting variations.** Chapter 8 showed that the trained distance metric (one of the previous attempts) reacted heavily to scene brightness (day/night/cave) rather than true distance to a tree — because it had never seen true night or cave scenes during its training. The plan: add artificial brightness and contrast variations to training images (requiring zero new data collection), then re-run the exact same offline test from Chapter 8 to verify if the rule better separates "far away" from "just dark". This fix would be particularly useful if avenue B needs a reliable distance signal to rank its own proposals.
- **A spawn point viability diagnostic.** Several episodes in this investigation (Chapters 7 and 8) ended in locations with zero trees in reach — a rocky ravine, an underground cavern. No algorithm can succeed from such a spawn point, regardless of its quality. The plan: simply record, at the start of each episode, the type of location where the agent spawns, in order to distinguish in future result batches "the algorithm failed" from "the spawn point made success impossible from step one". This isn't an agent improvement, it is a measurement improvement — but repeated failures on treeless spawn points, already observed twice, show that this measurement has been missing from the start.

## Planned execution order

1. Train and test avenue B (priority 1).
2. Fix the distance metric using lighting variations — a candidate to provide avenue B with a reliable signal to choose between its own proposals.
3. Add the spawn viability diagnostic, so future numbers finally distinguish algorithmic failure from impossible spawn.
4. Evaluate avenue B and the fixed distance metric together, once both exist.

As with every previous attempt in this project, the result — whether positive, negative, or inconclusive — will be reported under the exact same standards of honesty as previous chapters: true numbers, never a number tuned to look better than it is.

:::

::: expert

## Context: From a 5-Attack Diagnosis to a New Priority

Chapter 8 concludes with five convergent independent attacks: four targeting signal/score quality (online RND, re-wired scan, real CEM, trained distance metric) and a fifth (attempt #8, summarized below) directly targeting candidate *generation* via Proposals A (pool priming) and C (bushwhack maneuver), combined with `commit_length=4`. This chapter explicitly distinguishes what has been **executed** (A and C, NO-GO but yielding a clear qualitative finding) from what remains **an unexecuted plan** (Proposal B, promoted to priority 1, plus two refinements added post-attempt #8).

## Summary: Proposals A + C (attempt #8) — See Chapter 8 for Full Details

`planner.action_pool_priming` (~30 forward+attack macros, ~30 camera rotation macros, ~30 backward macros seeded into candidate pool of 512) + `scan.macro: bushwhack` (bounded forward sprint-jump replacing turn-in-place, triggered by flat `goal_score_std` on chop planner), combined with `commit_length=4`. **N=8, seed 0: 0/8 logs, 0/8 planks, reward 0** — non-significant against pooled base rate of `commit_length=4` alone (3/31 ≈ 9.7%, ≈0.8 expected successes on N=8).

Both mechanisms **verifiably triggered**: `a7` (primed forward+attack macro) 21-49% share in 3/8 episodes; `a13` (bushwhack macro) 28% with 8 scan triggers in 1/8 episode. **Finding mattering more than 0/8**: 3/8 episodes show `a14` (pre-existing forward+attack gesture) at 83-100% share — near-total behavioral lock-in, **recalling** (without quantitative confirmation yet established against distributions specific to `commit_length=4` alone — noted, not affirmed) real CEM action concentration regression of attempt #6 (66.3% mean vs 35.8%), obtained via different mechanism (fixed menu/coverage macro vs iterative refinement) but converging on same signature: a flat score lacking real gradient gets *locked into* by any mechanism concentrating candidate pool, rather than remaining diverse.

## Proposal B (Priority 1, Promoted) — Latent Policy Prior

Train an actor head via behavioral cloning on frozen `ebwm.pt`, using Treechop demos, to *propose* MPC candidates instead of uniform/sticky noise or a fixed menu (A) — MPC continues evaluating and re-planning at each step, so not a repeat of Chapter 5's pure BC failure (Phase 4, approaches 3-4), where BC was the uncorrected final policy.

**Refinement Added Post-Attempt #8**: Treechop demos guarantee tree proximity — containing almost zero authentic search trajectories. An actor trained exclusively on them risks learning "always attack visible tree" without ever learning to search, reproducing same structural weakness as A and C on search side. Planned mitigation: blend random coverage episodes from attempt #3 (`docs/10`) with Treechop demos during actor training, so imitated distribution contains authentic search behavior.

## Refinement 1 — Fixing Trained Distance Metric (attempt #7) via Photometric Augmentation

Attempt #7's offline gate cleanly separated close/far (7.9x ratio) but live in-game signal tracked scene lighting (day/night/cave, Pearson correlation -0.565 with `goal_score_std`) rather than true goal distance, because neither training source (Treechop demos, coverage episodes) contained true night or subterranean scenes. Concrete plan: add aggressive `ColorJitter` (brightness/contrast/gamma) to training loop of `train_value_projector.py`, then re-run exact same censored/hinge offline gate — zero new data collection required. A learned policy (B) still needs a non-flat score to rank its proposals; this fix is direct candidate for that role.

## Refinement 2 — Spawn Viability Diagnostic

Attempt #8 Episode 7 ended prematurely (1856/3000 steps) with zero recorded death and zero trees ever found — a treeless spawn point is structurally impossible to solve regardless of algorithm quality. Attempts #5 and #8 both show unviable spawns diluting every success rate measured so far. Plan: log spawn type (subterranean/oceanic vs near-forest) at start of each episode in `play_craft.py`/`play_minerl_multi.py`, so denominator of future batches separates "algorithm failure" from "impossible spawn by design". Measurement fix, not capability fix.

## Planned Execution Order

1. Proposal B (Priority 1).
2. Photometric fix for distance metric (attempt #7) — non-flat score candidate for B.
3. Spawn viability diagnostic — measurement fix, independent of top two.
4. Evaluate B and fixed metric together once both available.

None of these three tracks enjoys privileged status before execution and actual measurement — same honesty discipline as every prior attempt (#1-8).

## References (Verified, from docs/references/index.md)

- Terver, Yang, Ponce, Bardes, LeCun, *What Drives Success in Physical Planning with Joint-Embedding Predictive World Models?*, arXiv:2512.24497 (2025) — recommendation of real CEM tested and invalidated in this precise regime (attempt #6).
- Destrade, Bounou, Le Lidec, Ponce, LeCun, *Value-guided action planning with JEPA world models*, arXiv:2601.00844 (2026) — trained distance metric (attempt #7).
- Burda, Edwards, Storkey, Klimov, RND, arXiv:1810.12894 (2018) — online mechanism tested in attempt #4B.

:::

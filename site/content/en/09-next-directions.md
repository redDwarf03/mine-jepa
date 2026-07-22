---
title: "After tracks A and C: the learned policy was promoted, then tested (following Chapter 10)"
slug: "09-next-directions"
lang: "en"
order: 9
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft", "07-broken-curiosity", "08-the-wall-is-behavioral"]
source_docs: ["CLAUDE.md#Phase 5+"]
---

::: beginner

## Warning: this chapter has changed twice since its first version

When this chapter was first written, tracks A and C described below were still just ideas, not results. This has long ceased to be the case: they were tested together (Chapter 8 tells the full story, with the real numbers). At that time, this chapter had been updated a first time to promote track B (learning good gestures instead of hand-writing them) to top priority, alongside two untested complementary ideas.

**Second update, this one**: track B has also been built and tested for real — and the two complementary ideas have also been fully executed. **Chapter 10 tells this story in detail**; this chapter now summarizes the real state of each track, rather than continuing to present them as pending plans.

## Quick Recap: Tracks A and C, tested together (see Chapter 8 for details)

The two least expensive ideas from this plan — putting ready-made good gestures into the planner's trial list (track A) and replacing the "spin in place" reflex with a cruising maneuver that sprints forward (track C) — were tested together, on top of the fix already in place since Chapter 8. Result over 8 episodes: still zero logs chopped. But the two mechanisms did work: the ready-made good gesture was indeed chosen by the planner in several episodes, and the cruising maneuver also triggered at least once. The real lesson is therefore not the zero itself, but an unexpected behavior: in several episodes, the agent started repeating the exact same gesture almost all the time (up to 100% of the time) — a lockdown that recalls a problem already seen with a more refined planning method tested in Chapter 8, without it being confirmed yet as exactly the same mechanism.

This result refines the diagnosis: when the planner has no reliable clue to compare its options (because no tree is in sight), giving it pure noise makes it fidget aimlessly; giving it a concentrated choice of ready-made good gestures makes it, conversely, freeze blindly on one of them — because nothing ever comes along to make it change its mind. In both cases, the problem remains the same: the planner never *learned*, from real games, what a player actually does when they see nothing interesting.

## Where each track stands now (full details are in Chapter 10)

### Track B: learning good gestures instead of hand-writing them — **tested: FAILURE, but a failure that eliminates two explanations**

The idea, promoted to top priority after tracks A and C: train a small function that learns, from the expert games already used elsewhere in the project (plus the random coverage episodes from Chapter 7, to also show it real "lost, currently searching" situations), which actions a player typically chooses in a given situation. This function does not replace the planner — it only proposes better candidates among which the imagined world (Chapter 3) continues to choose and correct at each turn, just like highly recognized gaming methods (the same ideas that beat human champions at chess and the game of Go): a learned intuition proposes moves, an explicit search verifies them.

This track has now been built and tested for real. Result over 8 episodes: **still zero logs chopped.** But two important things could be verified and eliminated thanks to this test: the agent did **not** repeat a single gesture in a loop (unlike in Chapter 8), and the 8 starting points were **not** treeless areas — a new measurement tool (see below) confirmed it. It is the cleanest negative result of the whole investigation: a truly varied and well-trained action proposal, tested on confirmed playable starting points, and still zero. **Chapter 10 tells this story in detail**, with a new suspect (not yet confirmed) for the rest of the investigation.

**This same reminder remains valid**: Chapter 5 had already tested a "copy a human player" approach which had failed (zero reward), but that version used copying as the *final* decision, without any way to correct itself in case of drift. Here, the learned function only suggests — the planner keeps the final say at each turn; so it was not a simple "step backward" to the Chapter 5 failure, and Chapter 10 explains why the result nevertheless remained negative.

### Two complementary ideas — **both fully executed**

- **Fix the trained distance rule with lighting variety — tested: FAILURE.** Chapter 8 had shown that the trained distance rule reacted to scene brightness (day/night/cave) rather than the true distance to the tree. The planned fix (adding artificial brightness and contrast variation during training) was indeed tried — but the problem it aimed to correct **worsened** instead of improving on a cleaner measurement. Chapter 10 gives the details and the likely explanation.
- **A diagnostic on the starting point — built, and already useful.** The tool that records, at the beginning of each episode, whether a playable starting point is actually present was successfully built. It was directly used in the track B test (above) to confirm that the 8 failures of this batch were not due to unwinnable starting points — the first time this project can state this with a measurement, rather than an impression.

## And now

Chapter 10 tells the full story of the tested track B, what it eliminates, and the new hypothesis — not yet confirmed — that emerges from it to continue the investigation. As with every previous attempt in this project, the result has been reported with the same standards of honesty: the real numbers, never a number massaged to look better than it is.

:::

::: expert

## Context: From a diagnostic to five attacks, to a new priority

Chapter 8 now ends on five convergent independent attacks: four targeting signal/score quality (online RND, re-wired scan, true CEM, trained distance metric) and a fifth (attempt #8, recapped below) directly attacking candidate *generation* via Proposals A (pool priming) and C (bushwhack maneuver), combined with `commit_length=4`. This chapter initially distinguished what had been **executed** (A and C, NO-GO but a clear qualitative finding) from what remained **an unexecuted plan** (Proposal B, promoted to priority 1, plus two refinements added after attempt #8). **Update**: all three — Proposal B, photometric repair, spawn diagnostic — have since been executed (attempt #9, `CLAUDE.md#Phase 5+`). This chapter summarizes the real state of each; **Chapter 10 gives full details**, including the new diagnostic that emerges.

## Recap: Proposals A + C (attempt #8) — see Chapter 8 for full details

`planner.action_pool_priming` (~30 forward+attack macros, ~30 camera rotation, ~30 walk backward injected into the 512 pool) + `scan.macro: bushwhack` (bounded forward sprint-jump replacing turn-in-place, triggered by flat `goal_score_std` on the chop planner), combined with `commit_length=4`. **N=8, seed 0: 0/8 logs, 0/8 planks, reward 0** — not significant against the pooled `commit_length=4` alone base rate (3/31 ≈ 9.7%, ≈0.8 expected successes on N=8).

Both mechanisms **verifiably triggered**: `a7` (primed forward+attack macro) 21-49% share in 3/8 episodes; `a13` (bushwhack macro) 28% with 8 scan triggers in 1/8 episode. **Finding that exceeds the 0/8**: 3/8 episodes show `a14` (pre-existing forward+attack gesture) at 83-100% share — near total behavioral lockdown, which **resembles** (without quantitative confirmation yet established against `commit_length=4` alone's own distributions — flagged, not affirmed) the concentration regression of the true CEM from attempt #6 (66.3% mean vs 35.8%), obtained by a different mechanism (fixed menu/coverage macro vs iterative refinement) but converging on the same signature: a flat score stripped of real gradient gets *locked down* by any mechanism that concentrates the candidate pool, instead of remaining varied.

## Proposal B — latent policy prior — **tested (attempt #9): NO-GO, but the cleanest negative of the campaign**

The plan was to train an actor head via behavioral cloning on frozen `ebwm.pt`, using Treechop demos merged with the coverage episodes from attempt #3 (to prevent the actor from only learning "always attack the visible tree", the same structural weakness as A and C on the search side), to *propose* MPC candidates instead of uniform/sticky noise or a fixed menu (A). This plan was executed exactly: `mine_jepa/ebwm/actor.py::BCActor`, mandatory anti-collapse gate (a Treechop-only ablation was correctly rejected: `top_action_frac` 0.964 vs 0.863 for the retained version, trained with coverage), bit-for-bit wiring verified.

**N=8, seed 0, `configs/play_craft_commit4_actor.yaml`: 0/8 logs, reward 0** (Fisher p≈0.21 against the pooled 3/31 base rate). But this batch **eliminates two concrete explanations**: no behavioral lockdown (action concentration 16-54%, far from the 83-100% of attempt #8), and no unlivable spawns (`spawn_diag` confirms `max_chop_std` 0.017-0.047 over the 8 episodes, above the calibrated 0.005 threshold). **Full details, including the new diagnostic that emerges from it (evaluating the imagined world might be the real bottleneck, not candidate generation), are in Chapter 10.**

## Refinement 1 — fix the trained distance metric (attempt #7) with photometric augmentation — **tested: NO-GO**

Attempt #7's offline gate separated close/far well (ratio 7.9×) but the live in-game signal tracked scene brightness (day/night/cave, Pearson correlation -0.565 with `goal_score_std`) rather than real distance to the goal. The planned fix (aggressive `ColorJitter` in `train_value_projector.py`, then the same censored/hinge offline gate) was implemented and executed: the offline gate still holds (separation 8.7× vs 7.9×), but the actual confusion with brightness **worsens** on a cleaner isolated measurement (`r=0.117 → r=0.498`). **NO-GO** — the confusion is likely anchored in the frozen latent space of `ebwm.pt` itself, not introduced by the projector; the fixed checkpoint was therefore not deployed in the evaluation of Proposal B above, which proceeds using only the goal-centroid scoring. Full details in Chapter 10.

## Refinement 2 — spawn viability diagnostic — **built and already used**

Episode 7 of attempt #8 ended prematurely (1856/3000 steps) without ever finding a tree — a spawn with no trees in range structurally cannot be solved. The planned diagnostic (`spawn_diag` in `scripts/play_craft.py`, thumbnail + `max_chop_std` against a calibrated 0.005 threshold) was built and **already exploited in the evaluation of Proposal B above**, where it confirmed the viability of all 8 spawns in the batch — the first time this project has a measurement, rather than an impression, to distinguish algorithm failure from impossible spawn.

## And now

The three tracks in this chapter have all been executed and measured — same honesty discipline as every previous attempt (#1-8). Chapter 10 gives the complete narrative and the new, yet unconfirmed hypothesis that emerges from it for the rest of the investigation.

:::

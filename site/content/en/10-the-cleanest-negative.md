---
title: "The learned track was tested: it too is not enough — but it eliminates two explanations"
slug: "10-the-cleanest-negative"
lang: "en"
order: 10
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft", "07-broken-curiosity", "08-the-wall-is-behavioral", "09-next-directions"]
source_docs: ["CLAUDE.md#Phase 5+"]
---

::: beginner

## Where we left off

Chapter 9 ended with a promotion: after two cheap ideas (ready-made gestures in the menu, a cruising maneuver) failed to improve the score, the remaining track — training a small function that *learns* good gestures instead of hand-writing them — became the number one priority. This chapter tells what happened when this track was finally built and tested for real.

## What was built

The idea: instead of offering the planner (Chapter 4) stories drawn at random, or a small frozen menu of hand-written gestures (Chapter 8), we train a function that has *watched* thousands of images from expert games (the ones already used elsewhere in the project) and from the random coverage episodes from Chapter 7 (the ones that actually show "lost, searching" situations). This function learns to predict: based on what the agent sees right now, what action would a player likely choose next.

Important point, already announced in Chapter 9: this function never decides the final action. It only slips its best suggestions into the pile of 512 imagined stories that the planner continues to judge and correct at each turn — exactly the same principle as the highly recognized game methods mentioned in the previous chapter (the ones that beat human champions at chess and Go): a learned intuition proposes moves, an explicit search verifies them.

## A rejected verification: the project's honesty at work

Before trusting this function, we had to verify that it hadn't done what this project has dreaded since the very first chapter: collapse onto a single identical answer, regardless of the image shown (the "collapse" trap, Chapter 2 — applied here to an action policy rather than a visual representation).

Two versions were trained to test this. The planned version (expert games + mixed coverage episodes) passed the test: its predictions remain varied, and it becomes significantly more hesitant — proposing a wider array of actions — on images that look like "lost, searching" than on those that look like an expert scene right in front of a tree. A second version, trained only on expert games (without coverage episodes), **failed** the test, however: it had learned to almost always answer "attack", exactly the weakness Chapter 9 feared beforehand. The training program **refused to save** this faulty version — the same discipline as in the rest of the project: a tool that fails its own test is never kept just because it ran.

## The live test: still zero

Over 8 episodes, with this function in place: **0 logs chopped, zero reward.** As with previous attempts at this sample size, this number alone proves nothing definitive — but it also shows no positive sign to cling to.

## What this result actually eliminates

The zero itself is not the most interesting part. Two specific things were able to be verified, and eliminated, thanks to this test:

- **No locking onto a single gesture.** Unlike in Chapter 8, where the agent froze on a single action up to 100% of the time in several episodes, here the action distribution remains varied across all 8 episodes (the most frequent action takes up between 16% and 54% of the time, never more). The learned function does exactly what it was built for: propose a diverse menu of gestures, not a narrow menu that the agent freezes on.
- **No unwinnable starting points.** A new diagnostic tool (announced as a plan in Chapter 9, built since) confirms that, across the 8 episodes, something relevant was visibly present at one moment or another — well above the calibrated minimum threshold. This batch cannot therefore be explained by "the starting point made success impossible from the start," unlike some episodes in previous chapters.

## The new suspect

A truly varied source of proposals, trained correctly, tested on confirmed playable starting points — and still zero success. This is the cleanest negative result of this entire investigation, not just another zero: track B was the most "logical" answer to the Chapter 8 diagnosis ("the problem is generating candidate gestures"), and it did not move the needle.

This pushes the diagnosis one step further, toward a new hypothesis — not yet confirmed, only posited: perhaps the problem is not the diversity of the proposed gestures, but the way the imagined world itself **judges** these proposals in a situation it knows poorly. The model that scores the imagined stories learned mostly on expert games, where a tree is almost always guaranteed in the field of view. Faced with a true random starting point — without this guarantee, with an arbitrary camera angle — perhaps it poorly evaluates even good proposals, a bit like a chess player trained almost exclusively on classical openings who finds themselves misjudging a rare and unusual position, even if their way of thinking remains otherwise sound.

## What's next

Before spending more training time on a new fix, the next step is simpler: carefully watch the recorded images of these 8 episodes — see concretely what the agent does on a confirmed playable starting point that still fails to turn into a chopped log. A qualitative look before a new expensive undertaking, exactly the same discipline as the rest of the project.

:::

::: expert

## Context

Chapter 9 promoted Proposal B (latent policy prior trained by behavioral cloning) to priority 1, after Proposals A+C (Chapter 8, attempt #8) confirmed without solving the "behavioral wall" diagnosis. This chapter covers attempt #9 from `CLAUDE.md` (Phase 5+): Proposal B built, verified, and evaluated live.

## What was built

`mine_jepa/ebwm/actor.py::BCActor`: a small MLP classifier on the frozen latents of `ebwm.pt`, trained by `scripts/train_actor_bc.py` with a mandatory anti-collapse gate (refuses saving in case of collapse). Training on Treechop demos + attempt #3's coverage episodes, to mix authentic search behavior with expert demonstrations (the trap identified in Chapter 9: an actor trained only on Treechop would learn "always attack the visible tree").

Wiring into `_sample_actions()` via `planner.actor_prior` (config-gated), verified bit-for-bit identical to the old sampler when disabled — **confirmed by a real fixed-seed run, not just asserted by analogy** with other config-gated changes in the project. An independent reachability check shows that the actor's candidates do indeed win the planner's argmax on 6 out of 40 draws (versus a base rate of 25% with uniform drawing) — present in the executed stream, not silent dead code, yet without dominating.

## The anti-collapse gate: discriminating, with a true failure rejected

- **Actor with coverage** (the one used for evaluation): `val_acc` 0.483, mean entropy 1.296 nats (out of a maximum 2.833 nats) → **PASS**.
- **Treechop-only ablation**: `val_acc` 0.587, entropy 1.102, `top_action_frac` 0.964 → **FAIL, checkpoint correctly rejected**.

This contrast confirms that the coverage data carried real weight for the gate, it was not decorative: without it, the actor would have collapsed towards a degenerate policy (dominated at 96.4% by a single action).

## Live Result

N=8, seed 0, `configs/play_craft_commit4_actor.yaml`, goal-centroid scoring only (no non-flat distance signal available at this stage — see below). **0/8 logs, zero reward.** One-sided exact Fisher against pooled `commit_length=4` alone base rate (3/31 ≈ 9.7%): **p ≈ 0.21** — not significant at this N.

## What this result specifically eliminates

1. **No lockdown.** Action concentration over the 8 episodes: peak between 16% and 54%, across the entire range — nothing approaching the 83-100% near-total lockdown observed in attempt #8 on three out of eight episodes. The actor-prior mechanism does what it was designed for: propose a varied and non-degenerate menu of candidates.
2. **No unlivable spawn.** The spawn viability diagnostic (built following attempt #8, `spawn_diag` in `scripts/play_craft.py`) confirms that all 8 spawns were measurably viable: `max_chop_std` between 0.017 and 0.047, comfortably above the calibrated 0.005 threshold. This batch cannot therefore be explained by "the starting point made all success impossible", unlike some earlier episodes.

## Refined diagnosis: a new suspect, not yet confirmed

**This is the cleanest negative result of the campaign, not just another zero.** An authentically diverse, non-collapsed source of proposals, trained on expert demonstrations and authentic search, tested on demonstrably viable spawns — and still zero successes. Proposal B was the "correct" answer to the Chapter 8 diagnosis ("the wall is behavioral, fix action generation") and it did not move the needle.

This pushes the standing diagnosis one step further: the bottleneck might not be the *diversity* of what is proposed, but the imagined world's **evaluation** of these proposals under the cold-start visual distribution of `MineRLObtainIronPickaxeDense-v0` (random spawn, arbitrary camera pose, no forest guarantee) — a distribution on which `ebwm.pt` was never trained to score correctly, unlike the guaranteed-forest Treechop distribution. **Not yet tested directly; flagged as the next hypothesis, not yet as established fact.**

## Reminder: two complementary tracks from Chapter 9 already closed before this test

- **Photometric repair of the trained distance metric (attempt #7)**: implemented (`augmentation.color_jitter` in `scripts/train_value_projector.py`). The offline separation gate still holds (8.7× vs 7.9× in attempt #7). But the actual target — the confusion with brightness — **worsens instead of improving** on a cleaner isolated measurement: correlation `r=0.117` (attempt #7, no augmentation) → `r=0.498` (with augmentation). **NO-GO — the confusion is likely anchored in the frozen latent space of `ebwm.pt` itself** (Treechop, mostly daytime), not introduced by projector training; perturbing only the projector inputs cannot undo a shortcut the upstream encoder has already taken. `checkpoints/value_projector_colorjitter.pt` kept for comparison, **unused** in the evaluation above — hence goal-centroid scoring only for attempt #9.
- **Spawn viability diagnostic**: built and already used above (see "what this result eliminates"), not just planned.

## Next Step

Before any new training effort: qualitative inspection of the GIF (`assets/agent_play_craft_commit4_actor.gif`) and spawn thumbnails (`assets/spawn_thumbs/`) — visually understand what the agent does on a confirmed viable spawn that still fails to convert into chopping, before deciding which fix to test next.

:::

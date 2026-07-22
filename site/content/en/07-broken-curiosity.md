---
title: "Broken curiosity, then two patches that half-work"
slug: "07-broken-curiosity"
lang: "en"
order: 7
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft"]
source_docs: ["docs/09_curiosity_coldstart.md", "docs/10_coldstart_engineering.md", "CLAUDE.md#Phase 5+"]
---

::: beginner

## The problem we are tackling: finding the first tree, alone

Chapter 6 ended on a well-identified wall: the agent knows how to craft planks perfectly once it has wood, but in a real randomly generated survival world, it **never** finds its first tree — 0 logs out of 5 tested episodes. This chapter tells the story of the first major campaign to attack this wall. Honest spoiler, as always in this project: the first idea fails cleanly, and the subsequent patches only provide partial progress — but each failure reveals something precise about the true nature of the problem.

## Idea #1: Curiosity — rewarding the agent for what surprises it

The idea is called **artificial curiosity**. The principle: instead of only rewarding the agent for reaching a goal, give it a small reward every time it goes towards something **surprising** — a place its world model understands poorly, where its predictions are very wrong. The intuition: if the agent never finds a tree because it doesn't know which direction to look, pushing it towards what surprises it should naturally make it explore rather than standing still.

Practically, the project built a small committee of 5 "guessers" that each try to predict what will happen next in the embedding (the number-summary of the image, Chapter 1). When the 5 guessers agree, it is a familiar place — nothing surprising. When they disagree, it is a poorly understood place — potentially interesting to explore. This idea is called Plan2Explore and comes from a real research paper.

Before launching this experiment (and all the following ones in this chapter and the next), the project built a small team of three specialized software agents — one that proposes an experiment based on real scientific references, one that implements it without ever breaking what already works, and one that tests it honestly and reports the true numbers. This discipline prevents telling oneself stories about one's own results.

## The result: no difference, and slower

Comparison over 20 episodes of Treechop (the "just chop a tree" mode from Chapter 5), with and without curiosity enabled: **without curiosity, 30% success; with curiosity, 25%** — a difference far too small to be reliable with only 20 episodes on each side, and above all, with curiosity, the game runs **two and a half times slower** (the committee of 5 guessers has to judge each of the 512 imagined stories at every instant, Chapter 4). Honest verdict: **curiosity brought nothing, and it cost a lot in speed.**

## Why it failed: the committee agreed too fast

Looking at the training of the committee of guessers, the explanation becomes clear: by the third training pass, the 5 guessers **all agreed with each other**, and stayed in agreement for the rest of the training. A committee that always agrees can never again signal "this is surprising" anywhere — the curiosity signal flatlined everywhere, which explains exactly why enabling curiosity changed nothing (except slowing down the game).

The real cause, more interesting than the symptom: the real Plan2Explore method trains its committee of guessers **continuously, on what the agent discovers while exploring itself** — a naturally varied stream of data, since the agent constantly moves towards new places. This project, however, trained the committee **once and for all, on frozen recordings of expert games where they always chop the same tree the same way**. On such repetitive data, all 5 guessers find the same simple solution, and never again have a reason to disagree. **The project reproduced the form of the method without reproducing the condition that makes it work.**

## Idea #2: Stop looking through the lens of curiosity

After this failure, the project stepped back and asked the question differently: what does the planner (Chapter 4) *actually*, mechanically do when no tree is visible? Two very concrete flaws appeared — neither of which requires machine learning to be fixed.

**Flaw 1: The planner cannot even imagine the right gesture.** To search for an invisible tree, the right gesture is "turn the camera in one direction for several instants in a row". But the planner draws its 512 imagined stories by choosing, at *each* instant, an action completely independent of the previous one — a bit like rolling a 17-sided die 12 times in a row without memory. The probability of such a draw producing the "turn" action 6 times in a row is practically zero. **The problem is not that the planner chooses poorly — it's that the right gesture doesn't even exist in the list of things it considers.**

The fix is called **sticky sampling**: at each imagined instant, instead of drawing a completely new action, repeat the previous action with a certain probability. This single rule jumps the consecutive repetition rate from 7% (independent draw) to 72% (70% sticky) — the 512 imagined stories now contain gestures held over time (turn-and-look, walk-towards, strike continuously).

**Flaw 2: The agent doesn't even know it is lost.** When a tree is visible, the 512 imagined stories get very different scores (some get closer, some move away). When nothing is visible, the 512 scores are almost identical — the final choice becomes a disguised coin flip. This gap between scores (their standard deviation) is a free signal, already calculated, never used before: high means "I see something useful"; close to zero means "I am lost". A small rule was added: after several consecutive turns with this signal close to zero, the agent temporarily abandons the planner and **turns the camera methodically** until the signal goes back up (a tree entered the field of view) or a budget of turns is exhausted.

Take this for what it is: this is **not learning**. It is a hand-written reflex — the kind of thing that heavier methods (out of reach for a single consumer GPU) learn on their own. But it makes no sense to teach an agent to explore if it cannot even turn its head properly.

## The results: real progress on Treechop, zero on cold-start

On Treechop (the agent always starts in a forest), the sticky+reflex combination yields a nuanced result: at a moderate setting (50% sticky), the success rate remains within the normal range already observed in Chapter 5, but each success yields about twice as much reward — the stickiness helps to *dig deeper* (keep chopping a tree already found) more than to *search wider* (find more trees). At a stronger setting (70% sticky), the agent gets stuck too much on a single gesture and the result slightly worsens.

On the real cold-start (random spawn, no starting wood): **zero logs chopped, in all tested configurations.** Worse, at a certain threshold setting, the "turn head" reflex becomes pathological: the agent turns the camera 82 to 92% of the time, literally spinning in circles without ever stopping. The most revealing observation: in some episodes, the agent ends up **surrounded by trees and still does not chop them**. So it is not (only) a search problem — it is an *approach and chop* problem once the target is found.

A variant tested for understanding: give the agent two separate "brains" — the one that proved itself on Treechop drives the tree search, the new model takes over from the first log to craft. Result: still zero logs, but the behavior changes markedly (recognizable lumberjack gestures instead of confused wandering). One of the episodes shows the agent spawning in a rocky ravine without a single tree, and hitting stone instead — a reminder that a spawn point with no wood at all cannot be solved by any search reflex.

## One last attempt before concluding: fine-tuning the model on more diversity

Last avenue tested in this campaign: if the "I am lost" signal is blurry on the crafting model (unlike the Treechop model where it is sharp), it might be because the expert demonstrations used to train it rarely show moments where the expert is "lost" — experts find wood fast, they never linger in the void. By adding about twenty short games played randomly (thus, statistically, often lost) to the training dataset, and then lightly retraining the model on this mix, the "lost vs. found" signal indeed becomes much sharper than before.

But the final result does not change one bit: still zero logs chopped, with or without this fine-tuning. **Making the signal sharper did not make the behavior better.** This discovery confirms what the two-brains experiment had already suggested: the wall is not in the *perception* (knowing one is lost), it is in the *behavior* (knowing what to do once something is found, or how to cover ground when nothing is found). The next chapter continues this investigation with even more direct tools.

:::

::: expert

## Framing: From an Exploration Hypothesis to a Mechanical Diagnostic

The initial symptom (0 logs on `ObtainIronPickaxeDense`, 5 episodes, `docs/08_crafting.md`) was first treated as an exploration/intrinsic reward problem, then re-diagnosed as an implementation flaw of the MPC itself — two readings of the same symptom, tested in order.

## Harness: A 3-Agent Development Loop

Before any experiment: `jepa-explorer` (read-only, proposes an experiment grounded in `docs/references/index.md` §3), `jepa-developer` (implements, config-gated, never touches a working checkpoint, seeded), `jepa-tester` (runs gates + play, reports PASS/FAIL with real numbers, honest on variance), orchestrated by `/jepa-loop`.

## Proposal #1 — Plan2Explore, offline novelty

**Idea** (Sekar et al., [arXiv:2005.05960](https://arxiv.org/abs/2005.05960), ICML 2020): add an intrinsic bonus `score = goal_score + λ · novelty_score`, `novelty_score` = disagreement of an ensemble of k=5 1-step action-conditioned prediction heads on the spatial latent `[D,8,8]`.

**Implementation**: `mine_jepa/ebwm/curiosity.py::DisagreementEnsemble`; `scripts/train_curiosity.py` trains on **frozen** eb-JEPA latents, separate optimizer, seeded, saves to `checkpoints/curiosity_ensemble.pt`, never touches `ebwm.pt`; `DiscreteLatentPlanner` blends the z-scored novelty when `novelty_coeff > 0` (`0.0` default = bit-for-bit original behavior).

**Result, A/B on `MineRLTreechop-v0`, N=20, same `ebwm.pt` (ratio 0.927):**

| Condition | Success | Mean Reward | Logs | fps |
|---|---|---|---|---|
| OFF (goal-centroid only) | 6/20 = 30% | 0.40 | 8 | 63 |
| ON (novelty λ=1.0) | 5/20 = 25% | 0.25 | 5 | **25** |

Non-significant difference at N=20 (documented 25-50% Treechop variance); cost 2.5× the fps (the ensemble runs on the 512 candidates at every replan). Verdict: **FAIL**.

## Root Cause: Ensemble Collapse During Training

```
epoch 1: val_disagree = 0.0613   (healthy diversity)
epoch 2: val_disagree = 0.0122
epoch 3: val_disagree = 0.0017   (collapsed)
epoch 4-15: val_disagree ≈ 0.0005 (dead, never recovers)
```

By epoch 3, all 5 heads converge to the same function → disagreement ≈ 0 everywhere → novelty bonus uniformly null → planner identical to goal-centroid alone, just slower.

> **Reproducing the *form* of Plan2Explore without its *condition*.** Plan2Explore trains its ensemble **online**, on a data stream that the agent itself diversifies by exploring. Training on a frozen set of Treechop demos (same lumberjack gesture, same tree, same camera) — so homogeneous — makes every head converge to the same trivial low-loss solution. The quality of an ensemble's novelty signal is bounded by the diversity of its training data, and offline training on frozen latents from expert demos precisely destroys that diversity.

Retained candidates for the future, in order of relevance: explicit disagreement regularization; RND ([arXiv:1810.12894](https://arxiv.org/abs/1810.12894), structurally immune to this collapse since the target never moves); online self-play (the actual Plan2Explore recipe, more costly).

## Re-analysis Without the Curiosity Lens: Two Mechanical Flaws

**Flaw 1 — i.i.d. sampling cannot *propose* the right behavior.** The corrective gesture for "nothing in sight" is a held action (turn camera for several consecutive steps). The probability that an i.i.d. sequence over 17 actions produces 6 consecutive repetitions is (1/17)⁶ — negligible. Fix: **sticky sampling** (`_sample_actions()`, `mine_jepa/ebwm/planner.py`, used by `DiscreteLatentPlanner` and `SwitchingCraftPlanner`): repeat previous action with probability `sticky_prob`, else draw new. Measured on 4096 sequences: consecutive repetition rate 7% (i.i.d.) → 72% (`sticky_prob=0.7`). `sticky_prob=0.0` (default) reproduces old behavior bit-for-bit. Inspiration: iCEM ([arXiv:2008.06389](https://arxiv.org/abs/2008.06389)), colored noise for continuous actions, adapted here in discrete form.

**Flaw 2 — The agent is blind to its own blindness.** `goal_score_std` (standard deviation of scores across the 512 candidates, already computed, never exploited): high when a goal is visible (the ranking means something), ≈0 when nothing is visible (the argmax is noise). The **macro scan** (`plan(..., return_info=True)` exposing `goal_score_std`; `scripts/play_ebwm.py` and `scripts/play_craft.py` in chop mode) triggers, after `patience` consecutive flat replans, a fixed camera-yaw action (`a12`, +10°/replan) until signal recovery or `max_replans` expiry. `scan.enabled: false` by default. Explicit honesty: this is a hand-written reflex, not learning.

### Calibration (PC, 3 Treechop episodes, 750 replans/ep., seed 0)

| Situation | `goal_score_std` Band |
|---|---|
| Lost (wall, sky, open grass) | 0.0002 – 0.002 |
| Wandering, trees in distance | 0.003 – 0.01 |
| Tree/canopy full frame | 0.02 – 0.056 |

`flat_threshold: 0.003` retained (just above the "lost" band), `patience: 3`.

## Gate (PC, 2026-07-08) — Treechop: Partial Progress

| Condition | N | Success | Mean Reward | fps |
|---|---|---|---|---|
| OFF (fresh baseline) | 20 | 45% (9/20) | 0.50 | 65.9 |
| sticky 0.7 + scan@0.003 | 20 | 25% (5/20) | 0.45 | 65.0 |
| sticky 0.5 + scan@0.003 | 10 | 40% (4/10) | **0.90** | 64.6 |

No significant difference (Fisher p=0.32 / p=1.0) but consistent direction: 0.7 over-commits (a14 at 71-97%, walks indefinitely on a single gesture); 0.5 maintains success within the variance band and **doubles the reward per success** — stickiness buys *depth* (keep chopping the reached tree), not *breadth* (find more trees). fps unchanged.

## Gate — Cold-start: FAILURE in all configurations

| Config | N | Logs | Note |
|---|---|---|---|
| sticky 0.5 + scan@0.003 | 1 (aborted) | 0 | agent often *in* the forest, does not chop |
| sticky 0.5 + scan@0.004 | 5 | 0 | pathological: a12 82-92%, 15-34 scans/ep. — agent spins in circles |
| sticky 0.5, scan off | 5 | 0 | varied actions, still no first log |

Cause: on `craft_wm_v4.pt` the `goal_score_std` bands are **compressed** (lost ~0.002, tree-visible ~0.010, median 0.0047 — a 5× spread) versus Treechop's clean 10× spread. Any absolute threshold triggers too little or too often. Clearest finding: with scan@0.003, the agent is sometimes **surrounded by trees and still does not chop** — the wall is not (just) search, it is the approach-and-chop behavior itself.

**Micro-experiment — swap the chop compass**: use the Treechop centroid (12,056 reward≥0.5 frames) encoded by the `craft_wm_v4` encoder instead of the Obtain-demo centroid as the chop goal. Result: still 0/5. The compass alone does not save the cold-start.

**Two-brain agent** (`chop_model:`, config-gated): `ebwm.pt` drives chop (17 shared movement actions), `craft_wm_v4` takes over at first log. Result: still 0/5, but behavior transformed (a14 sprint+attack 30-52% instead of diffuse wandering). GIF of the most aggressive episode (a6=85%): spawn in a treeless rocky ravine, agent punches stone. 2/5 episodes die early. The remaining wall: random treeless spawn and search radius — precisely the domain of online curiosity.

Default flaws preserved: `play_ebwm.yaml` → sticky 0.5 + scan on (calibrated, risk-free, deeper chops); `play_craft.yaml` → sticky 0.5, scan **off**, two-brains on.

## Fine-tuning on Coverage Data (2026-07-20) — signal improved, result unchanged

Hypothesis: the compressed bands of `craft_wm_v4.pt` are an artifact of data coverage — the 40 expert demos rarely show "lost, no trees in sight" (experts find wood fast). Tested fix: ~20 short episodes (400 steps) of random policy on `ObtainIronPickaxeDense-v0` (random spawn = free biome diversity), merged with the 40 expert demos, then fine-tuned for 4 epochs at low LR from a `craft_wm_v4.pt` save (`checkpoints/craft_wm_v4_coverage.pt`). No collapse (`bvar` 1.24-1.27), no precondition regression (`dPlanks@craft` stayed between +1.22 and +1.35 over fine-tune epochs).

| | save (original) | coverage (fine-tuned) |
|---|---|---|
| Chopped logs (N=3) | 0/3 | 0/3 |
| Crafted planks (N=3) | 0/3 | 0/3 |
| Median `goal_score_std` | 0.0034 | 0.0126 (×3.7) |
| p90/p10 Ratio | ×3.2 | ×5.4 |
| Episode length | 3000/3000/3000 | 2295/3000/1070 (2 early deaths) |

**Verdict: the signal improved, the result did not.** The band separation indeed widened (×3.2 → ×5.4, approaching Treechop's ×10) — the data-coverage mechanism is real — but 0/3 logs identical on both checkpoints, and the fine-tuned checkpoint dies earlier on 2/3 episodes (more exploratory movement, no more chopping).

> **Lesson: refining the "am I lost?" signal does not, by itself, fix the search-and-approach behavior that must exploit it.** The two-brain experiment's diagnostic holds: the gap is behavioral (search/approach), not purely perceptual. The coverage data helps the model better *represent* the "lost" state; it does not teach it what to *do* with it.

`ebwm.pt`, `craft_wm_v4.pt`, `craft_wm_v4_backup.pt` intact; `craft_wm_v4_coverage.pt` is a separate comparison checkpoint, not a replacement.

## References (Verified, from docs/references/index.md)

- Sekar, Rybkin, Daniilidis, Abbeel, Hafner, Pathak, Plan2Explore, arXiv:2005.05960 (ICML 2020) — the principle of novelty via ensemble disagreement tested and diagnosed in this chapter.
- Burda, Edwards, Storkey, Klimov, RND, arXiv:1810.12894 (2018) — the retained candidate for the future, immune to ensemble collapse by design.
- iCEM, arXiv:2008.06389 (2020) — inspiration for the temporally correlated noise behind discrete sticky sampling.

:::

---
title: "Broken curiosity, then two patches that half-work"
slug: "07-broken-curiosity"
lang: "en"
order: 7
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft"]
source_docs: ["docs/09_curiosity_coldstart.md", "docs/10_coldstart_engineering.md", "CLAUDE.md#Phase 5+"]
---

::: beginner

## The problem being tackled: finding the first tree, alone

Chapter 6 ended on a well-defined wall: the agent crafts planks perfectly once it holds wood, but in a real randomly generated survival world, it **never** finds its first tree — 0 logs chopped over 5 tested episodes. This chapter tells the story of the first major campaign to attack that wall. An honest spoiler, as always in this project: the first idea fails cleanly, and subsequent patches provide only partial progress — but every failure reveals something precise about the true nature of the problem.

## Idea #1: curiosity — rewarding the agent for surprises

The concept is called **artificial curiosity**. The principle: instead of rewarding the agent strictly for reaching an explicit goal, we also give it a small reward whenever it moves toward something **surprising** — a location its world model understands poorly, where its predictions make large errors. The intuition: if the agent never finds a tree because it doesn't know which direction to search in, pushing it toward surprising experiences should naturally drive exploration over standing idle.

Concretely, the project built a small ensemble of 5 "predictors" that each try to predict what happens next in embedding space (the numerical summary of the frame, Chapter 1). When all 5 predictors agree, it's a familiar location — nothing surprising. When they disagree, it's a poorly understood location — potentially interesting to explore. This idea is called Plan2Explore and comes from a real published research paper.

Before launching this experiment (and all subsequent ones in this chapter and the next), the project built a small team of three specialized software sub-agents — one proposing experiments grounded in verified scientific literature, one implementing them without breaking existing working checkpoints, and one testing them honestly and reporting true numbers. This discipline prevents self-delusion about results.

## The result: zero difference, and much slower

Comparison across 20 Treechop episodes (the "just chop a tree" mode from Chapter 5), with and without curiosity enabled: **without curiosity, 30% success rate; with curiosity, 25%** — a difference far too small to be statistically meaningful over 20 episodes per arm, and critically, curiosity made the game run **2.5 times slower** (the 5-predictor ensemble has to evaluate all 512 imagined futures at every single timestep, Chapter 4). Honest verdict: **curiosity added zero performance benefit, and cost heavily in runtime speed.**

## Why it failed: the ensemble agreed too quickly

Examining the training logs of the predictor ensemble, the explanation became obvious: by training epoch 3, all 5 predictors **had converged to exact agreement**, and remained in lockstep agreement for the rest of training. An ensemble that always agrees can never flag "this is surprising" anywhere — the curiosity signal flatlined to zero everywhere, explaining precisely why enabling curiosity changed nothing (other than slowing down execution).

The true underlying cause, more interesting than the symptom: the true Plan2Explore method trains its predictor ensemble **online, on data collected as the agent explores on its own** — a stream of data that stays diverse because the agent continuously visits new places. This project trained the ensemble **once and for all, offline, on fixed recordings of expert human games that always chop the same tree in the same way**. On such repetitive data, all 5 predictors quickly find the exact same low-loss solution, and lose any reason to disagree. **The project reproduced the form of the method without reproducing the condition that makes it work.**

## Idea #2: looking past curiosity

Following this failure, the project took a step back and reframed the question: what is the planner (Chapter 4) *actually* doing, mechanically, when no tree is in view? Two very concrete flaws emerged — neither requiring machine learning to fix.

**Flaw 1: the planner cannot even imagine the right gesture.** To search for an unseen tree, the correct gesture is "rotate the camera in one direction for several consecutive frames". But the planner samples its 512 imagined futures by picking an action independently at *every single imagined step* — like rolling a 17-sided die 12 times in a row with zero memory. The probability of such sampling generating 6 consecutive "turn" actions is practically zero. **The problem isn't that the planner chooses poorly — it's that the correct gesture doesn't even exist in the set of candidate futures it considers.**

The fix is called **sticky sampling**: at each imagined step, instead of sampling a fresh random action, repeat the previous action with a chosen probability. This single rule increases consecutive action repetition from 7% (independent sampling) to 72% (70% sticky probability) — the 512 candidate futures now contain sustained gestures (turn-and-look, walk-forward, sustained striking).

**Flaw 2: the agent doesn't even know it's lost.** When a tree is in view, the 512 candidate futures yield wildly different goal scores (some get close to the tree, others move away). When nothing is in view, all 512 scores are nearly identical — the final choice becomes random button-mashing in disguise. This spread across scores (their standard deviation) is a free signal, already computed, never used before: high spread means "I see something useful"; near-zero spread means "I am lost". A simple rule was added: after several consecutive timesteps with near-zero score spread, the agent temporarily steps away from the planner and **turns the camera methodically** until score spread recovers (a tree enters view) or a budget expires.

To be clear: this is **not machine learning**. It is a hand-written reflex — the kind of behavior heavier methods (out of reach of a single consumer GPU) learn on their own. But it makes little sense to try to learn exploration when an agent cannot even turn its head properly.

## Results: real progress on Treechop, zero on cold-start

On Treechop (where the agent always spawns in a forest), combining sticky sampling + camera scan yields a nuanced result: at a moderate setting (50% sticky), success rate stays in the normal range observed in Chapter 5, but every successful episode yields roughly double the reward — sticky sampling helps *dig deeper* (continue chopping an already found tree) more than it helps *search* (find more trees). At a higher setting (70% sticky), the agent gets stuck on single actions too aggressively and performance degrades slightly.

On true cold-start (random spawn, no starting wood): **zero logs chopped across all tested configurations.** Worse, at certain threshold settings, the "turn head" reflex becomes pathological: the agent turns its camera 82% to 92% of the time, literally spinning in circles endlessly. The most revealing observation: in some episodes, the agent spawns **surrounded by trees and still does not chop them**. The core issue is not (just) a search problem — it is an *approach-and-chop* execution problem once a target is found.

A diagnostic variant tested to understand this: give the agent two separate "brains" — the proven Treechop model handles searching for the tree, and the new crafting model takes over once the first log is acquired. Result: still zero logs, but behavior shifts noticeably (recognizable lumberjack actions instead of confused wandering). One episode showed the agent spawning in a rocky ravine with zero trees, striking stone instead — a reminder that a spawn point with zero wood in range cannot be solved by any search reflex.

## One final attempt before concluding: fine-tuning on diverse data

The final avenue tested in this campaign: if the "am I lost?" signal is blurry on the crafting model (unlike the Treechop model where it is sharp), perhaps it's because expert human demos rarely show moments where the expert is "lost" — experts find wood instantly, never wandering in empty space. By adding ~20 short random gameplay recordings (statistically rich in "lost" states) to the training corpus and lightly fine-tuning the model on this blend, the "lost vs found" signal did indeed become much sharper than before.

Yet the final result didn't change one bit: still zero logs chopped, with or without this refinement. **Making the signal sharper did not make the behavior better.** This discovery reinforced what the two-brain experiment had suggested: the wall is not in *perception* (knowing you are lost), it is in *behavior* (knowing what to do once something is found, or how to cover ground when nothing is found). The next chapter continues this investigation with even more direct diagnostic tools.

:::

::: expert

## Framing: From Exploration Hypothesis to Mechanical Diagnostics

The initial symptom (0 logs on `ObtainIronPickaxeDense`, 5 episodes, `docs/08_crafting.md`) was initially treated as an intrinsic reward/exploration issue, then re-diagnosed as an implementation flaw in MPC itself — two interpretations of the same symptom, tested sequentially.

## Harness: 3-Agent Development Loop

Before any experiment: `jepa-explorer` (read-only, proposes experiment grounded in `docs/references/index.md` §3), `jepa-developer` (implements, config-gated, never touches working checkpoints, seeded), `jepa-tester` (runs gates + play, reports PASS/FAIL with true numbers, honest on variance), orchestrated by `/jepa-loop`.

## Proposal #1 — Plan2Explore, Offline Novelty

**Idea** (Sekar et al., [arXiv:2005.05960](https://arxiv.org/abs/2005.05960), ICML 2020): Add intrinsic bonus `score = goal_score + λ · novelty_score`, where `novelty_score` = disagreement of an ensemble of k=5 1-step action-conditioned prediction heads on spatial latent `[D,8,8]`.

**Implementation**: `mine_jepa/ebwm/curiosity.py::DisagreementEnsemble`; `scripts/train_curiosity.py` trains on **frozen** eb-JEPA latents, separate optimizer, seeded, saves to `checkpoints/curiosity_ensemble.pt`, never touches `ebwm.pt`; `DiscreteLatentPlanner` blends z-scored novelty when `novelty_coeff > 0` (`0.0` default = bit-for-bit original behavior).

**Result, A/B on `MineRLTreechop-v0`, N=20, same `ebwm.pt` (ratio 0.927):**

| Condition | Success Rate | Mean Reward | Logs | fps |
|---|---|---|---|---|
| OFF (goal-centroid only) | 6/20 = 30% | 0.40 | 8 | 63 |
| ON (novelty λ=1.0) | 5/20 = 25% | 0.25 | 5 | **25** |

Non-significant difference at N=20 (documented 25-50% Treechop variance); 2.5x fps penalty (ensemble evaluates all 512 candidates at every step). Verdict: **FAIL**.

## Root Cause: Ensemble Collapse During Training

```
epoch 1: val_disagree = 0.0613   (healthy diversity)
epoch 2: val_disagree = 0.0122
epoch 3: val_disagree = 0.0017   (collapsed)
epoch 4-15: val_disagree ≈ 0.0005 (dead, never recovers)
```

By epoch 3, all 5 heads converge to identical functions → disagreement ≈ 0 everywhere → novelty bonus uniformly zero → planner behaves identically to goal-centroid alone, just slower.

> **Form of Plan2Explore without its condition.** Plan2Explore trains its ensemble **online, on a data stream diversified by the exploring agent itself**. Training offline on a static set of Treechop demos (same chopping gesture, same tree type, same camera perspective) — highly homogeneous — drives every head to the same low-loss trivial solution. The quality of an ensemble novelty signal is bounded by training data diversity; offline training on frozen expert demo latents destroys that exact diversity.

Retained candidates for future work: explicit disagreement regularization; RND ([arXiv:1810.12894](https://arxiv.org/abs/1810.12894), structurally immune to collapse as target never moves); online self-play (true Plan2Explore recipe, higher compute cost).

## Re-analysis Without Curiosity Lens: Two Mechanical Flaws

**Flaw 1 — i.i.d. sampling cannot *propose* correct behavior.** The corrective gesture for "nothing in view" is sustained action (turning camera over multiple steps). The probability of an i.i.d. sequence over 17 actions producing 6 consecutive turns is (1/17)⁶ — negligible. Fix: **sticky sampling** (`_sample_actions()`, `mine_jepa/ebwm/planner.py`, used by `DiscreteLatentPlanner` and `SwitchingCraftPlanner`): repeat previous action with probability `sticky_prob`, else sample fresh. Measured over 4,096 sequences: consecutive action repetition rate 7% (i.i.d.) → 72% (`sticky_prob=0.7`). `sticky_prob=0.0` (default) reproduces legacy behavior bit-for-bit. Inspiration: iCEM ([arXiv:2008.06389](https://arxiv.org/abs/2008.06389)), temporally correlated noise for continuous actions, adapted to discrete actions.

**Flaw 2 — agent is blind to its own blindness.** `goal_score_std` (std of scores across 512 candidates, already computed, never used): high when goal is in view (ranking carries signal), ≈0 when nothing is in view (argmax is noise). **Macro scan** (`plan(..., return_info=True)` exposing `goal_score_std`; `scripts/play_ebwm.py` and `scripts/play_craft.py` in chop mode) triggers a fixed camera-yaw action (`a12`, +10°/replan) after `patience` consecutive flat replans, until signal recovery or `max_replans` exhaustion. `scan.enabled: false` by default. Explicit honesty: hand-written reflex, not machine learning.

### Calibration (PC, 3 Treechop episodes, 750 replans/ep, seed 0)

| Situation | `goal_score_std` Range |
|---|---|
| Lost (wall, sky, open grass) | 0.0002 – 0.002 |
| Wandering, distant trees | 0.003 – 0.01 |
| Tree/canopy full field | 0.02 – 0.056 |

`flat_threshold: 0.003` selected (just above "lost" band), `patience: 3`.

## Gate (PC, 2026-07-08) — Treechop: Partial Progress

| Condition | N | Success Rate | Mean Reward | fps |
|---|---|---|---|---|
| OFF (fresh baseline) | 20 | 45% (9/20) | 0.50 | 65.9 |
| sticky 0.7 + scan@0.003 | 20 | 25% (5/20) | 0.45 | 65.0 |
| sticky 0.5 + scan@0.003 | 10 | 40% (4/10) | **0.90** | 64.6 |

No statistically significant difference (Fisher p=0.32 / p=1.0) but consistent direction: 0.7 over-engages (a14 at 71-97%, walking indefinitely on single action); 0.5 maintains success within variance band and **doubles reward per success** — sticky sampling buys *depth* (chopping further into reached tree), not *breadth* (finding more trees). fps unchanged.

## Gate — Cold-Start: FAIL Across All Configurations

| Config | N | Logs | Note |
|---|---|---|---|
| sticky 0.5 + scan@0.003 | 1 (interrupted) | 0 | Agent often *in* forest, doesn't chop |
| sticky 0.5 + scan@0.004 | 5 | 0 | Pathological: a12 82-92%, 15-34 scans/ep — agent spins in circles |
| sticky 0.5, scan off | 5 | 0 | Varied actions, still zero first log |

Cause: on `craft_wm_v4.pt`, `goal_score_std` bands are **compressed** (lost ~0.002, tree-visible ~0.010, median 0.0047 — 5x gap) versus Treechop's clean 10x gap. Any absolute threshold triggers too rarely or constantly. Clear observation: with scan@0.003, agent is sometimes **surrounded by trees and still does not chop** — wall is not (only) search, but approach-and-chop execution itself.

**Micro-experiment — Swapping Chop Compass**: Use Treechop centroid (12,056 frames reward≥0.5) encoded by `craft_wm_v4` encoder instead of Obtain-demo centroid as chop goal. Result: still 0/5. Compass alone doesn't save cold-start.

**Two-Brain Agent** (`chop_model:`, config-gated): `ebwm.pt` drives chop (17 shared movement actions), `craft_wm_v4` takes over upon first log acquisition. Result: still 0/5, but behavior transformed (a14 sprint+attack 30-52% instead of diffuse wandering). GIF of most active episode (a6=85%): spawn in rocky ravine with zero trees, agent strikes stone. 2/5 episodes die early. Remaining wall: random spawn without nearby wood and search radius — precisely the domain of online curiosity.

Preserved defaults: `play_ebwm.yaml` → sticky 0.5 + scan on (calibrated, risk-free, deeper chops); `play_craft.yaml` → sticky 0.5, scan **off**, two-brain on.

## Fine-tuning on Coverage Data (2026-07-20) — Signal Improved, Result Unchanged

Hypothesis: compressed bands of `craft_wm_v4.pt` are a data coverage artifact — 40 expert demos rarely show "lost, no tree in sight" (experts find wood fast). Fix tested: ~20 short random policy episodes (400 steps) on `ObtainIronPickaxeDense-v0` (random spawn = free biome diversity), merged with 40 expert demos, fine-tuned 4 epochs low LR from `craft_wm_v4.pt` backup (`checkpoints/craft_wm_v4_coverage.pt`). Zero collapse (`bvar` 1.24-1.27), zero precondition regression (`dPlanks@craft` held between +1.22 and +1.35).

| | Backup (Original) | Coverage (Fine-tuned) |
|---|---|---|
| Logs Chopped (N=3) | 0/3 | 0/3 |
| Planks Crafted (N=3) | 0/3 | 0/3 |
| Median `goal_score_std` | 0.0034 | 0.0126 (3.7x) |
| Ratio p90/p10 | 3.2x | 5.4x |
| Episode Length | 3000/3000/3000 | 2295/3000/1070 (2 early deaths) |

**Verdict: Signal improved, result unchanged.** Band separation widened (3.2x → 5.4x, approaching Treechop's 10x) — data coverage mechanism is real — but 0/3 logs identical across both checkpoints, and fine-tuned checkpoint dies earlier in 2/3 episodes (more exploratory movement, no extra chopping).

> **Lesson: Sharpening the "am I lost?" signal does not, in itself, fix the search-and-approach behavior meant to exploit it.** The two-brain experiment diagnosis is confirmed: gap is behavioral (search/approach), not purely perceptual. Coverage data helps model better *represent* "lost" states; it doesn't teach it *what to do about them*.

`ebwm.pt`, `craft_wm_v4.pt`, `craft_wm_v4_backup.pt` intact; `craft_wm_v4_coverage.pt` is a separate comparison checkpoint, not a replacement.

## References (Verified, from docs/references/index.md)

- Sekar, Rybkin, Daniilidis, Abbeel, Hafner, Pathak, Plan2Explore, arXiv:2005.05960 (ICML 2020) — ensemble disagreement novelty principle tested and diagnosed here.
- Burda, Edwards, Storkey, Klimov, RND, arXiv:1810.12894 (2018) — candidate for future work, structurally immune to ensemble collapse.
- iCEM, arXiv:2008.06389 (2020) — inspiration behind discrete sticky sampling's temporally correlated noise.

:::

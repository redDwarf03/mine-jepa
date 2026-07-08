# Cold-start, part 2 — engineering before research

> Chapter 09 ended on a diagnosed failure: offline curiosity cannot fix cold-start
> chopping, because an ensemble trained on frozen expert demos loses the diversity
> its novelty signal depends on. Before reaching for the *next* research idea (online
> RND), this chapter fixes two things that were broken in plain sight — no learning
> involved, no checkpoint touched.

---

## Re-reading the failure without the curiosity lens

The cold-start symptom: the agent spawns, no tree in view, and it stands there
twitching (0 logs over 5 episodes in `ObtainIronPickaxeDense`). Chapter 09 framed this
as an *exploration* problem and attacked it with intrinsic reward. But look at what the
planner is actually doing at that moment, mechanically:

1. It samples **512 action sequences, each action drawn i.i.d. uniform** over 12 steps.
2. It imagines each future with the world model and scores it by similarity to the
   "success scene" prototype.
3. With no tree in view, **every imagined future scores the same** — the argmax picks
   among lottery tickets.

Two separate defects hide in there, and neither is about learning.

---

## Defect 1 — i.i.d. sampling cannot even *propose* the right behaviour

The fix for "nothing in view" is a sustained gesture: *turn the camera in one
direction for a couple of seconds*. Now compute the odds that a sequence like
`turn-turn-turn-turn-turn-turn` appears among 512 i.i.d. draws over 17 actions:
(1/17)⁶ per position — it effectively **never** does. The planner is not failing to
*choose* the searching behaviour; the behaviour **does not exist in its candidate
pool**. MPC can only pick the best of what it imagined.

This is a known weakness of random-shooting MPC, and the standard remedy is
temporally correlated sampling — iCEM ([arXiv:2008.06389](https://arxiv.org/abs/2008.06389))
uses colored noise; our discrete version is **sticky actions**:

```
at each step: repeat the previous action with probability p (sticky_prob ≈ 0.7)
              otherwise draw a fresh uniform action
```

Measured on 4096 sequences: consecutive-repeat rate goes from **7%** (i.i.d.) to
**72%** (sticky 0.7). The candidate pool now contains held gestures — turn-and-look,
walk-toward, sustained attack — the same reason `action_repeat=4` already helped
in Phase 4, applied *inside the imagination* instead of only at execution time.

Implementation: `_sample_actions()` in `mine_jepa/ebwm/planner.py`, used by both
`DiscreteLatentPlanner` and `SwitchingCraftPlanner`. `sticky_prob: 0.0` (the default)
reproduces the old behaviour bit-for-bit — project convention: every change is
config-gated, the baseline stays reachable.

## Defect 2 — the agent is blind to its own blindness

When a tree *is* visible, candidate futures differ sharply: sequences that approach
the trunk score much better than ones that wander off. When nothing is in view, all
512 scores collapse onto the same value. That spread — the **standard deviation of
the goal scores across candidates** — is a free, one-line signal that the planner
already computes and threw away:

```
goal_score_std  high → a goal is in view, the ranking means something
goal_score_std  ≈ 0  → "I am lost"; the argmax is noise
```

The **scan macro** turns that signal into a reflex: after `patience` consecutive flat
replans, override the planner and hold a camera-yaw action (`a12`, +10°/step) —
sweep the horizon — until the std recovers (a tree entered the frame) or a guard
(`max_replans`) expires. Then hand control back to the chopper, which already works
at 25–50% once a tree is visible.

Honesty first: **this is not learning.** It is a hand-written reflex, the kind of thing
DreamerV3 learns implicitly and we hard-code because our budget is one 8 GB GPU. The
research path (online RND curiosity, chapter 09's conclusion) stays on the roadmap —
but it makes no sense to teach an agent to *explore* while it cannot yet turn its head.

Implementation: `plan(..., return_info=True)` exposes `goal_score_std`;
`scripts/play_ebwm.py` and `scripts/play_craft.py` (chop mode only) run the state
machine, config block `scan:` in the play YAMLs, `enabled: false` by default.

---

## Calibrating the threshold (do this before enabling)

`flat_threshold` must be read from data, not guessed. On the NVIDIA PC:

```bat
:: scan.enabled=false, scan.log_std=true in configs/play_ebwm.yaml
run.bat scripts/play_ebwm.py --config configs/play_ebwm.yaml --episodes 3
```

Every replan prints `goal_score_std`. Cross-check against the GIF: read the typical
std when a tree fills the view vs. when the agent faces open grass/sky, and set
`flat_threshold` between the two bands (closer to the lost band).

**Calibration result (2026-07-07, PC, 3 Treechop episodes, 750 replans each, seed 0):**

| Situation (GIF cross-check) | `goal_score_std` band |
|---|---|
| Lost — facing dirt walls, sky, open grass | 0.0002 – 0.002 |
| Wandering, trees at a distance | 0.003 – 0.01 |
| Tree/canopy fills the view (chopping moments, Ep2) | 0.02 – 0.056 |

Per-episode percentiles: p10 = 0.0006–0.0016, median = 0.003–0.004, p90 = 0.009–0.011.
The winning episode (reward 1) had the highest tail (max 0.056 at the chop). Chosen
**`flat_threshold: 0.003`** — just above the lost band; with `patience: 3` consecutive
flat replans, transient dips don't trigger the sweep.

## The gate (what would make this chapter a PASS)

| Test | Baseline | Target |
|------|----------|--------|
| `MineRLTreechop-v0`, N=20, seeded, sticky=0.7 + scan vs. original | 25–50% (variance band) | ≥ 50%, fps ≈ unchanged |
| Cold-start `ObtainIronPickaxeDense`, N=5 (`play_craft.bat`) | **0/5 logs** | ≥ 1 log in ≥ 1 episode |

If the first cold-start log drops, the already-validated craft loop
(`MineRLObtainTest-v0`, 100% given wood) takes over — that is the milestone.
Both numbers get reported with variance, per the Phase 4 lesson: no claiming the
best run.

## Results (PC eval, 2026-07-08) — VERDICT: partial

**Treechop A/B** (seed 0, same `ebwm.pt`, same day):

| Condition | N | Success | Mean reward | fps |
|---|---|---|---|---|
| OFF — original planner (fresh baseline) | 20 | 45% (9/20) | 0.50 | 65.9 |
| sticky **0.7** + scan@0.003 | 20 | 25% (5/20) | 0.45 | 65.0 |
| sticky **0.5** + scan@0.003 (routing case 3) | 10 | 40% (4/10) | **0.90** | 64.6 |

- The ≥50% target was **missed**. No difference is statistically significant
  (Fisher: 0.7-vs-OFF p=0.32; 0.5-vs-OFF p=1.0), but the direction is consistent:
  **0.7 over-commits** — episodes lock onto one gesture (a14 at 71–97%) and march
  forever; **0.5 keeps success in the variance band and ~doubles reward per success**
  (one 5-log episode; total logs 9/10 eps vs 10/20 eps baseline). Sticky buys *depth*
  (keep chopping the tree you reached), not *breadth* (more trees found).
- fps unchanged (sticky and scan add no rollout cost), as designed.
- Scan on Treechop: fired 0–26×/ep with no visible harm at 0.003 — the bands there
  are well separated (lost ≤0.002 vs tree-visible ≥0.02, a 10× gap).

**Cold-start `ObtainIronPickaxeDense`** (N=5 each): **0 logs in every configuration —
gate FAILED.**

| Config | N | Logs | Note |
|---|---|---|---|
| sticky 0.5 + scan@0.003 | 1 (interrupted) | 0 | agent often *inside* the forest, still no chop |
| sticky 0.5 + scan@0.004 | 5 | 0 | **pathological**: a12 (turn) 82–92%, 15–34 scans/ep — the agent spins |
| sticky 0.5, scan OFF | 5 | 0 | diverse actions, still no first log |

Why the scan failed here: on `craft_wm_v4.pt` the std bands are **compressed**
(lost ~0.002, tree-visible ~0.010, median 0.0047 — a 5× gap with most mass in the
middle) vs Treechop's clean 10× gap. Any threshold either barely fires (0.003) or
fires constantly and the sweep eats the episode (0.004: each trigger runs toward
`max_replans=40` because the std rarely recovers above the line). The lost-state
detector needs a *relative* signal (e.g. std percentile over a trailing window),
not an absolute threshold — noted for a future pass.

Sharpest observation: with scan@0.003 the agent was often **surrounded by trees and
still didn't chop** — the cold-start wall is not (only) search, it's the
approach-and-chop behaviour itself, which `craft_wm_v4.pt`'s goal-centroid
(trained on Obtain demos, not Treechop demos) apparently doesn't drive as well as
`ebwm.pt` does. Routing case 4 applies: chapter closed as a **documented partial**;
next cycle is **online RND** (novelty that decays with experience — chapter 09's
conclusion stands).

**Follow-up micro-experiment — swap the chop compass.** The "inside the
forest, not chopping" observation suggested the culprit was the *goal*, not the
planner: the v4 chop centroid comes from Obtain-demo "log obtained" frames (players
doing many things), while `ebwm.pt`'s proven compass comes from Treechop reward
frames. Added `goal.chop_data_path` (config-gated, `scripts/play_craft.py`): use the
12,056 Treechop reward≥0.5 frames, encoded by *craft_wm_v4's own encoder*, as the
chop goal. Result: **still 0/5 logs** (sticky 0.5, scan off; two episodes also died
early — random survival spawns are hazardous). So the compass alone doesn't rescue
cold-start either: the remaining suspects are the *world model itself* (craft_wm_v4's
visual dynamics vs ebwm's — different training recipe and action space) and the
*environment* (Treechop spawns you inside a forest; ObtainIronPickaxe spawns you
anywhere, sometimes lethally). The option stays in the code; the config default
reverts to the Obtain centroid.

**Follow-up — the two-brain agent** (`chop_model:` block in `configs/play_craft.yaml`,
config-gated): `ebwm.pt` — the proven Treechop lumberjack — plans the chop phase over
the 17 movement actions shared by both action maps; `craft_wm_v4` takes over at the
first log (inventory dynamics is its actual strength). Result: **still 0/5 logs, but
the behaviour is transformed** — the action profile becomes the lumberjack gesture
(a14 sprint+attack 30–52%, a6/a7 attack) instead of the diffuse wandering seen with
the v4 brain. GIF inspection of the last episode (a6 at 85%): the agent spawned in a
**treeless rocky ravine and ground its axe on stone** — plus two of five episodes died
early. The remaining wall is neither the gesture nor the compass: it is the
`ObtainIronPickaxe` random spawn (biomes without trees in reach) and the search
radius. That is precisely the problem online RND is for; a cheaper first lever is
re-enabling the scan in two-brain mode, where the chop std comes from `ebwm.pt` again
and the 0.003 calibration is valid.

Kept defaults after this eval: `play_ebwm.yaml` → sticky 0.5 + scan on (calibrated,
harmless, deeper chops); `play_craft.yaml` → sticky 0.5, **scan off**, two-brain on.

---

## The lesson this chapter adds

> **Before asking "how does the agent learn X?", ask "can the agent even express X?"**
> The searching behaviour was impossible to sample and the lost-state was measurable
> all along. Curiosity (chapter 09) failed partly because it was aimed at a problem
> that is mostly *representational*: the planner's hypothesis space did not contain
> the solution. Fix the hypothesis space first; spend learning on what remains.

And its post-eval corollary:

> **A detector calibrated on one latent space does not transfer to another.** The
> lost-state signal was real on `ebwm.pt` (10× band separation) and unusable on
> `craft_wm_v4.pt` (5×, mass in the middle) — an absolute threshold on a
> checkpoint-dependent statistic is not a mechanism, it's a coincidence. And a
> recovery macro must be **bounded by budget, not by the signal it distrusts**:
> "turn until the std recovers" spun the agent for entire episodes.

*Previous: `docs/09_curiosity_coldstart.md`. Next (planned): online RND —
novelty that decays with experience, trained during play, per chapter 09's diagnosis.*

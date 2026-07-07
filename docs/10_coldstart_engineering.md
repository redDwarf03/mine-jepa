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

## The gate (what would make this chapter a PASS)

| Test | Baseline | Target |
|------|----------|--------|
| `MineRLTreechop-v0`, N=20, seeded, sticky=0.7 + scan vs. original | 25–50% (variance band) | ≥ 50%, fps ≈ unchanged |
| Cold-start `ObtainIronPickaxeDense`, N=5 (`play_craft.bat`) | **0/5 logs** | ≥ 1 log in ≥ 1 episode |

If the first cold-start log drops, the already-validated craft loop
(`MineRLObtainTest-v0`, 100% given wood) takes over — that is the milestone.
Both numbers get reported with variance, per the Phase 4 lesson: no claiming the
best run.

---

## The lesson this chapter adds

> **Before asking "how does the agent learn X?", ask "can the agent even express X?"**
> The searching behaviour was impossible to sample and the lost-state was measurable
> all along. Curiosity (chapter 09) failed partly because it was aimed at a problem
> that is mostly *representational*: the planner's hypothesis space did not contain
> the solution. Fix the hypothesis space first; spend learning on what remains.

*Previous: `docs/09_curiosity_coldstart.md`. Next (planned): online RND —
novelty that decays with experience, trained during play, per chapter 09's diagnosis.*

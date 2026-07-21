---
title: "Trying 512 futures in its head before pressing a button"
slug: "04-planning-in-imagination"
lang: "en"
order: 4
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model"]
source_docs: ["docs/05_planning.md", "CLAUDE.md#Phase 3 — gates validated"]
---

::: beginner

## One last piece is missing

Let's recap where we are. Chapter 1 gave the model an encoder that knows how to summarize an image into a short list of numbers (an **embedding**) without cheating (Chapter 2). Chapter 3 gave it a **world model**: a function that knows how to imagine "if I take this action, what will the next embedding look like?", beating the lazy "do nothing" solution by a clear margin.

However, summarizing images and imagining what comes next still isn't *playing*. One last piece is missing: **how do we choose which key to press, right now, at this exact moment?** That is the subject of this chapter — Phase 3 of the project, tested on Crafter (the lightweight training environment before real Minecraft).

## First, you need to know where you want to go

Before you can pick an action, you must define a **goal** — and that goal, too, is an embedding. The project builds what it calls the **goal embedding** in a very simple way: it takes all images from the game where the character has a good food level (hunger is a strong indicator of survival), passes them through the encoder, and averages all those vectors. That average point — the **centroid** — becomes "what a good state looks like". The agent was never given an explicit "this is a good state" label during training — this goal is constructed *after the fact*, from previously collected data.

## The idea: test lots of imaginary futures, pick the best one

Here comes the fun part. Imagine a "choose your own adventure" book, where on every page you can pick between several actions, and each choice leads to a different continuation of the story. Rather than picking an action at random and seeing what happens, imagine if, in a fraction of a second, you could **flip through 512 different imaginary stories** — each a sequence of 12 choices in a row — without ever turning a single physical page. You look at which of those 512 imaginary endings gets closest to what you want (the goal), and *only then* do you actually make the first choice of the best imagined story. Then you repeat the whole process from your new real-world situation.

This is exactly the algorithm Mine-JEPA uses, called **random-shooting MPC** (Model Predictive Control):

1. Encode the current state into an embedding.
2. Randomly sample 512 different sequences of 12 actions each.
3. For each sequence, unroll the world model step by step — 12 times — to imagine where it leads.
4. Compare each of the 512 imagined destinations to the goal; keep the sequence whose imagined destination gets closest.
5. Execute only the *first* action of that best sequence.
6. Repeat the entire process from the new real state.

## Why restart at every step instead of following the whole plan?

Great question, and the honest answer is: the world model gets increasingly inaccurate across imagined steps — small errors compound over time. If the agent blindly followed a 12-action plan imagined once, it would end up drifting far from reality. By re-planning at every single step starting from what *actually* happened, the agent continuously corrects its course. This is called a **receding horizon**: we only look far ahead to decide what to do *right now*.

## Why 512 stories are enough (and not billions)

With 17 possible actions and 12 steps, the total number of possible sequences is astronomical — about 600 billion. We only test 512. This works because many actions have very similar short-term effects (moving left vs. moving right doesn't lead to wildly different worlds after one step), so 512 random samples cover the important directions well enough. And because all this computation happens in embeddings — small numerical vectors — rather than full images, the computer can imagine 512 × 12 steps in a matter of milliseconds.

## What actually happened

The project evaluated this planner twice, at different points, yielding numbers that closely align without being identical (which happens when re-measuring on a fresh batch of episodes rather than forcing two results to match artificially).

An evaluation over 50 episodes yielded, for the JEPA-MPC agent vs. a random agent: average reward ~2.1 vs ~1.5, ~3.0 vs ~2.4 achievements per episode, and a success rate (at least 1 achievement) close to 100% vs 98% for random play.

Phase 3's official gate report in the project log shows: **100% success rate**, **2.56 achievements per episode vs 2.38** for random (+7.5%), and **+14% reward**. In the agent's very first episode, it achieves 3 distinct achievements: wake up, collect wood, and place a crafting table — requiring it to locate a tree, approach it, strike it, and place an item. None of this was hand-coded.

## Why it works — and what it doesn't solve

The intuition: the world model learned that "if I do X, the embedding moves in such-and-such direction". When the goal is "a state with high food", the planner naturally strings together actions that move the embedding closer to that goal — finding a plant, approaching it, eating it — without ever being told step-by-step how to do so.

It isn't perfect, however. The world model drifts over long horizons, and the goal is just an average point (a centroid): it describes *what a good state looks like*, not *how to get there*. Two visually distinct states can sometimes lie close together in embedding space without being functionally equivalent — an ambiguity that will resurface later in the project's story.

Even imperfect, this world model guides action far better than random button mashing. And the next logical step — the subject of the next chapter — is to plug this exact same pipeline (encoder, world model, planner) into real Minecraft.

:::

::: expert

## Problem Formulation

At the conclusion of Chapters 1-3, we possess `f_θ : x → s ∈ R^D` (encoder, frozen post-Phase 1) and `g : (s_t, a_t) → ŝ_{t+1}` (world model, Phase 2). A policy is missing. Mine-JEPA chooses **not to learn a parametric policy** (no policy gradient, no value function) — planning is executed via latent space search at every timestep, reusing trained modules with zero additional gradients.

## Goal Embedding Construction

```python
good_frames = frames[food >= 7]          # ~16,000 frames out of 32,000
goal = encoder(good_frames).mean(dim=0)  # [D] — centroid
```

The goal is a post-hoc centroid in latent space, constructed from a subset of the offline collection dataset filtered on a survival proxy (food ≥ 7), with zero task labels provided during encoder or world model training.

## Random-Shooting MPC

```
For each timestep:
  1. Encode current state → s_t
  2. Sample N=512 random action sequences of horizon length H=12
  3. For each sequence: unroll world model for H steps → ŝ_{t+H}
  4. Score: score_i = -MSE(ŝ_{t+H,i}, s_goal)
  5. Execute the first action of the highest-scoring sequence
  6. Repeat (receding horizon)
```

```python
class LatentMPCPlanner:
    @torch.no_grad()
    def plan(self, s_current, s_goal):
        s = s_current.expand(self.n_candidates, -1).clone()          # [N, D]
        actions = torch.randint(0, self.n_actions,
                                 (self.n_candidates, self.horizon))    # [N, H]
        for h in range(self.horizon):
            s = self.predictor(s, actions[:, h])                      # [N, D]
        scores = -(s - s_goal).pow(2).mean(dim=1)                     # [N]
        return actions[scores.argmax(), 0].item()
```

The entire planner fits in ~10 lines of code — a direct consequence of pushing scene understanding and dynamics into the encoder and predictor during earlier phases; the planner itself is purely a search mechanism.

## Computation Budget Rationale

Sequence space size: `17^12 ≈ 6×10^11`. The candidate budget (N=512) covers a tiny fraction, yet suffices because many actions produce similar short-term effects (directional redundancy in Crafter's action space) — i.i.d. sampling covers major useful directions without requiring exhaustive search. Batched rollout of 512×12 steps runs in <5ms on GPU because each step is a single forward pass of the predictor (~140K parameters) over a batch of 512 — operating entirely in latent space without environment/render calls.

## Receding Horizon

Re-planning at every step from the *actually* observed state, rather than blindly executing the 12-step plan, corrects compounding error accumulated by the world model over long rollouts (cf. Chapter 03 multi-step rollout discussion). This is a structural design choice: robustness stems from high re-planning frequency rather than world model accuracy alone.

## Measured Results — Two Distinct Evaluations

`docs/05_planning.md` reports an evaluation over 50 Crafter episodes:

| Metric | JEPA-MPC Agent | Random Baseline |
|--------|---------------|-----------------|
| Mean Reward | ~2.1 | ~1.5 |
| Achievements/episode | ~3.0 | ~2.4 |
| Success Rate (≥1 achievement) | ~100% | ~98% |
| FPS | ~150 | — |

`CLAUDE.md` (official Phase 3 gate) reports distinct numbers over what appears to be a different episode set: **100% success rate**, **2.56 achievements/episode vs 2.38** for random baseline (+7.5%), and **+14% reward**. Both measurements originate from Phase 3 and point in the same direction (clear improvement across all 3 metrics, near-total success), but do not match digit-for-digit — consistent with two separate evaluation runs. Both are reported as recorded. The agent's first episode strings together 3 achievements (`wake_up`, `collect_wood`, `place_table`) — a sequence requiring locating a tree, approaching, striking, and placing an item, with zero hand-coded task logic.

## Why It Works

The action-conditioned predictor learned the transition function `ŝ_{t+1} = g(s_t, a_t)`. When the goal is a centroid of "good" states, the `-MSE(ŝ_{t+H}, s_goal)` score naturally favors action sequences that pull the latent trajectory toward that region — without any explicit task reward ever injected into encoder or predictor training. Goal-directed behavior emerges entirely from the combination of (world model + search), not reinforcement learning.

## Identified Limitations & Future Directions

**Primary Limitation**: The goal embedding is a centroid — it encodes *what the goal looks like*, not *how to reach it*. Visually distinct states can be near each other in latent space without being functionally equivalent (geometric ambiguity of latent space); this prefigures a broader issue — latent geometry underlying planning is not guaranteed solely by prediction quality — which will resurface in a later project phase on a different dataset.

**Future Extension Noted in Phase 3 Plan**: Cross-Entropy Method (CEM) — iteratively refining the action sampling distribution over multiple iterations, rather than a single i.i.d. shot of 512 sequences — was implemented for continuous actions in `mine_jepa/eb_jepa/planning.py` at Phase 3 time, but not yet wired to Crafter's discrete planner. A discrete version of this idea will return in a later project phase.

## Full Pipeline at This Stage

```
64×64 Frames  →  [Phase 1 Encoder]  →  s_t  [D=128]
                                          │
                                    s_t + a_t
                                          │
                                [Phase 2 World Model]  →  ŝ_{t+1}
                                          │
                            512 imagined sequences
                                          │
                              [Score vs s_goal]
                                          │
                                     best_action
                                          │
                              Crafter.step(action)
                                          │
                                obs_{t+1}  ←─ (loop)
```

Everything takes place in latent space, except at the two endpoints: raw pixel input and final action output.

## References (Verified, from docs/references/index.md)

- Maes, Le Lidec, Scieur, LeCun, Balestriero, LeWorldModel, arXiv:2603.19312 (2026) — ratio convention from Chapter 03 underlying latent rollout reliability.
- Meta FAIR, eb_jepa (github.com/facebookresearch/eb_jepa) — planning logic (`mine_jepa/eb_jepa/planning.py`) reused for CEM extension.

:::

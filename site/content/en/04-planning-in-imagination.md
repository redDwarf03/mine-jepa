---
title: "Trying 512 futures in its head before pressing a button"
slug: "04-planning-in-imagination"
lang: "en"
order: 4
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model"]
source_docs: ["docs/05_planning.md", "CLAUDE.md#Phase 3 — gates validated"]
---

::: beginner

## Still missing one piece

Let's recap where we are. Chapter 1 gave the model an encoder that knows how to summarize an image into a short list of numbers (an **embedding**) without cheating (Chapter 2). Chapter 3 gave it a **world model**: a function that can imagine "if I take this action, what will the next embedding look like?", and clearly beats the lazy solution of copying the current state.

But summarizing images and imagining what happens next is still not *playing*. One final piece is missing: **how to choose which button to press, right now, at this exact moment?**
This is the subject of this chapter — Phase 3 of the project, tested on Crafter (the small training game before the real Minecraft).

## First, you have to know where you want to go

Before you can choose an action, you need to define a **goal** — and this goal, too, is an embedding. The project constructs what it calls the **goal embedding** very simply: it takes all the images from the game where the character has a good food level (hunger is a good proxy for survival), passes them through the encoder, and averages all these vectors together. This average point — the **centroid** — becomes "what a good state looks like". The agent was never given a "this is a good state" label during its training — this goal is constructed *after the fact*, from already collected data.

## The idea: try many imaginary futures, pick the best one

Here is the fun part. Imagine a "choose your own adventure" book, where at each page you can choose between several actions, and each choice leads to a different continuation of the story. Instead of picking an action at random and seeing what happens, imagine you could, in a fraction of a second, **flip through 512 different imaginary stories** — each a sequence of 12 consecutive choices — without ever turning a single real page of the book. You look at which of these 512 imaginary endings most closely resembles what you want (the goal), and *only then* do you actually make the first real choice of the best imagined story. Then you repeat the entire process from your new real situation.

This is exactly the algorithm Mine-JEPA uses, called **Random-Shooting MPC** (Model Predictive Control):

1. Encode the current state into an embedding.
2. Draw 512 different random sequences of 12 actions each.
3. For each sequence, unroll the world model step by step — 12 times — to imagine where it leads.
4. Compare each of the 512 imagined destinations to the goal; keep the sequence whose imagined destination is closest.
5. Actually execute only the *first* action of this best sequence.
6. Start the whole process over from the new real state.

## Why start over at every step instead of following the whole plan?

Good question, and the answer is honest: the world model makes more and more mistakes as imagined steps pile up — small errors accumulate. If the agent blindly followed a 12-action plan imagined just once, it would eventually drift far from reality. By re-planning at every step based on what *actually* happened, the agent continuously corrects its course. This is called a **receding horizon**: we only look far ahead to decide what to do *right now*.

## Why 512 stories are enough (and not billions)

With 17 possible actions and 12 steps, the total number of possible sequences is astronomical — about 600 billion. We only try 512. It works because many actions have very similar short-term effects (stepping left or right doesn't lead to completely different worlds after just one step), so 512 random draws already cover the meaningful directions well enough. And because all this calculation is done in embeddings — small vectors of numbers — rather than real images, the computer can imagine all 512 × 12 steps in a few milliseconds.

## What actually happened

The project measured this planner twice, at different times, yielding numbers that are similar without being identical (which happens when you re-run a measurement on a new batch of episodes rather than artificially making the two results match).

An evaluation over 50 episodes yielded, for the JEPA-MPC agent against an agent playing at random: average reward ~2.1 vs ~1.5, ~3.0 vs ~2.4 "achievements" (game objectives completed) per episode, and a success rate (at least one achievement) close to 100% vs 98% for the random agent.

The official Phase 3 gate, reported in the project log, yields: **100% success rate**, **2.56 achievements per episode against 2.38** for the random baseline (+7.5%), and a **+14%** reward increase. The agent's very first episode scored 3 different achievements: waking up, collecting wood, and placing a table — which requires finding a tree, approaching it, hitting it, and then placing an object. None of this was hand-coded.

## Why it works — and what it does not solve

The intuition: the world model learned that "if I do X, the embedding moves in this direction". When the goal is "a state with lots of food", the planner naturally strings together actions that move the embedding closer to that goal — find a plant, approach it, eat it — without ever being told how to do that step-by-step.

It is not perfect, though. The world model makes mistakes over long horizons, and the goal is just an average point (the centroid): it says *what* a good state looks like, not *how to get there*. Two visually very different states can sometimes be "close" in the embedding space without actually meaning the same thing functionally — an ambiguity that will resurface later in the project's story.

But even imperfect, this world model guides far better than a player pressing buttons at random. And the next logical step — the subject of the following chapter — is to plug this exact same pipeline (encoder, world model, planner) into the real Minecraft.

:::

::: expert

## The problem and its formalization

At the end of Chapters 1-3, we have `f_θ : x → s ∈ R^D` (encoder, frozen since Phase 1) and `g : (s_t, a_t) → ŝ_{t+1}` (world model, Phase 2). A policy is missing. Mine-JEPA chooses **not to learn a parametric policy** (no policy gradient, no value function network) — planning is done directly via search in latent space, at every time step, reusing the already trained modules without any additional gradients.

## Goal embedding construction

```python
good_frames = frames[food >= 7]          # ~16,000 frames out of 32,000
goal = encoder(good_frames).mean(dim=0)  # [D] — centroid
```

The goal is a post-hoc centroid in latent space, constructed from a subset of the collection dataset filtered on a survival proxy (food ≥ 7), with no task labels provided during the training of either the encoder or the world model.

## Random-shooting MPC

```
For each time step:
  1. Encode current state  →  s_t
  2. Draw N=512 random action sequences of length H=12
  3. For each sequence: unroll world model for H steps → ŝ_{t+H}
  4. Score: score_i = -MSE(ŝ_{t+H,i}, s_goal)
  5. Execute the first action of the sequence with the best score
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

The entire planner fits in about ten lines of code — a direct corollary of pushing all the heavy lifting (scene understanding, dynamics) into the encoder and predictor during previous phases; the planner itself is merely a search algorithm.

## Compute budget justification

Sequence space: `17^12 ≈ 6×10^11`. The candidate budget (N=512) covers only a tiny fraction of this, but suffices because many actions have similar short-term effects (directional redundancy in Crafter's action space) — i.i.d. sampling adequately covers the broad useful directions without needing exhaustive search. The batched rollout of 512×12 steps runs in < 5 ms on GPU, since each step is just a forward pass of the small predictor (~140K parameters) on a batch of 512 — everything happens in latent space, without ever touching the rendering engine or the real environment.

## Receding horizon

Re-planning at every step from the *actually* observed state, rather than blindly executing the 12-step plan, corrects the compounding error accumulated by the world model on long rollouts (cf. Chapter 03, section on k-step error accumulation). This is a structural choice: robustness comes from the re-planning frequency, not from the accuracy of the world model alone.

## Measured results — two distinct evaluations

`docs/05_planning.md` reports an evaluation over 50 Crafter episodes:

| Metric | JEPA-MPC Agent | Random Baseline |
|--------|----------------|-----------------|
| Mean reward | ~2.1 | ~1.5 |
| Achievements/episode | ~3.0 | ~2.4 |
| Success rate (≥1 achievement) | ~100% | ~98% |
| FPS | ~150 | — |

`CLAUDE.md` (the official Phase 3 gate) reports distinct numbers on what appears to be a different batch of episodes: **100% success rate**, **2.56 achievements/episode against 2.38** for the random baseline (+7.5%), and **+14% reward**. Both measurements stem from the same Phase 3 and point in the same direction (clear improvement across all three metrics, near-total success), but do not match digit-for-digit — consistent with being two distinct evaluation runs rather than the same measurement reported twice. Both are reported here as-is rather than forced to agree. The very first episode strings together 3 achievements (`wake_up`, `collect_wood`, `place_table`) — a sequence requiring locating a tree, approaching it, hitting it, and placing an object, with zero hand-coded task logic.

## Why it works

The action-conditioned predictor learned the transition function `ŝ_{t+1} = g(s_t, a_t)`. When the goal is a centroid of "good" states, the score `-MSE(ŝ_{t+H}, s_goal)` naturally favors action sequences that make the latent trajectory converge toward that region — without any explicit task reward ever being injected into the encoder or predictor training. Goal-oriented behavior emerges entirely from the combination of (world model + search), not from a reinforcement learning objective.

## Identified limits and project avenues

**Main limitation**: the goal embedding is a centroid — it encodes *what* the goal looks like, not *how* to reach it. Two visually distinct states can be close in latent space without being functionally equivalent (geometric ambiguity of the latent space); this foreshadows a broader issue — the latent geometry upon which planning relies is not guaranteed by prediction quality alone — which will resurface in a later phase of the project, on a different dataset.

**Future extension noted in Phase 3 plan**: CEM (Cross-Entropy Method) — iteratively refining the action sampling distribution over several iterations, rather than a single shot of 512 i.i.d. sequences — already implemented for continuous actions in `mine_jepa/eb_jepa/planning.py` at Phase 3 time, but not yet plugged into Crafter's discrete planner. A discrete version of this idea returns in a later project phase.

## The full pipeline at this stage

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

Everything happens in latent space, except at the two endpoints: the pixel input and the final action.

## References (verified, from docs/references/index.md)

- Maes, Le Lidec, Scieur, LeCun, Balestriero, LeWorldModel, arXiv:2603.19312 (2026) — the `ratio = val_pred/val_copy` convention from Chapter 03, the foundation making the latent rollout exploited here reliable.
- Meta FAIR, eb_jepa (github.com/facebookresearch/eb_jepa) — planning logic (`mine_jepa/eb_jepa/planning.py`) reused for the CEM extension mentioned at chapter's end.

:::

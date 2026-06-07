# Planning in latent space

> This doc explains how Mine-JEPA uses its world model to **plan actions**
> without ever interacting with the real environment during planning.
> This is the moment where the two previous phases assemble into an acting agent.

---

## The planning problem

The encoder (Phase 1) knows how to represent a game state in latent `s_t`.
The world model (Phase 2) knows how to predict `ŝ_{t+1} = f(s_t, a_t)`.

One piece is missing: **how to choose which action to execute**?

JEPA's answer: plan in latent space. We don't need to generate images or execute
thousands of actions in the real game. We can *imagine* consequences in latent space,
compare to the goal, and choose the best plan.

---

## The goal embedding

Before planning, we need to define **what we want to reach**.

In Mine-JEPA, the goal is a **latent embedding** `s_goal` — the centroid of latent
states of "desirable" frames drawn from the dataset:

```python
# Frames where food >= 7 (player has eaten recently = good survival state)
good_frames = frames[food >= 7]          # ~16,000 frames out of 32,000
goal = encoder(good_frames).mean(dim=0)  # [D] — centroid
```

The agent tries to bring its latent state toward this centroid. It never saw
labels during training — the goal is built *after the fact* from collected data.

---

## Random-shooting MPC (the algorithm)

Mine-JEPA uses **random-shooting MPC** (Model Predictive Control):

```
For each step:
  1. Encode current state  →  s_t
  2. Sample N=512 random action sequences of length H=12
  3. For each sequence: unroll world model for H steps → ŝ_{t+H}
  4. Score: score_i = -MSE(ŝ_{t+H,i}, s_goal)
  5. Execute the first action of the highest-scoring sequence
  6. Repeat (receding horizon)
```

**Why receding horizon?** The world model accumulates errors on long rollouts.
By re-planning every step from the actually observed state, we correct these errors
and the agent stays robust.

**Why 512 candidates suffice?** With 17 actions and horizon 12, the sequence space
is `17^12 ≈ 600 billion`. But most actions have similar short-term effects (e.g. moving
in any direction). 512 sequences cover the important directions well. On GPU, the
rollout of 512×12 takes < 5 ms.

---

## The planner code

```python
class LatentMPCPlanner:
    @torch.no_grad()
    def plan(self, s_current, s_goal):
        # N copies of current state: [N, D]
        s = s_current.expand(self.n_candidates, -1).clone()

        # N random action sequences: [N, H]
        actions = torch.randint(0, self.n_actions, (self.n_candidates, self.horizon))

        # World model rollout
        for h in range(self.horizon):
            s = self.predictor(s, actions[:, h])  # [N, D]

        # Score and return best first action
        scores = -(s - s_goal).pow(2).mean(dim=1)  # [N]
        return actions[scores.argmax(), 0].item()
```

It all fits in 10 lines. That's the power of JEPA: once the world model is trained,
planning is trivial to implement.

---

## Observed results (real Phase 3 run)

JEPA-MPC agent vs random baseline, 50 episodes in Crafter:

| Metric | JEPA-MPC Agent | Random baseline |
|----------|---------------|-----------------|
| Mean reward | ~2.1 | ~1.5 |
| Achievements/episode | ~3.0 | ~2.4 |
| Success rate (≥1 achievement) | ~100% | ~98% |
| FPS (steps/sec) | ~150 | — |

The first episode of the agent gets 3 achievements: `wake_up`, `collect_wood`,
`place_table`. That's non-trivial — the game requires finding a tree, approaching it,
hitting it, then placing a table.

---

## Why it works (intuition)

The world model was trained to predict the effect of actions on latent states.
Latent states capture game structure (position, nearby objects, health…).

When the planner imagines "if I move right 3 times", the world model predicts a
latent state "slightly shifted to the right". When the goal is "state where food is
high", the planner naturally sequences actions that lead toward food-related states —
find a plant, approach it, eat.

It's not perfect. The world model makes errors on long horizons.
But even an imperfect model guides better than a random policy.

---

## Limitations and next steps

**Main limitation**: the goal embedding is a centroid — it doesn't indicate *how*
to reach the goal, just *what it looks like*. The agent can end up in a latent-close
state that's visually different (latent space ambiguity).

**Phase 4**: plug the same pipeline into MineRL (real Minecraft) — same encoder,
world model and planner, on real 64×64 game frames.

**Future extension**: CEM (Cross-Entropy Method) to refine the action distribution
over several iterations — better performance on long tasks.
Implemented in `mine_jepa/eb_jepa/planning.py` (for continuous actions).

---

## The complete Mine-JEPA loop

```
64×64 Frames  →  [Phase 1 Encoder]  →  s_t  [D=128]
                                          │
                                    s_t + a_t
                                          │
                                [Phase 2 WM]  →  ŝ_{t+1}
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

Everything is in latent space except the two endpoints: the pixel input and the final action.

---

*Next concepts: `docs/06_minecraft_port.md` (Phase 4 — real Minecraft with MineRL),
`docs/01_jepa.md` (global architecture).*

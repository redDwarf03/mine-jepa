---
title: "Teaching the model to imagine what comes next"
slug: "03-the-world-model"
lang: "en"
order: 3
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap"]
source_docs: ["docs/04_world_model.md", "CLAUDE.md#Phase 2 — gates validated"]
---

::: beginner

## Understanding a picture isn't predicting the next one

By the end of Chapters 1 and 2, the encoder had learned to transform a Minecraft/Crafter image into a short list of numbers (an embedding) that truly captures something real about the game — not a "cheat" that collapses to a single constant response, but an honest summary of what is happening on screen.

However, knowing how to *summarize* an image is not the same as knowing how to *play*. To play, the agent must answer a harder question: "if I press this button right now, what will the world look like a split second later?" That is precisely what Phase 2 of this project — the **world model** — is built to answer.

## The flipbook test

Here is a simple image to understand the difference between a model that genuinely predicts and a model that cheats by doing nothing. Imagine a flipbook — that small notebook where you draw a slightly different picture on every page so that flipping through quickly creates a mini movie. There are two very different ways to "fill in" the next page of a flipbook:

- **Trace the current page.** Copy the previous drawing without changing anything. Technically, you produced *a* next page, and if nothing moves much in the scene from one frame to the next, that "prediction" won't even look that wrong.
- **Genuinely draw what happens next.** If the character strikes a tree with a wooden stick, draw the tree with a missing chunk, or wood chips flying off. That requires a true understanding of "what happens when you do X".

A world model that lazily copies the previous image's embedding does the flipbook equivalent of endlessly tracing the same page. It can even get a *decent* score on a naive test, because in many games, most moments don't change drastically from one frame to the next. The real test must be: **does it do better than simply copying?**

## The test the project actually uses

That is exactly the check used by this project. Two numbers are compared:

- **copy_loss**: how wrong you would be if you assumed "nothing changes" — that is, using the current embedding as your guess for the next one.
- **pred_loss**: how wrong the trained predictor actually is.

We then look at the **ratio**: `pred_loss / copy_loss`. If this ratio is greater than 1, the model is *worse* than doing nothing — a clear warning sign. If it is significantly below 1, the model beats the "lazy" solution — real proof that it learned cause and effect, not just inertia.

## What actually happened

In the first hundred training steps of Phase 2 (on Crafter, using Phase 1's encoder), the ratio started very high — around **14**, meaning the untrained predictor was fourteen times worse than doing nothing — and then dropped rapidly as training progressed, down to about **1.66** at step 100. This is expected: at the very beginning, the predictor hasn't learned anything yet, so guessing randomly is naturally worse than guessing that nothing changes.

After full training (30 epochs), the project measured **val_pred = 0.033** against **val_copy = 0.086** — a ratio of **0.38**. This means the trained predictor's error represents well under half the error of the "do nothing" baseline: genuine proof that the model learned real cause-and-effect structure in the game (what happens when you hit a tool, walk into a wall, etc.), rather than just repeating the previous image.

The project didn't stop at a single number: it also verified that this held across multiple imagined steps in a row (imagining step 2 from imagined step 1, step 3 from imagined step 2, and so on, without ever looking at a real image in between). Over 10 such steps, the trajectory imagined by the predictor stayed below the "do nothing" baseline every single time (10 out of 10). Error grows slightly the further into the future you imagine — which is expected as small errors compound — but the key check is that it does not *explode*, nor does it drop to a suspicious zero (which would mean the predictor learned to completely ignore the action).

## Why this matters for playing the game

Once a model knows how to reliably imagine "if I do X, the world will look like this", it can try several different plans *in its head*, compare which imagined result gets closest to what it wants, and only then take real action — rather than blindly reacting. That is the seed of planning, which is where the project goes next.

:::

::: expert

## Objective

Phase 2 trains an action-conditioned predictor `g(s_t, a_t) → ŝ_{t+1}` on top of Phase 1's **frozen** encoder (`s_t = f_θ(x_t)`, weights fixed post-Phase 1). Only the predictor receives gradients; the encoder representation is treated as a stable target space, justified directly by the anti-collapse guarantees established in Chapter 02 — a target space already possessing healthy non-degenerate variance (~1.15 measured at Phase 1 probe time) is intrinsically resistant to collapse, as VICReg is not even re-applied here.

## Architecture

```python
class ActionConditionedPredictor(nn.Module):
    def __init__(self, embed_dim=128, n_actions=17, action_dim=32):
        self.action_embed = nn.Embedding(n_actions, action_dim)
        self.net = nn.Sequential(
            nn.Linear(embed_dim + action_dim, 256), nn.GELU(),
            nn.Linear(256, 256), nn.GELU(),
            nn.Linear(256, embed_dim),
        )
```

~140K parameters — deliberately small compared to Phase 1's 688K parameter encoder (`docs/04_world_model.md`). Design intent: representational capacity to "understand the scene" should reside in the encoder; the predictor's role is strictly confined to transition dynamics. An oversized predictor risks compensating for encoder flaws rather than exposing them, blurring the boundary between Phase 1 and Phase 2 gates. GELU is used over ReLU for smoother gradients on zero-centered embedding inputs (no hard zero zone blocking backprop for small negative activations).

## Loss

```
L = MSE(ŝ_{t+1}, s_{t+1}) = ‖ g(s_t, a_t) - f_θ(x_{t+1}) ‖²
```

Pure latent MSE against frozen encoder output on the actual next frame — zero VICReg term here (contrasting Phase 1's composite objective in Chapter 02); anti-collapse guarantees from Phase 1 are inherited, not re-derived.

## Baseline and Gate Metric

```
copy_loss = MSE(s_t, s_{t+1})        # "nothing changes" baseline
pred_loss = MSE(ŝ_{t+1}, s_{t+1})    # trained predictor error
ratio     = pred_loss / copy_loss
```

`ratio > 1` → predictor underperforms constant-state baseline (gate fail).
`ratio < 1` → predictor beats copy-last baseline (gate pass). This ratio metric (`val_pred/val_copy`) follows the exact construction introduced by LeWorldModel (Maes, Le Lidec, Scieur, LeCun, Balestriero, arXiv:2603.19312, 2026) — Mine-JEPA's Phase 2 gate design directly adopts this evaluation convention, and later uses an empirical "sweet spot" ratio (~0.93 from Phase 4 ablation) warning against the assumption that lower ratio is monotonically superior — a nuance flagged here as a forward reference rather than back-applied to Phase 2's Crafter result.

## Measured Training Trajectory (First 100 steps, Crafter, frozen Phase 1 encoder val_loss=0.080)

| Step | pred_loss | copy_loss | ratio |
|-----:|----------:|----------:|------:|
| 20 | 1.0193 | 0.0710 | 14.36 |
| 40 | 0.5721 | 0.0905 | 6.32 |
| 60 | 0.2819 | 0.1015 | 2.78 |
| 80 | 0.1877 | 0.1026 | 1.83 |
| 100 | 0.1338 | 0.0806 | 1.66 |

The steep drop early in training (14.4x → 1.66x in 100 steps) reflects the predictor quickly mastering the dominant transition mode (near-identity — agent moves very little per frame in Crafter), consistent with `copy_loss` itself being a strong baseline early on.

## Phase 2 Gate Result (CLAUDE.md, after full 30-epoch run)

`val_pred=0.033` vs `val_copy=0.086` → **ratio=0.38** (0.033/0.086 = 0.384, rounded to 0.38 — exact value reported in `CLAUDE.md`). This same gate lists on a separate line "1-step latent error < baseline: ratio 0.367" — a second number from a distinct measurement (`eval_wm.py` 1-step check), not a rephrasing of the first; both are explicitly listed in `CLAUDE.md` and reported here as-is. This gate passes the `ratio < 1.0` threshold by a wide margin. Multi-step rollout gate (`scripts/eval_wm.py`) further confirmed **10/10** k (k=1..10) with rollout error remaining strictly below baseline at every horizon step:

```
s_1 = g(s_0, a_0); s_2 = g(s_1, a_1); ...; s_k = g(s_{k-1}, a_{k-1})
```

Error compounding with increasing k is expected and not inherently a failure signature; the failure signatures monitored by the project are either divergence (error exploding faster than baseline) or predictor collapse to action invariance (learning to ignore `a_t`, resulting in `ŝ_{t+1}` remaining nearly identical for different actions from the same `s_t`) — the 10/10 result below baseline is incompatible with either.

## Note on Downstream Interpretation of Ratio

This chapter reports the Phase 2 gate as executed: ratio=0.38 cleanly passes gate criteria. A subsequent project phase (Phase 4, MineRL ablation) revealed that lower ratios are not monotonically superior for downstream planning success — an overtrained world model with a lower ratio (~0.88) performed worse than a model with a higher ratio (~0.93). This finding is specific to MineRL action-conditioned world models and Phase 4 planning setup; it is noted here as a forward pointer, not back-applied to Phase 2's Crafter result.

## References (Verified, from docs/references/index.md)

- Maes, Le Lidec, Scieur, LeCun, Balestriero, LeWorldModel, arXiv:2603.19312 (2026) — origin of `ratio = val_pred/val_copy` evaluation convention adopted here.

:::

---
title: "What is JEPA, and why train a program to play Minecraft with it?"
slug: "01-what-is-jepa"
lang: "en"
order: 1
prerequisites: []
source_docs: ["docs/01_jepa.md", "docs/references/index.md", "CLAUDE.md#What this project is (1 line)"]
---

::: beginner

## The project, in one sentence

Mine-JEPA is an attempt to teach a program to play Minecraft simply by looking at images on the screen — no hand-written rules, no pre-cooked solutions, no "if you see a tree, press this button". Just raw pixels and a controller. This chapter is about the idea that makes it possible: an architecture called **JEPA**.

## Why not simply predict the next pixel?

The most intuitive idea would be this: show the program thousands of Minecraft images, and teach it to guess what the next image will look like, pixel by pixel. If it gets good at that, it must understand the game, right?

There's a catch. Imagine trying to predict, pixel by pixel, a video of someone walking through a forest. You would have to guess the exact color of every leaf, the precise texture of the dirt path, the exact shade of the sky. Almost all of that is visual noise — it doesn't change *the next decision you need to make*. A model forced to obsess over every single pixel spends most of its budget on the wrong problem, like a student trying to memorize a textbook word-for-word instead of understanding what it means.

Think about how *you* actually play a game. You don't think "the pixel at coordinate (340, 220) is brown". You think "there is a tree in front of me, if I hit it, it will break and give me wood". That is a much smaller, and much more useful, piece of information than the full image.

## The core idea: compress first, predict second

JEPA stands for **Joint-Embedding Predictive Architecture**. It was proposed by Yann LeCun (a well-known AI researcher at Meta) in 2022, as part of a broader vision of how machines could learn to understand the world. The idea hinges on one key principle: instead of predicting the future in *pixels*, we predict it in a **compressed summary** of the image — what we call an **embedding** (or latent representation). Think of an embedding as a short list of numbers capturing "what matters" in a scene, much like a one-sentence summary captures the plot of a book without repeating every word.

Here is how it works:

1. A **context encoder** looks at the current image and compresses it into a compact vector — "here is what I currently understand about the situation".
2. A **predictor** takes this vector, along with the action the agent is about to perform (move forward, strike with tool, etc.), and predicts what the *next* compact vector will look like.
3. A second encoder looks at the *actual* next image, and produces the corresponding true compact vector.
4. The model is trained so that its prediction gets as close as possible to this true vector.

Crucial detail: at no point in this loop does the model try to redraw the image. It compares "the compressed summary of my guess" with "the compressed summary of what really happened". That's the whole trick.

## A concrete analogy to remember it by

Imagine playing chess by text message with a friend. Instead of describing every detail of the board, you agree to simply say things like "knight takes pawn, check". You don't waste words describing the wood grain of the pieces. You only keep the information that changes what happens next. JEPA tries to do exactly that: let a neural network invent its own version of this shorthand — automatically, just by watching images — and then use that shorthand to predict "what happens if I do this".

## What this brings to the project

Once a model knows how to predict "what my compact summary of the world will look like if I take this action", it can start to *imagine* — try an action in its head, check if the imagined result gets closer to what it wants, and only then actually press the button. This is the seed of planning, and it's why Mine-JEPA is built around JEPA rather than a model that tries to generate full future images.

## Why not use a huge off-the-shelf AI model?

You might wonder: don't giant AI models (the ones behind chatbots or image generators) already understand video? In a way — but the largest ones are massive (hundreds of millions to billions of parameters), designed to describe or generate video, not react in real time, and were never trained specifically on Minecraft. This project deliberately uses a **lightweight** JEPA model — small enough to train on a single consumer GPU — built and trained *directly on the game it needs to understand*. It won't write a poem about Minecraft, but it can react to an image in a fraction of a second, which is exactly what playing a real-time game requires.

:::

::: expert

## Problem Statement

The backbone of Mine-JEPA is a lightweight JEPA (~15M parameters) trained end-to-end on pixel Crafter/MineRL data, chosen explicitly over a heavy frozen video foundation model (see rationale for rejection below). The architecture follows Yann LeCun's JEPA proposal (*A Path Towards Autonomous Machine Intelligence*, openreview BZ5a1r-kVsf, 2022) and inherits its encoder lineage from I-JEPA (Assran et al., arXiv:2301.08243, CVPR 2023).

## Why Not Generative Pixel-Space Prediction

A generative model (autoencoder, diffusion, autoregressive pixel model) is trained to minimize a reconstruction or likelihood loss over the *entire* observation — every pixel carries equal weight in the objective. On a POV Minecraft/Crafter view, this means the loss is dominated by high-entropy, task-irrelevant signal (foliage texture, sky gradient, lighting noise) rather than the low-dimensional task-relevant structure (agent posture, nearby object identity, inventory state). This is precisely the generic failure mode JEPA is designed against: features useful for control are generally *low variance, high influence* in the pixel signal, not high variance — see Littwin et al. (arXiv:2407.03475) for the theoretical argument showing that JEPA's implicit bias favors precisely these high-influence predictive features over the high-variance noisy features pursued by reconstruction objectives (e.g. MAE).

## Architecture

Three components, all operating on a per-frame latent `s ∈ R^D` (D=128 in Mine-JEPA's Phase 1 Crafter encoder):

```
x_t  ──→ [Context Encoder f_θ]  ──→ s_x
                                       │
                              [Predictor g] + a_t  ──→ ŝ_{t+1}
                                                             │
x_{t+1} ──→ [Target Encoder f_θ̄]  ──→ s_y                  │
                                       │                     │
                            L = ‖ŝ_{t+1} - s_y‖²  ←──────────┘
```

- **Context encoder** `f_θ`: ResNet5 (~40K parameters) taking a 64×64 RGB image as input (`docs/01_jepa.md`).
- **Target encoder** `f_θ̄`: Architecturally identical, but its weights are an Exponential Moving Average (EMA) of `f_θ` (`θ̄_{t+1} ← 0.99·θ̄_t + 0.01·θ_t`), with gradients blocked (`@torch.no_grad()` in update step). This mechanism prevents both encoders from co-collapsing into a trivial constant — see Chapter 02 for full anti-collapse details.
- **Predictor**: A small MLP (or lightweight convolution) taking `s_x` and a discrete action embedding (`Embedding(n_actions, 32)` over Crafter's 17-action space), producing `ŝ_{t+1}`.

The loss is strictly L2 in latent space: `L_JEPA = ‖ŝ_{t+1} - s_y‖²`. There is zero pixel reconstruction term in the objective — this structural distinction defines JEPA against generative/autoencoding world models, not a mere training detail.

## Action Conditioning and Latent Rollouts

Because the predictor is conditioned on `a_t`, it encodes transition dynamics rather than marginal next-state statistics: `ŝ_{t+1} = g(s_t, a_t)`. This enables full latent unrolling without calling the render engine or environment:

```
s_1 = g(s_0, a_0);  s_2 = g(s_1, a_1); ...; s_k = g(s_{k-1}, a_{k-1})
```

This "latent imagination" is the mechanism leveraged by the planner (upcoming chapter on world model and planning) via MPC/CEM: sample candidate action sequences, unroll them in latent space, score them against a goal embedding, execute the first action of the best sequence, replan.

## Architectural Choices & Rejected Alternative

The project explicitly rejected frozen V-JEPA 2 (Assran et al., arXiv:2506.09985, 30 authors, 2025) as the primary backbone: a 600M parameter ViT-H trained on ~1M hours of natural video is out-of-distribution (OOD) on stylized Minecraft POV, and is neither clonable nor end-to-end fine-tunable on a consumer GPU with 8GB VRAM. It remains available solely for secondary comparison via `torch.hub`, never as a planning substrate. The chosen backbone design — lightweight, trained directly on target domain, action-conditioned — closely follows LeWorldModel (Maes, Le Lidec, Scieur, LeCun, Balestriero, arXiv:2603.19312, 2026): ~15M parameters, single GPU, and a two-term objective (next-embedding prediction + variance/covariance regularizer) mirrored in Mine-JEPA's loss formulation (see Chapter 02).

## Why This Over an LLM/VLM Policy for This Task

JEPA and language/vision-language models solve distinct problems and are not competing substitutes here: an LLM-driven agent ("computer use") reasons well over high-level instructions, but at ~1–10s per decision is far too slow for reactive control, and its "understanding" of scene dynamics goes through textual description rather than direct pixel-conditioned prediction. Mine-JEPA's JEPA backbone runs in under 100ms per action and predicts visual dynamics directly from pixels, at the cost of lacking high-level reasoning. The project framing: an LLM would specify *what* to do (high level), JEPA executes *how* to do it — this project builds and validates only the latter.

## References (Verified, from docs/references/index.md)

- LeCun, *A Path Towards Autonomous Machine Intelligence*, openreview BZ5a1r-kVsf (2022) — original JEPA proposal.
- Assran et al., I-JEPA, arXiv:2301.08243 (CVPR 2023) — encoder lineage.
- Maes, Le Lidec, Scieur, LeCun, Balestriero, LeWorldModel, arXiv:2603.19312 (2026) — closest published architecture; source of `ratio = val_pred/val_copy` gate used from Chapter 03.
- Assran et al., V-JEPA 2, arXiv:2506.09985 (2025) — rejected as primary backbone, comparison only.
- Littwin et al., arXiv:2407.03475 (2024) — theoretical foundation on why JEPA favors predictive over high-variance noisy features.

:::

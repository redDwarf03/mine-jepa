---
title: "The shortcut the model always tries to find (and how we prevent it)"
slug: "02-the-collapse-trap"
lang: "en"
order: 2
prerequisites: ["01-what-is-jepa"]
source_docs: ["docs/03_representation_collapse.md", "CLAUDE.md#Risk #1: COLLAPSE"]
---

::: beginner

## A model that "wins" without learning anything

In Chapter 1, we set up JEPA's training game: look at an image, compress it into a short list of numbers (an **embedding**), predict what the *next* image's embedding will look like, and get scored on how accurate that prediction is. The lower the error, the better things are supposed to be.

Except there is a way to get a perfect score at this game without learning anything at all about Minecraft.

Imagine a student who notices that their grader never checks if an answer is *correct*, but only if it *matches whatever they wrote last time*. That student could simply write the exact same word — say, "banana" — for every question, on every test, forever. If "banana" is judged to be an acceptable prediction of itself, that student gets a perfect score every single time without understanding a word of the subjects being tested.

That is exactly the trap JEPA can fall into. It is called **collapse**: the encoder learns to flatten *all* images — regardless of what is actually happening in the game — into the exact same output vector, say `[0, 0, 0, ..., 0]`. If every image produces the same vector, predicting "the next image's vector" becomes trivial: it is just that same constant vector again. The error between prediction and target drops to zero. The training loss curve looks gorgeous. And the model has learned strictly zero about Minecraft — it cannot distinguish a tree from a zombie or a clear sky, because it never looked at what makes those images different from each other.

This is a serious issue because a collapsed model is *actively misleading* if you only monitor the loss curve. A loss near zero looks like success. The only way to detect the trap is to check something else: are the model's outputs actually *different* for genuinely different inputs?

## How we detect it

The fix is to constantly measure how spread out the model's embeddings are across a batch of different images — a quantity the project calls `batch_var` (batch variance). If images that look very different in the game (standing in a desert vs. standing in a forest) produce very different embeddings, `batch_var` stays reasonably high. If the model has fallen into the "always answer banana" shortcut, `batch_var` collapses to zero — every image gets mapped to (nearly) the same point, so there is nothing left to spread out.

## Two safeguards, not just monitoring

Merely monitoring the number isn't enough: we also want to make collapse hard to reach in the first place. Mine-JEPA combines two countermeasures:

**1. A lagging target evaluation (EMA).** Rather than having an encoder grade itself against a copy of itself updating at the exact same speed (making it very easy for both copies to slide together toward the same lazy answer), the "target" encoder — the one producing the answer key — only moves in tiny steps, using a weighted average called an **EMA** (Exponential Moving Average). It's like separating a student from the answer key with a delay in time: the answer key updates slightly after the student, preventing the student from copying the same shortcut into both simultaneously.

**2. An explicit "spread out" penalty (VICReg).** In addition to the EMA, the training recipe adds a direct penalty (from a technique called VICReg) that punishes the model whenever its embeddings for different images start clustering too close together. It's a rule that effectively says: "you are not allowed to give the same answer for everything, even if doing so would give you good grades in the short term."

## What actually happened during this project's first training run

This isn't a theoretical risk the team worried about in the abstract — it was measured directly during Phase 1 training (30 epochs, on an RTX 5060 Ti, over 32,676 Crafter game transitions). At verification time, `batch_var` was **1.13** — well above the documented alert threshold (`batch_var < 1e-4`) — and final validation loss was **0.080**. In other words: loss went down *and* embeddings stayed spread out. That combination is what "the model is actually learning something, not cheating" looks like in numbers.

The team didn't rely on numbers alone, either: an independent test followed (a linear probe: can a very simple classifier read the agent's health directly off the frozen embeddings, without adding anything else?). Result: **90.8%**, compared to a baseline of **86.9%** — about **3.9 percentage points** better. That is independent proof that the embeddings contain genuinely useful information about the game state, not just healthy-looking variance.

:::

::: expert

## Collapse: Mechanism and Susceptibility of Joint-Embedding Architectures

Reconstruction-based self-supervised methods (autoencoders, BERT/MAE masked pixel/token prediction) are structurally immune to representational collapse: one cannot reconstruct an image from a constant code, so the loss itself forbids the trivial solution. JEPA has no such built-in protection — context encoder and predictor are jointly optimized in latent space with no anchor to raw pixels in the loss, freeing the pair to co-adapt to any solution that minimizes `‖ŝ_{t+1} - s_y‖²`, including the global minimum at `s_x = s_y = ŝ_{t+1} = const`. Contrastive methods (SimCLR) avoid this via explicit negative pairs (a repulsive term pushing different inputs apart), which JEPA deliberately omits — the trade-off accepted by this project: no negatives, no need for massive batch sizes, but higher collapse risk that must be handled architecturally.

## Monitored Signal

`batch_var = embeddings.var(dim=0).mean()` — mean variance per dimension across a training batch. This project documents two distinct thresholds:

- `docs/03_representation_collapse.md` sets the **operational alert threshold** at `batch_var < 1e-4` — this is the threshold the Phase 1 gate actually uses (requiring `> 1e-4` to pass, measured at 1.178 at probe time, per `CLAUDE.md`).
- The "Risk #1: COLLAPSE" section of `CLAUDE.md` (the general project architecture rule) sets a more extreme alarm, "`batch_var < 1e-6`: collapse in progress", as a signal of collapse already heavily underway rather than a gate pass threshold.

This chapter treats `1e-4` as the operational Phase 1 gate threshold, and `1e-6` as the alarm floor beyond which collapse is a fact rather than a hypothesis. This check is run every epoch as a permanent gate, not a one-off check.

## Countermeasure 1 — Target Encoder EMA

```
θ̄_{t+1} ← 0.99 · θ̄_t + 0.01 · θ_t
```

`θ` (context encoder) receives gradients normally; `θ̄` (target encoder) updates solely via this EMA, with `@torch.no_grad()` enforced during the update step — zero gradient path exists from loss to `θ̄` directly. This decouples the rate of change of the prediction target from the rate of change of predictor inputs, eliminating the easiest collapse path: if both encoders moved in lockstep under gradient descent, the pair could co-slide toward a constant with zero loss and zero gradient signal to escape. With a slowly drifting target, the predictor cannot "settle" on a fixed trivial solution because the target itself keeps moving — momentum self-distillation, structurally identical to the target network mechanism in DINO/BYOL, used here for the same anti-collapse purpose.

## Countermeasure 2 — VICReg (Bardes, Ponce, LeCun, arXiv:2105.04906, ICLR 2022)

Two explicit regularization terms added to the objective, building on the recipe documented locally in `ES2025-19.pdf` (ESANN 2025):

**Variance Term** (direct anti-collapse):
```
L_std = mean( max(0, 1 - std(s_x, dim=0)) )
```
Zero when every embedding dimension has std ≥ 1; increases as variance drops (collapse underway), providing a gradient signal that actively opposes collapse rather than merely detecting it after the fact.

**Covariance Term** (anti-redundancy):
```
L_cov = mean( off_diagonal( cov(s_x)^2 ) )
```
Penalizes correlation between embedding dimensions — without it, a model could satisfy the variance term while having every dimension encode the exact same 1D signal, which is functionally equivalent to collapse even with a nominally high `batch_var`.

## Total Phase 1 Objective in Mine-JEPA

```
L = L_JEPA + λ_std · L_std + λ_cov · L_cov
    λ_std = 1.0, λ_cov = 0.04   (configs/train_encoder.yaml)
```

`λ_std` is set an order of magnitude higher than `λ_cov` because variance collapse is the existential risk; decorrelation is a secondary refinement.

## Measured Training Dynamics (Real Run, Crafter, 32,676 transitions, RTX 5060 Ti)

| Epoch | total | jepa | std_loss | cov_loss | batch_var | val_loss |
|------:|------:|-----:|---------:|---------:|----------:|---------:|
| 1 | 0.190 | 0.134 | 0.040 | 0.434 | 1.057 | 0.250 |
| 2 | 0.119 | 0.101 | 0.001 | 0.405 | 1.124 | 0.191 |
| 3 | 0.106 | 0.091 | 0.001 | 0.347 | 1.128 | 0.122 |
| 4 | 0.094 | 0.081 | 0.001 | 0.303 | 1.133 | 0.114 |
| 5 | 0.084 | 0.073 | 0.001 | 0.271 | 1.150 | 0.098 |

Takeaway: `batch_var` *increases* (1.057→1.150) over training rather than decaying toward zero — the opposite of a collapse signature. `std_loss` saturates near its floor (~0.001) by epoch 2, indicating the variance constraint is satisfied early at low cost, leaving the JEPA prediction term (which keeps dropping, 0.134→0.073) as the primary binding objective. `cov_loss` decreases monotonically (0.434→0.271), consistent with progressive decorrelation across dimensions.

Phase 1 gate result reported in `CLAUDE.md` after the full 30-epoch run: **val_loss=0.080, batch_var=1.13** — well above the alert threshold of 1e-4. `CLAUDE.md` also notes a separate reading, `batch_var` = 1.178 "at probe time", slightly different from the final 1.13 — both trace the same run at different measurement points, consistent with `batch_var` continuing to fluctuate slightly during training rather than converging to a single frozen value.

Independent corroboration via `scripts/probe.py`: a linear probe trained on frozen embeddings predicts agent health at **90.8%**, against an **86.9%** baseline — a **+3.9 percentage point** gain (90.8 − 86.9; `CLAUDE.md` rounds this gap to "+3.8%", a slight rounding variance against the direct subtraction of the two percentages it reports — both measured values, 90.8% and 86.9%, are fully verified). This proves the preserved variance represents *task-relevant signal*, not random non-zero variance.

## The Failure Signature Being Guarded Against

For contrast (not executed as a documented ablation experiment, but presented as the expected pattern without EMA/VICReg): `batch_var` decaying from ~1.05 down toward `1e-9` across training epochs while JEPA loss simultaneously drops toward zero — the diagnostic trap being that the loss curve alone looks like success. This is why `batch_var` is tracked as a permanent mandatory diagnostic (per Risk #1 instructions in `CLAUDE.md`), rather than an occasional debugging check.

## References (Verified, from docs/references/index.md)

- Bardes, Ponce, LeCun, VICReg, arXiv:2105.04906 (ICLR 2022) — variance/covariance regularization used directly in `mine_jepa/ebwm/losses.py`.
- ES2025-19 (ESANN 2025, local PDF) — anti-collapse recipe adapted in `docs/03_representation_collapse.md`.
- Sobal et al., arXiv:2211.10831 (2022) — tendency of JEPAs to latch onto slow task-irrelevant features; useful context for why variance alone does not guarantee useful representations (motivating the covariance term and subsequent masking choices, unresolved by VICReg alone).

:::

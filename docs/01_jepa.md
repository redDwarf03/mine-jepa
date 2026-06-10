# What is JEPA?

> This doc explains the architecture at the heart of Mine-JEPA. No prerequisites —
> if you know what a neural network is, you can read this.

---

## The problem JEPA solves

Imagine you want to teach a model to understand the dynamics of a video game
(Minecraft, Crafter…) without any labels. The classic solution? The **auto-encoder**:
compress the image, reconstruct it, and if the reconstruction is good, the model
has "understood" something.

**Problem**: an auto-encoder values *every pixel* equally. It will struggle to
perfectly reconstruct the ground texture, the sky color, the background sheep —
details that the agent doesn't need to understand to act.

A human doesn't think in pixels when playing. They think: *"If I hit this wooden
block, it breaks and falls"*. That's an **abstract** representation, not pixel-level.

JEPA (Joint-Embedding Predictive Architecture) is the architecture proposed by
**Yann LeCun (Meta, 2022)** to learn exactly these abstract representations.

---

## The idea in 3 components

```
Past frames ──→ [ Context Encoder ] ──→ s_x (latent state)
                                               │
                                         [ Predictor ] + action a_t ──→ ŝ_{t+1}
                                                                              │
Future frames ──→ [ Target Encoder  ] ──→ s_y (latent target)              │
                                               │                              │
                                         Loss = ‖ŝ_{t+1} - s_y‖²  ←─────────┘
```

### 1. The Context Encoder (x-encoder)
Encodes what the agent *sees now* (the last 1–3 frames) → latent vector `s_x`.
In Mine-JEPA: a **ResNet5** (~40K params) taking a 64×64 RGB frame.

### 2. The Target Encoder (y-encoder)
Encodes what *will happen* (next frames) → latent vector `s_y`.
**Key**: this network is an **EMA copy** (Exponential Moving Average) of the context encoder.
Its weights are never updated by backprop directly — they follow the context encoder
weights slowly:

```
θ̄_{t+1} ← 0.99 · θ̄_t + 0.01 · θ_t
```

Why EMA? To avoid collapse (see below).

### 3. The Predictor
A small network (MLP or light Conv) that predicts `ŝ_{t+1}` from `s_x` and action `a_t`.
This is the **world model**: it predicts how the world state changes when the agent acts.

**The loss is always in latent space**:
```
L_JEPA = ‖ŝ_{t+1} - s_y‖²
```

Never pixel-by-pixel reconstruction. That's the fundamental difference from a generative model.

---

## Trap #1: Collapse

JEPA has one major flaw: it can "cheat". If the encoder learns to map everything to
the same constant vector (e.g. `[0, 0, 0, …, 0]`), then `ŝ_{t+1} ≈ s_y` always,
loss drops to 0, and the model learned nothing.

**Indicator**: embedding variance drops below `1e-6`.

**Two countermeasures**, from VICReg (Bardes & LeCun, 2021) and the ESANN 2025 paper
(*JEPA for RL*):

1. **EMA target encoder**: if the encoder weights change abruptly, targets change
   more slowly → forces prediction to remain non-trivial.

2. **Variance regularization (VICReg)**: add a loss that penalizes embeddings
   with too-low variance:
   ```
   L_reg = -min(1, (1/D) Σ_i Var(s_x)_i)
   ```
   Clamped at 1 so it's a bounded loss.

Mine-JEPA total training loss:
```
L = L_JEPA + λ_reg · L_reg + (RL gradients if training an agent)
```

---

## The action-conditioned world model

In Mine-JEPA, the predictor receives **the agent's action** in addition to the latent state:

```
ŝ_{t+1} = Predictor(s_t, a_t)
```

For discrete actions (Crafter has 17 actions), we use a **discrete embedding**:
```python
a_encoded = Embedding(n_actions=17, d_model=32)(action)
```

This allows **unrolling the world model over multiple steps** without ever touching
the real environment:
```
s_1 = Predictor(s_0, a_0)
s_2 = Predictor(s_1, a_1)
...
s_k = Predictor(s_{k-1}, a_{k-1})
```
This is **imagination in latent space**.

---

## How the agent plans

With a world model that predicts future latent state, we can plan via **MPC**
(Model Predictive Control):

1. Define a **goal**: the encoded embedding of a target frame (e.g. "standing next to a tree").
2. Sample random candidate action sequences.
3. Unroll each sequence in the world model in latent space.
4. Keep the sequence whose final state is **closest to the goal embedding**.
5. Execute only the 1st action, re-observe, re-plan.

This algorithm is called **CEM (Cross-Entropy Method)**. It's already implemented in
`mine_jepa/eb_jepa/planning.py` (`CEMPlanner`).

---

## Why it's better than an LLM for this use case

| | LLM / VLM (Computer Use) | JEPA (Mine-JEPA) |
|---|---|---|
| High-level reasoning | ✅ Strong | ❌ Absent |
| Reactive control | ❌ Too slow (1–10s/action) | ✅ Fast (<100ms/action) |
| Understands visual dynamics | ⚠️ Approx. (via description) | ✅ Direct (from pixels) |
| Size | Billions of params | ~15M params |
| GPU required | Server or API | RTX 3080+ |
| "Imagines" the future | ❌ No (generates text) | ✅ Yes (latent rollout) |

JEPA doesn't replace the LLM — it complements it. The LLM says **what** to do (high
level), JEPA does **how** to do it (low-level reactive).

---

## Summary in one sentence

> JEPA learns an abstract world representation by predicting the **latent** future state
> (not pixels), with an EMA target encoder to avoid collapse, and an action-conditioned
> predictor to simulate the consequences of each move.

---

*Next concepts: `docs/03_representation_collapse.md` (collapse in detail),
`docs/04_world_model.md` (the action-conditioned predictor).*

*Full bibliography (papers implemented, read, rejected): [`docs/references/index.md`](references/index.md)*

# The action-conditioned world model

> This doc explains Mine-JEPA's second component: the **world model**.
> If Phase 1 taught you to represent game states in latent space,
> Phase 2 teaches you to *predict how those states change* when the agent acts.

---

## The central question

At the end of Phase 1, the encoder knows how to transform a Crafter frame into a
latent vector `s_t` that captures game structure (position, health, objects…).

But the agent can't plan yet. It can't answer the question:
> "If I perform the action *hit this block*, what will my latent state look like after?"

The world model answers exactly that.

---

## The architecture in one line

```
s_t  +  a_t  →  [ Predictor ]  →  ŝ_{t+1}
```

- `s_t`: current latent state (output of frozen encoder, Phase 1) — `[B, 128]`
- `a_t`: discrete action (0–16 in Crafter) — `[B]`
- `ŝ_{t+1}`: **prediction** of the next latent state — `[B, 128]`

The predictor never touches pixels. It operates entirely in latent space.

---

## Why "action-conditioned" is crucial

A predictor without action would just predict "the average next state" — useful for
passive dynamics (sun moving) but useless for planning.

With the action as input, the predictor learns causal rules:
- Action *move_right* + left position → right position
- Action *do* + tree in front → tree disappears + wood in inventory
- Action *sleep* + low energy → energy recovers

That's the difference between **observing** the world and **understanding** what you can do in it.

---

## The predictor architecture (Mine-JEPA)

```python
class ActionConditionedPredictor(nn.Module):
    def __init__(self, embed_dim=128, n_actions=17, action_dim=32):
        self.action_embed = nn.Embedding(n_actions, action_dim)
        self.net = nn.Sequential(
            nn.Linear(embed_dim + action_dim, 256),
            nn.GELU(),
            nn.Linear(256, 256),
            nn.GELU(),
            nn.Linear(256, embed_dim),
        )

    def forward(self, s, a):
        a_emb = self.action_embed(a)           # [B, 32]
        return self.net(torch.cat([s, a_emb])) # [B, 128]
```

**Why so small (140K params)?** We want *understanding* to be in the encoder
(Phase 1, 688K params). The predictor just needs to learn *transitions* — making
it too large lets it compensate for a weak encoder.

**Why GELU?** Smooth activation that doesn't block gradients for small negative
values, better than ReLU for zero-centered embeddings.

---

## The loss: MSE in latent space

```
L = MSE(ŝ_{t+1}, s_{t+1})
  = ‖ Predictor(s_t, a_t) - Encoder(frame_{t+1}) ‖²
```

The encoder is **frozen** — its weights no longer move since Phase 1. Only the
predictor receives gradients. This guarantees that Phase 1 representations stay stable.

**No VICReg needed here**: the target `s_{t+1}` is provided by the frozen encoder
which already has healthy variance (~1.15 from Phase 1). Hard to collapse against a
target that actually moves.

---

## The baseline and the gate

To know if the predictor is useful, we compare against the **simplest baseline**:
*"the state doesn't change"*, i.e. `ŝ_{t+1} = s_t`.

```
copy_loss = MSE(s_t, s_{t+1})       # how much states differ per step
pred_loss = MSE(ŝ_{t+1}, s_{t+1})  # predictor error
ratio     = pred_loss / copy_loss
```

- `ratio > 1`: the predictor is **worse** than doing nothing
- `ratio < 1`: the predictor **predicts better** than copying → gate passed ✅

---

## What we observe (real Phase 2 run)

First epoch on RTX 5060 Ti, frozen Phase 1 encoder (val_loss=0.080):

| Step | pred_loss | copy_loss | ratio |
|-----:|----------:|----------:|------:|
|   20 | 1.0193    | 0.0710    | 14.36 |
|   40 | 0.5721    | 0.0905    |  6.32 |
|   60 | 0.2819    | 0.1015    |  2.78 |
|   80 | 0.1877    | 0.1026    |  1.83 |
|  100 | 0.1338    | 0.0806    |  1.66 |

Ratio drops from 14x to 1.4x in 100 steps — the predictor very quickly learns the
most frequent transitions (the agent often barely moves).
The gate (ratio < 1.0) is expected around epochs 5–10.

---

## Latent imagination: unrolling over k steps

Once trained, the predictor allows **imagining the future without touching the game**:

```python
s_hat_1 = predictor(s_0, a_0)        # imagine step 1
s_hat_2 = predictor(s_hat_1, a_1)    # imagine step 2
...
s_hat_k = predictor(s_hat_{k-1}, a_{k-1})  # imagine step k
```

This is exactly what the `eval_wm.py` multi-step gate does: measure whether
rollout error over k=1..10 steps stays below the constant baseline.

**Why does error grow with k?** Each step accumulates a small error. That's
normal and expected. What would be abnormal: error that explodes, or zero error
(the predictor would have learned to ignore actions).

---

## Visualization: nearest-neighbor retrieval

The most telling visualization of the world model isn't a loss curve —
it's **seeing what the model imagines**.

Method:
1. Take an initial state `s_0` (encoded from a real frame).
2. Unroll k steps in the world model with an action sequence → `ŝ_1, ..., ŝ_k`.
3. For each `ŝ_k`, find the closest real frame in the dataset
   (by cosine distance in latent space) → display that frame.

Result: an "imagination" of what might happen if the agent executed this action
sequence. That's Phase 2's visual hook.

→ Implemented in `scripts/eval_wm.py` (future option: `--visualize`).

---

## Summary: the full loop so far

```
Phase 1 :  Frame → [Encoder] → s_t        (representation, frozen)
Phase 2 :  s_t + a_t → [Predictor] → ŝ_{t+1}  (world model, trained now)
Phase 3 :  s_goal + [WM] → action plan     (latent planning, coming next)
```

The world model is the missing piece between "understanding the game" and "playing the game".

---

*Next concepts: `docs/05_planning.md` (latent MPC/CEM, goal-conditioned),
`docs/01_jepa.md` (global architecture).*

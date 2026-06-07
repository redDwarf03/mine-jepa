# Collapse and anti-collapse in JEPA

> This doc explains JEPA's #1 problem: **representation collapse**.
> You'll learn why it happens, how EMA and VICReg prevent it,
> and how to read your own training curves to detect a collapse.

---

## The problem: learning to cheat

Imagine giving a neural network this objective:

> "Encode video game frames such that the embedding of frame *t*
> can predict the embedding of frame *t+1*."

The *honest* solution: the encoder learns to represent game structure (player position,
nearby objects, health…) so that dynamics are predictable in latent space.

The *dishonest* solution: the encoder maps **all frames to the same vector**,
e.g. `[0, 0, 0, …, 0]`. Prediction loss immediately drops to 0 — the predictor
has nothing to do. The model has "won" without learning anything.

This is **collapse**: convergence toward a trivial, constant solution.

```
Frames  →  Encoder  →  s = [0, 0, 0, ..., 0]  (always)
                                    ↓
           Predictor →  ŝ = [0, 0, 0, ..., 0]  (trivial)
                                    ↓
               Loss = ‖ŝ - s_y‖² = 0  ✓ (but nothing learned)
```

---

## How to detect collapse: `batch_var`

The primary indicator is the **mean embedding variance over a batch**:

```python
batch_var = embeddings.var(dim=0).mean()
```

- High `batch_var` (~1.0) → embeddings are spread out → the model encodes different
  information per frame → **healthy**
- `batch_var` → 0 → all embeddings converge to the same point → **collapse**

Alert threshold in Mine-JEPA: `batch_var < 1e-4`.

---

## Why JEPA collapses easily (vs. BERT, etc.)

Architectures like BERT avoid collapse by construction: they work in **pixel/token
space** with reconstruction. It's impossible to reconstruct an image from a constant vector.

JEPA works in **latent space**: the encoder AND predictor are free to learn any solution
together, including the trivial one.

Classic contrastive models (SimCLR) avoid this by **comparing negative examples**
(repulsive push between different embeddings). But that requires large batches and an
explicit definition of "which pairs are different".

JEPA wants to avoid all that (no negatives, no pixel reconstruction) — which makes it
powerful *but* more vulnerable to collapse.

---

## Countermeasure #1: EMA Target Encoder

The root cause of joint-embedding collapse: if context encoder and target encoder
update together via gradient, nothing prevents both from converging to the same constant.
Loss stays zero and gradients see no problem.

**Solution**: cut the target encoder's gradient and update it slowly via an
**Exponential Moving Average (EMA)** of the context encoder:

```
θ̄_{t+1} ← 0.99 · θ̄_t + 0.01 · θ_t
```

- `θ` = context encoder weights (updated normally by backprop)
- `θ̄` = target encoder weights (never direct gradient — EMA only)

**Why it helps**: the target encoder evolves *slowly*. Its output `s_y` is a
non-trivial target that changes little, but enough that the predictor can't "sleep"
on a constant solution. It's a form of **momentum knowledge distillation**.

In the code (`mine_jepa/encoder/crafter_encoder.py:54`):

```python
class EMATargetEncoder(nn.Module):
    @torch.no_grad()
    def update(self, source: CrafterEncoder) -> None:
        for ema_p, src_p in zip(self.net.parameters(), source.parameters()):
            ema_p.data.mul_(self.decay).add_(src_p.data, alpha=1.0 - self.decay)
```

The `@torch.no_grad()` is critical: no gradient ever flows through this path.

---

## Countermeasure #2: VICReg (Variance-Invariance-Covariance Regularization)

EMA alone is not enough. We add **explicit regularization** that directly forbids collapse.

### Variance penalty (anti-collapse)

```
L_std = mean( max(0, 1 - std(s_x, dim=0)) )
```

This loss is zero if all embedding dimensions have std ≥ 1.
If variance drops (collapse in progress), the loss rises and pushes the encoder back.

*Intuition*: we "force" the encoder to use all of latent space, not just one point.

### Covariance penalty (anti-redundancy)

```
L_cov = mean( off_diagonal( cov(s_x)² ) )
```

This loss penalizes correlations between embedding dimensions. If two dimensions
encode the same information, they are correlated → penalty.

*Why*: an embedding where all dimensions say the same thing is almost as bad as a
constant embedding. VICReg forces **decorrelation** so each dimension encodes something different.

### Mine-JEPA Phase 1 total loss

```
L = L_JEPA  +  λ_std · L_std  +  λ_cov · L_cov

with λ_std = 1.0  (configs/train_encoder.yaml)
     λ_cov = 0.04
```

`λ_cov` is small (0.04) because decorrelation is less critical than variance.
`λ_std = 1.0` is strong to truly forbid collapse.

---

## What we observe in Mine-JEPA (real run)

Here are the metrics from the first epochs of Phase 1 training on RTX 5060 Ti,
Crafter dataset 32,676 transitions:

| Epoch | total loss | jepa | std_loss | cov_loss | batch_var | val_loss |
|------:|----------:|-----:|---------:|---------:|----------:|---------:|
| 1     | 0.190      | 0.134 | 0.040   | 0.434    | **1.057** | 0.250    |
| 2     | 0.119      | 0.101 | 0.001   | 0.405    | **1.124** | 0.191    |
| 3     | 0.106      | 0.091 | 0.001   | 0.347    | **1.128** | 0.122    |
| 4     | 0.094      | 0.081 | 0.001   | 0.303    | **1.133** | 0.114    |
| 5     | 0.084      | 0.073 | 0.001   | 0.271    | **1.150** | 0.098    |

**Reading**:

- `batch_var` **rises** from 1.06 to 1.15 → the model uses more and more of latent
  space. Opposite of collapse.
- `std_loss` drops quickly to ~0.001 → variance constraint satisfied by epoch 2.
  VICReg did its job.
- `cov_loss` decreases (0.43 → 0.27) → dimensions progressively decorrelate.
- `jepa_loss` halved in 5 epochs → the predictor is learning.

---

## What a collapse looks like (for comparison)

If we disabled VICReg and EMA, we'd typically see:

```
Epoch  1 | batch_var=1.05  (normal at start)
Epoch  5 | batch_var=0.12  (dropping)
Epoch 10 | batch_var=0.003 (collapse in progress)
Epoch 15 | batch_var=8e-7  ← ALERT
Epoch 20 | batch_var=1e-9  (total collapse — model is useless)
```

The jepa loss also drops toward ~0, which *seems* good at first glance.
That's the most dangerous misleading signal: **a very low loss without variance
= collapse, not success**.

---

## Summary: the 3 signals to watch

| Signal | Healthy value | Alert |
|--------|-------------|--------|
| `batch_var` | > 0.1, ideally ~1 | < 1e-4 |
| `std_loss` | close to 0 (variance OK) | rising → passive collapse |
| `jepa_loss` | decreasing steadily | staying high → predictor too weak |

If `batch_var < 1e-4`: increase `std_coeff` in `configs/train_encoder.yaml`
(e.g. 1.0 → 5.0) and restart.

---

## The visualization that proves it works

The best test isn't numerical: it's the **PCA/t-SNE projection of embeddings**
colored by a game state (health, nearby objects…).

If the model learned something useful, clusters appear — regions of latent space
correspond to similar game situations, *without any labels during training*.

→ This is what `scripts/probe.py` validates: a linear classifier on these frozen
embeddings must exceed the random baseline (~33%) for the Phase 1 gate to pass.

---

*Next concepts: `docs/04_world_model.md` (action-conditioned predictor),
`docs/01_jepa.md` (full architecture).*

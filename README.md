# Mine-JEPA

**A JEPA agent that learns to play Minecraft from pixels — no reward shaping, no human annotation labels, no frozen pretrained VLM.**

The agent trains a Joint-Embedding Predictive Architecture entirely on raw gameplay trajectories, builds a latent world model, and uses Model Predictive Control to plan action sequences in latent space — all on a consumer 8 GB GPU.

![eb-JEPA agent playing MineRL Treechop](assets/agent_play_ebwm.gif)

*eb-JEPA MPC agent on MineRLTreechop-v0 — 50% success rate (tree chopped), reward 0.75/ep*

---

## Results at a glance

| Phase | Task | Key metric | Value |
|-------|------|-----------|-------|
| 1 — Encoder | JEPA self-supervised | batch_var (no collapse) | **1.17** |
| 1 — Probe | Linear health probe | Accuracy vs majority baseline | **90.8% vs 86.9% (+3.9pp)** |
| 2 — World Model | Crafter 1-step prediction | pred/copy ratio | **0.38** (< 1 = beats baseline) |
| 3 — Planner | Crafter MPC agent | Achievements vs random | **+7.5%** (+14% reward) |
| 4 — Minecraft | MineRL Treechop eb-JEPA | Success rate | **50%** (reward 0.75/ep) |
| 4 — WM v2 | Action-conditioned on human demos | Best ratio (epoch 16) | **0.919**, batch_var 1.28 |

**No collapse across all runs.** `batch_var > 1` throughout — embeddings are diverse and informative.

---

## What is JEPA?

A **Joint-Embedding Predictive Architecture** (LeCun, 2022) learns visual representations by predicting *in embedding space* rather than in pixel space:

```
frame_t  ──[Encoder f]──►  s_t ──────────────────────────────────┐
                                                                   │
frame_t+1 ──[Target g]──► s_t+1  ◄── [Predictor p(s_t, a_t)]────┘
```

- The **encoder** maps frames to compact latent vectors
- The **target encoder** is an EMA copy of the encoder (no gradient) — the stabilisation key
- The **predictor** learns to predict `s_{t+1}` from `s_t + action` in latent space

This is the **world model**: once trained, it can *imagine* the consequences of actions without touching the environment.

The planner uses **random-shooting MPC**: sample 512 action sequences of length 12, unroll all of them through the world model, pick the one that reaches the goal latent. No policy gradient, no value function.

Full explanation: [`docs/01_jepa.md`](docs/01_jepa.md)

---

## The anti-collapse problem

JEPA is prone to **representation collapse** — all embeddings converge to the same constant, loss → 0, but the model has learned nothing.

Two countermeasures are active at all times:

1. **EMA target encoder** — `θ̄ ← 0.99·θ̄ + 0.01·θ` — the target never copies the encoder directly, preventing shortcut solutions
2. **VICReg regularisation** — penalises low variance and high covariance between dimensions

Collapse indicator: `batch_var` (inter-sample variance of embeddings). If it drops below `1e-6`, collapse is in progress.

Full explanation: [`docs/03_representation_collapse.md`](docs/03_representation_collapse.md)

---

## Architecture

```
frames (64×64×3)
    │
    ▼
┌─────────────┐     ┌──────────────────┐
│  Encoder    │     │  Target Encoder  │  ← EMA copy, gradient blocked
│  ResNet5    │     │  ResNet5         │
│  15M params │     │  15M params      │
└──────┬──────┘     └────────┬─────────┘
       │ s_t                 │ s_t+1 (target)
       │                     │
       ▼                     │
┌──────────────┐             │
│  Predictor   │─────────────┘
│  action MLP  │  loss = MSE(pred, target) + VICReg
│  140K params │
└──────────────┘

At play time:
    s_t + [512 random sequences × horizon 12]
         → World Model rollout
         → score vs goal latent
         → best first action
```

Phase 4 uses **Meta's eb_jepa** (vendored in `mine_jepa/eb_jepa/`) with spatial latent maps `[D, 8, 8]` instead of a flat vector — preserving "where is the trunk" information that the MPC planner needs.

---

## Quick start

### Requirements

- Python 3.11+
- `uv` package manager (`pip install uv`)
- GPU with 8 GB VRAM for training (CPU works for testing imports)
- Java 8 for MineRL (Phase 4 only — see [`docs/02_setup.md`](docs/02_setup.md))

### Install

```bash
git clone https://github.com/redDwarf03/mine-jepa.git
cd mine-jepa
uv sync
```

### Collect data (Crafter, no GPU needed)

```bash
run.bat scripts/collect.py --episodes 200
# → data/crafter/episodes.npz  (33k transitions)
```

### Train the JEPA encoder (Phase 1)

```bash
run.bat scripts/train_encoder.py
# Monitor: batch_var > 1e-4 = no collapse
# Target: val_loss ≈ 0.08 after 30 epochs
```

### Verify representations (linear probe)

```bash
run.bat scripts/probe.py
# Phase 1 gate: accuracy > majority baseline
```

### Train the world model (Phase 2)

```bash
run.bat scripts/train_wm.py
# Gate: val_pred / val_copy < 1.0
```

### Run the MPC agent (Phase 3 — Crafter)

```bash
run.bat scripts/play.py
# Gate: success_rate >= 50%, achievements > random
```

### Run on real Minecraft (Phase 4 — MineRL)

```bash
# Requires MineRL installation — see docs/02_setup.md
play_ebwm.bat
# Gate: success_rate >= 30% (50% achieved)
```

---

## Project structure

```
mine_jepa/              ← Python package
  encoder/              ← CrafterJEPA, EMA, VICReg, datasets
  predictor/            ← ActionConditionedPredictor (WM)
  planning/             ← LatentMPCPlanner (random-shooting)
  policy/               ← BCPolicy, BCCNNPolicy (Phase 4 ablations)
  ebwm/                 ← Action-conditioned JEPA (Meta eb_jepa assembly)
  eb_jepa/              ← Meta's eb_jepa vendored code

scripts/                ← One script = one verifiable deliverable
  collect.py            ← Collect trajectories (Crafter or MineRL)
  train_encoder.py      ← Phase 1: JEPA encoder
  probe.py              ← Phase 1: linear probe gate
  train_wm.py           ← Phase 2: world model
  eval_wm.py            ← Phase 2: multi-step rollout evaluation
  play.py               ← Phase 3: MPC agent (Crafter)
  train_eb_jepa.py      ← Phase 4: action-conditioned eb-JEPA
  play_ebwm.py          ← Phase 4: eb-JEPA MPC on MineRL
  collect_minerl_multi.py  ← MALMOBUSY workaround: 1 process/episode
  play_minerl_multi.py     ← Same workaround for play

configs/                ← YAML hyperparameters (no hardcoded values)
docs/                   ← Pedagogy + technical notes
  01_jepa.md            ← What is JEPA
  02_setup.md           ← Installation guide
  03_representation_collapse.md
  04_world_model.md
  05_planning.md
  06_minecraft_port.md  ← MineRL port: 4 approaches, lessons learned
assets/                 ← GIFs and demo videos
```

---

## Phase 4 deep-dive: what worked and what didn't

Porting from Crafter to real Minecraft (MineRL Treechop) required 5 attempts:

| Approach | Description | Result |
|----------|-------------|--------|
| 1 | MPC + 1-step WM (flat vector) | reward = 0 — planner blind on near-static frames |
| 2 | MPC + residual WM | reward = 0 — same root cause |
| 3 | Behavioral Cloning (frozen encoder) | reward = 0 — covariate shift, agent stuck |
| 4 | End-to-end BC CNN | reward = 0 — no memory, no sustained attack |
| **5** | **eb-JEPA action-conditioned MPC** | **50% success, reward 0.75/ep** ✅ |

**The key insight:** flat 128-d latent vectors lose spatial information (where is the trunk?). Switching to spatial latent maps `[64, 8, 8]` + action-conditioned joint training unlocked the planner.

**The action_repeat trick:** planning every 4 steps and repeating the action produces the sustained attack (holding "forward + attack" for multiple ticks) that is physically necessary to chop a log. Without it: reward = 0.

Full analysis: [`docs/06_minecraft_port.md`](docs/06_minecraft_port.md)

---

## Training details

### Hardware used

| Stage | Hardware | Time |
|-------|----------|------|
| Data collection (Crafter) | Any CPU | ~5 min / 100 ep |
| Data collection (MineRL) | Any CPU + Java 8 | ~2 min / episode |
| Encoder training (Phase 1) | RTX 5060 Ti 8 GB | ~15 min / 30 epochs |
| World model training (Phase 2) | RTX 5060 Ti 8 GB | ~10 min / 30 epochs |
| eb-JEPA training (Phase 4) | RTX 5060 Ti 8 GB | ~45 min / 25 epochs |
| MPC play (Crafter) | CPU or GPU | ~1 min / episode |
| MPC play (MineRL) | RTX 5060 Ti 8 GB | ~3 min / episode |

### Model sizes

| Component | Parameters |
|-----------|-----------|
| JEPA encoder (ResNet5) | ~15M |
| Action predictor (MLP) | ~140K |
| eb-JEPA full model | ~2.47M |
| Total inference footprint | < 20M |

---

## Self-supervised vs supervised CUAs

A key differentiator of this project: **zero human annotation**.

Current state-of-the-art Computer Use Agents (Claude Computer Use, UI-TARS, OpenAI CUA) are trained via supervised fine-tuning on millions of `(screenshot, correct_action)` pairs annotated by humans. ByteDance built an entire "data flywheel" to produce UI-TARS.

Mine-JEPA learns from **raw trajectories only**:

```
(frame_t, frame_{t+1})           → JEPA encoder (no label needed)
(frame_t, action_t, frame_{t+1}) → world model  (action just recorded, not judged)
```

Any gameplay video is a valid training dataset. This makes the approach:
- **Zero annotation cost** — no human labelling pipeline
- **Scalable** — more video = better model
- **Privacy-preserving** — no screenshots sent to external servers

The full analysis is in [`docs/07_cua_landscape_june2026.md`](docs/07_cua_landscape_june2026.md).

---

## Docs

| Document | Content |
|----------|---------|
| [`docs/01_jepa.md`](docs/01_jepa.md) | What is JEPA — 3 components, collapse, planning |
| [`docs/02_setup.md`](docs/02_setup.md) | Installation (Crafter + MineRL + Java 8) |
| [`docs/03_representation_collapse.md`](docs/03_representation_collapse.md) | Collapse detection, EMA, VICReg |
| [`docs/04_world_model.md`](docs/04_world_model.md) | WM architecture, action-conditioning, eval |
| [`docs/05_planning.md`](docs/05_planning.md) | Random-shooting MPC, goal embedding |
| [`docs/06_minecraft_port.md`](docs/06_minecraft_port.md) | MineRL port — 5 approaches, MALMOBUSY bug |
| [`docs/07_cua_landscape_june2026.md`](docs/07_cua_landscape_june2026.md) | CUA landscape June 2026, JEPA positioning |
| [`PLAN.md`](PLAN.md) | Full project plan with gates and phases |

---

## Key papers

- **JEPA** — LeCun, Y. (2022). *A Path Towards Autonomous Machine Intelligence.* [openreview](https://openreview.net/forum?id=BZ5a1r-kVsf)
- **V-JEPA 2** — Assran et al. (2025). *V-JEPA 2: Self-Supervised Video Models Enable Understanding, Prediction and Planning.* arXiv:2506.09985
- **eb_jepa** — Meta FAIR. *Action-conditioned JEPA for embodied planning.* [github](https://github.com/facebookresearch/eb_jepa)
- **VICReg** — Bardes et al. (2022). *VICReg: Variance-Invariance-Covariance Regularization.* arXiv:2105.04906
- **LeWorldModel** — arXiv:2603.19312

---

## Acknowledgements

- **Meta FAIR** for the [`eb_jepa`](https://github.com/facebookresearch/eb_jepa) codebase (vendored in `mine_jepa/eb_jepa/`)
- **MineRL** team for the MineRLTreechop-v0 environment and Zenodo human demonstrations
- **Crafter** (Hafner 2021) for the lightweight test environment
- **ESANN 2025** paper `ES2025-19.pdf` for the VICReg anti-collapse recipe

---

## License

MIT — see [`LICENSE`](LICENSE).

The vendored `mine_jepa/eb_jepa/` code is from Meta FAIR under its original license (Apache 2.0).

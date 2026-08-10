# Mine-JEPA

**A complete lab notebook — failures included — on building a JEPA agent that plays Minecraft from pixels, on a single consumer GPU.**

The agent trains a Joint-Embedding Predictive Architecture on raw gameplay trajectories, builds a latent world model, and plans with Model Predictive Control in latent space. No reward shaping, no human annotation labels, no frozen pretrained VLM. It chops trees in real Minecraft and crafts planks end to end.

It also spent twenty documented attempts failing to solve one specific problem, and the twentieth attempt finally explains why. That part is written down at the same level of detail as the successes.

🌐 **Interactive learning site (EN & FR):** [**https://reddwarf03.github.io/mine-jepa/**](https://reddwarf03.github.io/mine-jepa/)
*20 chapters, dual-track (Beginner / Expert), written directly from this repository's research log.*

![eb-JEPA agent playing MineRL Treechop](assets/agent_play_ebwm.gif)

*eb-JEPA MPC agent on MineRLTreechop-v0 — chops trees autonomously, up to 2 logs/episode. 25% success on the released checkpoint (varies 25–50% across training draws).*

---

## What this is, and what it is not

Read this section before anything else. It is the honest framing, and it is deliberately first.

**What this is:**

- A working, reproducible JEPA → world-model → MPC pipeline, small enough to train on one 8 GB GPU, with every phase gated on a stated numerical bar *before* being called a success.
- A teaching resource. 20 site chapters and 10 technical docs, written as the work happened, including the parts that did not work.
- An unusually complete record of a research dead end: 20 numbered attempts at one open problem, six independent confirmations of a single measurement confound, one result retracted the same session it was found, and a root-cause diagnosis at the end.

**What this is not:**

- **This is not novel research, and it never claimed to be.** A JEPA-family world model planning in Minecraft has been done, and done better, by teams with more compute. See [ActSWM](https://arxiv.org/abs/2607.26712) (2026), which uses the same architecture family as this project and reaches 19/20 on closed-loop stone mining; also DreamerV3 and VPT for Minecraft agents generally. If you want the state of the art, go there, not here.
- **This is not a solved cold-start agent.** Starting from a random survival spawn with no tree in view, the best configuration ever measured reached ~10%. That campaign is now closed — see below.
- **This is not a benchmark-chasing repo.** The numbers here are small, honest, and often negative.

**The one thing here you probably will not find elsewhere:** almost nobody publishes their failures at this resolution. Papers show what worked. Tutorials show what worked. This shows twenty attempts of what did not, with the measurements, the wrong turns, and the self-corrections. If that is useful to you, that is what this repository is for.

---

## Results at a glance

| Phase | Task | Key metric | Value |
|-------|------|-----------|-------|
| 1 — Encoder | JEPA self-supervised (Crafter) | batch_var (no collapse) | **1.17** |
| 1 — Probe | Linear health probe | Accuracy vs majority baseline | **90.8% vs 86.9% (+3.9pp)** |
| 2 — World Model | Crafter 1-step prediction | pred/copy ratio | **0.38** (< 1 = beats baseline) |
| 3 — Planner | Crafter MPC agent | Achievements vs random | **+7.5%** (+14% reward) |
| 4 — Minecraft | MineRL Treechop eb-JEPA (664K params) | Success rate | **25–50%** (draw-dependent; released ckpt 25%) |
| 5 — Crafting | WM v4 crafts planks in **live** Minecraft (given wood) | Craft success | **100%**, +16–20 planks/ep (rule learned: dPlanks +3.8) |
| 5+ — Cold-start | Crafting from a random spawn, no starting wood | Best config ever measured | **~10%** (3/31) — **campaign closed, unsolved** |

**No isotropic collapse across any run.** `batch_var > 1` throughout.

> **On the MineRL number, honestly:** the agent chops trees in real Minecraft, but success varies
> **25–50% between training runs** at the same prediction ratio (~0.93). Training is not seeded,
> and downstream planning performance is only weakly coupled to the world-model prediction metric.
> The released checkpoint scores 25% (5/20). See
> [`docs/06_minecraft_port.md`](docs/06_minecraft_port.md) for the full ablation.

---

## The cold-start campaign: 20 attempts, closed

Crafting **given wood** works 100% of the time. Crafting **from a random survival spawn** — no tree in view, no wood in hand — is a different and much harder problem. It is unsolved here, and the campaign is closed.

Full record: [`docs/10_coldstart_engineering.md`](docs/10_coldstart_engineering.md) and [`docs/09_curiosity_coldstart.md`](docs/09_curiosity_coldstart.md).

**The three mechanisms that actually worked** (the project's standing baseline):

| Mechanism | Result |
|---|---|
| `commit_length=4` — hold a planned gesture for 4 steps instead of replanning every tick | **3/31 (~9.7%)** — the campaign's best result, and its first non-zero one |
| `FrontierTracker` — dead-reckoned visit-count grid driving exploration | 1/20, no behavioural pathology |
| Hazard avoidance — a calibrated drowning detector plus a steered escape | Drowning **60% → 15%** at N=20; fair-shot episodes 40% → 60% |

**What repeatedly did not work**, and the two findings that explain it:

- **Six independent mechanisms all hit the same brightness confound** when scoring "is there a tree nearby": two trained heads, an off-the-shelf 400M-image model (CLIP), a direct encoder fine-tune with photometric augmentation, a hand-designed lighting-invariant feature, and — decisively — an untrained closed-form statistic with no gradient and nothing to learn. The confound is in the frozen representation itself, not in how anything was trained. In this domain, dark forests versus bright open fields is the *real* scene composition, so no single-frame photometric feature can separate them.
- **Attempt #20 measured something nobody had checked in 20 attempts: does the world model react to actions at all?** It does — the 17 actions genuinely move the prediction — but conditioning on the *true* action predicts the future measurably **worse** than assuming the agent did nothing (p=0.0130 on Treechop, its own training domain; the true action wins in only 13–36% of windows, against 50% for chance). The consistent ordering is `noop > true action > random action`. Reproduce with `run.bat scripts/diagnose_context_collapse.py`.

**Why that closes it.** Attempts #2–#19 tuned search, scoring and execution on top of a frozen world model whose action conditioning is a net liability against copy-last. An MPC planner sitting on that ranks candidate action sequences by differences that do not track consequences. It also explains why `commit_length` — deciding *less often* — was the only lever that ever worked.

**Stated plainly, what closing does not claim:** not that cold-start chopping is impossible, and not that the remaining lever would fail. The remaining lever is a world-model rebuild (an inverse-dynamics readout term, plus a context length greater than 1), which is a different project, not a 21st attempt.

⚠️ **One honest caveat, not smoothed over:** the agent chops trees 25–50% on Treechop *with this exact defect present*. So attempt #20's finding cannot on its own be the complete explanation of the cold-start failure. No such explanation is offered here; it would be a hypothesis, not a measurement.

---

## What is JEPA?

A **Joint-Embedding Predictive Architecture** (LeCun, 2022) learns visual representations by predicting *in embedding space* rather than in pixel space:

```
frame_t  ──[Encoder f]──►  s_t ──────────────────────────────────┐
                                                                 │
frame_t+1 ──[Encoder f]──► s_t+1  ◄── [Predictor p(s_t, a_t)]────┘
```

- The **encoder** maps frames to compact latent representations
- The **predictor** learns to predict `s_{t+1}` from `s_t + action`, in latent space
- An **anti-collapse regulariser** stops the trivial solution where every frame maps to the same point

This is the **world model**: once trained, it can *imagine* the consequences of actions without touching the environment.

The planner uses **random-shooting MPC**: sample 512 action sequences of length 12, unroll all of them through the world model, pick the one whose imagined outcome lands closest to a goal latent. No policy gradient, no value function.

Full explanation: [`docs/01_jepa.md`](docs/01_jepa.md)

---

## The anti-collapse problem

JEPA is prone to **representation collapse** — all embeddings converge to the same constant, loss → 0, but the model has learned nothing.

**Two different pipelines live in this repo, and they defend against collapse differently.** This distinction matters and is easy to get wrong:

| Pipeline | Used by | Anti-collapse |
|---|---|---|
| Crafter encoder (`mine_jepa/encoder/`) | Phases 1–3 | EMA target encoder (`θ̄ ← 0.99·θ̄ + 0.01·θ`, gradient blocked) **+** VICReg |
| eb-JEPA (`mine_jepa/ebwm/`, `mine_jepa/eb_jepa/`) | Phases 4–5, the released Minecraft agent | **No EMA target.** Variance + covariance terms on a single tensor only (`HingeStdLoss` + `CovarianceLoss`); `sim_coeff_t` and `idm_coeff` are inert at 0 |

Runtime indicator: `batch_var` (inter-sample variance of embeddings). Below `1e-6`, collapse is in progress.

> **`batch_var` has a blind spot, discovered in attempt #19.** It detects *isotropic* collapse (all
> embeddings identical) but not *dimensional* collapse — embeddings staying different from one
> another while all their variation concentrates into a handful of directions. An experimental
> SIGReg run kept `batch_var` at a perfectly healthy 1.36 while effective rank fell from 26.7 to
> 4.5 (−83%). If you change the anti-collapse loss, monitor effective rank too.

Full explanation: [`docs/03_representation_collapse.md`](docs/03_representation_collapse.md)

---

## Architecture (the released Minecraft agent)

```
frames (64×64×3)
    │
    ▼
┌──────────────────┐
│  Encoder         │  ResNet5 → spatial latent [64, 8, 8]
│  156K params     │  (spatial map, NOT a flat vector — see below)
└────────┬─────────┘
         │ s_t
         ▼
┌──────────────────┐      ┌────────────────────┐
│  ACConvPredictor │◄─────│  Action encoder    │  17 discrete actions
│  507K params     │      │  272 params        │
│  context_length=1│      └────────────────────┘
└────────┬─────────┘
         │  loss = MSE(pred, target) + variance/covariance regulariser
         ▼
    s_{t+1}

At play time:
    s_t + [512 random action sequences × horizon 12]
         → world-model rollout
         → score against goal latent
         → execute the first 4 actions (commit_length), then replan
```

**Total: 663,792 parameters.** Phases 4–5 use **Meta's eb_jepa** (vendored in `mine_jepa/eb_jepa/`) with spatial latent maps `[64, 8, 8]` instead of a flat vector — preserving "where is the trunk" information that the MPC planner needs. The Phase 1–3 Crafter encoder is a separate, larger (~15M) model.

---

## Quick start

### Requirements

- Python 3.11+
- `uv` package manager (`pip install uv`)
- GPU with 8 GB VRAM for training (CPU works for testing imports)
- Java 8 for MineRL (Phases 4–5 only — see [`docs/02_setup.md`](docs/02_setup.md))

### Install

```bash
git clone https://github.com/redDwarf03/mine-jepa.git
cd mine-jepa
uv sync
```

### The pipeline, phase by phase

```bash
# Collect data (Crafter, no GPU needed) → 33k transitions
run.bat scripts/collect.py --episodes 200

# Phase 1: train the JEPA encoder. Gate: batch_var > 1e-4 (no collapse)
run.bat scripts/train_encoder.py

# Phase 1 gate: linear probe must beat the majority baseline
run.bat scripts/probe.py

# Phase 2: world model. Gate: val_pred / val_copy < 1.0
run.bat scripts/train_wm.py

# Phase 3: MPC agent in Crafter. Gate: success >= 50%, achievements > random
run.bat scripts/play.py

# Phase 4: real Minecraft (needs MineRL — see docs/02_setup.md)
play_ebwm.bat
```

### Reproduce attempt #20 (the campaign's closing measurement)

Fully offline — no MineRL, no Java, no checkpoint modified:

```bash
run.bat scripts/diagnose_context_collapse.py --config configs/diagnose_context_collapse.yaml
```

---

## Project structure

```
mine_jepa/              ← Python package
  encoder/              ← CrafterJEPA, EMA, VICReg, datasets (Phases 1–3)
  predictor/            ← ActionConditionedPredictor
  planning/             ← LatentMPCPlanner (random-shooting)
  policy/               ← BCPolicy, BCCNNPolicy (Phase 4 ablations)
  ebwm/                 ← Action-conditioned JEPA assembly, planner, frontier, hazard, depth
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
  play_craft.py         ← Phase 5+: cold-start agent (frontier, hazard, commit_length)
  diagnose_*.py         ← The cold-start campaign's offline diagnostics
  collect_minerl_multi.py  ← MALMOBUSY workaround: 1 process/episode
  build_site.py         ← Generates the learning site from site/content/

configs/                ← YAML hyperparameters (no hardcoded values)
docs/                   ← Pedagogy + technical notes
site/                   ← The learning site (content/ = Markdown source, fr|en/ = generated)
assets/                 ← GIFs, demo videos, diagnostic outputs
```

---

## Phase 4 deep-dive: what worked and what didn't

Porting from Crafter to real Minecraft (MineRL Treechop) took 5 attempts:

| Approach | Description | Result |
|----------|-------------|--------|
| 1 | MPC + 1-step WM (flat vector) | reward = 0 — planner blind on near-static frames |
| 2 | MPC + residual WM | reward = 0 — same root cause |
| 3 | Behavioural cloning (frozen encoder) | reward = 0 — covariate shift, agent stuck |
| 4 | End-to-end BC CNN | reward = 0 — no memory, no sustained attack |
| **5** | **eb-JEPA action-conditioned MPC** | **chops trees — 25–50% across draws** ✅ |

**Key insight:** flat 128-d latent vectors lose spatial information (where is the trunk?). Switching to spatial latent maps `[64, 8, 8]` + action-conditioned joint training unlocked the planner.

**Second key insight, found twice:** planning every 4 steps and *repeating* the action produces the sustained attack physically required to chop a log. Without it, reward = 0. The same principle reappeared independently in Phase 5+ as `commit_length`, the cold-start campaign's only working lever — and attempt #20 later explained why deciding less often helps.

**A lesson that cost real time:** the recipe, not the latent size, is the lever. Over-training (T=12/25 epochs → ratio ~0.88) breaks the agent at any embedding size. A *lower* prediction ratio is not better.

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
| eb-JEPA training (Phase 4) | RTX 5060 Ti 8 GB | ~35 min / 20 epochs |
| MPC play (Crafter) | CPU or GPU | ~1 min / episode |
| MPC play (MineRL) | RTX 5060 Ti 8 GB | ~3 min / episode |

### Model sizes

| Component | Parameters |
|-----------|-----------|
| Crafter JEPA encoder, Phases 1–3 (ResNet5) | ~15M |
| Crafter action predictor (MLP) | ~140K |
| **eb-JEPA agent, Phases 4–5 — encoder** | **156,512** |
| **eb-JEPA agent — ACConvPredictor** | **507,008** |
| **eb-JEPA agent — action encoder** | **272** |
| **eb-JEPA agent — total (`ebwm.pt`)** | **663,792** |

The agent that plays real Minecraft is the 664K one. It is small enough to train in ~35 minutes on a consumer GPU, which is the whole point — and, per attempt #20, small enough that its dynamics do not usefully depend on the action.

---

## Self-supervised vs supervised computer-use agents

A genuine differentiator of the approach: **zero human annotation**.

Current computer-use agents (Claude Computer Use, UI-TARS, OpenAI CUA) are trained via supervised fine-tuning on millions of `(screenshot, correct_action)` pairs annotated by humans. Mine-JEPA learns from raw trajectories only:

```
(frame_t, frame_{t+1})           → JEPA encoder (no label needed)
(frame_t, action_t, frame_{t+1}) → world model  (action recorded, not judged)
```

Any gameplay video is a valid training dataset: no labelling pipeline, scales with more video, nothing sent to external servers. Full analysis: [`docs/07_cua_landscape_june2026.md`](docs/07_cua_landscape_june2026.md).

---

## The learning site

**[https://reddwarf03.github.io/mine-jepa/](https://reddwarf03.github.io/mine-jepa/)** — 20 chapters written directly from this repository's research log.

- **Dual-track**: switch between **Beginner** (analogies, visual intuition) and **Expert** (equations, gates, actual numbers) at any time.
- **Bilingual**: [English](https://reddwarf03.github.io/mine-jepa/en/index.html) and [Français](https://reddwarf03.github.io/mine-jepa/fr/index.html).
- **Unfiltered**: negative results stay negative. Chapter 18 documents a result that was retracted the same session it was found; chapter 20 closes the campaign on its own diagnosis.

Run it locally:

```bash
python -m http.server 8000
# → http://localhost:8000/site/index.html
```

Rebuild it after editing `site/content/`:

```bash
run.bat scripts/build_site.py
```

---

## Docs

| Document | Content |
|----------|---------|
| [`docs/01_jepa.md`](docs/01_jepa.md) | What is JEPA — components, collapse, planning |
| [`docs/02_setup.md`](docs/02_setup.md) | Installation (Crafter + MineRL + Java 8) |
| [`docs/03_representation_collapse.md`](docs/03_representation_collapse.md) | Collapse detection, EMA, VICReg |
| [`docs/04_world_model.md`](docs/04_world_model.md) | WM architecture, action-conditioning, eval |
| [`docs/05_planning.md`](docs/05_planning.md) | Random-shooting MPC, goal embedding |
| [`docs/06_minecraft_port.md`](docs/06_minecraft_port.md) | MineRL port — 5 approaches, MALMOBUSY bug |
| [`docs/07_cua_landscape_june2026.md`](docs/07_cua_landscape_june2026.md) | CUA landscape, JEPA positioning |
| [`docs/08_crafting.md`](docs/08_crafting.md) | Teaching the WM to craft: v3 fails → v4 inventory-as-state → preconditions |
| [`docs/09_curiosity_coldstart.md`](docs/09_curiosity_coldstart.md) | Cold-start attempt #1 — a diagnosed negative result |
| [`docs/10_coldstart_engineering.md`](docs/10_coldstart_engineering.md) | Cold-start attempts #2–#20 and the campaign's closure |
| [`docs/references/index.md`](docs/references/index.md) | Annotated bibliography — implemented, read, or explicitly rejected |
| [`PLAN.md`](PLAN.md) | Full project plan with gates and phases |

---

## Key papers

Full annotated bibliography, with implementation notes and rejection reasons: [`docs/references/index.md`](docs/references/index.md). Every arXiv ID there is verified against the live abstract page.

| Paper | Role in mine-jepa |
|---|---|
| LeCun 2022 — *A Path Towards Autonomous Machine Intelligence* | Original JEPA concept |
| Assran et al. CVPR 2023 — I-JEPA ([2301.08243](https://arxiv.org/abs/2301.08243)) | Encoder architecture |
| Bardes et al. 2022 — VICReg ([2105.04906](https://arxiv.org/abs/2105.04906)) | Anti-collapse regularisation |
| Meta FAIR — [eb_jepa](https://github.com/facebookresearch/eb_jepa) | **Our backbone** (vendored, action-conditioned) |
| Maes et al. 2026 — LeWorldModel ([2603.19312](https://arxiv.org/abs/2603.19312)) | World model design + the `ratio` gate |
| Terver et al. 2025 — *What Drives Success in Physical Planning with JEPA World Models?* ([2512.24497](https://arxiv.org/abs/2512.24497)) | MPC planning design |
| **Gan et al. 2026 — ActSWM ([2607.26712](https://arxiv.org/abs/2607.26712))** | **Names *Context Collapse* and motivated attempt #20's measurement. Same architecture family as this project, on Minecraft, with better results — read this before concluding anything from our numbers.** |
| Lee et al. 2018 — Mahalanobis OOD ([1807.03888](https://arxiv.org/abs/1807.03888)) | Attempt #17 — the untrained detector that still hit the brightness confound |
| Burda et al. 2018 — RND ([1810.12894](https://arxiv.org/abs/1810.12894)) | Cold-start exploration — **tried, negative** |
| Sekar et al. 2020 — Plan2Explore ([2005.05960](https://arxiv.org/abs/2005.05960)) | Cold-start exploration — **tried offline, failed**: the ensemble collapsed on frozen demos |
| Assran et al. 2025 — V-JEPA 2 ([2506.09985](https://arxiv.org/abs/2506.09985)) | Studied; **not used** (OOD on Minecraft, 600M params) |

---

## Status

**Phases 0–5 complete. The Phase 5+ cold-start campaign is closed, unsolved, and documented.**

The project is not under active research development. The mechanisms that work
(`commit_length=4`, `FrontierTracker` coverage search, hazard avoidance) are the standing baseline;
`checkpoints/ebwm.pt` (md5 `ac14e65361fbddeb057963362ea1382d`) is the released agent and was never
modified during the campaign.

If you want to pick this up, the best-motivated next step is **not** another planner fix. It is
rebuilding the world model so that its rollouts actually depend on the action — an inverse-dynamics
readout term (half the machinery already exists in `mine_jepa/eb_jepa/losses.py`, disabled since
day one) plus a context length greater than 1. Start from
[`docs/10_coldstart_engineering.md`](docs/10_coldstart_engineering.md) and
[ActSWM](https://arxiv.org/abs/2607.26712).

---

## Acknowledgements

- **Meta FAIR** for the [`eb_jepa`](https://github.com/facebookresearch/eb_jepa) codebase (vendored in `mine_jepa/eb_jepa/`)
- **MineRL** team for the environments and the Zenodo human demonstrations
- **Crafter** (Hafner 2021) for the lightweight test environment
- **ESANN 2025** paper `ES2025-19.pdf` for the VICReg anti-collapse recipe

---

## License

MIT — see [`LICENSE`](LICENSE).

The vendored `mine_jepa/eb_jepa/` code is from Meta FAIR under its original license (Apache 2.0).

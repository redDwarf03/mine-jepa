# Mine-JEPA — A JEPA agent playing Minecraft from pixels

> **Self-contained document.** All necessary context is here. The conversation context can
> be cleared/compacted: this file is the single source of truth.

---

## 1. Context & objective (the "why")

**Who**: a developer discovering JEPA. Doesn't know the subject yet → **the project is
also a learning journey**.

**Dual objective (validated with the user)**:
1. **Learn JEPA in depth** by building it.
2. **Ship a visible project** on the AI scene: clonable demo + shareable video.
   Strategy = **spectacular integration** (leveraging existing open-source building blocks)
   rather than from-scratch research.

**Why this project is not pointless (state of the art, June 2026)**:
- **Open slot on the packaging side**: the *capability* of JEPA-from-pixels already exists
  in research (LeWorldModel, March 2026; Sub-JEPA, May 2026), but **nobody has shipped a
  public, clonable, spectacular demo** of "JEPA plays a game". The green field is in
  **application + packaging**, not in architecture.
- **Novel brand collision**: "JEPA + Minecraft" rides two waves (LeCun's world-models +
  the AI-Minecraft lineage VPT/Voyager/Dreamer). Never published.
- **Demo-friendly**: an agent that *plays* is one of the rare JEPA outputs that is truly
  **visible** (JEPA produces invisible latent embeddings by default — you MUST attach it
  to something that acts on screen).

**Honest caveats built in**:
- We're NOT aiming to "beat Meta" or write a research paper. We *apply + package*.
- Realistic goal = **recognition in the AI niche** + strong portfolio + real learning.
- Non-negotiable constraint: **it must run on consumer GPU and be easy to clone-and-run**,
  otherwise no distribution.

---

## 2. What is JEPA? (pedagogical foundation — to become `docs/01_jepa.md`)

JEPA = **Joint-Embedding Predictive Architecture** (Yann LeCun, 2022). Core idea:
- A **context-encoder** encodes what we see (e.g. last 3 frames) → latent vector `s_x`.
- A **target-encoder** (EMA copy, gradient blocked) encodes what we want to predict (next
  frames) → `s_y`.
- A **predictor** predicts `ŝ_y` from `s_x` (+ optionally an **action**).
- **Loss = distance in latent space** between `ŝ_y` and `s_y` (NO pixel reconstruction).

**Why it's clever**: a generative model exhausts itself predicting every pixel (ground
texture, background sheep). JEPA predicts only **abstract structure** ("if I hit this
block, it breaks") and **ignores irrelevant details**. More efficient, more robust.

**Trap #1 = collapse**: if encoder + predictor learn to map everything to a constant,
loss drops to 0 but the model learned nothing (embedding variance → 0).
**Countermeasures** (see `ES2025-19.pdf` already in the repo, *JEPA for RL*, ESANN 2025):
- target-encoder via **EMA** (θ̄ ← 0.99·θ̄ + 0.01·θ) with gradient blocked on target side;
- **variance/covariance regularization (VICReg)**: force embedding variance above threshold;
- (in RL) let task gradients flow through the encoder.

**Action-conditioned world model**: inject action `a_t` into the predictor → it predicts
the **next latent state** `ŝ_{t+1}`. Chaining these, we **imagine the future in latent
space**. We can then **plan**: simulate several action sequences in latent space, keep
the one that brings us closest to the goal. This is exactly what V-JEPA 2-AC does for robots.

---

## 3. Reused building blocks (DO NOT reinvent)

| Block | Role | Source |
|---|---|---|
| `facebookresearch/eb_jepa` | Official JEPA examples **with action-conditioned video + planning** — most direct starting point | github.com/facebookresearch/eb_jepa |
| `facebookresearch/vjepa2` (torch.hub) | Pre-trained V-JEPA 2 encoder + AC predictor (`vjepa2_ac_vit_giant`) — "pro"/comparison mode | github.com/facebookresearch/vjepa2 |
| **LeWorldModel (LeWM)** | Stable JEPA end-to-end **from pixels, ~15M params**, 2D/3D control → ideal for consumer GPU. **Check code availability in Phase 0** | arXiv 2603.19312 |
| `ES2025-19.pdf` (in repo) | JEPA→RL recipe + VICReg anti-collapse | ESANN 2025 |
| **Crafter** | Lightweight Minecraft clone, `pip install`, runs anywhere → **de-risking testbed** | github.com/danijar/crafter |
| **MineRL** | Real Minecraft, VPT action space (keyboard/mouse) → **the spectacular final demo** | minerllabs/minerl |

**Architecture decision**: primary backbone = **lightweight JEPA LeWM-style (~15M) trained
on the game** (clonable + pedagogical + proven by LeWM). Secondary/stretch mode = plug in
**frozen V-JEPA 2** for comparison. Reason: "clonable on consumer GPU" + "you learn by
building it" outweigh the raw power of V-JEPA giant (heavy + OOD on Minecraft).

**Environment decision**: **Crafter first** (JEPA pipeline validated quickly, runs
anywhere), **MineRL second** (the real Minecraft visuals = the brand that generates buzz).

---

## 4. Execution plan by phases (each phase = one visible deliverable + one pedagogical doc)

> Driven by **gates**: we only move to the next phase if the criterion is met.
> Each phase produces (a) a **visible** artifact (for the demo) and (b) a **pedagogical**
> doc (for your learning AND the project's viral documentation).

### Phase 0 — Foundations & scaffolding
- Scaffold repo: `mine_jepa/` (code), `docs/` (pedagogy), `scripts/`, `configs/`, `assets/`.
  Python env (uv or conda), PyTorch, timm, einops. Minimal CI.
- Install **Crafter**, capture frames + actions, run a random agent → **first video**.
- Check **LeWM** code availability; clone `eb_jepa` and run an example.
- 📚 **Pedagogy**: `docs/01_jepa.md` (section 2 above, explained) + `docs/02_setup.md`.
- 🎬 **Visible**: GIF of a random agent in Crafter + architecture diagram.
- ✅ **GATE**: env runs, `(frames, actions)` pipeline captured, eb_jepa executed.

### Phase 1 — JEPA representation (encoder without collapse)
- Implement/adapt a **JEPA encoder** (LeWM or eb_jepa style) trained self-supervised on
  game frames. EMA target + **VICReg** anti-collapse.
- **Linear-probe**: train a linear classifier on frozen embeddings to predict a game state
  (inventory, nearby objects) → proves the embedding captures meaning.
- 📚 **Pedagogy**: `docs/03_representation_collapse.md` (collapse, EMA, VICReg, variance curves).
- 🎬 **Visible**: PCA/t-SNE projection of latent **colored by game state** → "the model
  learned structure with zero labels". (Excellent narrative visual.)
- ✅ **GATE**: linear-probe > random baseline; embedding variance healthy (no collapse).

### Phase 2 — Action-conditioned world model (the core)
- Train the **predictor**: `s_t` + `a_t` → `ŝ_{t+1}` in latent space. Projected action +
  added to hidden (ESANN recipe). Validate latent prediction error **1-step AND multi-step**
  vs "copy current state" baseline.
- 📚 **Pedagogy**: `docs/04_world_model.md` (action-conditioning, latent rollout, why
  predicting latents > predicting pixels).
- 🎬 **Visible — THE spectacular hook**: "**the AI imagines Minecraft's future in its
  head**". Unroll world-model in latent for K steps and visualize via **nearest-neighbor
  retrieval of real frames** (or a mini-decoder trained *only* for viz).
- ✅ **GATE**: multi-step latent error clearly < copy baseline; no collapse.

### Phase 3 — Playing agent (latent planning)
- **MPC/CEM planning in latent space** toward an **image-goal** (target capture):
  sample action sequences, unroll world-model, score by distance to goal, execute first
  action, re-plan (receding horizon). Reuse `eb_jepa` planning logic.
- Short verifiable tasks: go to a visible object, pick up wood, descend N cells.
- (Stretch) policy learned **in imagination** (Dreamer-style) for reward tasks.
- 📚 **Pedagogy**: `docs/05_planning.md` (CEM/MPC, image-goal, planning in latent space).
- 🎬 **Visible — THE VIRAL ASSET**: video of the agent **playing from pixels**.
- ✅ **GATE**: ≥ 1 task reliably achieved over N episodes.

### Phase 4 — Port to real Minecraft
- Port the pipeline from Crafter → **MineRL** (real Minecraft visuals = the brand).
  Retrain predictor/encoder on MineRL frames.
- Demo polish: split-screen "**JEPA imagines vs reality**" + "JEPA plays Minecraft,
  it learned its own world model".
- 📚 **Pedagogy**: `docs/06_minecraft_port.md` (MineRL, VPT action space, install pitfalls).
- ✅ **GATE**: runs on consumer GPU, reproducible (seed + configs).

### Phase 5 — Viral packaging
- **README** with GIFs/video at top, 2-line pitch, **one-command install** (Docker +
  Colab notebook for those without GPU), weights on Hugging Face.
- **Storytelling**: X thread/blog "I made an AI play Minecraft with LeCun's architecture
  (JEPA), from pixels, without image generation". The `docs/0X_*.md` pedagogical docs
  **become** the "how it works" content (your learning = your marketing).
- (Narrative bonus) micro-comparison vs an LLM/VLM playing the same task → angle
  "JEPA faster/cheaper per action".
- ✅ **GATE**: a stranger clones and gets a demo in < 15 min (or via Colab with nothing to install).

---

## 5. Risks (honest) & mitigations

- **R1 — Collapse** (JEPA's #1 pitfall). → EMA target + VICReg; monitor variance from Phase 1.
- **R2 — OOD perception** (V-JEPA = natural video; game = synthetic). → We train a JEPA
  *on the game* (LeWM-style), not frozen V-JEPA as primary; linear-probe Phase 1 = gate.
- **R3 — Real-time throughput** (encoder + CEM). → lightweight model ~15M, downsampled
  frames, short rollouts, encoding cache. Crafter first (lightweight).
- **R4 — MineRL install** (JDK8, Zenodo mirrors). → Crafter validates everything first;
  MineRL in Phase 4.
- **R5 — Demo "doesn't work" = no buzz.** → Strict gates: we only package (Phase 5) if
  the agent truly succeeds (Phase 3). No hype over nothing.
- **R6 — LeWM code unavailable.** → Fallback: eb_jepa (official action-conditioned +
  planning) as base; verified in Phase 0.

---

## 6. Verification (how we'll know it works)

- Phase 0: `scripts/collect.py` produces a `(frames, actions)` dataset + random agent GIF.
- Phase 1: `scripts/probe.py` → linear-probe accuracy > threshold; variance log (anti-collapse).
- Phase 2: `scripts/eval_wm.py` → latent error curve 1/k-step vs copy baseline + imagination viz.
- Phase 3: `scripts/play.py` → task success rate over N episodes + videos.
- Phase 4: same on MineRL, on consumer GPU.
- Phase 5: "clone-and-run" test by a third party / Colab.

---

## 7. First concrete iteration (at startup)

**Phase 0**: repo scaffold + install Crafter + `scripts/collect.py` (frames+actions+GIF) +
`docs/01_jepa.md` (pedagogy) + check LeWM code availability & run an eb_jepa example.
This is the foundation that validates tooling before any training.

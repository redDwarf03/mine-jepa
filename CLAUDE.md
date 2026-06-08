# Mine-JEPA — Instructions for Claude Code

## What this project is (1 line)
A JEPA agent that plays Minecraft from pixels — spectacular packaging of existing
open-source building blocks, not from-scratch research. Full plan: `PLAN.md`.

## Architecture rules — DO NOT deviate without discussion
- **Backbone**: lightweight JEPA ~15M params trained *on the game* (LeWorldModel / eb_jepa style).
  **DO NOT** use frozen V-JEPA 2 as primary (heavy, OOD on Minecraft, not clonable
  on consumer GPU).
- **Env**: **Crafter first** (lightweight, pip install, validates the pipeline), **MineRL second**
  (Phase 4, real Minecraft visuals = the brand).
- **Building blocks to reuse** (do not reinvent):
  - `facebookresearch/eb_jepa` — action-conditioned + official JEPA planning
  - `facebookresearch/vjepa2` via torch.hub — secondary/comparison only
  - LeWorldModel (arXiv 2603.19312) — check availability in Phase 0
  - Anti-collapse VICReg: recipe in `ES2025-19.pdf` (ESANN 2025, in the repo)

## Risk #1: COLLAPSE
JEPA is **prone to collapse** (all embeddings → constant, variance → 0, loss → 0
but the model learned nothing). **Always**:
- target-encoder via EMA (θ̄ ← 0.99·θ̄ + 0.01·θ), gradient blocked
- VICReg regularization on embedding variance
- monitor `batch_var` each epoch — if < 1e-6: collapse in progress

## Current phase
**PHASE 4 — Port to real Minecraft (MineRL)** (see PLAN.md §4). Phases 0→3 complete ✅.

Phase 0 — gates validated:
- [x] Python env running + Crafter installed
- [x] `scripts/collect.py` → 33,406 transitions (frames, actions, health, food, drink, energy) + GIF
- [x] `mine_jepa/eb_jepa/` — Meta code vendored, importable, smoke test OK
- [x] `docs/01_jepa.md` + `docs/02_setup.md` written

Phase 1 — gates validated ✅:
- [x] `scripts/train_encoder.py` → 30 epochs GPU RTX 5060 Ti — val_loss=0.080, batch_var=1.13
- [x] `batch_var` > 1e-4 — measured 1.178 at probe (no collapse)
- [x] `scripts/probe.py` → linear-probe health: 90.8% vs baseline 86.9% (+3.8%) ✅
- [x] `docs/03_representation_collapse.md` written

Phase 2 — gates validated ✅:
- [x] `scripts/train_wm.py` → 30 epochs GPU — val_pred=0.033 vs val_copy=0.086 (ratio=0.38)
- [x] 1-step latent error < baseline: ratio 0.367 ✅
- [x] `scripts/eval_wm.py` → multi-step 10/10 k below baseline (ratio ~0.38 stable) ✅
- [x] `docs/04_world_model.md` written

Phase 3 — gates validated ✅:
- [x] `scripts/play.py` → MPC latent agent in Crafter (random-shooting, horizon=12, N=512)
- [x] 100% success rate, 2.56 achievements/ep vs 2.38 random (+7.5%), reward +14%
- [x] GIF saved: `assets/agent_play.gif`
- [x] `docs/05_planning.md` written

Phase 4 gates:
- [x] MineRL installed and env running (`import minerl` OK, 33 envs including MineRLTreechop-v0) ✅
- [x] `docs/06_minecraft_port.md` written ✅
- [x] `scripts/collect_minerl_multi.py --shards 15` → 119,852 MineRL transitions ✅
- [x] JEPA encoder retrained on MineRL: val_loss=0.0528, batch_var=1.168 (no collapse) ✅
- [x] World model retrained on MineRL: val_pred=0.0329 < val_copy=0.0334 (ratio=0.983) ✅
- [x] eb-JEPA WM v2 retrained on human demos (453k Zenodo): best ratio=0.890 @ epoch 25, batch_var=1.26 (no collapse) ✅
- [x] **4 approaches tested, only eb-JEPA works: 50% success, reward 0.75/ep** ✅
  - Approach 1-2: MPC + 1-step WM (ratio ≈0.96) → reward 0 (planner blind on static frames)
  - Approach 3: BC frozen encoder + head → reward 0 (covariate shift, agent frozen on 1 action)
  - Approach 4: BC CNN end-to-end → reward 0 (no memory, no sustained attack possible)
  - **Approach 5: eb-JEPA action-conditioned MPC → 50% success, reward 0.75/ep ✅**
- [ ] `scripts/play_minerl_multi.py --episodes 20` → agent plays real Minecraft (MALMOBUSY bug workaround)
  - ⚠️ DO NOT use `scripts/play.py --env minerl` with episodes > 1 (blocks on reset)

⚠️ Phase 4 on **NVIDIA PC only**. MineRL requires Java 8.
Installation: DO NOT use `uv pip install minerl` directly.
See complete procedure below (patches gym + minerl + Gradle).

MineRL installation notes (Windows/Python 3.12):
- `gym==0.19.0`: patch `opencv-python>=3.0` in setup.py (download source, patch, install)
- `minerl`: build from patched source `C:\tmp\minerl_src\minerl-0.4.4\`
  - `setup.py`: `shell=True` for gradlew.bat + copy pre-built JAR
  - `build.gradle`: replace MixinGradle JitPack with `org.spongepowered:mixingradle:0.6-SNAPSHOT`
  - Initial Gradle build: run via `C:\tmp\run_gradle.bat` (Java 8 required)
- Java 8: `choco install temurin8` (admin) → `C:\Program Files\Eclipse Adoptium\jdk-8.0.472.8-hotspot`

Windows PC notes:
- Always use `run.bat <script>` (wrapper PYTHONUTF8=1 + PYTHONUNBUFFERED=1)
- torch CUDA 12.8 installed manually (uv sync installs CPU by default)

## Code conventions
- Python 3.11+, PyTorch 2.x, timm, einops
- `uv` for package management (lockfile in `uv.lock`)
- Configs in YAML in `configs/` (no hardcoded hyperparams in code)
- Standalone scripts in `scripts/` (each script = one verifiable deliverable)
- Type hints everywhere, no obvious comments

## Embedded pedagogy (learning objective)
The user is **discovering JEPA** — they don't know the subject. For each new concept
introduced in the code: explain the *why* in conversation and point to the corresponding
`docs/0X_*.md` doc. The pedagogical docs = also the project's marketing content.

## Hardware
- **Dev**: MacBook Air M1, 16 GB RAM, **no NVIDIA GPU** → OK for writing code,
  collecting data, testing imports. Too slow for training.
- **Training**: PC with **NVIDIA GPU 8 GB VRAM**, 32 GB RAM → switch BEFORE running
  `train_encoder.py` (Phase 1), `train_wm.py` (Phase 2), `play.py` (Phase 3+).
- **Transfer**: `git push` from Mac → `git clone` + `uv pip install -e .` on PC.

## Python environment
Always prefix with `uv run` (uses the uv-managed venv):
```bash
uv run python scripts/collect.py ...
uv run pytest
```

## Useful commands
```bash
# Collect trajectories (frames + actions) from Crafter
uv run python scripts/collect.py --env crafter --episodes 100 --out data/crafter/

# Linear-probe (Phase 1 gate)
uv run python scripts/probe.py --data data/crafter/ --checkpoint checkpoints/encoder.pt

# Evaluate world model (Phase 2 gate)
uv run python scripts/eval_wm.py --checkpoint checkpoints/wm.pt --steps 10

# Run the agent (Phase 3 gate)
uv run python scripts/play.py --env crafter --task reach_plant --episodes 50
```

## Repo structure
```
mine_jepa/        ← Python source code (encoder, predictor, planner, agent)
scripts/          ← standalone verifiable scripts (collect, probe, eval_wm, play)
configs/          ← YAML hyperparams
docs/             ← pedagogy + marketing
  01_jepa.md      ← What is JEPA (to learn + for the README)
  02_setup.md     ← How to install and run
  03_representation_collapse.md
  04_world_model.md
  05_planning.md
  06_minecraft_port.md
data/             ← datasets (gitignore)
checkpoints/      ← weights (gitignore, then HuggingFace)
assets/           ← GIFs, videos for the README
```

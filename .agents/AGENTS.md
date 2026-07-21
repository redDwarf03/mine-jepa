# Mine-JEPA — Project Rules & Guidelines for Gemini Agents

## Project Overview
Mine-JEPA is a Joint-Embedding Predictive Architecture (JEPA) agent that learns to play Minecraft from pixels using open-source building blocks (not from-scratch research).
Full plan: `PLAN.md`. Project log & ground truth: `CLAUDE.md`.

---

## Architecture Rules — DO NOT deviate without discussion
- **Backbone**: Lightweight JEPA ~15M params trained *on the game* (LeWorldModel / eb_jepa style).
  **DO NOT** use frozen V-JEPA 2 as primary (heavy, OOD on Minecraft, not clonable on consumer GPU).
- **Environment**: **Crafter first** (lightweight, pip install, validates pipeline), **MineRL second** (Phase 4, real Minecraft visuals).
- **Building Blocks to Reuse**:
  - `facebookresearch/eb_jepa` — action-conditioned + official JEPA planning
  - `facebookresearch/vjepa2` via `torch.hub` — secondary/comparison only
  - LeWorldModel (arXiv 2603.19312)
  - Anti-collapse VICReg: recipe in `ES2025-19.pdf` (ESANN 2025, in repo)

---

## Risk #1: COLLAPSE
JEPA is **prone to collapse** (all embeddings → constant, variance → 0, loss → 0 but model learned nothing).
**Always**:
- Target-encoder via EMA ($\bar{\theta} \leftarrow 0.99 \cdot \bar{\theta} + 0.01 \cdot \theta$), gradient blocked.
- VICReg regularization on embedding variance (`std_coeff`, `cov_coeff`).
- Monitor `batch_var` each epoch — if `< 1e-6`: collapse in progress (`batch_var > 1e-4` is required).

---

## Non-Negotiable Hard Rules (Project-Wide)
1. **NEVER run any git command** (`git add`, `git commit`, etc.) — leave all changes in the working tree uncommitted unless explicitly instructed.
2. **NEVER run `taskkill`, `Stop-Process`, or any process-killing command** for any reason.
3. **NEVER launch a second copy of the same eval/play script** without confirming via process listing (`Get-CimInstance Win32_Process`) that earlier copies have actually exited. Concurrent MineRL play scripts corrupt each other's Minecraft instances.
4. **NEVER overwrite a good checkpoint**. `scripts/train_eb_jepa.py` overwrites `checkpoints/ebwm.pt`. Back up current good checkpoints before training (e.g., `ebwm_backup_<date>.pt`).
5. **SEED EVERYTHING** trained (`torch.manual_seed`, `numpy`, CUDA deterministic).
6. **The proxy metric lies**: Lower WM `ratio` (`val_pred/val_copy`) does NOT mean a better agent. Recipe $T=8$/20ep ($\text{ratio} \approx 0.93$) is the sweet spot. Over-training ($\text{ratio} \approx 0.88$) breaks the planner. Judge by real cold-start play gates.
7. **Site build & Last Updated Date**: Whenever modifying site content or code, always execute `python scripts/build_site.py` to regenerate `site/fr/` and `site/en/` pages. `scripts/build_site.py` automatically updates the last publication date at the top of every site page.

---

## Environment & Commands (Windows + NVIDIA GPU)
- Always run Python scripts through the wrapper: `run.bat scripts/<x>.py ...` (sets `PYTHONUTF8=1` and `PYTHONUNBUFFERED=1`).
- Equivalent raw execution: `uv run python scripts/<x>.py ...`.
- Configs are stored in YAML inside `configs/` — **no hardcoded hyperparams in code**.
- Code conventions: Python 3.11+, PyTorch 2.x, timm, einops, `uv` package manager. Type hints everywhere.

---

## Project Roles & Skills
The project utilizes specialized agent roles defined in `.agents/skills/`:
- **`jepa-developer`**: Implements proposals & fixes, runs training, respects guardrails.
- **`jepa-explainer`**: Writes dual-track pedagogical tutorials (`beginner` & `expert`) in French (`site/content/fr/`).
- **`jepa-explorer`**: Read-only research explorer proposing cold-start curiosity experiments.
- **`jepa-tester`**: Runs gates & play evals, reporting honest verdicts & statistical variance.
- **`jepa-webdesigner`**: Builds static pixel-art / Minecraft-themed tutorial site (`site/`).
- **`jepa-loop`**: Orchestrates the Explore $\rightarrow$ Develop $\rightarrow$ Test loop.
- **`explain-jepa`**: Explains JEPA concepts with concrete analogies & code links.
- **`gate-check`**: Checks phase deliverables and gates.
- **`phase-status`**: Reports repo status, checkpoints, datasets, and current phase.

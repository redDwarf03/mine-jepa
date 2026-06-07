# Installation & Getting Started

> This guide assumes macOS or Linux, Python 3.12, and a GPU (NVIDIA recommended,
> CPU possible for testing but too slow for training).

---

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (package manager)
- Git
- NVIDIA GPU (RTX 3080+ recommended for training in reasonable time)

---

## Installation in 3 commands

```bash
git clone https://github.com/redDwarf03/mine-jepa.git
cd mine-jepa
uv pip install -e ".[dev]"
```

This installs: PyTorch, Crafter, timm, einops, and all project dependencies.

> **Why `uv`?** It's the fastest Python packaging tool in 2026 (Rust-based).
> It manages a local virtualenv in `.venv/`. Always prefix commands with `uv run`.

---

## Verify installation

```bash
uv run python -c "import crafter, timm, einops, torch; print('OK', torch.__version__)"
```

Expected: `OK 2.x.x`

---

## Collect data (Phase 0)

Run a random agent in Crafter and save trajectories:

```bash
uv run python scripts/collect.py
```

Outputs:
- `data/crafter/episodes.npz` — `(frames, actions)` dataset, ~4 MB for 200 episodes
- `assets/random_agent.gif` — random agent visualization

Options:
```bash
uv run python scripts/collect.py --episodes 500 --out data/crafter
```

---

## Check the current phase gate

```bash
# In a Claude Code session (after restarting):
/gate-check
```

Or manually:
```bash
uv run python -c "import numpy as np; d = np.load('data/crafter/episodes.npz'); print(d['frames'].shape, d['actions'].shape)"
```

---

## Project structure

```
mine-jepa/
├── mine_jepa/              ← Python source code
│   ├── eb_jepa/            ← Official Meta building blocks (JEPA, CEM, VICReg)
│   ├── encoder/            ← Encoder adaptations for Crafter/MineRL
│   ├── predictor/          ← Discrete action-conditioned predictor
│   ├── planning/           ← MPC agent
│   └── agent/              ← Full agent loop
├── scripts/
│   ├── collect.py          ← Collect trajectories (Phase 0)
│   ├── probe.py            ← Linear-probe (Phase 1 gate)
│   ├── eval_wm.py          ← Evaluate world model (Phase 2 gate)
│   └── play.py             ← Run the agent (Phase 3 gate)
├── configs/                ← YAML hyperparameters
├── docs/                   ← Pedagogy (you are here)
├── assets/                 ← GIFs and videos for the README
├── data/                   ← Datasets (gitignored)
└── checkpoints/            ← Model weights (gitignored → HuggingFace)
```

---

## Command reference

| Command | Description | Phase |
|---|---|---|
| `uv run python scripts/collect.py` | Collect trajectories | 0 |
| `uv run python scripts/probe.py` | Linear-probe on embeddings | 1 |
| `uv run python scripts/eval_wm.py` | Evaluate world model | 2 |
| `uv run python scripts/play.py` | Run the playing agent | 3 |
| `uv run pytest` | Unit tests | all |
| `/gate-check` *(Claude Code)* | Check current phase gates | all |
| `/phase-status` *(Claude Code)* | Current phase status | all |
| `/explain-jepa <concept>` *(Claude Code)* | Explain a JEPA concept | all |

---

## FAQ

**Q: Can I train without a GPU?**  
Yes, but the ResNet5 encoder on Crafter takes ~10× longer on CPU. For testing phases,
it's feasible. For full training (~50K steps), expect a few hours on CPU vs ~20 min
on an RTX 3080.

**Q: Why Crafter and not Minecraft directly?**  
Crafter is a 2D Minecraft clone (`pip install crafter`, ~1 MB) that runs without Java,
without MineRL, without JDK8. We validate the entire JEPA pipeline on it, then port to
real Minecraft (MineRL) in Phase 4 once the architecture is stable.

**Q: What is eb_jepa in `mine_jepa/eb_jepa/`?**  
It's Meta/FAIR's official JEPA library, vendored into our project (to avoid Python
compatibility issues). It contains the core: `JEPA`, `JEPAProbe`, `CEMPlanner`,
`MPPIPlanner`, `VICRegLoss`. We don't modify it — we use it.

# Installation & premiers pas

> Ce guide suppose macOS ou Linux, Python 3.12, et une carte GPU (NVIDIA recommandé,
> CPU possible pour les tests mais trop lent pour l'entraînement).

---

## Prérequis

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (gestionnaire de packages)
- Git
- GPU NVIDIA (RTX 3080+ recommandé pour entraîner en temps raisonnable)

---

## Installation en 3 commandes

```bash
git clone https://github.com/redDwarf03/mine-jepa.git
cd mine-jepa
uv pip install -e ".[dev]"
```

Ça installe : PyTorch, Crafter, timm, einops, et toutes les dépendances du projet.

> **Pourquoi `uv` ?** C'est l'outil de packaging Python le plus rapide en 2026 (Rust-based).
> Il gère un virtualenv local dans `.venv/`. Toujours préfixer les commandes avec `uv run`.

---

## Vérifier l'installation

```bash
uv run python -c "import crafter, timm, einops, torch; print('OK', torch.__version__)"
```

Attendu : `OK 2.x.x`

---

## Collecter des données (Phase 0)

Lance un agent aléatoire dans Crafter et sauvegarde les trajectoires :

```bash
uv run python scripts/collect.py
```

Outputs :
- `data/crafter/episodes.npz` — dataset `(frames, actions)`, ~4 Mo pour 200 épisodes
- `assets/random_agent.gif` — visualisation de l'agent aléatoire

Options :
```bash
uv run python scripts/collect.py --episodes 500 --out data/crafter
```

---

## Vérifier le gate de la phase courante

```bash
# Dans une session Claude Code (après avoir relancé) :
/gate-check
```

Ou manuellement :
```bash
uv run python -c "import numpy as np; d = np.load('data/crafter/episodes.npz'); print(d['frames'].shape, d['actions'].shape)"
```

---

## Structure du projet

```
mine-jepa/
├── mine_jepa/              ← code Python du projet
│   ├── eb_jepa/            ← briques officielles Meta (JEPA, CEM, VICReg)
│   ├── encoder/            ← adaptations encoder pour Crafter/MineRL
│   ├── predictor/          ← predictor action-conditionné discret
│   ├── planning/           ← agent MPC
│   └── agent/              ← boucle agent complète
├── scripts/
│   ├── collect.py          ← collecter des trajectoires (Phase 0)
│   ├── probe.py            ← linear-probe (gate Phase 1)
│   ├── eval_wm.py          ← évaluer le world model (gate Phase 2)
│   └── play.py             ← lancer l'agent (gate Phase 3)
├── configs/                ← hyperparamètres YAML
├── docs/                   ← pédagogie (tu es ici)
├── assets/                 ← GIFs et vidéos pour le README
├── data/                   ← datasets (gitignored)
└── checkpoints/            ← poids des modèles (gitignored → HuggingFace)
```

---

## Référence des commandes

| Commande | Description | Phase |
|---|---|---|
| `uv run python scripts/collect.py` | Collecter des trajectoires | 0 |
| `uv run python scripts/probe.py` | Linear-probe sur les embeddings | 1 |
| `uv run python scripts/eval_wm.py` | Évaluer le world model | 2 |
| `uv run python scripts/play.py` | Lancer l'agent qui joue | 3 |
| `uv run pytest` | Tests unitaires | toutes |
| `/gate-check` *(Claude Code)* | Vérifier les gates de la phase courante | toutes |
| `/phase-status` *(Claude Code)* | État de la phase en cours | toutes |
| `/explain-jepa <concept>` *(Claude Code)* | Expliquer un concept JEPA | toutes |

---

## FAQ

**Q : Puis-je entraîner sans GPU ?**  
Oui, mais l'encodeur ResNet5 sur Crafter prend ~10× plus de temps sur CPU. Pour les
phases de tests, c'est praticable. Pour l'entraînement complet (~50K steps), compte
quelques heures sur CPU vs ~20 min sur une RTX 3080.

**Q : Pourquoi Crafter et pas directement Minecraft ?**  
Crafter est un clone Minecraft 2D (`pip install crafter`, ~1 Mo) qui tourne sans Java,
sans MineRL, sans JDK8. On valide toute la pipeline JEPA dessus, puis on porte vers
le vrai Minecraft (MineRL) en Phase 4 quand l'architecture est stabilisée.

**Q : Qu'est-ce que eb_jepa dans `mine_jepa/eb_jepa/` ?**  
C'est la bibliothèque officielle de Meta/FAIR pour JEPA, copiée en vendored dans notre
projet (pour éviter les problèmes de compatibilité Python). Elle contient le cœur :
`JEPA`, `JEPAProbe`, `CEMPlanner`, `MPPIPlanner`, `VICRegLoss`. On ne la modifie pas —
on l'utilise.

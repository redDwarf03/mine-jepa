# Mine-JEPA — Instructions pour Claude Code

## Ce qu'est ce projet (1 ligne)
Agent JEPA qui joue à Minecraft depuis les pixels — packaging spectaculaire de briques
open-source existantes, pas de recherche from-scratch. Plan complet : `PLAN.md`.

## Règles d'architecture — NE PAS déroger sans discussion
- **Backbone** : JEPA léger ~15M params entraîné *sur le jeu* (style LeWorldModel / eb_jepa).
  **NE PAS** utiliser V-JEPA 2 gelé comme primaire (lourd, OOD sur Minecraft, pas clonable
  sur GPU grand public).
- **Env** : **Crafter d'abord** (léger, pip install, valide la pipeline), **MineRL ensuite**
  (Phase 4, le visuel Minecraft = la marque).
- **Briques à réutiliser** (ne pas réinventer) :
  - `facebookresearch/eb_jepa` — action-conditioned + planning officiel JEPA
  - `facebookresearch/vjepa2` via torch.hub — secondaire/comparaison seulement
  - LeWorldModel (arXiv 2603.19312) — vérifier dispo en Phase 0
  - Anti-collapse VICReg : recette dans `ES2025-19.pdf` (ESANN 2025, dans le repo)

## Risque n°1 : le COLLAPSE
JEPA est **prone au collapse** (tous les embeddings → constante, variance → 0, loss → 0
mais le modèle n'a rien appris). **Toujours** :
- target-encoder en EMA (θ̄ ← 0.99·θ̄ + 0.01·θ), gradient bloqué
- régularisation VICReg sur la variance des embeddings
- monitorer `batch_var` à chaque epoch — si < 1e-6 : collapse en cours

## Phase courante
**PHASE 1 — Représentation JEPA** (voir PLAN.md §4). Phase 0 complète ✅.

Phase 0 — gates validés :
- [x] Env Python tourne + Crafter installé
- [x] `scripts/collect.py` → 33 406 transitions (frames, actions, health, food, drink, energy) + GIF
- [x] `mine_jepa/eb_jepa/` — code Meta vendored, importable, smoke test OK
- [x] `docs/01_jepa.md` + `docs/02_setup.md` rédigés

Gates à valider avant Phase 2 :
- [ ] `scripts/train_encoder.py` → entraînement 30 epochs sur GPU NVIDIA (PC)
- [ ] `batch_var` > 1e-4 à la fin de l'entraînement (pas de collapse)
- [ ] `scripts/probe.py` → linear-probe accuracy > baseline (33 %) sur `health`
- [ ] `docs/03_representation_collapse.md` rédigé

⚠️  Entraînement Phase 1 sur **PC NVIDIA uniquement** (8 Go VRAM).
Commande : `uv run python scripts/train_encoder.py`

## Conventions de code
- Python 3.11+, PyTorch 2.x, timm, einops
- `uv` pour le package management (lockfile dans `uv.lock`)
- Configs en YAML dans `configs/` (pas de hardcode de hyperparams dans le code)
- Scripts standalone dans `scripts/` (chaque script = un livrable vérifiable)
- Type hints partout, pas de commentaires évidents

## Pédagogie embarquée (objectif d'apprentissage)
L'utilisateur **découvre JEPA** — il ne connaît pas le sujet. Pour chaque nouveau concept
introduit dans le code : expliquer le *pourquoi* en conversation et pointer vers le doc
`docs/0X_*.md` correspondant. Les docs pédago = aussi le contenu marketing du projet.

## Hardware
- **Dev** : MacBook Air M1, 16 Go RAM, **pas de GPU NVIDIA** → OK pour écrire du code,
  collecter des données, tester des imports. Trop lent pour entraîner.
- **Training** : PC avec **GPU NVIDIA 8 Go VRAM**, 32 Go RAM → basculer AVANT de lancer
  `train_encoder.py` (Phase 1), `train_wm.py` (Phase 2), `play.py` (Phase 3+).
- **Transfert** : `git push` depuis Mac → `git clone` + `uv pip install -e .` sur PC.

## Environnement Python
Toujours préfixer avec `uv run` (utilise le venv géré par uv) :
```bash
uv run python scripts/collect.py ...
uv run pytest
```

## Commandes utiles
```bash
# Collecter des trajectoires (frames + actions) depuis Crafter
uv run python scripts/collect.py --env crafter --episodes 100 --out data/crafter/

# Linear-probe (gate Phase 1)
uv run python scripts/probe.py --data data/crafter/ --checkpoint checkpoints/encoder.pt

# Évaluer le world model (gate Phase 2)
uv run python scripts/eval_wm.py --checkpoint checkpoints/wm.pt --steps 10

# Lancer l'agent (gate Phase 3)
uv run python scripts/play.py --env crafter --task reach_plant --episodes 50
```

## Structure du repo
```
mine_jepa/        ← code source Python (encodeur, predictor, planner, agent)
scripts/          ← scripts standalone vérifiables (collect, probe, eval_wm, play)
configs/          ← hyperparams YAML
docs/             ← pédagogie + marketing
  01_jepa.md      ← C'est quoi JEPA (pour apprendre + pour le README)
  02_setup.md     ← Comment installer et lancer
  03_representation_collapse.md
  04_world_model.md
  05_planning.md
  06_minecraft_port.md
data/             ← datasets (gitignore)
checkpoints/      ← poids (gitignore, puis HuggingFace)
assets/           ← GIFs, vidéos pour le README
```

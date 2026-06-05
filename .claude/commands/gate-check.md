Vérifie le gate de Phase 0 de Mine-JEPA en utilisant les données ci-dessous (déjà collectées).

**Résultats des checks :**

Crafter importable :
!`uv run python -c "import crafter; print('OK')" 2>&1`

Contenu de data/crafter/ :
!`ls -lh data/crafter/ 2>/dev/null || echo "ABSENT"`

Dataset valide (frames + actions) :
!`uv run python -c "import numpy as np; d=np.load('data/crafter/episodes.npz'); print('frames:', d['frames'].shape, 'actions:', d['actions'].shape)" 2>/dev/null || echo "ABSENT ou invalide"`

GIF généré :
!`ls -lh assets/random_agent.gif 2>/dev/null || echo "ABSENT"`

docs/01_jepa.md :
!`wc -l docs/01_jepa.md 2>/dev/null || echo "ABSENT"`

docs/02_setup.md :
!`wc -l docs/02_setup.md 2>/dev/null || echo "ABSENT"`

eb_jepa cloné/utilisé :
!`ls vendor/eb_jepa 2>/dev/null || echo "PAS ENCORE"`

---

Sur la base de ces résultats, affiche un tableau ✅ / ❌ par critère et un verdict : gate Phase 0 passé ou non.

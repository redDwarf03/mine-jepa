Check the Phase 0 gate of Mine-JEPA using the data below (already collected).

**Check results:**

Crafter importable:
!`uv run python -c "import crafter; print('OK')" 2>&1`

Contents of data/crafter/:
!`ls -lh data/crafter/ 2>/dev/null || echo "MISSING"`

Valid dataset (frames + actions):
!`uv run python -c "import numpy as np; d=np.load('data/crafter/episodes.npz'); print('frames:', d['frames'].shape, 'actions:', d['actions'].shape)" 2>/dev/null || echo "MISSING or invalid"`

GIF generated:
!`ls -lh assets/random_agent.gif 2>/dev/null || echo "MISSING"`

docs/01_jepa.md:
!`wc -l docs/01_jepa.md 2>/dev/null || echo "MISSING"`

docs/02_setup.md:
!`wc -l docs/02_setup.md 2>/dev/null || echo "MISSING"`

eb_jepa cloned/used:
!`ls vendor/eb_jepa 2>/dev/null || echo "NOT YET"`

---

Based on these results, display a ✅ / ❌ table per criterion and a verdict: Phase 0 gate passed or not.

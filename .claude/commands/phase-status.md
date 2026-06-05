Donne l'état de la Phase 0 de Mine-JEPA à partir des données réelles ci-dessous.

**État du repo :**
!`find . -not -path './.git/*' -not -path './.venv/*' -not -path './data/*' -not -path './checkpoints/*' -type f | sort`

**Taille du dataset collecté :**
!`du -sh data/ 2>/dev/null || echo "data/ absent"`

**Checkpoints existants :**
!`ls checkpoints/ 2>/dev/null || echo "aucun checkpoint"`

**Docs rédigées :**
!`ls docs/ 2>/dev/null || echo "docs/ absent"`

---

Sur la base de ces données, affiche :
1. La phase courante et son objectif
2. Les livrables **déjà produits** (artefact visible + doc pédago)
3. Ce qui **reste à faire** avant de passer à la Phase 1
4. Le prochain livrable concret à attaquer

Give the status of Phase 0 of Mine-JEPA from the real data below.

**Repo state:**
!`find . -not -path './.git/*' -not -path './.venv/*' -not -path './data/*' -not -path './checkpoints/*' -type f | sort`

**Collected dataset size:**
!`du -sh data/ 2>/dev/null || echo "data/ absent"`

**Existing checkpoints:**
!`ls checkpoints/ 2>/dev/null || echo "no checkpoints"`

**Written docs:**
!`ls docs/ 2>/dev/null || echo "docs/ absent"`

---

Based on this data, display:
1. The current phase and its objective
2. **Already produced** deliverables (visible artifact + pedagogical doc)
3. What **remains to do** before moving to Phase 1
4. The next concrete deliverable to tackle

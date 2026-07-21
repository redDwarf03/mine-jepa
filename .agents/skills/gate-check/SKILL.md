---
name: gate-check
description: Skill to check Phase 0/1/2/3/4 deliverables and gate criteria for Mine-JEPA.
---

# Gate Check — Mine-JEPA

Execute validation commands to verify project phase gates.

## Phase 0 Validation Checks
1. Crafter importable: `uv run python -c "import crafter; print('OK')"`
2. Dataset presence: check `data/crafter/` and verify frame/action shapes in `data/crafter/episodes.npz`.
3. Artifacts: check `assets/random_agent.gif`.
4. Pedagogical docs: check `docs/01_jepa.md` and `docs/02_setup.md`.

## Response Format
Return a clear tabular checklist ($\text{Criteria} \mid \text{Status} \mid \text{Details}$) followed by a final Phase Gate Verdict.

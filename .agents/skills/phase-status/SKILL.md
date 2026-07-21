---
name: phase-status
description: Skill to report the current Mine-JEPA project phase, completed deliverables, dataset sizes, checkpoints, and remaining tasks.
---

# Phase Status Report — Mine-JEPA

Inspect the repository and summarize current phase status.

## Status Checks
1. List source files in `mine_jepa/`, `scripts/`, `configs/`, `docs/`.
2. Check dataset sizes in `data/`.
3. Check existing model weights in `checkpoints/`.
4. Review current phase in `CLAUDE.md` and `.agents/AGENTS.md`.

## Output Format
1. **Current Phase & Objective**
2. **Completed Deliverables** (code, datasets, checkpoints, docs)
3. **In-Progress Work & Open Walls** (e.g. Phase 5+ cold-start tree chopping)
4. **Next Concrete Deliverable**

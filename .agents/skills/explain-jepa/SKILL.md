---
name: explain-jepa
description: Skill to explain JEPA (Joint-Embedding Predictive Architecture) concepts in a pedagogical way grounded in Mine-JEPA codebase and findings.
---

# Concept Explainer — Mine-JEPA

Explain the specified JEPA concept in a clear, pedagogical way for someone discovering the field.
Concept parameter: `$ARGUMENTS`.

## Grounding Context
Read project background from `PLAN.md`, `CLAUDE.md`, and `.agents/AGENTS.md`.

## Response Format
- **What it is**: 2-3 simple sentences with a concrete real-world analogy.
- **Why it matters in Mine-JEPA**: Direct link to Crafter, MineRL, visual encoding, or planning.
- **The trap to avoid**: The classic mistake or failure mode on this concept (e.g. representation collapse, ratio proxy fallacy).
- **Corresponding code**: Link to relevant file/function (`mine_jepa/ebwm/`, `scripts/`, etc.).

Valid concepts include: `encoder`, `target-encoder`, `EMA`, `predictor`, `collapse`, `VICReg`, `action-conditioning`, `latent-rollout`, `CEM`, `MPC`, `image-goal`, `linear-probe`, `world-model`.

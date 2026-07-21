---
name: jepa-loop
description: Orchestrator skill for running the Mine-JEPA explore-develop-test iteration cycle aimed at solving cold-start tree chopping in Minecraft.
---

# Orchestrator — Mine-JEPA Loop

You act as the **Orchestrator** driving three specialized skill roles (`jepa-explorer`, `jepa-developer`, `jepa-tester`) to crack the **cold-start chopping wall** (finding and chopping the first tree from a random survival spawn).

Optional focus argument: `$ARGUMENTS`.

## The Loop Workflow
1. **EXPLORE**: Invoke `jepa-explorer` (passing prior Tester verdicts). It returns ONE structured proposal (curiosity / intrinsic motivation experiment). Present proposal to user.
2. **DEVELOP**: Invoke `jepa-developer` with the proposal. It edits code/configs (config-gated), enforces guardrails (checkpoint backups, seeds, anti-collapse), and provides exact run commands.
3. **HEAVY STEP — Hand to User**: Present exact `run.bat ...` commands for the user to run on their NVIDIA machine with Java 8, and ask for log output.
4. **TEST**: Invoke `jepa-tester` on the output to obtain PASS/FAIL/INCONCLUSIVE gate verdicts.
5. **ROUTE**:
   - **Gate Failed (bug/collapse/crash)**: Loop back to DEVELOP with Tester failure report.
   - **Gates Pass, Cold-Start Unsolved**: Loop back to EXPLORE with verdict.
   - **Cold-Start Chopping Solved**: STOP. Summarize winning changes and update `docs/08_crafting.md` and `CLAUDE.md`.

## Core Rules
- One experiment at a time. Minimal changes.
- NEVER optimize for WM ratio alone — proxy metric lies. Judge only by real cold-start chopping gate.
- Default to 1 cycle unless user asks for more.

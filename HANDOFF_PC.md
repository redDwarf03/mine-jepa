# HANDOFF — resume here on the NVIDIA PC (session of 2026-07-07, Mac)

**Current task: evaluate cold-start attempt #2 (sticky sampling + scan macro).**
Code is DONE and smoke-tested on the Mac; nothing has run against MineRL yet.
Full pedagogy/rationale: `docs/10_coldstart_engineering.md`. Status also in `CLAUDE.md`
(Phase 5+ attempt #2 block). Delete this file once the eval is done and documented.

## Where we are (1 paragraph)

The agent chops trees when one is visible (25–50% Treechop) and crafts planks at 100%
given wood, but scores **0/5 logs cold-start** (`ObtainIronPickaxeDense`, random spawn,
no tree in view). Curiosity attempt #1 (offline Plan2Explore) failed — diagnosed in
`docs/09`. Attempt #2 is *engineering, not learning*: (1) the planner's i.i.d. uniform
candidate sampling could never propose sustained gestures like "turn 6 steps" → added
**sticky sampling** (iCEM-lite); (2) "no tree in view" is detectable for free (std of
goal scores across the 512 candidates ≈ 0) → added a **camera-sweep scan macro**.
Everything is config-gated; defaults reproduce the old behaviour bit-for-bit;
**no checkpoint was touched, nothing needs retraining.**

## What changed (this push)

| File | Change |
|------|--------|
| `mine_jepa/ebwm/planner.py` | `_sample_actions()` helper; `sticky_prob` on `DiscreteLatentPlanner` + `SwitchingCraftPlanner`; `plan(..., return_info=True)` → `goal_score_std` |
| `scripts/play_ebwm.py` | scan state machine + `[scan]` std logging + "scan triggers=" episode line |
| `scripts/play_craft.py` | same, active in **chop mode only** |
| `configs/play_ebwm.yaml`, `configs/play_craft.yaml` | `planner.sticky_prob` + `scan:` block (both OFF by default) |
| `scripts/smoke_planner_coldstart.py` | CPU smoke test (no MineRL needed) |
| `docs/10_coldstart_engineering.md` | the chapter for this attempt |

## PC procedure (in order)

```bat
:: 0. sanity — should print ALL SMOKE TESTS PASSED (CPU, ~5 s)
run.bat scripts/smoke_planner_coldstart.py
```

**1. Calibrate `flat_threshold` (do NOT skip).** In `configs/play_ebwm.yaml` set
`scan.log_std: true` (keep `scan.enabled: false`, `sticky_prob: 0.0`), then:

```bat
run.bat scripts/play_ebwm.py --config configs/play_ebwm.yaml --episodes 3
```

Every replan prints `[scan] step=... goal_score_std=...`. Cross-check with the GIF:
read the typical std when a tree fills the view vs. facing grass/sky. Set
`scan.flat_threshold` between the two bands, closer to the lost band. Record both
bands in `docs/10` (calibration section). Then set `log_std: false`.

**2. Treechop A/B gate** — N=20 each, seeded (`agent.seed: 0`), same `ebwm.pt`:
- Condition OFF: `sticky_prob: 0.0`, `scan.enabled: false` (fresh baseline, same day)
- Condition ON: `sticky_prob: 0.7`, `scan.enabled: true`
- Target: ON ≥ 50% success (baseline band is 25–50%), fps ≈ unchanged (sticky and
  scan add no rollout cost). Watch "scan triggers=" — if it never fires on Treechop
  (trees usually visible), that's fine; sticky is the active ingredient there.

**3. Cold-start gate** — the real milestone. `configs/play_craft.yaml`: same
`sticky_prob: 0.7` + `scan.enabled: true` (threshold from step 1 — same encoder family
but different checkpoint (`craft_wm_v4.pt`), so if scan behaves oddly re-calibrate with
`log_std: true` on this config too):

```bat
play_craft.bat   :: N=5, ObtainIronPickaxeDense
```

Target: **≥ 1 log in ≥ 1 episode** (current: 0/5). If a log drops, the validated craft
loop takes over → planks = milestone reached.

**4. Report honestly** (per project rules): both numbers with variance, no best-run
claims. Update `docs/10` (gate table → actual results), `CLAUDE.md` Phase 5+ block
(`[ ]` → `[x]` or a documented FAIL), then delete this handoff file.

## If the gate FAILS — pre-agreed routing

1. Scan fires but the agent still can't reach/chop the tree it finds → the wall is the
   approach/chop gesture, not search: try `sticky_prob` 0.5–0.8 sweep (N=10 quick),
   and/or `patience: 2`, `max_replans: 20`.
2. Scan never fires in cold-start despite the agent being lost → `flat_threshold` too
   low; recalibrate on `ObtainIronPickaxeDense` frames, not Treechop.
3. Sticky alone degrades Treechop → try 0.5 before concluding; if it still degrades,
   report it — that would be a real (publishable-in-docs) negative result.
4. All tuned and still 0 logs → the chapter closes as a documented partial, and the
   next cycle is **online RND** (`docs/09` conclusion): novelty that decays with
   experience, predictor updated during play. NOT offline-on-demos (mistake #1).

## Standing warnings (unchanged)

- Always `run.bat <script>` on the PC (PYTHONUTF8 + unbuffered).
- Do NOT retrain anything for this task; `ebwm.pt` and `craft_wm_v4.pt` stay as-is.
- `train_eb_jepa.py` OVERWRITES `checkpoints/ebwm.pt` — irrelevant here, but never run it casually.
- The `Ep N/M | reward=...` line format is parsed by `play_minerl_multi.py` — scan info
  is printed on separate lines on purpose; keep it that way.
- MineRL multi-instance: the malmo.py `.decode(..., errors="replace")` patch is lost on
  reinstall (see CLAUDE.md installation notes).

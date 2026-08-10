# Mine-JEPA — Instructions for Claude Code

## What this project is (1 line)
A JEPA agent that plays Minecraft from pixels — spectacular packaging of existing
open-source building blocks, not from-scratch research. Full plan: `PLAN.md`.

## Architecture rules — DO NOT deviate without discussion
- **Backbone**: lightweight JEPA ~15M params trained *on the game* (LeWorldModel / eb_jepa style).
  **DO NOT** use frozen V-JEPA 2 as primary (heavy, OOD on Minecraft, not clonable
  on consumer GPU).
- **Env**: **Crafter first** (lightweight, pip install, validates the pipeline), **MineRL second**
  (Phase 4, real Minecraft visuals = the brand).
- **Building blocks to reuse** (do not reinvent):
  - `facebookresearch/eb_jepa` — action-conditioned + official JEPA planning
  - `facebookresearch/vjepa2` via torch.hub — secondary/comparison only
  - LeWorldModel (arXiv 2603.19312) — check availability in Phase 0
  - Anti-collapse VICReg: recipe in `ES2025-19.pdf` (ESANN 2025, in the repo)

## Risk #1: COLLAPSE
JEPA is **prone to collapse** (all embeddings → constant, variance → 0, loss → 0
but the model learned nothing). **Always**:
- target-encoder via EMA (θ̄ ← 0.99·θ̄ + 0.01·θ), gradient blocked
- VICReg regularization on embedding variance
- monitor `batch_var` each epoch — if < 1e-6: collapse in progress

## Current phase
**PHASE 5 — Crafting (MineRLObtainIronPickaxe)** — core objectives met ✅. Phases 0→4 complete ✅.
**The Phase 5+ cold-start campaign is CLOSED on attempt #20 (2026-08-10)** — see the closure
block at the end of the Phase 5+ section for the reasoning and for what is explicitly NOT claimed.

▶ **RESUMING WORK? Read this file's "Phase 5+" section below** — it's the up-to-date
record of every cold-start attempt (sticky sampling/scan, coverage fine-tune, and
whatever is in progress). `HANDOFF_PC.md` (a session-to-session bridge doc) has been
retired now that this file stays current within a single continued session.
⚠️ Do NOT open a 21st attempt in the old idiom (patching planner/score around a frozen
`ebwm.pt`) — attempt #20 measured why that layer cannot work. The only lever left is a
world-model rebuild, and that is a new piece of work, not a continuation.

Phase 0 — gates validated:
- [x] Python env running + Crafter installed
- [x] `scripts/collect.py` → 33,406 transitions (frames, actions, health, food, drink, energy) + GIF
- [x] `mine_jepa/eb_jepa/` — Meta code vendored, importable, smoke test OK
- [x] `docs/01_jepa.md` + `docs/02_setup.md` written

Phase 1 — gates validated ✅:
- [x] `scripts/train_encoder.py` → 30 epochs GPU RTX 5060 Ti — val_loss=0.080, batch_var=1.13
- [x] `batch_var` > 1e-4 — measured 1.178 at probe (no collapse)
- [x] `scripts/probe.py` → linear-probe health: 90.8% vs baseline 86.9% (+3.8%) ✅
- [x] `docs/03_representation_collapse.md` written

Phase 2 — gates validated ✅:
- [x] `scripts/train_wm.py` → 30 epochs GPU — val_pred=0.033 vs val_copy=0.086 (ratio=0.38)
- [x] 1-step latent error < baseline: ratio 0.367 ✅
- [x] `scripts/eval_wm.py` → multi-step 10/10 k below baseline (ratio ~0.38 stable) ✅
- [x] `docs/04_world_model.md` written

Phase 3 — gates validated ✅:
- [x] `scripts/play.py` → MPC latent agent in Crafter (random-shooting, horizon=12, N=512)
- [x] 100% success rate, 2.56 achievements/ep vs 2.38 random (+7.5%), reward +14%
- [x] GIF saved: `assets/agent_play.gif`
- [x] `docs/05_planning.md` written

Phase 4 gates:
- [x] MineRL installed and env running (`import minerl` OK, 33 envs including MineRLTreechop-v0) ✅
- [x] `docs/06_minecraft_port.md` written ✅
- [x] `scripts/collect_minerl_multi.py --shards 15` → 119,852 MineRL transitions ✅
- [x] JEPA encoder retrained on MineRL: val_loss=0.0528, batch_var=1.168 (no collapse) ✅
- [x] World model retrained on MineRL: val_pred=0.0329 < val_copy=0.0334 (ratio=0.983) ✅
- [x] **4 approaches tested, only eb-JEPA works** ✅ (1-4 = reward 0)
  - Approach 1-2: MPC + 1-step WM (ratio ≈0.96) → reward 0 (planner blind on static frames)
  - Approach 3: BC frozen encoder + head → reward 0 (covariate shift, agent frozen on 1 action)
  - Approach 4: BC CNN end-to-end → reward 0 (no memory, no sustained attack possible)
  - **Approach 5: eb-JEPA action-conditioned MPC (embed_dim=64, 664K) → agent chops trees ✅**
- [x] **Ablation — what drives agent success (4 training runs on demos):**
  - Original (T=8, 20ep, ratio 0.929): 50% — checkpoint LOST (overwritten by v2)
  - WM v2 (embed=128, T=12, 25ep, ratio 0.890): 5% ❌
  - v1-retrain (embed=64, T=12, 25ep, ratio 0.882): ~0% ❌ → disproves "bigger latent breaks it"
  - v1-restored (embed=64, T=8, 20ep, ratio 0.927): **25%** ✅ (released ckpt, 1 ep chopped 2 logs)
  - **LESSON: the TRAINING RECIPE (not latent size) is the lever. T=8/20ep → ratio ~0.93 = sweet
    spot. Over-training (T=12/25ep → ratio ~0.88) breaks the agent at any embed_dim (planner copies
    static a6-attack pose instead of the a14 move+attack gesture). Lower ratio ≠ better.**
  - **LESSON: high run-to-run variance (50% vs 25% at same recipe+ratio). Training is UNSEEDED →
    different latent geometry each draw; planning success weakly coupled to prediction ratio.
    → SEED training before claiming reproducibility. Released number = 25% (honest), best seen = 50%.**
- [x] `play_ebwm.bat` (= play_minerl_multi.py) → agent plays real Minecraft, 25% success ✅
  - GIF fix: play_minerl_multi.py keeps the BEST-success episode GIF (not the last/failing one)
  - ⚠️ DO NOT use `scripts/play.py --env minerl` with episodes > 1 (blocks on reset)
  - ⚠️ train_eb_jepa.py OVERWRITES checkpoints/ebwm.pt — back up a good checkpoint before retraining

Phase 5 gates (crafting — chop log → craft planks → … → wooden tool):
- Goal: at least one agent that figures out crafting. ⚠️ wooden_sword is NOT craftable in
  MineRL 0.4.4 (no handler) → wooden_pickaxe is the supported equivalent (same recipe:
  log→planks→stick→crafting_table→tool). Env: `MineRLObtainIronPickaxeDense-v0` (dense reward + inventory obs).
- [x] Obtain demos: `scripts/prepare_demos_obtain.py` → `data/minerl_craft` (40 demos, 84,902 frames,
  144 craft-planks steps, 37/40 reach pickaxe). Source: Zenodo 12659939 `MineRLObtainIronPickaxe-v0.zip` (2.8 GB).
- [x] 22-action space (17 movement + 5 craft): `configs/minerl_actions_obtain.yaml`
- [x] WM v3 (inventory as a HEAD off the visual latent) → **FAILED for crafting**: the POV does not
  contain the inventory → the head learns only scene correlations, the predictor copies (ratio ~0.98)
  → planner blind to craft. Baseline only.
- [x] **WM v4 (inventory as a STATE variable)**: visual eb-JEPA + `InventoryDynamics` MLP
  (`inv_{t+1}=inv_t+g(inv_t,action,visual)`). **dPlanks@craft = +4.0** → the WM LEARNED the craft rule
  (1 log → 4 planks). ✅ `checkpoints/craft_wm_v4.pt`, `scripts/train_craft_wm_v4.py`.
- [x] **Precondition fix**: expert demos never show failed crafts → v4 first crafted on an EMPTY
  inventory forever (a17=30%). Fix = synthetic negatives (`craft+empty→0`) + upweight rare craft
  steps ×30 (precond at 5.0 first crushed the +4 signal → use craft_weight=30, precond_coeff=2).
  Balanced: **dPlanks +3.8 AND precond ≈0** → agent stops crafting uselessly. ✅
- [x] **Switching planner** (`SwitchingCraftPlanner`): no log → chop (goal-centroid, Treechop trick);
  has log → craft (inventory gain). Mode switching correct in live play. ✅
- [x] **Live craft demo** (`play_craft_test.bat` → `MineRLObtainTest-v0`, starts with log=5): the agent
  switches to craft mode and crafts planks LIVE — **100% over 6+ ep, +16–20 planks/ep, reward 10**. Full
  craft loop works end-to-end given wood. (Craft is invisible in POV → proof is inventory/reward, not a GIF.)
- [~] **Cold-start milestone** (`play_craft.bat` → `ObtainIronPickaxeDense`): the agent **cannot chop the
  first log cold-start** (random survival spawn, trees not in view; 0 logs over 5 ep). Treechop chopping
  wall, harder here. Decision: **consolidate** (`docs/08_crafting.md`). Cold-start chopping = future work.
- KEY LESSON: **crafting is a discrete-inventory-state problem, not a pixel problem.** The POV never shows
  the inventory count → inventory MUST be part of the world-model state, not predicted from the frame.
- KEY LESSON: **expert demos teach actions, not preconditions** (no failed-craft examples). Negatives
  (synthetic, or via curiosity/self-play) are required.
- Next chapter (user's hybrid choice): **curiosity** (WM prediction error as intrinsic reward) + self-play
  → teaches the precondition from experience AND drives exploration toward trees. WM v4 is the foundation.

Phase 5+ — Cold-start campaign (chopping the first log from a random spawn). Full
attempt-by-attempt detail: `docs/09_curiosity_coldstart.md` (attempt #1) and
`docs/10_coldstart_engineering.md` (attempts #2-#12). **Attempt #13 and the drowning
free-diagnostic below are NOT YET in docs/10 — this file is currently their only record;
add them there before trusting docs/10 alone.**

- **#1 — Plan2Explore offline novelty bonus (`docs/09`): FAILED.** k=5 ensemble collapsed
  during training (val_disagree 0.061→0.0005) → novelty flat everywhere, ON≈OFF on
  Treechop A/B. Lesson: offline-frozen-ensemble curiosity is a dead end on expert demos;
  Plan2Explore needs its ONLINE training condition, not just its form.
- **#2 — sticky sampling (iCEM-lite) + scan macro: PARTIAL.** Treechop sticky
  0.5+scan 40% (4/10) vs OFF 45% (not significant). Cold-start: 0/5, scan pathological on
  `craft_wm_v4` (compressed std bands, agent spins). Two-brain agent (`ebwm.pt` plans chop,
  v4 takes over at first log) transformed behaviour, still 0/5 — established that the wall
  is approach/chop behaviour, not just search.
- **#3 — coverage fine-tune of `craft_wm_v4`: signal improved, outcome unchanged.**
  std band separation widened ×3.2→×5.4 but 0/3 logs, identical on backup vs fine-tuned.
  **Lesson (confirms #2): sharpening the "am I lost" signal doesn't fix the search/approach
  behaviour that acts on it — the wall is behavioural, not perceptual.**
- **#4 — `commit_length=4` (real result) + online RND (inconclusive→negative).**
  `commit_length=4`: the planner was discarding steps 2-12 of its own already-correct
  winning plan every replan; fixing this gave **3/31 (9.7%)**, the campaign's first non-zero
  result, vs 0/27 pooled at `commit_length=1`. Online RND on top: first pass inconclusive
  (diagnostic left unlogged); re-run with `novelty_mean` logged confirmed negative — novelty
  tracks elapsed ticks (256-slot ring buffer saturates on a homogeneous biome), not scene
  content, corr with `goal_score_std` -0.83..+0.15.
- **#5 — scan macro re-enabled in two-brain mode (correctly calibrated on `ebwm.pt`): NO-GO.**
  0/7. One episode sat in the salient-scene std band for ~880 ticks, scan correctly stayed
  inert, agent still didn't chop. **Standing diagnosis established here: a correctly-wired
  "I'm lost" detector isn't a fix if the behaviour consuming it can't convert "visible" into
  "approach and chop."**
- **#6 — real CEM planner: NO-GO, first regression.** 0/8; action concentration 66.3% vs
  `commit_length=4`-alone's 35.8% — CEM's elite-refit locks onto sampling noise when the
  score is flat, amplifying noise as readily as signal.
- **#7 — trained cost-to-reach distance metric (Destrade et al. arXiv:2601.00844): NO-GO.**
  Offline separation 7.9× (passed), live 0/6. `goal_score_std` tracked scene *brightness*
  (r=-0.57), not tree-proximity — a data-composition gap (no night/cave training frames).
- **Standing diagnosis after #4-#7: the wall is BEHAVIOURAL (action generation), not
  perceptual.** Three score/search-quality fixes (RND, CEM, trained distance) each failed
  differently; `commit_length` (a pure execution fix) is the only lever that ever worked.
- **#8 — action-pool priming + bushwhack cruise macro: NO-GO, most informative negative
  yet.** 0/8 vs the 9.7% baseline (not itself surprising at N=8). Both mechanisms verifiably
  fired, but 3/8 episodes showed 83-100% single-action lock-in — hand-designed action
  generation degenerates the same way CEM did. Built the `spawn_diag` viability diagnostic
  as a byproduct (used by #9-#13).
- **#9 — BC actor as MPC candidate proposer ("Proposal B"): NO-GO, sharpest negative of the
  campaign.** 0/8, Fisher p≈0.21 vs baseline. Rules out lock-in (16-54% action share,
  normal) AND unwinnable spawns (`max_chop_std` 0.017-0.047, all viable) — a genuinely
  diverse, non-collapsed, expert-trained proposer on confirmed-viable spawns still didn't
  move the outcome. Pushes suspicion onto the world model's *evaluation* of proposals.
- **#10 — offline diagnostic: does `ebwm.pt`'s own goal-centroid scoring generalize
  Treechop→Obtain? CONFIRMED, sharper than expected.** On Obtain frames, tree-visible scores
  LOWER than tree-absent (reversed vs. Treechop's correct ~6× higher-when-close direction) —
  not a flat/collapsed signal but a **directional confound**. Answers #9's open question: the
  evaluator itself is measurably wrong, not just under-informative.
- Campaign paused after #10. Four candidate directions ranked by cost: (1) Obtain-domain
  score correction [cheapest], (2) topological frontier memory, (3) H-JEPA [highest
  cost/risk], (4) BC fine-tuning on search footage [deprioritized — improves proposals, not
  evaluation, doesn't address finding (b)].
- **#11 — direction 1, Obtain-domain score correction: NO-GO, third confirmation of a
  frozen-encoder brightness shortcut.** Offline gates looked best-ever (separation 11.26×,
  87.5% correct direction) but corr(is_tree_close, brightness) = -0.917 on the hand-labeled
  set — the apparent win was brightness in disguise. Same shortcut as #7-original and its
  ColorJitter repair, now shown domain-of-training-data-independent → **the confound lives in
  `ebwm.pt`'s frozen encoder itself.** Direction 1 closed unless revisited as an encoder-side
  fix.
- **#12 — direction 2, topological frontier memory (`FrontierTracker`: pure dead-reckoned
  visit-count grid, no learned function, no frozen-encoder dependency — sidesteps both #4's
  RND failure and #10's confound by construction).** Sanity N=3 clean (no lock-in,
  `unique_cells_visited` growing). Confirmation N=20: **1/20 (5.0%) logs+planks, reward
  0.45** — the campaign's second non-zero result and the first from a mechanism entirely
  outside action-generation/scoring, with no lock-in anywhere in the batch. Same order of
  magnitude as `commit_length`'s 9.7%, not proven better at this N. (⚠️ `agent.seed` is a
  pre-existing no-op in `play_craft.py` for every config — standing reproducibility debt.)
- **Free diagnostic on #12's batch — drowning confirmed as dominant early-termination
  cause.** 12/20 episodes' Malmo logs show an explicit `MineRLAgent0 drowned`; the other
  episodes ran the full 3000-step cap with zero drown messages (clean bimodal split). On
  episodes that survived long enough to search fairly, the success rate is closer to ~1-in-
  7-8, not 1/20 — a large share of the gap is spawn-hazard, not search/approach. Motivates
  #13.

- **#13 — hazard-awareness for the frontier scan macro (`mine_jepa/ebwm/hazard.py`,
  `hazard_avoidance:` config block, `configs/play_craft_commit4_hazard.yaml`) — built,
  well-calibrated detector, escape reflex does not reliably resolve what it detects; N=5
  inconclusive-to-negative, no larger batch justified. ⚠️ Not yet in `docs/10` — kept in
  full detail here:**
  - No health/breath/air observable exists in `MineRLObtainIronPickaxeDense-v0`'s obs space
    (verified against `minerl.herobraine.env_specs.obtain_specs.Obtain`) — `detect_underwater()`
    is a calibrated pixel heuristic, not a proxy for a real signal. Calibrated twice: an
    absolute-RGB version caught a daytime drowning but missed a night one; switched to
    lighting-invariant ratios (`B/max(R,G)`, `|R-G|/max(R,G)`) — re-validated on ~5900 pooled
    frames + both real drownings: zero false positives, 100%/~81% catch rate day/night (the
    missed 19% are near-black frames where all channels collapse, an inherent pixel-heuristic
    limit, not a tuning failure).
  - Live N=5: Ep1/4/5 ran full episodes, hazard never triggered (not testing chopping).
    Ep2 (died step 750): hazard never fired — death was NOT a drowning (fall/mob/lava,
    an unhandled death class). **Ep3 (died step 922): the mechanism DID fire continuously
    for 260+ ticks (detector correct) — the escape motor pattern (alternate jump a5 +
    retreat a2) never got the agent back to dry land, and the episode still ended in death.**
  - **Lesson, same shape as #5, now for hazard instead of search: a correctly-calibrated
    detector is not itself a fix if the action it dispatches doesn't resolve the situation.**
    The reflex has no sense of *which way* is land, only "am I currently wet." Fix would need
    a smarter escape heading (e.g. reuse `FrontierTracker`'s dead-reckoning to retreat toward
    the most-recently-dry cell) or accepting hazard-avoidance as partial mitigation only.
  - Process note: the dispatching agent was killed mid-write-up (no conclusion delivered);
    the numbers above were independently re-verified from `logs/coldstart_attempt13_hazard_sanity.log`
    and the GIF (`assets/agent_play_craft_commit4_hazard.gif`), not taken from that agent's
    report. Default `enabled: false` is structurally guarded (`if hazard_enabled:` wraps every
    new path) but not yet re-confirmed with a dedicated disabled-vs-baseline run.
  - **Follow-up: steered escape (turn toward last-known-dry `FrontierTracker` position instead
    of blind jump/retreat) — NO-GO, with two specific bugs found, not just "still doesn't
    work."** N=6 (`logs/coldstart_attempt13_hazard_steered_n6.log`): 4/6 died, and **all 4 died
    while the hazard reflex was actively escaping** (`died_during_escape=True` on every one,
    independently confirmed against 4 real `MineRLAgent0 drowned` messages in the raw Malmo
    logs) — a worse ratio than the blind version's 1-drowning-death-out-of-2-early-deaths.
    The mechanism is genuinely wired correctly (dry position is recorded, a real bearing is
    computed, turn→forward switching happens as designed, jump is interleaved throughout) and
    one episode (#4) shows real measurable progress — distance to the remembered dry point
    shrank from >50 units to ~5.6 before death, something the old blind retreat structurally
    could never do — it just wasn't fast enough. Two distinct root causes for the rest:
    1. **Turn/alignment granularity mismatch**: each replan's turn action covers ~80° (a
       `commit_length`-sized block at ~10°/tick) while `align_deg=20°` — the turn structurally
       overshoots the alignment window on almost every replan, so delta flips sign and the
       agent ping-pongs between two headings ~80-100° apart (seen directly: -52.2°/+27.8° for
       18 replans in ep3, +20.0°/-60.0° for 11 replans in ep4) without ever entering "forward"
       long enough to close distance — a bang-bang hunting bug, not a conceptual failure of
       "steer toward dry land."
    2. **Anchor corruption**: the remembered dry position occasionally jumps to a point right
       next to the agent's own still-submerged position (ep3) rather than staying a stable
       distant point — a likely single-tick false "not underwater" reading (surface wave/
       lighting noise at the water's edge) corrupting the memory, not staleness.
  - **Second follow-up (last quick attempt on this mechanism): widened `align_deg` + debounced
    dry-anchor — GO. Drowning genuinely fixed at this N.** N=6
    (`logs/coldstart_attempt13_hazard_fixed_n6.log`): **6/6 episodes survived the full 3000
    steps, zero deaths** — vs. 3/5 and 2/6 survival in the two prior rounds. Hazard fired
    heavily and repeatedly (7/4/0/5/11/9 triggers per episode, 36 total across the batch) and
    resolved every single time, not just on easy cases. Directly confirmed in the trace that
    the oscillation is gone: turn deltas now shrink monotonically in one direction
    (-180°→-100°→...→0°/"forward") instead of ping-ponging between two far-apart values as
    before. Doesn't fix chopping/crafting itself (0 planks, unrelated axis) but resolves the
    specific spawn-hazard/drowning failure mode attempt #12's diagnostic identified (12/20
    drowned in that batch). N=6 with 36 real trigger events and 0 failures is a much stronger
    signal than this campaign's usual small-N noise — a real confirmation batch (N≥15-20) is
    now justified if this line of work continues, unlike every earlier hazard round.
  - `ebwm.pt`, `craft_wm_v4.pt` untouched throughout #4-#13 (all mechanisms live in planner
    call convention, chop-planner scoring, or small separately-trained/zero-parameter
    modules — never a retrain of either main checkpoint).

Phase 5+ — Cold-start attempt #14: H-JEPA reconsidered, pivoted to a cheaper Occam's-razor
test first (external expert review) — **Phase 1 (CLIP zero-shot) run, informative NO-GO on
its own gate; Phase 2 (retrain `ebwm.pt` on mixed data) in progress**:
- An Explorer proposal for literal H-JEPA (a second, slower hierarchical world model) was
  externally reviewed before any code was written. Verdict: premature — `ebwm.pt` itself has
  NEVER been retrained/fine-tuned in 13 attempts (always frozen, worked around); attempts
  #7/#8-followup/#11 only ever trained a small head ON TOP of its frozen latents, never applied
  photometric augmentation to the encoder's OWN pretraining. So "the confound lives in the
  frozen encoder" (the working assumption since #11) was itself never directly tested.
- **Phase 1 (cheap, offline, no training, Mac-portable but run on this PC session)**: does
  off-the-shelf zero-shot CLIP (arXiv:2103.00020, ViT-B/32) already separate tree-close from
  no-tree correctly on the attempt #10 frame set, without training anything?
  `scripts/diagnose_clip_score_generalization.py`. **Result: direction gate PASSED (ratio
  1.807 ≥ 1.3) but brightness-independence gate FAILED badly (r=-0.947 on the labeled set,
  -0.74 across the full 251-frame population — including on TREECHOP's own home distribution,
  where `ebwm.pt`'s score already works fine).** A 400M-image pretrained model shows the same
  shortcut, worse than every prior variant (0.117→0.498→0.643→0.947).
- **Interpretation, held to the project's own "hypothesis vs. confirmed" discipline**: this
  weakens (doesn't confirm) the idea that more/diverse pretraining alone fixes the reversal —
  brightness may be a real, partly-legitimate ecological signal (canopy blocks light) rather
  than a pure shortcut, BUT this doesn't fully explain attempt #10's own data: a dark CAVE
  frame was grouped with bright open scenes as "no tree" and scored similarly — pure brightness
  can't explain that pairing, so something beyond raw luminance is still in play. Any causal
  story about *why* `ebwm.pt` specifically reverses on Obtain (e.g. "OOD geometric distortion")
  is an unverified hypothesis, not measured — flagged as such, not asserted as fact.
- **Decision: proceed to Phase 2 anyway** (mixed-gate outcome, not a clean pass or fail per the
  Explorer's own decision rule), but **the acceptance gate is corrected**: Phase 2 is judged by
  re-running attempt #10's actual diagnostic on the new checkpoint (does the reversal go away
  on real Obtain frames?), NOT by a brightness-decorrelation target — Phase 2 never depended on
  that gate in the first place, only Phase 1's cheap CLIP check did.
- **Phase 2 — done, MIXED result, not promoted, leaning NO-GO.** Fine-tuned `ebwm.pt` (resumed
  from its own weights, same embed_dim=64/664K architecture) on Treechop + `data/minerl_craft`
  + `data/minerl_coverage` merged (~4x oversampled Obtain data), per-window photometric
  augmentation on the encoder's own training. Recipe discipline honored: low LR (3e-5), 5
  epochs, `batch_var` 1.15-1.17 every epoch (no collapse), ratio barely moved (0.9265→0.946-
  0.951, as intended for a nudge not a retrain). **The real gate — re-running attempt #10's
  diagnostic against all 5 snapshots — did NOT cleanly pass**: excluding one dark/underwater
  frame, the reversal is genuinely FIXED in every epoch (tree-close beats open by 2.1-4.6x,
  vs. baseline's inverted 0.58x) — but INCLUDING that one dark frame flips the ratio back below
  1 in every epoch, because that specific frame's score got WORSE after fine-tuning (0.0130 →
  0.025-0.031) — a new brightness-linked anomaly, same family as attempts #7/#11's confound,
  just relocated to a different frame. No checkpoint promoted to the unsuffixed name; no
  Treechop sanity batch or cold-start batch run (correctly withheld per the dispatch's own
  contingency rule — only proceed to live testing on a clear pass). Kept:
  `checkpoints/ebwm_v2_treechop_obtain_aug_epoch{1..5}.pt` (comparison only), `ebwm.pt`
  untouched (`ebwm_backup_20260722.pt` confirmed md5-identical beforehand). Self-flagged gap:
  Treechop's own close-canopy-vs-distant paired direction was not independently re-verified
  post-fine-tune (only bulk score-distribution stats, which stayed healthy) — not confirmed
  fine, not confirmed broken.
- **This is now the 4th independent confirmation of a brightness-linked confound, via four
  completely different mechanisms**: a small head on frozen latents (#7), the same head
  Obtain-domain-sourced (#11), an off-the-shelf 400M-image model never touched by this project
  (#14 Phase 1, CLIP), and now direct retraining of the encoder itself with real photometric
  augmentation (#14 Phase 2) — the most direct attack on the problem yet, and it STILL produced
  a new anomaly on a low-light frame instead of a clean fix. This substantially weakens "the
  encoder just needs more diverse/augmented training data" as a sufficient standalone fix —
  the pattern is broader and more stubborn than a training-data gap.

Phase 5+ — Cold-start attempt #15: H-JEPA proposal reassessed with all new evidence, plus a
cheap offline test of one narrower idea it raised — **hand-rolled visual heuristic rejected
before being built; ratio-normalized chromaticity tested directly and also failed, a 5th
confirmation that closes the "smarter feature engineering" line of inquiry**:
- Reassessment (read-only, no code): given CLIP (a 400M-image model built specifically to
  resist photometric variation) already failed the same dual gate a hand-rolled hue/edge
  heuristic would face, building that heuristic was judged very likely to just be a 5th
  confirmation at real engineering cost, not new information — **recommended NOT building it**.
  Also recommended: the campaign's only two working, non-visual-scoring mechanisms
  (`FrontierTracker` coverage, `commit_length`) are the better-justified place to invest next,
  not grafting more visual content bias onto them.
- One narrower, cheaper idea from the reassessment WAS tested directly: does
  `mine_jepa/ebwm/hazard.py`'s proven trick (lighting-invariant channel RATIOS, not raw values —
  which works for water because underwater tint is a uniform frame-global cast) also work for
  foliage if computed PER SPATIAL TILE instead of whole-frame? `scripts/diagnose_chroma_tile_generalization.py`,
  same 251-frame set + hand-labeled ground truth as every prior diagnostic.
- **Result: MIXED, but the brightness gate failed almost as badly as CLIP's worst case.**
  Direction gate PASSED (ratio 1.482 ≥ 1.3). Brightness-independence gate FAILED: r=-0.925 on
  the labeled set (vs. CLIP's -0.947 — essentially tied for the worst in the campaign, opposite
  sign), r=-0.585 across the full 251-frame population (treechop -0.748, obtain_spawn -0.600,
  obtain_coverage -0.671) — broad, not just the small labeled set.
- **Sharpest interpretation yet**: ratio-normalization removes GLOBAL brightness scaling
  exactly as designed (why it works for water) — but it cannot remove a COMPOSITIONAL confound
  where the ground-truth labels themselves correlate scene type with brightness (dark forests
  vs. bright open fields is the actual scene composition of this domain, not an artifact of any
  one scoring mechanism). **This means the brightness confound is not fixable by ANY purely
  photometric single-frame feature — learned, off-the-shelf, or hand-designed-invariant —
  without additional structure (multi-frame, spatial/geometric, or a different modality
  entirely).** Closes the "maybe a cleverer feature trick fixes it" line definitively; the
  encoder/scoring-side avenue (candidate direction 1) stays closed for a stronger reason than
  before.

Phase 5+ — Confirmation batch: frontier+hazard combined at N=20, measuring real chop rate (not
just survival) for the first time on this combination — **drowning fix holds at scale;
chopping still 0/20, within this campaign's established noise:**
- `configs/play_craft_commit4_hazard.yaml` (frontier search + the final fixed hazard-avoidance
  from attempt #13) run at N=20. ⚠️ **Process note, corrected**: the Tester's own report claimed
  a "hard infrastructure failure" halting the batch at episode 4 — this was WRONG, independently
  verified: `play_minerl_multi.py` launches one Java/Malmo process per episode, so one episode's
  transient Malmo state-machine error did not kill the orchestrator, which simply moved on to
  the next episode. The batch ran all 20 episodes end-to-end (`FINAL RESULTS — 20/20 episodes
  succeeded`) without any intervention. Lesson: a per-episode error in this harness is not the
  same as a batch-level failure — confirm the orchestrator process itself before declaring a
  hard stop.
- **Drowning: 3/20 (15%), confirmed via real `MineRLAgent0 drowned` Malmo messages** — down
  from attempt #12's original 12/20 (60%) baseline. **The attempt #13 fix holds at N=20, not
  just the N=6 it was confirmed at.** Other early terminations (unrelated causes — fall/mob/
  etc., not in scope for this fix): 5/20 (25%). Full-length "fair shot" episodes: 12/20 (60%),
  up from ~8/20 (40%) in attempt #12's original batch.
- **Chopping/crafting: 0/20 logs, 0/20 planks** — despite more episodes getting a fair shot,
  no chops this batch (vs. attempt #12's 1/20). Not a significant regression at this N (Fisher
  would not distinguish 0/20 from 1/20) — just this campaign's usual small-N variance. Confirms
  the standing diagnosis again: removing the drowning confound increases fair-shot episodes but
  does not by itself convert into chopping — survival and search/approach effectiveness remain
  separate problems.
- **The `reward=144.000` anomaly — investigated, NOT reproduced, remains unexplained.**
  `play_craft.py` gained an optional `logging.full_inventory` diagnostic (default off, bit-
  for-bit unchanged when unset) that tracks/prints the max value of EVERY inventory key per
  episode, not just log/planks. A fresh N=12 batch with it enabled (same config) showed:
  reward=0.000 on all 12 episodes, and the ONLY inventory item ever non-zero across the whole
  batch was `dirt` (1-30 per episode, picked up incidentally while walking/attacking) — dirt is
  NOT in the reward table (`RewardForPossessingItem` covers log/planks/stick/crafting_table/
  wooden_pickaxe/cobblestone/furnace/stone_pickaxe/iron_ore/iron_ingot/iron_pickaxe only), so it
  earns zero reward and is a red herring for the original mystery. The original episode's
  process had already exited before this diagnostic existed, so its exact state is
  unrecoverable — the mechanism that produced 144 did not recur in 12 fresh attempts and stays
  a one-off, uncharacterized event. Doesn't affect any campaign conclusion (chop rate is what
  matters, and this is orthogonal to it) — parked as a documented curiosity, not pursued
  further absent a much larger sample.

Phase 5+ — Cold-start attempt #16: Coverage-Value Predictor (CVP), the first candidate-3
mechanism built under the "no single-frame photometric scoring" constraint (per #15) —
**offline aggregate gates encouraging, per-trial trained regressor NO-GO at this sample size**:
- Design (Explorer proposal, externally reviewed and refined — see the exchange above): a
  small MLP predicting `Δunique_cells` (exploration payoff) per candidate heading from
  non-photometric features only (classical per-quadrant frame-diff flow + `FrontierTracker`'s
  local visitation histogram) — a genuine JEPA-shaped predictor (input+action → future state)
  with the target swapped from pixels to geometry, feeding the already-validated frontier scan
  macro rather than replacing its handoff to the chop planner.
- **Instrumentation + data collection**: `scan.frontier.log_transitions` (config-gated, default
  off) added to `scripts/play_craft.py`; two batches collected. First (N=12, 57 rows) hit a
  real, previously-unnoticed bug: `FrontierTracker.frontier_heading_deg()` breaks ties toward
  the smallest heading index, and since sparse-grid cells are almost always tied at 0 visits,
  54/57 triggers "chose" heading 0.0° by construction, not genuine preference — Gate 1
  (dynamic range across headings) was uncertifiable on this data. Fixed via a config-gated
  `tie_break="random"` option (seeded, default `"first"` = old behavior verified unchanged) and
  re-collected (N=14, 44 rows, all 12 headings represented, 1-7 rows each).
- **Offline gates on the re-collected data**: Gate 2 (brightness does not dominate the target)
  **passed on BOTH batches independently** (r≈0.10, opposite signs — the most reproducible
  non-confound result in the campaign's history). Gate 1 (dynamic range) improved substantially
  post-fix but rests on small per-heading samples (1-7 rows) — assessed as "encouraging, not a
  rock-solid confirmation."
- **The actual trained model — NO-GO, and thoroughly checked, not just badly tuned.** Combined
  both CSVs (~101 rows), trained a small MLP (~1.9K params) with mandatory 5-fold CV against a
  trivial "always predict the mean" baseline. Default config: model MAE 1.590 vs. baseline
  1.169 (worse). An 8-way hyperparameter sweep (smaller nets, heavier regularization) never
  once beat the baseline (best ratio 1.06, still worse). A from-scratch linear Ridge-regression
  sweep confirmed this isn't an MLP-overfitting artifact: as regularization strength increases,
  the model's error only approaches the baseline as it's forced toward predicting a near-
  constant — it never surpasses it. **Diagnosis: predicting one specific noisy trial's outcome
  from 4 coarse scene-level features is a much harder task than the aggregate statistics Gates
  1-2 checked, and isn't learnable at N≈100 with this feature set** — not evidence the
  aggregate signal is fake, just that per-row prediction needs substantially more data (likely
  several hundred rows, not tuning) to be learnable, if it's learnable at all with these
  features.
- Per the dispatch's own honesty discipline, the model was correctly NOT wired into
  `play_craft.py`, no `scan.macro: "learned_frontier"` was added, and no live episode was
  spent testing a model the CV gate said doesn't work. No checkpoint written
  (`checkpoints/coverage_predictor.pt` does not exist). `ebwm.pt`/`craft_wm_v4.pt` untouched.

▶ **Status — campaign has now run 16 numbered attempts; the central chop-planner metric
(confirmed backwards in attempt #10) is the one major mechanism never yet fixed, and is
increasingly the last unexamined lever:**
- **#1 (encoder/scoring correction) closed, 5-fold confirmed**: attempts #7, #11, #14 (Phase
  1 CLIP + Phase 2 direct retrain), and #15 (ratio-normalized chromaticity) each independently
  hit a brightness/domain-composition confound. No single-frame photometric feature — learned,
  off-the-shelf, or hand-designed-invariant — fixes it.
- **#2 (coverage/execution) has the campaign's only real positive results**:
  `commit_length=4` alone (9.7% pooled), attempt #12's frontier search (1/20, later confirmed
  at N=20 with attempt #13's hazard fix layered on: drowning 60%→15%, fair-shot episodes
  40%→60%, but chop rate stayed at 0/20 — diminishing returns from coverage alone, exactly the
  condition that justified trying #3). Attempt #16 (CVP) extended this line under the
  no-photometric-scoring constraint and found real aggregate signal (Gate 2, twice) but no
  learnable per-trial model yet at this sample size.
- **#3 (H-JEPA proper) not built** — attempt #16 was the cheap, non-photometric first probe
  the standing diagnosis called for; it didn't produce a deployable mechanism, but it also
  didn't fail for a photometric reason, so the door isn't closed the way #1 is. Next-cheapest
  version if resumed: collect substantially more transition rows (~several hundred) before
  retraining, per the CVP dispatch's own recommendation.
Phase 5+ — Cold-start attempt #17: two-pronged direct attack on `ebwm.pt`'s central,
never-fixed goal-centroid score — **both prongs NO-GO, and the result is more conclusive than
just "two more failures":**
- **Prong A — OOD-gated fallback (Mahalanobis distance on `ebwm.pt`'s own pooled latent,
  Lee et al. arXiv:1807.03888, added to `docs/references/index.md`).** Idea: detect when a
  frame is out-of-distribution for `ebwm.pt` and defer to the already-working `FrontierTracker`
  search instead of trusting an uncalibrated score there — orthogonal to "fix the score,"
  closed-form statistics only, no trainable component. `scripts/diagnose_ood_gate.py`, 3
  offline gates, all FAILED: separation 1.294x (bar 1.3x — missed by a hair), specificity to
  attempt #10's confirmed-wrong frames only 1.105x (bar 1.2x — detects "this is Obtain," not
  "this score is wrong"), and — the sharpest finding — **correlation with raw brightness
  r=0.56, squarely inside the established confound range (0.117-0.947), despite this being a
  plain closed-form Gaussian fit with NO gradient, NO loss function, and NO way to "learn" a
  shortcut.** This is the 6th confirmation of the confound, and the most structurally decisive
  one: it shows the confound isn't something downstream heads learn — it's baked into the raw
  geometry of `ebwm.pt`'s frozen latent space itself, inherited by any statistic built on top
  without retraining the encoder.
- **Prong B — check whether attempt #14 Phase 2's one-frame anomaly is a data-coverage gap
  (attempt #7's original, never-tested hypothesis) before collecting anything new.** Read-only
  analysis using `hazard.py`'s own calibrated underwater/cave detector (not raw brightness,
  which turned out to be a poor discriminator here — Treechop is actually darker on average
  due to canopy shade). Result: `ebwm.pt`'s ORIGINAL Treechop-only training data has only 1.0%
  underwater/cave-flagged frames — attempt #7's flagged gap was real for the original model.
  **But the Obtain-domain data attempt #14 Phase 2 actually fine-tuned on
  (`minerl_coverage`/`minerl_craft`) already has 16-22% such frames, even 4x-oversampled** —
  the gap that motivated this prong is already closed for the data actually used. The specific
  anomalous frame was tentatively identified (visual + numeric match, one unreconciled
  discrepancy honestly flagged rather than papered over) and sits well inside the range of
  already-present training examples, not an extreme outlier. **Conclusion: new data collection
  is not well-supported as the next step** — if revisited, a reweighting/training-objective
  fix (nothing in VICReg+prediction loss explicitly rewards correct relative distance ordering
  across biomes) is the better-motivated next question, not more data.
- **Standing diagnosis, now on its firmest footing yet**: 6 independent, mechanistically
  diverse approaches (2 trained heads, 1 off-the-shelf 400M-image model, 1 direct encoder
  fine-tune, 1 hand-designed ratio feature, 1 untrained closed-form statistic) all converge on
  the same brightness/scene-composition confound. Combined with Prong B closing the
  "just needs more data" theory, the confound looks structural to `ebwm.pt`'s frozen
  representation and/or its training objective, not fixable by anything built on top of the
  existing checkpoint without retraining its core objective — a materially more expensive
  undertaking than anything tried in attempts #7-#17. **Not yet decided whether that's worth
  pursuing, or whether to consolidate around the mechanisms that already work
  (`commit_length`, frontier coverage, hazard avoidance) and accept the central score as a
  permanent known limitation — ask the user.**
- **Site**: French chapters 1-17 complete and live (`site/fr/17-le-raccourci-est-dans-l-oeil.html`),
  `docs/10_coldstart_engineering.md` has full detail through attempt #17. English translation
  (separate tool, not this session's agents) lags at chapter 13 by deliberate convention.

Phase 5+ — Cold-start attempt #18 (literature-motivated): a dedicated arXiv search pass
(2026-07-27, covering 2026-07-13 to 2026-07-27) surfaced 5 new JEPA papers, added to
`docs/references/index.md`. Two of them reopened concrete, cheap sub-questions ahead of the
retrain-vs-consolidate decision attempt #17 left open — two offline diagnostics were dispatched
in parallel to inform it. **Diagnostic 1's initial small-N result looked like the campaign's
first-ever GO on the central scoring problem, but did NOT survive a same-day follow-up with a
larger, more representative hand-labeled set — corrected below, not swept under the rug.
Diagnostic 2 found a genuinely new, non-photometric contributing factor that still stands.
Neither has been wired into the live planner — both are offline-gate results only.**

- **Diagnostic 1 — pseudo-depth generalization — initial GO did not replicate at larger N;
  corrected verdict MIXED.** Motivated by Khan, "Depth-Regularized JEPA World Models Learn More
  Transferable Representations from Real Outdoor Robot Data" (arXiv:2607.16314): that paper adds
  a depth-supervision auxiliary term to a JEPA world model and gets measurably better in-domain
  AND out-of-domain generalization under real domain shift — the first published instance of
  attempt #15's own conclusion that the brightness confound needs "a different modality
  entirely," not another photometric single-frame feature. `scripts/diagnose_depth_gate.py` runs
  MiDaS_small (torch.hub `intel-isl/MiDaS`, off-the-shelf, zero Minecraft-specific training, same
  "outside model" logic as attempt #14 Phase 1's CLIP test) over the campaign's standard
  251-frame diagnostic set, scoring each frame by the mean of its closest 10% of MiDaS-predicted
  pixels (nearest-object proxy).
  - **First pass, tiny hand-labeled sample (tree_close n=4, no_tree n=6 — the same small set
    every prior attempt reused)**: Gate A (separation) ratio **1.304x**, just over the 1.3x bar;
    Gate B (brightness-independence, all 251 frames) r=**0.0451**, by far the campaign's best.
    Read at face value this looked like the first mechanism in 7 independent tests to pass both
    established gates — flagged at the time as "a thin margin on a small sample," not a
    declared victory, precisely because that margin looked fragile.
  - **Follow-up, same day: hand-labeled set expanded to tree_close n=10, no_tree n=17** (10
    genuinely new frames visually inspected and added to `configs/diagnose_depth_gate.yaml`'s
    `direction_check` block, no cherry-picking — see the script's own git history for exactly
    which episodes/chunks were added). **Gate A now FAILS: ratio dropped to 1.086x** (mean 644.3
    vs. 593.5) — the original 1.304x was a small-sample artifact, not a real, robust separation.
    **Gate B still PASSES comfortably, unchanged: r=0.0451.**
  - **Corrected VERDICT: MIXED, not GO.** The depth signal remains genuinely independent of raw
    brightness — a real, reproducible property, and still the best brightness-independence
    result in the campaign's history — but it does NOT reliably separate tree-close from open
    scenes once judged on a larger, more representative sample. This is the same pattern the
    campaign has seen before (small-N encouraging results not surviving scrutiny) — being
    corrected here in the same session rather than left standing as a false "first GO."
  - **Live sanity test (N=6, new `scan.macro: "depth"` steering variant,
    `configs/play_craft_commit4_depth.yaml`, built on top of the already-validated
    commit_length=4 + hazard-avoidance baseline) — result: no chopping (expected, not the
    question this batch was asked), mechanism barely exercised, and one concerning regression
    signal not to ignore.** Dispatched against the ORIGINAL small-N Gate A pass; read correctly
    as "does a depth-driven heading behave sanely," not as fixing anything, since Gate A did not
    hold up (above). `mine_jepa/ebwm/depth.py` (new module: MiDaS model loading, per-column
    depth scoring, heading-delta computation — kept separate from `diagnose_depth_gate.py` and
    never touches `CraftPlannerV4`/`SwitchingCraftPlanner`'s latent-space scoring, only chooses a
    scan-macro heading from the real current frame, exactly the design constraint this dispatch
    was given).
    - 0/6 logs, 0/6 planks, mean reward 0.000 (below MineRL's ~0.4 random-policy baseline) —
      unsurprising and not the question asked.
    - **The scan macro triggered only 3 times total across all 6 episodes** — `goal_score_std`
      rarely dropped low enough to invoke it, so this batch barely exercised the new mechanism.
      The "does it behave sanely" question this test was designed to answer is only weakly
      answered by this N, independent of the small-N caveat that already applies everywhere in
      this campaign.
    - Of the 3 triggers, per-tick `[depth]` logs show no severe lock-in (unlike attempt #6's CEM
      or attempt #8's action-pool priming, both >80% single-action concentration) — one trigger
      (ep1) converged in 2 ticks; one (ep4) held a consistent rightmost-column heading across 4
      of 6 ticks with one detour; **one (ep5) reversed from the rightmost column (delta +26.2°)
      to the leftmost (delta -26.2°) in a single 16-tick step** — not the campaign's classic
      ping-pong-every-replan oscillation bug (attempt #13's first steered-escape round), but a
      real, unexplained full reversal on too small a sample (2 data points) to characterize
      further.
    - **Regression signal, flagged not buried**: 2/6 episodes ended with `died_during_escape=True`
      (death while the hazard-avoidance reflex was actively trying to escape water) — the exact
      failure mode attempt #13's final round (widened `align_deg` + debounced dry-anchor)
      believed FIXED at 6/6 survived, 0 deaths, N=6. This batch reused that identical hazard
      config, only adding the new depth scan macro alongside it. Not established as causal at
      this N (could be batch-to-batch noise recurring by chance), but plausible: monocular depth
      models are known to behave unpredictably on reflective/transparent surfaces like water, so
      a depth-driven heading could plausibly steer toward or linger near water in a way the
      previous `"turn"`/`"frontier"` macros didn't. **Before trusting the attempt #13 hazard fix
      as robust across scan-macro choices, this deserves a dedicated check — not asserted as a
      confirmed regression, but not dismissed either.**
    - GIF: `assets/agent_play_craft_commit4_depth.gif`. Full log:
      `logs/coldstart_attempt18_depth_sanity_n6.log`.
- **Diagnostic 2 — Treechop/Obtain action-coverage overlap — a genuinely new, non-photometric
  factor found.** Motivated by Zhang, Guan, Zhang, Zhang, Li, "On the Identifiability of
  Controlled World Models" (arXiv:2607.22430): an action-conditioned JEPA only recovers
  reliable state/dynamics when the training action distribution has adequate coverage.
  `scripts/diagnose_action_coverage.py` measured this directly (no GPU needed, pure action-array
  statistics, seeded, self-calibrated against a Treechop-vs-Treechop split-half null):
  - **Out-of-vocabulary fraction**: only **2.33%** of pooled Obtain-domain actions use an index
    outside `ebwm.pt`'s trained 17-action vocabulary (far lower than the naive "5/22≈22.7%"
    estimate this dispatch started from — the craft-heavy expert demos rarely invoke crafting
    actions relative to movement; the random-policy coverage set alone is 22.6% OOV).
  - **Jensen-Shannon divergence, shared action indices**: Treechop vs. pooled Obtain = **0.1453**,
    vs. a Treechop-vs-Treechop-split-half null baseline of **0.0014** — a **104x** ratio, not
    explainable by sampling noise. Treechop's own demos are 58.5% attack / 14.7% forward / 12.0%
    noop ("walk to a tree, hold attack"); Obtain is comparatively noop/forward-heavy and
    attack-light (33%/31%/25%). **This is the first diagnostic in 18 attempts to surface a real,
    large, non-photometric distributional gap between the two domains.**
  - **Bonus finding, more specific than what was asked**: Treechop's *own* training data only
    ever exercises **8 of `ebwm.pt`'s 17 trained action indices** (strafe, jump, and both camera
    tilt directions are never sampled during training at all) — an internal coverage gap inside
    Treechop itself, independent of the Obtain domain.
  - **Interpretation, held to the campaign's own discipline**: this establishes a real
    distributional gap, but does NOT by itself prove the arXiv:2607.22430 mechanism causes the
    attempt #10 score reversal — the paper's claim is about state-action-next-state
    identifiability, and this diagnostic only measured the marginal action-usage histogram, not
    whether specific transitions needed for correct Obtain-domain dynamics exist in `ebwm.pt`'s
    training set. A plausible contributing factor, not a confirmed cause.
- **Updated standing diagnosis**: the "encoder/scoring confound is structural and unfixable
  by anything short of retraining" conclusion from attempt #17 **still stands on the separation
  question** — depth's Gate A pass did not replicate at larger N, so no mechanism has yet
  cleanly separated tree-close from open scenes AND stayed brightness-independent at a
  trustworthy sample size. What genuinely changed: depth's brightness-INDEPENDENCE (Gate B,
  r=0.045, unchanged across both samples) is real and reproducible — a non-photometric signal
  that isn't itself a brightness shortcut, even though it isn't (yet, alone) a working
  tree-detector — and Diagnostic 2's action-coverage gap is a separate, still-standing, genuinely
  new non-photometric factor. Neither is a proven live fix. Diagnostic 2's finding (action-
  coverage gap, including Treechop's own internal 8/17 gap) reframes "retrain the core
  objective" from a vague, expensive idea into two concrete, scoped candidate fixes: broaden
  Treechop's own action coverage, and/or reweight training toward the actions Obtain actually
  uses — this reframing is unaffected by Diagnostic 1's correction. **Decision made (2026-07-28):
  retrain `ebwm.pt`'s core training objective (not consolidate).** Rationale given: after 18
  attempts with diminishing returns on the "fix it from outside the frozen checkpoint" line,
  and with two concretely scoped levers now on the table (broaden Treechop's own action
  coverage / reweight toward Obtain's action mix, per Diagnostic 2; swap VICReg for SIGReg per
  Arnez & Gomez-Villa arXiv:2607.13612), retraining is judged the path to definitive progress
  rather than continued small partial fixes. The small drowning-regression signal from the
  live sanity test (2/6 `died_during_escape`) is explicitly deferred, not dropped — to be
  checked later, not blocking this decision. **This opens cold-start attempt #19.**

Phase 5+ — Cold-start attempt #19: the first real retrain of `ebwm.pt`'s core training
objective in 19 attempts (previously only ever frozen or lightly nudged) — **both concretely
scoped levers from attempt #18's decision failed, Run A diagnosed (data-side), Run B diagnosed
more severely (architecture-side); campaign paused and consolidated here, not continued into a
3rd lever:**
- **Run A — broaden Treechop's own action coverage: NO-GO, diagnosed (not just failed).**
  `scripts/prepare_demos.py::discretize_actions()` was extended to read `action$jump/left/
  right/back` + camera pitch (previously only forward/attack/sprint/yaw), raising Treechop's
  own action-index coverage from 8/17 to 15/17. Fused with Obtain data exactly as attempt #14
  Phase 2, fine-tuned 5 epochs from `ebwm.pt`'s current weights (LR=3e-5, VICReg intact,
  seed=0, snapshots `ebwm_v3_actioncoverage_epoch{1..5}.pt`, `ebwm.pt` never touched, md5
  reverified). **Gate A (separation, expanded n=10/17 hand-labeled set) failed on baseline
  (0.790x) AND all 5 epochs (0.531x-0.775x), non-monotone, never ≥1.3x.** A new Gate C
  (Treechop non-regression) was added; its direction sub-test turned out to be invalid by
  construction (the baseline itself fails it, 0.434x — not a fine-tune-caused regression,
  removed from the verdict, magnitude-only band kept). JSD(Treechop, Obtain) barely moved
  (0.1453→0.1585, slightly worse) — raw index coverage improved but distributional shape
  didn't.
  - **Root-cause diagnostic (dispatched on the user's request before deciding next steps)**:
    independently re-verified, twice, that the "jump masks attack in the if/elif priority
    order" hypothesis is FALSE — attack-frame counts are byte-identical between old and new
    datasets (265,454/265,454). What actually changed: 4.73% of frames relabeled, dominated by
    a real `forward→forward+jump` reclassification (11,626 frames, genuine bunny-hop, a
    correct relabel not corruption). **Best-supported (not proven) explanation**: those
    long-idle action indices (jump/strafe/pitch) went from ~1.2% to ~3.8% of the weighted
    training mass in one step (~9x on the jump+forward index alone) — a sudden gradient
    injection onto near-untrained action embeddings, plausibly destabilizing the predictor's
    shared weights even though the already-well-trained indices' own frames never changed. A
    Run A-bis (warmup / frozen action-embedding table / lower LR) was scoped but not attempted
    — user chose to go directly to Run B instead.
- **Run B — VICReg→SIGReg (Balestriero & LeCun arXiv:2511.08544 / Arnez & Gomez-Villa
  arXiv:2607.13612): NO-GO, more severely broken than Run A.** Scoping found `ebwm.pt`'s
  current "VICReg" is actually only `HingeStdLoss+CovarianceLoss` on a single tensor (`state`)
  — `sim_coeff_t`/`idm_coeff` were already inert at 0, no paired-view/EMA-target mechanism
  exists in this pipeline. Implemented as a ~15-line `SIGRegRegularizer` calling the
  already-vendored `BCS(state, state)` (same tensor twice — invariance term neutral at 0 by
  construction, anti-collapse role from Epps-Pulley marginal-gaussianity test alone, no EMA
  needed per LeJEPA's own "collapse-free without stop-grad" claim). Full replacement, not
  additive (`std_coeff=cov_coeff=0`, `sigreg_coeff=1.0`), original (non-`_v2`) dataset,
  augmentation disabled to isolate the one variable, LR=1e-5 (10x more conservative than Run
  A), 3-epoch cap with a new **effective-rank gate** (participation ratio on `state`'s
  covariance) built specifically because `batch_var` cannot see dimensional (as opposed to
  isotropic) collapse.
  - **The new gate did exactly the job it was built for**: epoch 1 alone triggered early stop
    — effective rank collapsed 26.69→4.50 (-83%) while `batch_var` stayed perfectly healthy
    (1.36, as high as any VICReg run) — a real, invisible-to-the-old-metric collapse mode,
    caught before wasting epochs 2-3. Offline gates on the one snapshot produced: Gate A worse
    than Run A's baseline (0.367x vs 0.790x, more reversed, not less), Gate C badly failed
    (Treechop's own score fell to 5.7% of baseline — a generically broken checkpoint, not a
    nuanced confound reading). Gate B passed nominally (r=0.131) but is judged low-value here —
    a brightness-independence reading on a representation collapsed to ~4.5 effective
    dimensions isn't measuring much. `ebwm.pt` never touched (md5 reverified).
  - Explicitly NOT read as an 8th confound confirmation — the failure mode here (dimensional
    collapse from a single-term anti-collapse loss with no covariance pressure) is mechanically
    distinct from the brightness/composition confound the rest of the campaign established. A
    mitigated Run B-bis (partial CovarianceLoss retained alongside SIGReg, additive rather than
    full replacement) was proposed as an option but not attempted.
- **Decision (user's call, both levers having failed): pause and consolidate rather than scope
  a 3rd lever immediately.** Both of attempt #18 Diagnostic 2's concretely-scoped fixes are now
  exhausted as originally specified — this is not the same as "retraining `ebwm.pt`'s core
  objective is impossible," only that these two specific, cheapest-available implementations
  of it failed for two different, now-diagnosed reasons (data-side gradient-injection
  instability; architecture-side single-term anti-collapse under-constraining covariance). The
  working, non-photometric mechanisms from earlier in the campaign
  (`commit_length=4`, `FrontierTracker` coverage search, hazard-avoidance/drowning fix) remain
  the only validated positive results and stand as the campaign's current baseline. No live
  MineRL/Java test was run for either Run A or Run B (correctly withheld — neither passed its
  offline gate). `checkpoints/ebwm.pt` untouched throughout attempt #19 (md5
  `ac14e65361fbddeb057963362ea1382d`, reverified after both runs); `ebwm_v3_actioncoverage_
  epoch{1..5}.pt` and `ebwm_v3_sigreg_epoch1.pt` kept as comparison artifacts only, neither
  promoted.

Phase 5+ — Cold-start attempt #20: the first measurement, in 20 attempts, of whether `ebwm.pt`'s
rollouts respond to ACTIONS at all — a dynamics-side question, where attempts #7-#19 were almost
entirely scoring-side. **Offline result: the action pathway is alive but net-harmful; conditioning
on the true action is significantly WORSE than assuming noop, on the training domain itself.
Nothing wired live, no checkpoint touched.** Full detail: `docs/10_coldstart_engineering.md`
(⚠️ note: attempt #19 was never written into `docs/10` — this file remains its only record).
- **Origin**: a bibliography refresh (2026-08-10, arXiv + Google Scholar, first pass since
  2026-07-27) surfaced Gan et al., "ActSWM" (arXiv:2607.26712), **whose baseline is LeWM — our own
  architecture family — on closed-loop Minecraft planning**. It names *Context Collapse*: a latent
  predictor that keeps high similarity to the true future while producing nearly indistinguishable
  futures under different actions — a healthy `ratio` with a blind planner, which is this
  project's exact Phase 4/5 symptom. Paper verified by reading the LaTeXML source directly
  (equations, Table 3 hyperparameters, Table 8 counts), not a summarizer.
- **Method** (`scripts/diagnose_context_collapse.py`, `configs/diagnose_context_collapse.yaml`):
  ActSWM Eq. 10 — roll out K=12 twice from the same context frame under recorded vs. all-noop
  actions, compare both to the encoded true future by cosine. Plus two additions reported
  separately: a **random-action arm** (the planner compares non-noop candidates, never
  "recorded vs. noop") and a **planner-matched spread arm** (offline counterpart of the live
  `goal_score_std`). Treechop serves as its own positive control — the agent demonstrably plans
  there (25-50% chop), and this project has no external threshold for this never-before-measured
  quantity. A near-zero delta being ambiguous, a **second measurement disambiguates it**: L2
  spread of the 1-step prediction across all 17 actions, over the true 1-step latent change.
- **Result (n=400/domain; 266 for `obtain_coverage`, the only windows surviving `max_action=17`
  — treated as the noisier column, not equal evidence):**
  - **Not Context Collapse as literally defined.** The action pathway works: 17 actions move the
    prediction (spread 0.52-0.70), embedding table healthy (mean pairwise cosine -0.014).
  - **But the response is a net liability.** `delta_zero` is negative in all three domains, and
    significantly so **at k=1 — the exact regime `ebwm.pt` was trained on** (`nsteps=1`), so this
    is NOT multi-step rollout drift: treechop -0.000444 (t=-2.49, p=0.0130, true action wins in
    only **35.5%** of windows), obtain_craft -0.000113 (t=-4.37, p<0.0001, **13.0%**),
    obtain_coverage -0.000149 (t=-2.51, p=0.0126, **28.2%**) — chance is 50%.
  - Consistent ordering everywhere: **noop > true action > random action.** The model learned
    something real (true beats random) but not enough to clear the trivial copy-last baseline the
    noop rollout approximates — consistent with `ratio=0.9265` (beats copy-last by only ~7%).
  - **Unplanned internal consistency check**: the win-rate is perfectly monotone in how dynamic
    the domain is (real 1-step latent move 4.82 → 13.0%, 11.31 → 28.2%, 16.22 → 35.5%). The more
    static the footage, the stronger copy-last is and the more the miscalibrated action
    perturbation costs. Fell out of the data; was not designed for.
  - **Negative control**: corr(delta, brightness) = -0.048 / +0.031 / -0.225 — **first mechanism
    in the campaign essentially uncorrelated with brightness** (prior range 0.117-0.947). Expected
    by construction (delta differences two rollouts from the SAME frame, so frame-level confounds
    cancel), but worth stating after six prior failures on this check.
- **What it establishes**: `ebwm.pt` is, for planning, close to a copy-last predictor carrying an
  action perturbation that doesn't track consequences. **This holds on Treechop, its own training
  domain** — so unlike attempt #10's reversal it is NOT a domain-shift effect. A second,
  independent defect on the **dynamics** side.
- **What it does NOT establish, stated as a real tension not a footnote**: this cannot by itself
  be the cold-start cause, since the agent chops 25-50% on Treechop *with this exact deficit*.
  Any account leaning on this finding must explain that too; none is offered. Nor is ActSWM's fix
  shown to transfer — their predictor carries H=32 context, `ACConvPredictor` has
  `context_length=1`, so their causal story ("long context lets it extrapolate while ignoring the
  action") cannot apply unchanged.
- **What it reframes**: `commit_length=4` (the only lever that ever gave a non-zero result, 9.7%)
  makes sense mechanically — if per-step action information is at noise level against copy-last,
  committing to an action block instead of re-ranking every tick on a noise-dominated score is
  the right compensation. Found empirically in attempt #4 without knowing why.
- **Lever this opens (not taken — user's call)**: ActSWM's `L_readout` (Eq. 8) enforces exactly
  the broken property. **Half that machinery already exists here, disabled since day one**:
  `mine_jepa/eb_jepa/losses.py::InverseDynamicsLoss` is `(state_t, state_t+1) → action`, wired
  into `VC_IDM_Sim_Regularizer`, but `build_ac_jepa` passes `idm_coeff=0.0, idm=None`
  (`mine_jepa/ebwm/__init__.py:146`) so it is never instantiated. Missing vs. ActSWM: parameter
  freezing (`idm.stop_grad=true`), application to rollout-predicted transitions (Eq. 8b), and the
  hinge term (Eq. 5). Attempt #19 spent two retrains for two NO-GOs; this diagnostic does not on
  its own promise a third would land.
- `ebwm.pt` md5 `ac14e65361fbddeb057963362ea1382d` reverified after the run; `craft_wm_v4.pt`
  untouched. 9 new papers added to `docs/references/index.md` in the same pass (all IDs verified
  against live arXiv pages), including two the arXiv-only queries had missed and Google Scholar
  found (JEDI arXiv:2605.13013, MineExplorer arXiv:2605.30931).

▶ **CAMPAIGN CLOSED on attempt #20 (user's decision, 2026-08-10).** Not paused — closed, with #20
as the concluding result rather than a 21st attempt. Rationale:
- **The campaign was working on the wrong layer.** Attempts #2-#19 tuned search/scoring/execution
  on top of a frozen `ebwm.pt`; attempt #20 measured that `ebwm.pt`'s action conditioning is a net
  liability against copy-last, so the MPC planner ranks candidates by differences that don't track
  consequences. That retrospectively explains why three score fixes (#7/#11/#17), two search fixes
  (#5/#6) and two retrains (#19 Run A/B) each failed differently — none touched the dynamics.
- **The remaining lever is a rebuild, not a patch.** ActSWM's `L_readout`+hinge target exactly the
  measured defect and half the machinery already exists disabled (`InverseDynamicsLoss`), but
  applying it well plausibly also means changing `ACConvPredictor`'s `context_length=1` (their
  causal story depends on a 32-frame context). That is a world-model rebuild.
- **The project's stated purpose is already met** (line 1: packaging, not from-scratch research):
  Phases 0-4 validated with real gates, agent chops trees in real Minecraft (25-50%), live craft
  demo 100% over 6+ episodes, and the whole campaign documented including its negatives.
- **NOT claimed**: that cold-start chopping is impossible, or that the remaining lever would fail.
  ActSWM shows a LeWM-family model planning successfully in closed-loop Minecraft (mining 19/20),
  so the capability is real for this architecture family at larger scale. The narrower, supported
  claim: **this campaign's approach — fix the planner around a frozen 664K-param world model with
  `context_length=1` — is exhausted, and #20 explains why.**
- **Standing baseline if work ever resumes**: `commit_length=4` (9.7% pooled, campaign best),
  `FrontierTracker` coverage search (#12), hazard-avoidance drowning fix (#13, confirmed at N=20:
  drowning 60%→15%, fair-shot episodes 40%→60%). Left open, not resolved: attempt #18's deferred
  2/6 `died_during_escape` signal (possible regression of the #13 fix under the depth scan macro).

⚠️ Phase 4 on **NVIDIA PC only**. MineRL requires Java 8.
Installation: DO NOT use `uv pip install minerl` directly.
See complete procedure below (patches gym + minerl + Gradle).

MineRL installation notes (Windows/Python 3.12):
- `gym==0.19.0`: patch `opencv-python>=3.0` in setup.py (download source, patch, install)
- `minerl`: build from patched source `C:\tmp\minerl_src\minerl-0.4.4\`
  - `setup.py`: `shell=True` for gradlew.bat + copy pre-built JAR
  - `build.gradle`: replace MixinGradle JitPack with `org.spongepowered:mixingradle:0.6-SNAPSHOT`
  - Initial Gradle build: run via `C:\tmp\run_gradle.bat` (Java 8 required)
- Java 8: `choco install temurin8` (admin) → `C:\Program Files\Eclipse Adoptium\jdk-8.0.472.8-hotspot`
- ⚠️ `minerl/env/malmo.py`: 2 `.decode(mine_log_encoding)` calls (lines ~511 `launch` and ~579
  `log_to_file`) crash on Minecraft's § colour byte (0xa7/0x82) because PYTHONUTF8=1 forces utf-8
  as the locale encoding. Patch both with `errors="replace"` (lost on minerl reinstall). Surfaces
  on MULTI-instance launches (more log output → hits a bad byte).

Multi-agent (shared world) — attempted, see `mine_jepa/envs/__init__.py` (`MineRLTreechopMulti-v0`,
agent_count=2) + `scripts/smoke_multiagent.py`:
- MineRL supports it natively (`EnvSpec(agent_count=N)`, dict step/reset). Both clients LAUNCH and
  reach DORMANT, but `reset()→_peek_obs` TIMES OUT: the 2-client mission sync fails (Malmo MALMOBUSY
  family, never solved here). Shared-world multi-agent = BLOCKED on this setup.
- WORKAROUND that works: `scripts/play_parallel.py` (`play_parallel.bat --agents 2`) runs N
  single-agent Minecraft worlds CONCURRENTLY (the stable path) and stitches their videos side by
  side → `assets/agent_play_parallel.gif`. 2 agents run at ~40 fps each on the 8 GB machine. Delivers
  "multiple JEPA agents playing at once" without the shared-world sync wall.

Windows PC notes:
- Always use `run.bat <script>` (wrapper PYTHONUTF8=1 + PYTHONUNBUFFERED=1)
- torch CUDA 12.8 installed manually (uv sync installs CPU by default)

## Code conventions
- Python 3.11+, PyTorch 2.x, timm, einops
- `uv` for package management (lockfile in `uv.lock`)
- Configs in YAML in `configs/` (no hardcoded hyperparams in code)
- Standalone scripts in `scripts/` (each script = one verifiable deliverable)
- Type hints everywhere, no obvious comments

## Embedded pedagogy (learning objective)
The user is **discovering JEPA** — they don't know the subject. For each new concept
introduced in the code: explain the *why* in conversation and point to the corresponding
`docs/0X_*.md` doc. The pedagogical docs = also the project's marketing content.

## Hardware
- **Dev**: MacBook Air M1, 16 GB RAM, **no NVIDIA GPU** → OK for writing code,
  collecting data, testing imports. Too slow for training.
- **Training**: PC with **NVIDIA GPU 8 GB VRAM**, 32 GB RAM → switch BEFORE running
  `train_encoder.py` (Phase 1), `train_wm.py` (Phase 2), `play.py` (Phase 3+).
- **Transfer**: `git push` from Mac → `git clone` + `uv pip install -e .` on PC.

## Python environment
Always prefix with `uv run` (uses the uv-managed venv):
```bash
uv run python scripts/collect.py ...
uv run pytest
```

## Useful commands
```bash
# Collect trajectories (frames + actions) from Crafter
uv run python scripts/collect.py --env crafter --episodes 100 --out data/crafter/

# Linear-probe (Phase 1 gate)
uv run python scripts/probe.py --data data/crafter/ --checkpoint checkpoints/encoder.pt

# Evaluate world model (Phase 2 gate)
uv run python scripts/eval_wm.py --checkpoint checkpoints/wm.pt --steps 10

# Run the agent (Phase 3 gate)
uv run python scripts/play.py --env crafter --task reach_plant --episodes 50
```

## Repo structure
```
mine_jepa/        ← Python source code (encoder, predictor, planner, agent)
scripts/          ← standalone verifiable scripts (collect, probe, eval_wm, play)
configs/          ← YAML hyperparams
docs/             ← pedagogy + marketing
  01_jepa.md      ← What is JEPA (to learn + for the README)
  02_setup.md     ← How to install and run
  03_representation_collapse.md
  04_world_model.md
  05_planning.md
  06_minecraft_port.md
data/             ← datasets (gitignore)
checkpoints/      ← weights (gitignore, then HuggingFace)
assets/           ← GIFs, videos for the README
```

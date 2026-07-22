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
**PHASE 5 — Crafting (MineRLObtainIronPickaxe)** — in progress. Phases 0→4 complete ✅.

▶ **RESUMING WORK? Read this file's "Phase 5+" section below** — it's the up-to-date
record of every cold-start attempt (sticky sampling/scan, coverage fine-tune, and
whatever is in progress). `HANDOFF_PC.md` (a session-to-session bridge doc) has been
retired now that this file stays current within a single continued session.

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
- **Open anomaly, not yet explained**: one episode logged `reward=144.000` despite its own
  summary showing `planks crafted: no` and `chop=188 craft=0` (never left chop mode). The
  underlying env's `RewardForPossessingItem` reward chain covers 11 items up to `iron_pickaxe`
  (log=1 through iron_pickaxe=256) — `play_craft.py`'s own summary line only tracks
  logs/planks specifically, so this episode may have picked up real reward-chain progress
  (e.g. cobblestone/other items) that the script's summary doesn't surface. One sampled Malmo
  log in this batch's time window shows the reward counter climbing to 21. Not reconciled with
  the specific episode yet — flagged as an open item, not asserted as a hidden success or
  dismissed as a bug.

▶ **Status — five independent confirmations of a domain-composition brightness confound;
two cheap next actions dispatched (N=20 confirmation batch + this chromaticity test, the
latter now concluded); H-JEPA (if pursued) must not rely on single-frame visual scoring:**
- Of the 4 post-#10 candidate directions: **#1 closed, more firmly than before** (attempt #11's
  original finding, reinforced by #14's direct-retrain, #14 Phase 1's CLIP test, and #15's
  chromaticity test — 5 mechanistically different approaches, same wall); **#2** has the
  campaign's only two non-zero chopping successes (`commit_length=4` alone, 9.7%, and attempt
  #12's 1/20) **plus attempt #13's hazard-avoidance, fixed at N=6** — a combined
  frontier+hazard confirmation batch at N=20 is in flight (measuring real chop rate, not just
  survival, for the first time on this combination). **#3 (H-JEPA) — the better-justified
  direction if the coverage-only path plateaus, but must be built around a signal that is NOT a
  single-frame photometric score** (per #15's conclusion) — e.g. multi-frame/temporal state,
  dead-reckoned geometry (already proven viable via `FrontierTracker`), or an entirely
  different modality. **#4 (BC fine-tuning) deprioritized.**
- **Site**: French chapters 1-14 complete and live (chapter 13 = attempt #13, chapter 14 =
  attempt #14 Phase 1/CLIP only — Phase 2's conclusion above is NOT yet on the site or in
  `docs/10`, a known gap). English translation (handled by a separate tool, not this session's
  agents) lags — a known, flagged, not-yet-actioned gap.

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

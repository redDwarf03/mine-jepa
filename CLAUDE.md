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

Phase 5+ — Curiosity for cold-start, attempt #1 (`docs/09_curiosity_coldstart.md`):
- Built a **3-agent dev loop** in `.claude/`: `jepa-explorer` (read-only, proposes from verified refs),
  `jepa-developer` (implements + fixes, guardrailed), `jepa-tester` (runs gates + play, honest on variance),
  orchestrated by `/jepa-loop`. The agents encode the project's lessons (recipe=lever, seed, anti-collapse,
  proxy-ratio-lies). ⚠️ `.claude/agents/` only register on session RESTART.
- Bibliography: `docs/references/index.md` — **all arXiv IDs verified** (6/8 of an earlier draft were wrong);
  §3 = exploration refs (Plan2Explore 2005.05960, ICM 1705.05363, RND 1810.12894) for cold-start.
- **Experiment #1 — Plan2Explore offline novelty bonus → FAILED.** A/B on Treechop, 20 ep: OFF (goal-centroid)
  30% / 0.40 reward; ON (novelty λ=1.0) 25% / 0.25 / **fps 63→25**. Difference NOT significant at N=20.
- ROOT CAUSE: the k=5 ensemble **collapsed during training** (`val_disagree` 0.061→0.0005 by epoch 3) →
  all heads agree → novelty signal flat everywhere → ON≈OFF. **LESSON: we reproduced Plan2Explore's FORM
  without its CONDITION** — it trains the ensemble ONLINE on diverse self-gathered data; we trained OFFLINE
  on narrow frozen Treechop demos, which destroys head diversity. Offline-frozen-ensemble curiosity is a
  dead end on expert demos. Next: RND (immune — fixed random target), or diversity reg, or online self-play.
- Code (config-gated, WM never touched): `mine_jepa/ebwm/curiosity.py`, `scripts/train_curiosity.py`,
  `DiscreteLatentPlanner(novelty_coeff)`, `configs/{train_curiosity,play_explore}.yaml`. `ebwm.pt` intact.

Phase 5+ — Cold-start attempt #2: engineering fixes (`docs/10_coldstart_engineering.md`) — CODE DONE,
awaiting PC eval:
- Diagnosis (Fable): the cold-start failure is partly REPRESENTATIONAL, not just exploratory —
  (1) i.i.d. uniform candidate sampling never proposes sustained gestures ("turn 6 steps then walk"
  ≈ (1/17)⁶); (2) "no tree in view" is detectable for free: std of goal_scores across the 512
  candidates ≈ 0 ("the argmax picks among lottery tickets").
- [x] **Sticky sampling (iCEM-lite, arXiv:2008.06389)**: `_sample_actions()` in planner.py, used by
  `DiscreteLatentPlanner` + `SwitchingCraftPlanner`. `planner.sticky_prob` YAML key (0.0 default =
  bit-for-bit original, verified; 0.7 → repeat rate 72% vs 7% i.i.d., smoke-tested on Mac).
- [x] **Scan macro**: `plan(..., return_info=True)` → `goal_score_std`; play_ebwm.py + play_craft.py
  (chop mode only) force camera-yaw a12 after `patience` flat replans until std recovers. Config
  block `scan:` (enabled:false default). ⚠️ `flat_threshold` MUST be calibrated first on the PC:
  `scan.log_std=true`, 2-3 Treechop episodes, read std tree-visible vs lost.
- [x] **Gate (PC, 2026-07-08): PARTIAL — full results in `docs/10` results section.**
  - Treechop A/B (seed 0): OFF 45% (9/20, rw 0.50); sticky 0.7+scan 25% (5/20) — over-commits;
    **sticky 0.5+scan 40% (4/10, rw 0.90)** — success in band, ~2× reward/success (depth not breadth).
    ≥50% target missed; no diff significant (Fisher p=0.32/1.0). fps unchanged.
  - Cold-start: **0 logs in all configs (gate FAILED)** — scan@0.004 pathological (agent spins,
    a12 82-92%: std bands COMPRESSED on craft_wm_v4.pt, lost~0.002 vs tree~0.010 vs Treechop's
    0.002/0.02); sticky-only 0/5. Sharpest fact: agent often INSIDE the forest without chopping →
    the wall is the approach/chop behaviour under craft_wm_v4's goal-centroid, not just search.
  - LESSON: an absolute threshold on a checkpoint-dependent statistic doesn't transfer; a recovery
    macro must be bounded by budget, not by the signal it distrusts.
  - Compass swap tested (`goal.chop_data_path`, config-gated): Treechop reward-frames
    centroid encoded by v4 → **still 0/5**. Remaining suspects: craft_wm_v4's visual dynamics
    itself, and the env (Treechop spawns in-forest; Obtain spawns anywhere, sometimes lethal).
  - **Two-brain agent tested** (`chop_model:` config block): ebwm.pt plans chop (17 shared
    movement actions), v4 takes over at first log. Still 0/5 BUT behaviour transformed
    (lumberjack profile a14/a6/a7). GIF: last ep spawned in a TREELESS rocky ravine, ground
    its axe on stone → remaining wall = random spawn without trees + search radius, not the
    gesture. Next levers: scan re-enable in two-brain mode (chop std comes from ebwm.pt →
    0.003 calibration valid again), then online RND.
  - Kept defaults: play_ebwm.yaml sticky 0.5 + scan on (flat_threshold 0.003 calibrated);
    play_craft.yaml sticky 0.5, scan OFF.
- Next cycle: **online RND** (novelty that DECAYS with experience, predictor updated during play —
  RND offline on demos would repeat mistake #1: novelty never decays, agent stares at the sky).

Phase 5+ — Cold-start attempt #3: coverage fine-tune (PC, 2026-07-20, `docs/10` follow-up
section) — **signal improved, outcome unchanged**:
- Hypothesis: `craft_wm_v4.pt`'s compressed `goal_score_std` bands (5x vs Treechop's 10x) are
  a training-data-coverage artifact — the 40 expert Obtain demos rarely show "lost, no tree
  in view" frames. Fix: ~20 short random-policy coverage episodes merged with the demos, then
  a 4-epoch low-LR fine-tune from a backup (`checkpoints/craft_wm_v4_coverage.pt`, seeded, no
  collapse, no craft-precondition regression).
- Result: std band separation widened (p90/p10 ratio ×3.2 → ×5.4) — the coverage-gap
  mechanism is real — but **0/3 logs chopped on BOTH the backup and fine-tuned checkpoints**,
  identical craft outcome, and the fine-tuned checkpoint died early in 2/3 episodes (more
  movement, more danger, not more chopping).
  - **LESSON: sharpening the "am I lost" signal does not by itself fix the search/approach
    behaviour that acts on it.** This confirms attempt #2's two-brain diagnosis: the wall is
    behavioural (search/approach), not perceptual. Coverage data made the model *know* it's
    lost more clearly; it did not teach it what to *do* about it.
- `ebwm.pt`, `craft_wm_v4.pt`, `craft_wm_v4_backup.pt` all intact — `craft_wm_v4_coverage.pt`
  is a new, separate comparison checkpoint, not a replacement.
- Next: **online RND** — behaviour-shaping (reward computed and the predictor updated
  during play), not another perception-side patch. Concrete reuse plan: `mine_jepa/ebwm/curiosity.py`
  (`DisagreementEnsemble`, already config-gated for the offline version that failed in
  chapter 09).

Phase 5+ — Cold-start attempt #4: `commit_length` (real result) + online RND (tried, inconclusive)
(PC, 2026-07-20, `docs/10` follow-up section):
- **`commit_length` — first non-zero cold-start result.** `plan()` was scoring good multi-step
  sequences correctly but returning only their 1st action every replan, discarding steps 2..12
  of its own winning plan on every tick. `commit_length=4` (config-gated, `mine_jepa/ebwm/planner.py`,
  default 1 = old behaviour byte-for-byte) executes the first 4 actions of the winning sequence
  before replanning. Pooled over 3 batches (N=5+6+20=31, seed 0, two-brain, sticky 0.5, scan
  off): **3/31 logs chopped (9.7%)**, every success identical (+4 planks, reward 9 — the known
  craft rule) — vs **0/27 pooled for `commit_length=1`** across every earlier cold-start batch
  in attempts #2-#3. Fisher one-sided p≈0.15 (not significant at this N) but the first-ever
  non-zero result on this milestone.
  - **LESSON: a scoring bug and a calling-convention bug look identical from outside.**
    Attempts #2-#3 kept sharpening the *signal* (sticky sampling, scan, coverage fine-tune);
    the actual gap was that the planner wasn't *executing* the multi-step plan it had already
    correctly picked.
- **Online RND on top of `commit_length=4` — inconclusive, stopped before a confirmation batch.**
  N=7 launch attempt: 3/7 crashed at setup on a real bug (`ResNet5.out_dim` didn't exist; fixed
  mid-batch, now in the committed code — not MineRL/Java flakiness, verified by file mtime
  falling inside the run window). Of the 4 valid episodes: 0/4 successes — uninformative on its
  own at this N (expected ≈0.4 successes at the 9.7% base rate). Qualitative check: action
  profiles mixed (2/4 kept the lumberjack a14 signature, 2/4 didn't); GIF visually
  indistinguishable from a *successful* `commit_length=4`-alone episode (same close-trunk,
  camera-pitched-up frames) — no visible "less stuck" behaviour attributable to RND. **The
  `novelty_mean` diagnostic that would have actually answered the question was never logged**
  (`scan.log_std: false` in the config used) — zero data on whether the novelty signal behaved
  as designed. Per the project's own rule (no N=15-20 batch without a real positive qualitative
  signal first): **stopped here, no larger batch run.**
  - **LESSON: an unlogged diagnostic is the same as a nonexistent one.** `novelty_mean` existed
    in `plan(return_info=True)`'s return dict already; one YAML key (`scan.log_std: true`) would
    have told us whether RND was alive. Next RND attempt: flip that key first, at the same
    cheap N=4-7 scale, before spending a confirmation batch.
- **RND follow-up with `novelty_mean` actually logged — confirmed negative, root cause found.**
  N=6, `scan.log_std: true`. All 6 episodes show the same shape: `novelty_mean` starts at
  0.02-0.09, decays smoothly to 10-60× lower within ~150-280 ticks, **regardless of what's on
  screen** — correlation with `goal_score_std` (the independent lost/found signal) ranges
  -0.83 to +0.15 across episodes, no reliable relationship. Sharpest evidence: in one episode,
  `goal_score_std` hit its single highest value of the whole run (the most visually salient
  moment) at the exact tick where `novelty_mean` was near its lowest. **Root cause: the 256-slot
  ring buffer fills within ~150 ticks with visually homogeneous single-biome frames; the online
  predictor converges on that narrow local distribution, so "novelty" tracks elapsed ticks, not
  scene content.** Different failure mechanism from chapter 09's offline ensemble collapse, same
  outcome (no usable signal in the deployment that matters). No N=15-20 batch run — the
  mechanism is answered, more episodes would only restate it.
- `ebwm.pt`, `craft_wm_v4.pt` untouched by attempts #4-#7 (all of them live only in the planner
  call convention, the two-brain chop planner's scoring, or a small separately-trained head —
  no retraining of either main checkpoint).

Phase 5+ — Cold-start attempt #5: re-enable the scan macro in two-brain mode (`docs/10`
follow-up) — **NO-GO**:
- Hypothesis: the scan macro (attempt #2, calibrated `flat_threshold: 0.003` on `ebwm.pt`,
  genuine 10× band separation) was disabled for craft configs only because `craft_wm_v4`'s
  bands were compressed — but the two-brain chop phase runs on `ebwm.pt`, the model scan was
  actually calibrated on. Wiring verified correct (scan reads `chop_planner`'s std, not
  `craft_wm_v4`'s). Combined with `commit_length=4`.
- N=7: **0/7 successes.** 2/7 episodes reproduced a bounded version of attempt #2's "agent
  spins" pathology (a12 turn-camera action at 51%/87%, some scan triggers running to the
  `max_replans=40` cap). One episode's std sat in the salient-scene band (comparable to
  Treechop's canopy band) for ~880 ticks with scan correctly staying inert — **and the agent
  still didn't chop**, a direct replay of attempt #2's "surrounded by trees, still doesn't chop"
  finding, this time on a confirmed-correctly-wired signal. One episode ended in a treeless
  underground/rocky passage — a scan macro cannot fix a spawn like that by construction.
  - **LESSON: a correctly-wired, well-calibrated "I'm lost" detector is not itself a fix if the
    behaviour that consumes it (turn in place) can't cover ground or can't convert "something
    is visible" into "approach and chop."** This is now the standing diagnosis, not a hypothesis.

Phase 5+ — Cold-start attempt #6: real CEM (Cross-Entropy Method) planner (`docs/10`
follow-up) — **NO-GO**:
- Replaced single-generation random/sticky-shooting with an iterative categorical-CEM refit
  loop (`cem_iters`, config-gated, `cem_iters<=1` reproduces old behaviour bit-for-bit, verified
  on both checkpoints). `cem_iters=3`: fps cost ×2.94 per call, ~41% live throughput drop
  (not disqualifying alone).
- N=8: **0/8 successes.** The qualitative signal is a **regression, not a wash**: mean top-action
  concentration 66.3% (range 50-89%) vs. `commit_length=4`-alone's 35.8% average — roughly
  double, with almost no search/turn actions in the highest-concentration episodes.
  - **LESSON: CEM's elite-refit loop needs a real gradient in the score to refine toward. When
    the score is flat (no tree in view — the standing diagnosis), refitting locks onto sampling
    *noise* instead, and does so more aggressively each generation than plain random-shooting
    would. An optimizer that amplifies whatever it's given amplifies noise just as readily as
    signal.** This is the third independent confirmation (after RND, after scan) that the wall
    survives fixes aimed at the score/search signal itself.

Phase 5+ — Cold-start attempt #7: trained cost-to-reach distance metric (`docs/10` follow-up,
Destrade et al. arXiv:2601.00844) — **NO-GO, but a genuinely new diagnostic finding**:
- Replaced the untrained raw-latent L2 distance with a small projector `P` (frozen `ebwm.pt`,
  only `P`'s ~49 params trained) so `||P(z_t)-P(z_goal)||` approximates true step-count-to-goal,
  trained on Treechop + the attempt #3 coverage episodes (as capped/censored "far" examples,
  one-sided hinge loss) so the metric would see genuinely-lost frames during training, not just
  Treechop's forest-guaranteed ones. `distance_projector=None` verified bit-for-bit identical to
  old behaviour.
- **Offline validation (the real gate) passed clearly**: near pairs (true k≤5) predicted
  distance mean 12.3; far/coverage pairs mean 97.3 — **separation ratio 7.9** (required ≥1.3,
  far above it, unlike RND's flat collapse).
- Live N=6: **0/6 successes**, no crashes, action-profile concentration normal (16-40%, no
  CEM-style regression). Frame/std analysis on the one surviving episode: `goal_score_std`
  correlates with scene *brightness* (r=-0.57, day vs. dusk/night frames differ ~2×) but **not
  monotonically** — the two darkest frames right before a death had the lowest std in the whole
  episode, the opposite of what a genuine "lost" signal should do.
  - **LESSON: the metric discriminates — a real ~150× dynamic range, structurally unlike RND's
    flat collapse — but along a lighting/scene-composition axis, not tree-proximity.** Neither
    training source (Treechop, coverage) contains true night/cave frames, so the metric never
    learned to separate "unusual lighting" from "far from goal" — a specific, third failure
    mode (data composition gap), distinct from "no signal" (RND) and "score amplifies noise"
    (CEM). Concrete next step if revisited: targeted dusk/night/cave coverage collection, or
    photometric augmentation during projector training — not more live episodes on this
    checkpoint, which won't fix a training-data gap.

**Standing diagnosis after attempts #4-#7 — the wall is BEHAVIOURAL (action generation), not
PERCEPTUAL (score quality).** Three independent score/search-quality fixes (online RND, real
CEM, a trained cost-to-reach metric) each landed differently — one flat, one actively regressive,
one real-but-misaligned — and none moved the outcome. The one lever that ever produced a
non-zero result (`commit_length=4`, attempt #4) is a pure execution fix: it changed nothing
about how good the *choice* was, only how long a chosen plan is *held*. The world model can
already evaluate situations correctly (attempt #7's own offline gate proves that); the 512
randomly/stickily-sampled candidate sequences it evaluates essentially never contain the
right long-duration gesture to act on that evaluation.

Phase 5+ — Cold-start attempt #8: Proposal A (action-pool priming) + Proposal C (bushwhack
cruise macro), combined with `commit_length=4` (`docs/10` follow-up) — **NO-GO, but the most
informative negative result of the campaign**:
- Both mechanisms verified config-gated and bit-for-bit-identical when disabled
  (`planner.action_pool_priming`, `scan.macro: bushwhack`), new config
  `configs/play_craft_commit4_ac.yaml`. `mine_jepa/ebwm/planner.py`'s `_sample_actions()` now
  injects ~30 hand-authored forward+attack / turn / backward macro rows into the 512-candidate
  pool (Proposal A); `scripts/play_craft.py`'s scan block gained a `bushwhack` mode that forces
  a bounded forward-sprint+jump cruise instead of turning in place when `goal_score_std` is flat
  on the chop planner (Proposal C).
- N=8, seed 0: **0/8 logs, 0/8 planks, reward 0.** Against the standing `commit_length=4`-alone
  base rate (3/31 ≈ 9.7%), 0/8 is not itself surprising (≈0.8 expected successes) — not a
  significant regression, but not a confirmation either.
- **Both mechanisms verifiably fired** (not just wired-but-unused): the primed forward+attack
  macro (a7) reached 21-49% share in 3/8 episodes; the bushwhack macro (a13) reached 28% with 8
  scan triggers in 1/8 episode (only when the flat signal actually persisted long enough).
- **The finding that matters more than the 0/8**: 3/8 episodes showed a single action (a14, the
  pre-existing "move+attack" gesture) at 83-100% share — near-total behavioural lock-in. This
  echoes attempt #6's real-CEM regression (66.3% mean top-action concentration vs.
  `commit_length=4`-alone's 35.8%) on a *different* mechanism (fixed-menu priming + a
  ground-covering macro, not iterative refitting) reaching a structurally similar failure mode.
  ⚠️ Not yet cross-checked against `commit_length=4`-alone's own action distributions before
  calling this "the same lock-in" in the docs — flagged for the write-up to verify, not assert.
- **Standing-diagnosis refinement**: the MPC's argmax has no real gradient to follow when
  `goal_score_std` is flat (no tree in view) — feed it i.i.d. noise (attempts #1-3) and it
  fidgets in place; feed it a concentrated menu (real CEM, attempt #6) or continuous macros
  (attempt #8) and it locks blindly onto one of them, because nothing in the flat score ever
  corrects the choice. Hand-designed action generation (A/C) and score sharpening aimed at
  *hard-coded* macros both hit the same wall from opposite directions. The mechanism that
  should not lock blindly is one that has *learned* the full contextual behaviour distribution
  (including how experts search) rather than being handed a small fixed menu.
- Next actions, in this order:
  1. **Proposal B (latent policy prior), promoted to next priority.** Train a lightweight BC
     actor on frozen `ebwm.pt` using Treechop demos to *propose* MPC candidates (not decide
     final actions — the MPC still evaluates/re-plans every step, so this is not a repeat of
     Phase 4's failed pure-BC, where BC was the uncorrected final policy). ⚠️ Treechop demos
     guarantee forest proximity — they contain almost no genuine "lost, searching" trajectories,
     so the actor risks learning "always attack the visible tree" without learning to search.
     Mitigation: fold in the attempt #3 coverage episodes (random-policy, genuinely lost frames)
     alongside the Treechop demos so the actor sees at least some search-like behaviour.
  2. **Repair the attempt #7 distance metric with photometric augmentation — DONE, NO-GO.**
     Implemented (`augmentation.color_jitter` in `scripts/train_value_projector.py` /
     `configs/train_value_projector_colorjitter.yaml`, training-input-side only, `ebwm.pt`
     untouched). Offline separation held up (8.7× vs. attempt #7's 7.9×, gate passes) but the
     actual target — the brightness confound — got **worse, not better**, on a cleaner isolated
     measure (coverage-only pool, same "far" label by construction so any brightness→distance
     relationship is a pure shortcut): r=0.117 (attempt #7, unaugmented) → **r=0.498 (augmented)**.
     **LESSON: the confound is plausibly baked into `ebwm.pt`'s frozen latent space itself (narrow,
     mostly-daytime Treechop training), not introduced by the projector's own training. Perturbing
     only the projector's inputs can't undo a shortcut the upstream frozen encoder already
     committed to** — a fourth distinct failure mode after attempt #7's "data composition gap"
     (RND=flat, CEM=amplifies noise, distance-metric=wrong axis, this=confound is upstream not
     downstream). `checkpoints/value_projector_colorjitter.pt` kept for comparison, NOT used in
     place of the original — do not deploy it in the combined Proposal-B eval. Revisiting this
     properly would need an encoder-side fix (adapter fine-tune under anti-collapse guardrails),
     out of scope for now. The combined eval below proceeds on goal-centroid scoring alone
     (no working non-flat distance signal), same as every attempt through #8.
  3. **Spawn-viability diagnostic.** Attempt #8's episode 7 ended early (1856/3000 steps) with
     no death logged and no tree ever found — log spawn type (e.g. underground/oceanic vs.
     forest-adjacent) at episode start in `play_craft.py`/`play_minerl_multi.py` so a batch's
     denominator can distinguish "the algorithm failed" from "the spawn made success
     impossible by construction." Measurement fix, not a capability fix — but attempts #5 and
     #8 both show unwinnable spawns diluting every success-rate number so far.
  4. Evaluate B + the repaired distance metric together once both land.

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

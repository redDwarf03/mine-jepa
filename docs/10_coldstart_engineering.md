# Cold-start, part 2 — engineering before research

> Chapter 09 ended on a diagnosed failure: offline curiosity cannot fix cold-start
> chopping, because an ensemble trained on frozen expert demos loses the diversity
> its novelty signal depends on. Before reaching for the *next* research idea (online
> RND), this chapter fixes two things that were broken in plain sight — no learning
> involved, no checkpoint touched.

---

## Re-reading the failure without the curiosity lens

The cold-start symptom: the agent spawns, no tree in view, and it stands there
twitching (0 logs over 5 episodes in `ObtainIronPickaxeDense`). Chapter 09 framed this
as an *exploration* problem and attacked it with intrinsic reward. But look at what the
planner is actually doing at that moment, mechanically:

1. It samples **512 action sequences, each action drawn i.i.d. uniform** over 12 steps.
2. It imagines each future with the world model and scores it by similarity to the
   "success scene" prototype.
3. With no tree in view, **every imagined future scores the same** — the argmax picks
   among lottery tickets.

Two separate defects hide in there, and neither is about learning.

---

## Defect 1 — i.i.d. sampling cannot even *propose* the right behaviour

The fix for "nothing in view" is a sustained gesture: *turn the camera in one
direction for a couple of seconds*. Now compute the odds that a sequence like
`turn-turn-turn-turn-turn-turn` appears among 512 i.i.d. draws over 17 actions:
(1/17)⁶ per position — it effectively **never** does. The planner is not failing to
*choose* the searching behaviour; the behaviour **does not exist in its candidate
pool**. MPC can only pick the best of what it imagined.

This is a known weakness of random-shooting MPC, and the standard remedy is
temporally correlated sampling — iCEM ([arXiv:2008.06389](https://arxiv.org/abs/2008.06389))
uses colored noise; our discrete version is **sticky actions**:

```
at each step: repeat the previous action with probability p (sticky_prob ≈ 0.7)
              otherwise draw a fresh uniform action
```

Measured on 4096 sequences: consecutive-repeat rate goes from **7%** (i.i.d.) to
**72%** (sticky 0.7). The candidate pool now contains held gestures — turn-and-look,
walk-toward, sustained attack — the same reason `action_repeat=4` already helped
in Phase 4, applied *inside the imagination* instead of only at execution time.

Implementation: `_sample_actions()` in `mine_jepa/ebwm/planner.py`, used by both
`DiscreteLatentPlanner` and `SwitchingCraftPlanner`. `sticky_prob: 0.0` (the default)
reproduces the old behaviour bit-for-bit — project convention: every change is
config-gated, the baseline stays reachable.

## Defect 2 — the agent is blind to its own blindness

When a tree *is* visible, candidate futures differ sharply: sequences that approach
the trunk score much better than ones that wander off. When nothing is in view, all
512 scores collapse onto the same value. That spread — the **standard deviation of
the goal scores across candidates** — is a free, one-line signal that the planner
already computes and threw away:

```
goal_score_std  high → a goal is in view, the ranking means something
goal_score_std  ≈ 0  → "I am lost"; the argmax is noise
```

The **scan macro** turns that signal into a reflex: after `patience` consecutive flat
replans, override the planner and hold a camera-yaw action (`a12`, +10°/step) —
sweep the horizon — until the std recovers (a tree entered the frame) or a guard
(`max_replans`) expires. Then hand control back to the chopper, which already works
at 25–50% once a tree is visible.

Honesty first: **this is not learning.** It is a hand-written reflex, the kind of thing
DreamerV3 learns implicitly and we hard-code because our budget is one 8 GB GPU. The
research path (online RND curiosity, chapter 09's conclusion) stays on the roadmap —
but it makes no sense to teach an agent to *explore* while it cannot yet turn its head.

Implementation: `plan(..., return_info=True)` exposes `goal_score_std`;
`scripts/play_ebwm.py` and `scripts/play_craft.py` (chop mode only) run the state
machine, config block `scan:` in the play YAMLs, `enabled: false` by default.

---

## Calibrating the threshold (do this before enabling)

`flat_threshold` must be read from data, not guessed. On the NVIDIA PC:

```bat
:: scan.enabled=false, scan.log_std=true in configs/play_ebwm.yaml
run.bat scripts/play_ebwm.py --config configs/play_ebwm.yaml --episodes 3
```

Every replan prints `goal_score_std`. Cross-check against the GIF: read the typical
std when a tree fills the view vs. when the agent faces open grass/sky, and set
`flat_threshold` between the two bands (closer to the lost band).

**Calibration result (2026-07-07, PC, 3 Treechop episodes, 750 replans each, seed 0):**

| Situation (GIF cross-check) | `goal_score_std` band |
|---|---|
| Lost — facing dirt walls, sky, open grass | 0.0002 – 0.002 |
| Wandering, trees at a distance | 0.003 – 0.01 |
| Tree/canopy fills the view (chopping moments, Ep2) | 0.02 – 0.056 |

Per-episode percentiles: p10 = 0.0006–0.0016, median = 0.003–0.004, p90 = 0.009–0.011.
The winning episode (reward 1) had the highest tail (max 0.056 at the chop). Chosen
**`flat_threshold: 0.003`** — just above the lost band; with `patience: 3` consecutive
flat replans, transient dips don't trigger the sweep.

## The gate (what would make this chapter a PASS)

| Test | Baseline | Target |
|------|----------|--------|
| `MineRLTreechop-v0`, N=20, seeded, sticky=0.7 + scan vs. original | 25–50% (variance band) | ≥ 50%, fps ≈ unchanged |
| Cold-start `ObtainIronPickaxeDense`, N=5 (`play_craft.bat`) | **0/5 logs** | ≥ 1 log in ≥ 1 episode |

If the first cold-start log drops, the already-validated craft loop
(`MineRLObtainTest-v0`, 100% given wood) takes over — that is the milestone.
Both numbers get reported with variance, per the Phase 4 lesson: no claiming the
best run.

## Results (PC eval, 2026-07-08) — VERDICT: partial

**Treechop A/B** (seed 0, same `ebwm.pt`, same day):

| Condition | N | Success | Mean reward | fps |
|---|---|---|---|---|
| OFF — original planner (fresh baseline) | 20 | 45% (9/20) | 0.50 | 65.9 |
| sticky **0.7** + scan@0.003 | 20 | 25% (5/20) | 0.45 | 65.0 |
| sticky **0.5** + scan@0.003 (routing case 3) | 10 | 40% (4/10) | **0.90** | 64.6 |

- The ≥50% target was **missed**. No difference is statistically significant
  (Fisher: 0.7-vs-OFF p=0.32; 0.5-vs-OFF p=1.0), but the direction is consistent:
  **0.7 over-commits** — episodes lock onto one gesture (a14 at 71–97%) and march
  forever; **0.5 keeps success in the variance band and ~doubles reward per success**
  (one 5-log episode; total logs 9/10 eps vs 10/20 eps baseline). Sticky buys *depth*
  (keep chopping the tree you reached), not *breadth* (more trees found).
- fps unchanged (sticky and scan add no rollout cost), as designed.
- Scan on Treechop: fired 0–26×/ep with no visible harm at 0.003 — the bands there
  are well separated (lost ≤0.002 vs tree-visible ≥0.02, a 10× gap).

**Cold-start `ObtainIronPickaxeDense`** (N=5 each): **0 logs in every configuration —
gate FAILED.**

| Config | N | Logs | Note |
|---|---|---|---|
| sticky 0.5 + scan@0.003 | 1 (interrupted) | 0 | agent often *inside* the forest, still no chop |
| sticky 0.5 + scan@0.004 | 5 | 0 | **pathological**: a12 (turn) 82–92%, 15–34 scans/ep — the agent spins |
| sticky 0.5, scan OFF | 5 | 0 | diverse actions, still no first log |

Why the scan failed here: on `craft_wm_v4.pt` the std bands are **compressed**
(lost ~0.002, tree-visible ~0.010, median 0.0047 — a 5× gap with most mass in the
middle) vs Treechop's clean 10× gap. Any threshold either barely fires (0.003) or
fires constantly and the sweep eats the episode (0.004: each trigger runs toward
`max_replans=40` because the std rarely recovers above the line). The lost-state
detector needs a *relative* signal (e.g. std percentile over a trailing window),
not an absolute threshold — noted for a future pass.

Sharpest observation: with scan@0.003 the agent was often **surrounded by trees and
still didn't chop** — the cold-start wall is not (only) search, it's the
approach-and-chop behaviour itself, which `craft_wm_v4.pt`'s goal-centroid
(trained on Obtain demos, not Treechop demos) apparently doesn't drive as well as
`ebwm.pt` does. Routing case 4 applies: chapter closed as a **documented partial**;
next cycle is **online RND** (novelty that decays with experience — chapter 09's
conclusion stands).

**Follow-up micro-experiment — swap the chop compass.** The "inside the
forest, not chopping" observation suggested the culprit was the *goal*, not the
planner: the v4 chop centroid comes from Obtain-demo "log obtained" frames (players
doing many things), while `ebwm.pt`'s proven compass comes from Treechop reward
frames. Added `goal.chop_data_path` (config-gated, `scripts/play_craft.py`): use the
12,056 Treechop reward≥0.5 frames, encoded by *craft_wm_v4's own encoder*, as the
chop goal. Result: **still 0/5 logs** (sticky 0.5, scan off; two episodes also died
early — random survival spawns are hazardous). So the compass alone doesn't rescue
cold-start either: the remaining suspects are the *world model itself* (craft_wm_v4's
visual dynamics vs ebwm's — different training recipe and action space) and the
*environment* (Treechop spawns you inside a forest; ObtainIronPickaxe spawns you
anywhere, sometimes lethally). The option stays in the code; the config default
reverts to the Obtain centroid.

**Follow-up — the two-brain agent** (`chop_model:` block in `configs/play_craft.yaml`,
config-gated): `ebwm.pt` — the proven Treechop lumberjack — plans the chop phase over
the 17 movement actions shared by both action maps; `craft_wm_v4` takes over at the
first log (inventory dynamics is its actual strength). Result: **still 0/5 logs, but
the behaviour is transformed** — the action profile becomes the lumberjack gesture
(a14 sprint+attack 30–52%, a6/a7 attack) instead of the diffuse wandering seen with
the v4 brain. GIF inspection of the last episode (a6 at 85%): the agent spawned in a
**treeless rocky ravine and ground its axe on stone** — plus two of five episodes died
early. The remaining wall is neither the gesture nor the compass: it is the
`ObtainIronPickaxe` random spawn (biomes without trees in reach) and the search
radius. That is precisely the problem online RND is for; a cheaper first lever is
re-enabling the scan in two-brain mode, where the chop std comes from `ebwm.pt` again
and the 0.003 calibration is valid.

Kept defaults after this eval: `play_ebwm.yaml` → sticky 0.5 + scan on (calibrated,
harmless, deeper chops); `play_craft.yaml` → sticky 0.5, **scan off**, two-brain on.

**Follow-up — coverage fine-tune (attempt #3, PC, 2026-07-20).** Hypothesis (jepa-explorer
audit): the compressed std bands on `craft_wm_v4.pt` (5× vs Treechop's 10×) are a
training-data-coverage artifact, not a metric problem — the 40 expert Obtain demos almost
never show "lost, no tree in view" frames, because experts reach wood fast. A value-guided
distance calibration (arXiv:2601.00844) was considered and set aside first: it would train
on the same narrow data and inherit the same blind spot, so coverage had to be ruled out
before touching the metric.

Fix tested: ~20 short (400-step) random-policy episodes on `ObtainIronPickaxeDense-v0`
(random spawn = biome diversity for free), merged with the 40 expert demos (coverage
episodes zero-filled on inventory/reward — visual diversity only, no craft signal), then a
4-epoch low-LR fine-tune resumed from a backup of `craft_wm_v4.pt`
(`checkpoints/craft_wm_v4_coverage.pt`). No collapse (`bvar` stayed 1.24–1.27), no
craft-precondition regression (`dPlanks@craft` stayed +1.22 to +1.35 across epochs).

**VERDICT: the signal improved; the outcome did not.**

| | backup (original) | coverage (fine-tuned) |
|---|---|---|
| Logs chopped (N=3) | 0/3 | 0/3 |
| Planks crafted (N=3) | 0/3 | 0/3 |
| `goal_score_std` median | 0.0034 | 0.0126 (×3.7) |
| p90/p10 ratio (lost-vs-promising proxy) | ×3.2 | ×5.4 |
| Episode length | 3000/3000/3000 | 2295/3000/1070 (2 early deaths) |

The std band separation did widen (×3.2 → ×5.4, moving toward Treechop's ×10x) — the
coverage-gap hypothesis is directionally correct as a mechanism. But it changed nothing
behaviorally: identical 0/3 logs on both checkpoints, and the fine-tuned checkpoint died
earlier in 2 of 3 episodes (more exploratory movement into more danger, not more chopping).

LESSON: **sharpening the "am I lost" signal does not by itself fix the search-and-approach
behaviour that is supposed to act on it.** The diagnosis from the two-brain experiment above
stands: this is a behavioural gap (search/approach), not a purely perceptual one. Coverage
data helps the model represent "lost" more distinctly; it does not teach the planner what to
*do* about it. Online RND — reward for novelty *during play*, shaping behaviour rather than
perception — remains the next concrete step, not a fourth perception-side patch.

---

## Cold-start attempt #4, part A (PC, 2026-07-20) — commit_length: the planner was discarding its own commitment

Re-reading `plan()` after attempt #3's "behavioural, not perceptual" verdict surfaced a third
defect, sitting next to the two from Defect 1/2 above: **every replan draws a fresh independent
512-candidate sample and returns only the winning sequence's first action.** Even when sticky
sampling proposes a genuinely good 12-step gesture ("turn toward the trunk, walk in, attack"),
the caller executes exactly one step of it, then resamples 512 *new* i.i.d.-ish sequences from
scratch — steps 2..12 of the winning plan are thrown away every single tick. The scoring
correctly identifies the good multi-step plan; the calling convention never lets the agent act
on more than 1/12th of it.

Fix: `commit_length` (`mine_jepa/ebwm/planner.py`, wired through `DiscreteLatentPlanner.plan()`
and `SwitchingCraftPlanner.plan()`) returns the first `min(commit_length, horizon)` actions of
the winning sequence instead of 1, so the caller executes a sustained gesture before replanning.
`commit_length=1` (default) is the exact original code path — same scoring, same argmax, same
single-int return, verified byte-for-byte.

**Results — `commit_length=4` alone (no RND), two-brain chop planner, sticky 0.5, scan off,
seed 0, `MineRLObtainIronPickaxeDense-v0`:**

| Batch | N | Logs chopped | Planks crafted (success) | Notes |
|---|---|---|---|---|
| `coldstart_commit3.log` (`commit_length=3`) | 5 | 0 | 0/5 | control — 3 steps not enough |
| `coldstart_commit4.log` | 5 | 1 | 1/5 (ep 4, +4 planks, reward 9.0) | |
| `coldstart_commit4_fix_verify_n6.log` | 6 | 1 | 1/6 (ep 5, +4 planks, reward 9.0) | re-run after a launch fix, see part B |
| `coldstart_commit4_n20_clean.log` | 20 | 1 | 1/20 (ep 8, +4 planks, reward 9.0) | |
| **Pooled `commit_length=4`** | **31** | **3** | **3/31 (9.7%)** | |
| Pooled `commit_length=1` (attempts #2+#3: gate/gate2/sticky_only/compass/twobrain/coverage batches) | 27 | 0 | 0/27 (0%) | documented above and in the coverage follow-up |

Every success shows the identical signature: 1 log chopped → craft-planks fires once → +4
planks → reward 9 (the known WM v4 craft rule, `docs/08_crafting.md`). Fisher's exact test on
3/31 vs 0/27, one-sided: **p ≈ 0.15** — not significant at N this small, but this is the
**first non-zero, reproducible cold-start result in the project's history**: every earlier
cold-start batch across attempts #1-#3 (i.i.d. sampling, sticky-only, scan, compass swap,
two-brain, coverage fine-tune) chopped exactly 0 logs, ever.

> **LESSON: a scoring bug and a calling-convention bug can look identical from the outside.**
> Attempts #2-#3 kept re-diagnosing "the agent can't find/approach trees" and kept patching the
> *signal* (sticky sampling, scan, coverage fine-tune) — all real, all necessary, all
> individually insufficient. The missing piece was not a better plan but *executing more of the
> plan already being computed*. This is consistent with, not contradictory to, the two-brain
> diagnosis in attempt #2: the wall was "behavioural, not perceptual" — and one of the
> behaviours being blocked was simply *following through*.

At 9.7%, `commit_length=4` is nowhere near the 30% planks-milestone gate, and every success is
still gated on a lucky spawn near a tree (mean steps to first success ≈ 3000, i.e. most episodes
never see a chop-able tree at all within the budget) — this does not replace search/exploration,
it just stops discarding the plan once a tree is found. Kept as the new default for
`configs/play_craft_commit4*.yaml`; `configs/play_craft.yaml` (`commit_length` unset → 1) is
untouched.

## Cold-start attempt #4, part B (PC, 2026-07-20) — online RND: inconclusive, stopped before a confirmation batch

With `commit_length=4` establishing that the wall is partly "no follow-through," the next lever
per attempt #3's conclusion was online RND (`mine_jepa/ebwm/rnd.py`, docs/09's diagnosis) —
predictor/target trained continuously on states actually visited during play, novelty decaying
as a state is revisited, wired as a z-score-normalised bonus (`novelty_coeff=0.5`) into the
two-brain chop planner's `DiscreteLatentPlanner` (`configs/play_craft_commit4_rnd.yaml`, RND
untouched in craft mode — it would encode into the wrong latent space there by construction).

**A launch bug, found and fixed mid-batch, not flakiness.** `coldstart_commit4_rnd_falsify_n7.log`
(N=7) shows episodes 1-3 crashing at setup (`AttributeError: 'ResNet5' object has no attribute
'out_dim'` — the RND wiring tried to read the chop encoder's output width off a nonexistent
model attribute) before episodes 4-7 ran cleanly. `scripts/play_craft.py`'s current code already
reads `state_dim` from the checkpoint's own saved config instead
(`chop_embed_dim = _ebwm_ckpt["cfg"]["model"]["embed_dim"]`), and the file's mtime falls inside
the same batch's run window — the fix landed between episode 3 and episode 4 of this exact log,
which is why the back half of the same file runs clean. **This was a real bug in the RND launch
path, now fixed in the committed code, not MineRL/Java launch flakiness** — worth correcting for
the record since it looked like the latter at a glance.

**Valid data: N=4 (episodes 4-7), 0/4 successes** (0 logs, 0 planks, reward 0 in all four).
At the pooled `commit_length=4`-alone base rate of 3/31 (9.7%), the expected count in 4 trials
is ≈0.4 successes — 0/4 is not evidence of anything by itself, positive or negative, and per the
project's own standard (no claiming significance below N≈20) this could not have been the
deciding batch either way. The call has to rest on qualitative/mechanistic evidence instead:

- **Action-profile concentration**: 2 of 4 valid episodes kept a strong `a14` (sprint+attack,
  "lumberjack") signature comparable to `commit_length=4`-alone's successes (ep 6: 54%, ep 5:
  29%); the other 2 were attack/forward-dominant but less concentrated (ep 4: `a6=49%`, ep 7:
  `a1=25%` top action). Mixed, not a clean signal either way.
- **GIF** (`assets/agent_play_craft_commit4_rnd.gif`, last episode = ep 7, no success episode to
  keep): shows the agent deep in forest canopy, camera pitched steeply upward at close range to
  a trunk — **visually indistinguishable in character from the successful
  `commit_length=4`-alone episode's GIF** (`assets/agent_play_craft_commit4.gif`, same
  close-trunk/canopy-pitch frames). No visible "less stuck," no visible search sweep, no
  qualitatively new behaviour attributable to RND.
- **The one diagnostic that would have actually answered the question was never recorded.**
  `planner.py`'s `plan(..., return_info=True)` does expose `novelty_mean` (added alongside RND),
  but `scripts/play_craft.py` only prints it when `scan.log_std: true` — and
  `configs/play_craft_commit4_rnd.yaml` shipped with `scan.log_std: false`. **This batch
  produced zero `novelty_mean` values.** There is no data, of any kind, on whether the novelty
  signal was elevated when the agent was lost, flat everywhere (the chapter 09 failure mode
  recurring), or doing anything coherent at all.

**VERDICT: inconclusive, not negative — stopped here rather than spending an N=15-20
confirmation batch.** Per the project's own decision rule (qualitative signal must be genuinely
positive to justify a larger run), there is no real qualitative signal to confirm: the action
profiles are mixed, the GIF shows the same failure mode as a *successful* run elsewhere (so it
proves nothing), and the one instrument that could distinguish "RND is doing something" from
"RND is inert" was configured off. Running N=15-20 now would only repeat the N=4 batch's
uninformativeness at higher cost.

> **LESSON: an intervention can't be judged by outcome counts alone when the outcome is rare and
> the mechanism-checking instrument was left disabled.** `novelty_mean` existed in the code and
> was one YAML key away from being logged; not enabling it turned a batch that could have given
> a real mechanistic answer (novelty decaying vs. flat) into one that could only ever be
> ambiguous. Before any RND re-run: `scan.log_std: true` is mandatory, not optional — the point
> of this diagnostic pass is not "did it chop," it's "is the novelty term is alive."

Next, if RND is revisited: re-run with `scan.log_std: true` (no code change needed, config
only) at the same N=4-7 scale first — cheap, and this time it produces the evidence part B was
missing — before committing to N=15-20.

## Cold-start attempt #4, part B continued — instrumented re-run: RND's novelty signal does not discriminate lost from found in live play (verdict: STOP, no N=15-20 batch)

`novelty_mean` was already computed in `mine_jepa/ebwm/planner.py`'s `DiscreteLatentPlanner.plan()`
(added alongside RND, verified present in the committed code — no change needed there); the only
gap was `configs/play_craft_commit4_rnd.yaml`'s `scan.log_std: false`, which suppressed the print.
Flipped to `true` (`scan.enabled` left `false` — the scan macro's behavior override stays inert;
only the diagnostic print is turned on, so this run isolates RND's effect exactly as before, with
no confound from the scan reflex). Re-ran the same config, N=6, two-brain chop planner,
`commit_length=4`, sticky 0.5, seed 0, `MineRLObtainIronPickaxeDense-v0`
(`logs/coldstart_commit4_rnd_diag.log`).

**Outcome: 0/6 successes** (0 logs, 0 planks, reward 0 in all six episodes; steps to death/cutoff
826, 646, 644, 644, 3000, 912 — five of six episodes died before the 3000-step budget, only
episode 5 survived the full budget). Consistent with the pooled `commit_length=4`-alone base rate
(3/31, 9.7%) — 0/6 is not surprising on its own (expected count ≈0.6) and was not the deciding
signal; `novelty_mean` was.

**The `novelty_mean` values, read across all 6 episodes:**

| Ep | n replans | novelty_mean at tick 0 | peak | tick-final | corr(goal_score_std, novelty_mean) |
|---|---|---|---|---|---|
| 1 | 52 | 0.0325 | 0.0652 @ step 48 | 0.00095 | -0.198 |
| 2 | 41 | 0.0894 | 0.0969 @ step 64 | 0.00285 | -0.310 |
| 3 | 41 | 0.0244 | 0.0244 @ step 0 | 0.00145 | -0.827 |
| 4 | 41 | 0.0196 | 0.0196 @ step 0 | 0.00264 | +0.145 |
| 5 | 188 | 0.0304 | 0.0304 @ step 0 | 0.00164 | -0.150 |
| 6 | 57 | 0.0218 | 0.0348 @ step 16 | 0.00154 | +0.092 |

Every single episode shows the **same shape**: a brief rise or flat start over the first
~50-130 steps, then a **smooth, monotonic decay** to a value 10-60x lower by episode end —
regardless of episode length (41 replans or 188), regardless of when/whether the agent died,
and regardless of what `goal_score_std` (the independent, already-validated "am I lost"
signal) was doing at the same time. The correlation between the two signals is inconsistent
in both sign and magnitude across episodes (-0.83 to +0.15) — there is no reliable
relationship, in either direction.

**The sharpest single data point** is in episode 5 (the one long, 188-replan episode):
around step 2480-2576, `goal_score_std` spikes to 0.045-0.046 — by a wide margin the most
distinctive/salient scene of the entire episode (10-20x the surrounding baseline, in the
band the Treechop calibration in this same chapter associates with "canopy fills the view").
`novelty_mean` at that exact moment is 0.0015-00017 — among the **lowest** values seen in the
whole episode, not elevated. If RND's novelty term were tracking scene-level novelty the way
the offline smoke test showed it could (`scripts/smoke_test_rnd.py`: a genuine, persistent
separation between a revisited and a novel probe over 600 ticks, both held fixed and read
without training on them), the most distinctive frame of the episode should be one of the
higher-novelty moments, not one of the lowest.

**Read: this is not the smoke test's separation showing up in play — it is the buffer-fill /
predictor-convergence curve from the smoke test's OWN early ticks, not its later plateau.**
The smoke test drove disagreement down for a *specific revisited state* while keeping it high
for a *held-out novel probe*, over 300 ticks on a frozen, pre-recorded, temporally shuffled-free
sequence. In live play, the 256-state ring buffer fills with visually similar,
temporally-adjacent frames (dense forest canopy, near-identical spawn-area views) within the
first ~130 steps, and the predictor converges on THAT narrow, homogeneous distribution —
after which novelty is low almost everywhere the agent's actual trajectory goes, because the
trajectory itself does not visit anything the buffer hasn't already shown the predictor
repeatedly. The one moment that broke that homogeneity (the step-2480 spike) did not register
as novel, because "different from the recent training batch" and "the most goal-salient scene
per `goal_score_std`" are not the same criterion, and RND is answering the former.

**VERDICT: STOP — this reproduces chapter 09's original failure mode in the online setting.**
Chapter 09 concluded "a novelty signal that doesn't discriminate in the deployment that
matters" from an offline ensemble that collapsed during training; this instrumented re-run
shows the SAME symptom (no discrimination where it matters — lost vs. found, or flat-scene vs.
salient-scene) from an online predictor that never collapsed but converges too fast, on too
narrow a state distribution, to produce anything but a monotone decay curve dominated by tick
count rather than by scene content. Per the task's own decision rule, this is exactly the
"flat, noisy, or uncorrelated with anything observable" branch: **no N=15-20 confirmation
batch was run.** Spending it would only re-confirm 0-ish success counts already consistent with
the `commit_length=4`-alone base rate, on top of a mechanism now shown not to be contributing
anything — the N=6 batch, at a fraction of the cost, already answers the mechanistic question
part A's calling-convention fix could not: RND is inert here, not marginally helpful and hard
to measure.

> **LESSON: RND's online advantage over the offline ensemble (chapter 09) is "the predictor
> doesn't collapse to a constant," not "the predictor tracks the state distribution the agent
> actually needs discriminated."** The buffer/update cadence that makes RND stable (small
> ring buffer, frequent updates, `update_every=4`) is the same mechanism that makes it converge
> within ~100-150 ticks on whatever narrow visual distribution the current episode happens to
> wander through — which, in a forest-canopy chop episode, is nearly the whole episode. A
> novelty bonus that decays with *time-in-episode* rather than with *genuine state
> revisitation* is not a curiosity signal, it's a decaying constant; z-score-normalising it
> against the goal term (as this planner does) does not fix that, it just changes its scale.

*Previous: `docs/09_curiosity_coldstart.md`. Current: `commit_length` — first non-zero
cold-start result (3/31, part A above); online RND — inconclusive on outcome counts (N=4,
part B above), then **ruled out mechanistically** by the instrumented N=6 re-run (this
section): `novelty_mean` decays monotonically with tick count in every episode, uncorrelated
with the independent lost/found signal, and lowest exactly at the episode's most salient frame.
Next: a genuinely online self-play/exploration loop with a buffer and update cadence tuned to
retain cross-episode state diversity (not just within-episode stability), or move past
curiosity-as-bonus entirely and revisit the search/approach behaviour itself (attempt #2's
"behavioural, not perceptual" diagnosis, still the strongest standing lead).*

## The lesson this chapter adds

> **Before asking "how does the agent learn X?", ask "can the agent even express X?"**
> The searching behaviour was impossible to sample and the lost-state was measurable
> all along. Curiosity (chapter 09) failed partly because it was aimed at a problem
> that is mostly *representational*: the planner's hypothesis space did not contain
> the solution. Fix the hypothesis space first; spend learning on what remains.

And its post-eval corollary:

> **A detector calibrated on one latent space does not transfer to another.** The
> lost-state signal was real on `ebwm.pt` (10× band separation) and unusable on
> `craft_wm_v4.pt` (5×, mass in the middle) — an absolute threshold on a
> checkpoint-dependent statistic is not a mechanism, it's a coincidence. And a
> recovery macro must be **bounded by budget, not by the signal it distrusts**:
> "turn until the std recovers" spun the agent for entire episodes.

And attempt #4's corollary:

> **A calling convention can silently discard a correct answer.** `commit_length=4` didn't
> change the scoring, the sampling, or the model — it only stopped throwing away steps 2..12 of
> a plan the planner had already picked correctly. That single change produced the project's
> first non-zero cold-start result, after three attempts that improved the *signal* (sticky
> sampling, scan, coverage fine-tune) without touching *how much of the plan gets executed*.
> And when testing the next lever (RND) on top of it: a diagnostic that exists in the code but
> isn't wired into the logging config is the same as not existing — `novelty_mean` was one YAML
> key away from turning an ambiguous N=4 batch into a real mechanistic answer, and that key
> was left off.

*Previous: `docs/09_curiosity_coldstart.md`. Current: `commit_length` — first non-zero
cold-start result (3/31, part A above); online RND on top of it — inconclusive, N=4,
diagnostic instrumentation left disabled (part B above). Next: re-run RND with
`scan.log_std: true` to actually observe the novelty signal before spending a larger batch,
or move to a genuinely online self-play loop (RND's predictor training online during
exploration episodes, not just during MPC scoring) if the instrumented re-run is still flat.*

## Cold-start attempt #5 (PC, 2026-07-20) — scan re-enabled in two-brain mode, on top of commit_length=4: mechanism confirmed valid, outcome still negative

Attempt #2 closed with the scan macro disabled for craft mode because `craft_wm_v4.pt`'s
`goal_score_std` bands were compressed (5×, mass in the middle) — but flagged that the
**two-brain chop planner** (added later that same day, `chop_model:` block) runs the CHOP
phase on `ebwm.pt`, the exact model the 0.003/patience=3/max_replans=40 calibration was
measured on, and never got a combined run with scan re-enabled. `commit_length=4` (attempt
#4) then produced the project's first non-zero cold-start result but every batch shipped
with `scan.enabled: false`. This attempt closes that gap.

**Wiring check (done before running anything, per the task's own requirement not to assume):**
`scripts/play_craft.py`'s main loop calls `chop_planner.plan(obs_t, chop_goals,
return_info=True)` whenever `mode == "chop"` in two-brain configs, and reads
`info["goal_score_std"]` from *that* call — `chop_planner` is the `DiscreteLatentPlanner`
built on `checkpoints/ebwm.pt` (`chop_cfg["checkpoint"]`), never `SwitchingCraftPlanner`
(`craft_wm_v4`), which is only reached once `has_log` is true (craft mode, where the scan
gate `mode == "chop"` structurally excludes it — see `if scan_enabled and mode == "chop":`).
**Confirmed: re-enabling scan here reads `ebwm.pt`'s std, exactly where the calibration is
valid** — the premise that broke attempt #2 (craft_wm_v4's compressed bands under an
absolute threshold) does not apply to this wiring.

`configs/play_craft_commit4_scan.yaml`: clone of `configs/play_craft_commit4.yaml`
(two-brain, sticky 0.5, `commit_length: 4`) with `scan.enabled: true`,
`flat_threshold: 0.003` (the Treechop-calibrated value, not craft_wm_v4's 0.004 recalibration
— carried over together with `patience: 3`, `turn_action: 12`, `max_replans: 40`, all from
the same calibration), and `scan.log_std: true` (per the RND part-B lesson: never ship an
instrumented run with its own diagnostic print left off).

**Result, N=7 (`logs/coldstart_commit4_scan.log`, seed 0, `MineRLObtainIronPickaxeDense-v0`,
exit code 0, no crashes): 0/7 successes** (0 logs, 0 planks, reward 0 in all seven episodes).

| Ep | steps | top action | scan triggers | read |
|---|---|---|---|---|
| 1 | 3000 | **a12=51%** | 6 | 2 of 6 triggers ran near the 40-replan cap (~624 steps each, traced in the raw `goal_score_std` trace) — a bounded but substantial camera-spin, not the unbounded 82-92% of attempt #2's craft_wm_v4 pathology, but the same shape |
| 2 | 3000 | **a12=87%** | 5 | same signature, more pronounced |
| 3 | 641 | a14=38% | 0 | scan never fired; ordinary commit_length=4 profile; episode ended early (death) |
| 4 | 3000 | a7=25%/a14=23% | 5 | mixed, scan fired but did not dominate |
| 5 | 3000 | a13=71% | 1 | scan barely fired; looks like a normal commit_length=4-alone profile |
| 6 | 3000 | a14=39% | 1 | same — normal profile, scan inert |
| 7 | 961 | a14=33% | 1 | scan barely fired; GIF (kept, last episode, no success) shows the agent ending in a stone passage/cave-like frame, not a forest — a treeless-spawn case scan cannot fix by construction |

At the pooled `commit_length=4`-alone base rate (3/31, 9.7%), the expected count in 7 trials
is ≈0.68 — 0/7 is not surprising by itself, positive or negative, so the call rests on the
qualitative evidence, per this project's own standing rule.

**Reading episode 1's raw `goal_score_std` trace closely** (the only one with enough scan
activity to say something specific): std genuinely climbs into the "salient scene" band
(0.008–0.026, comparable to the Treechop canopy band) for roughly 880 of the 3000 steps,
late in the episode (~step 2100–2990) — scan correctly stays inert through that stretch
(no `SCANNING` tags), meaning the mechanism is doing exactly what it's calibrated to do:
back off when something salient is in view. **The agent still didn't chop a log during that
entire high-std stretch.** This is a direct, in-run replication of attempt #2's sharpest
finding ("surrounded by trees and still didn't chop") — under a working, correctly-wired
scan signal.

**VERDICT: hypothesis half-confirmed, outcome negative — NO-GO on the N=15-20 batch.**

- **Confirmed**: the wiring hypothesis was correct. In two-brain mode, scan reads
  `ebwm.pt`'s `goal_score_std`, not `craft_wm_v4`'s — the exact fix the task set out to
  test. This is not the same failure mode as attempt #2 (checkpoint-mismatched threshold).
- **Not confirmed**: that fixing the wiring makes scan *useful* here. Two of seven episodes
  reproduce a bounded version of the same "agent spins on a12" symptom attempt #2 flagged as
  pathological — smaller in degree (bounded by `max_replans`, not the full episode) but the
  same shape, on a signal now known to be correctly calibrated. The other five episodes are
  indistinguishable from `commit_length=4` alone (scan rarely fires, same top-action
  vocabulary). No episode shows more forest-oriented behaviour, a longer stretch near a tree,
  or any qualitative sign that the sweep is finding wood it wouldn't otherwise have found.
- The single most detailed data point available — episode 1's high-std stretch with an
  inert (correctly non-triggering) scan — shows the wall is not "the agent doesn't know a
  tree is there," it is still "knowing doesn't convert into chopping," exactly attempt #2's
  two-brain conclusion. Scan cannot address that by construction: it is a *search* reflex,
  and search was not the failure mode in the one episode with actual evidence of it.
- Per the task's own decision rule (encouraging signal required to justify the larger
  batch; regression/pathology or a wash both stop here): this is a wash on outcome (0/7,
  statistically uninformative) with a mild, real regression signature in 2/7 episodes and no
  compensating positive signal anywhere — that is a **no-go**, not a coin flip. Running
  N=15-20 now would spend budget confirming a symptom already visible in the raw trace at
  N=7, at the same statistical power problem (a 9.7%-ish true rate needs N≈30+ either way).

> **LESSON: wiring a signal correctly is necessary, not sufficient.** Attempt #2's original
> scan failure had two candidate causes: (1) the signal was read from the wrong checkpoint,
> and (2) scan-as-search cannot fix an approach/chop deficit. This attempt isolates (1) —
> fixed, confirmed by code inspection and by the trace — while (2) remains exactly as
> diagnosed. Re-plumbing a calibration to the right model can only ever fix problems of type
> (1); it was always going to be silent on type (2), and the data says it was.

Kept default: `configs/play_craft_commit4.yaml` (scan off) stays the reference
`commit_length=4` config; `configs/play_craft_commit4_scan.yaml` is a new, separate
comparison config, not a replacement — no checkpoint touched by this attempt.

*Previous: `docs/09_curiosity_coldstart.md`; `commit_length` (attempt #4A, first non-zero
result 3/31); online RND on top of it, ruled out mechanistically (attempt #4B). Current:
scan + commit_length=4 in two-brain mode — wiring hypothesis confirmed, outcome still 0/7,
no-go on a larger batch. Next: the approach/chop behaviour itself (attempt #2's "behavioural,
not perceptual" diagnosis, now replicated three times — attempt #2's own two-brain run,
attempt #3's coverage fine-tune, and this attempt's high-std stretch in episode 1) is the
standing lead; scan and RND have each, independently, run into the same wall from opposite
directions (search-side, novelty-side) without touching it.

## Cold-start attempt #6 (PC, 2026-07-20) — real CEM (iCEM-lite for discrete actions, arXiv:2512.24497): no-go, first evidence of a NEW degenerate-convergence pathology

With online RND ruled out (attempt #4B: novelty converges on single-episode homogeneous
frames within ~150 ticks, doesn't discriminate lost-vs-found) and scan re-enabled in
two-brain mode also ruled out (attempt #5: wiring confirmed correct, outcome still 0/7,
"surrounded by trees and still didn't chop" replicated a third time), the user's next
lever, reasoning from the project's own bibliography (Terver et al., arXiv:2512.24497,
recommends real CEM over random-shooting for JEPA-WM planning), was to replace
`DiscreteLatentPlanner`'s single-generation random/sticky-shooting with iterative CEM
refinement: sample once, score, keep elites, refit a **categorical** distribution (this
is discrete-action iCEM, not classical continuous-Gaussian CEM), resample, repeat.

**Implementation** (`mine_jepa/ebwm/planner.py`): `DiscreteLatentPlanner` gained
`cem_iters` (default 1), `cem_elite_frac` (default 0.1), `cem_smoothing` (default 0.01).
The scoring/rollout block (nearest-prototype MSE + optional Plan2Explore novelty blend)
was factored out into `_score()` so both the `cem_iters<=1` path and the refit loop call
the identical code — no duplicated scoring logic. Generation 1 still samples via the
existing `_sample_actions()` (sticky_prob still seeds the starting pool); for
`cem_iters>1`, the top `cem_elite_frac` fraction of candidates by score become the elite
set, a `[horizon, n_actions]` categorical table is built from their per-timestep action
frequencies (+`cem_smoothing` Laplace floor, renormalised per row so no action's
probability collapses to exactly 0), and generations 2..`cem_iters` sample fresh,
independent-per-timestep candidates from that table. The single best-scoring sequence
seen across ALL generations (tracked, not just the last generation's argmax) is what
gets returned. `cem_iters<=1` skips the refit loop entirely.

**Bit-for-bit verification (done before any live run, no MineRL/Java involved):** a
standalone script reimplemented the pre-CEM `plan()` body verbatim and compared its
output, under a fixed seed, against the new `plan(cem_iters=1)` on BOTH `ebwm.pt` and
`craft_wm_v4.pt` (via `wm.jepa`), across `sticky_prob ∈ {0.0, 0.5}` and
`commit_length ∈ {1, 4}` — 8 cases total, chosen action AND `goal_score_std` identical
to machine precision in all 8. `cem_iters=1` is confirmed the exact original code path.

**New config**: `configs/play_craft_commit4_cem.yaml` — clone of
`configs/play_craft_commit4.yaml` (two-brain, sticky 0.5, scan off, `commit_length=4`)
with `planner.cem: {iters: 3, elite_frac: 0.1, smoothing: 0.01}`, `n_candidates: 512`
kept (not reduced) for generation fidelity.

**fps cost, measured before the live batch**: a microbenchmark (20 `plan()` calls,
`ebwm.pt`, `n_candidates=512`, `commit_length=4`, `sticky_prob=0.5`, GPU) gave
53.0 ms/call at `cem_iters=1` vs 156.1 ms/call at `cem_iters=3` — **2.94×**, in line with
the expected ~3× (3 generations × the same per-generation rollout cost).

**Result, N=8 (`logs/coldstart_commit4_cem.log`, seed 0, `MineRLObtainIronPickaxeDense-v0`,
exit code 0, no crashes): 0/8 successes** (0 logs chopped, 0 planks, reward 0, `chop=188
craft=0` — mode NEVER switched to craft — in all eight episodes).

| Ep | steps | top action | fps |
|---|---|---|---|
| 1 | 3000 | a6=50% a7=24% a14=10% | 66.0 |
| 2 | 3000 | **a14=77%** a13=9% a6=5% | 67.1 |
| 3 | 3000 | a14=58% a13=9% a6=6% | 67.6 |
| 4 | 3000 | **a14=81%** a13=13% a7=3% | 66.8 |
| 5 | 3000 | a14=74% a13=22% a6=3% | 67.3 |
| 6 | 3000 | a14=51% a6=43% a13=3% | 68.0 |
| 7 | 3000 | a6=50% a14=24% a1=8% | 64.8 |
| 8 | 3000 | **a6=89%** a14=2% a12=2% | 66.6 |

Mean fps 67.0 vs the `commit4`-alone baseline's mean ~114 (range 101-132,
`logs/coldstart_commit4_n20_clean.log`) — a **~41% wall-clock throughput drop**, close to
the 2.94× per-call planning cost diluted by the fixed cost of the env step/action-repeat
loop. Not disqualifying on its own: `max_steps` is a step budget, not a wall-clock budget,
so the drop does not shrink any episode's actual chance of finding a tree.

At the pooled `commit_length=4`-alone base rate (3/31, 9.7%), the expected count in 8
trials is ≈0.78 — 0/8 is not surprising by itself, positive or negative, so per this
project's own standing rule the call rests on the qualitative evidence, not the outcome
count.

**The qualitative evidence is not neutral — it points to a NEW, real regression.**
Top-action concentration (the % share of the single most-used action over the whole
episode) averages **66.3%** across these 8 CEM episodes (50, 77, 58, 81, 74, 51, 50, 89),
roughly **double** the `commit4`-alone baseline's 20-episode average of **35.8%** (range
19-69%, only one episode ever exceeding 51%). Half the CEM episodes (2, 4, 5, 8) exceed
every non-outlier baseline episode's concentration. This is the CEM refit doing exactly
what `cem_smoothing` was meant to prevent it from doing, just more slowly: with a mostly
flat, undiscriminating reward landscape (Defect 2 — no tree in view for most of an
episode, per the "am I lost" diagnosis running through attempts #2-#5), the elite set's
tiny residual noise-driven preference for one action gets amplified generation-over-
generation into near-total commitment to it — episode 8 spent 89% of 3000 steps just
attacking in place (`a6`, no forward component), episodes 2/4/5 spent 74-81% of the
episode sprint-attacking in a fixed direction (`a14`) with almost no camera-turn actions
surviving in the top 3, i.e. no visible search-sweep behaviour once the initial heading
didn't find a tree. This is mechanistically distinct from attempt #2/#5's "agent spins
on a12" pathology (that one *turns* pathologically; this one *commits* pathologically) —
a second, independent way for a flat-signal cold-start region to break a planner that
assumes its own top candidates are informative.

**VERDICT: no-go on the N=15-20 batch.**

- **0/8, not "any success"** — the first go/no-go criterion (any success) is not met.
- **Not "visibly more coherent/less erratic"** — the opposite: action-profile
  concentration nearly doubles the baseline's, and the episodes with the highest
  concentration (74-89%) show the LEAST evidence of search behaviour (turn actions drop
  out of the top 3 almost entirely), the opposite of CEM's promise of "more coherent
  approach trajectories."
- fps cost (-41%) is real but not disqualifying by itself (step-budgeted, not
  time-budgeted) — it is not what drove this call.
- Per the task's own decision rule: a wash-or-regression on outcome, combined with a
  genuine, mechanistically explainable regression on the one qualitative axis CEM was
  supposed to improve, is a clear stop — spending N=15-20 here would confirm a symptom
  already visible in the N=8 action-profile data, not discover new information.

> **LESSON: CEM's elite-refit mechanism needs a discriminative score to refine — it has
> no way to know the score is uninformative.** Attempts #2-#5 established that most of
> a cold-start episode has a near-flat `goal_score_std` (no tree in view). Random/sticky
> shooting degrades gracefully in that regime (each replan draws a fresh, still-diverse
> candidate pool, so the agent's behaviour stays varied even when the score can't
> discriminate). Iterative CEM refit does the opposite: it treats a flat landscape's tiny
> noise-driven ranking as real signal and concentrates the next generation's samples on
> it, generation over generation — the *sharper* the method, the *more confidently wrong*
> it commits when the underlying signal has nothing to say. This is a variant of the
> project's own root-cause pattern from `docs/09` (reproducing a method's FORM without the
> CONDITION it needs to work): CEM's iterative refinement helps when scores are
> discriminative almost everywhere (Terver et al.'s setting); here the score is
> discriminative in a small fraction of an episode and flat everywhere else, which is
> exactly the regime CEM's core mechanism is not built to handle gracefully.

No checkpoint touched by this attempt (`ebwm.pt`, `craft_wm_v4.pt` both read-only).
`configs/play_craft_commit4.yaml` (cem_iters=1 implicit default) stays the reference
`commit_length=4` config; `configs/play_craft_commit4_cem.yaml` is a new, separate
comparison config. The CEM machinery itself (`cem_iters`, `_score`, `_refit_categorical`)
stays in `planner.py`, config-gated off by default (`cem_iters=1` bit-for-bit verified) —
available for a future attempt that first fixes the flat-signal problem (still Defect 2,
still open) rather than layering a sharper search on top of it.

*Previous: `docs/09_curiosity_coldstart.md`; commit_length (attempt #4, first non-zero
result 3/31); online RND (attempt #4B, ruled out mechanistically); scan re-enabled in
two-brain mode (attempt #5, wiring confirmed correct, outcome still 0/7). Current: real
CEM (attempt #6) — no-go, and the first attempt to actively make things measurably worse
on a proxy axis (action-profile concentration) rather than merely fail to help. The
standing lead is unchanged and now reinforced from a fourth independent angle: the
flat-signal "no tree in view" regime (Defect 2) is the thing that needs fixing before any
search-mechanism refinement (sticky, scan, CEM) can pay off — each of the last three
attempts has broken against exactly that same wall from a different direction.

## Cold-start attempt #7 (PC, 2026-07-20) — trained distance metric (Destrade et al., arXiv:2601.00844): offline gate PASSED, live no-go, and a NEW, more specific diagnosis than "doesn't discriminate"

Attempts #1-#6 all worked *around* the same defect (Defect 2: `goal_score_std` goes
flat/undiscriminating with no tree in view) without ever retraining the distance itself —
`_score()`'s goal distance was always raw-latent squared-L2 on `ebwm.pt`'s untrained
latent space. This attempt targets the distance directly: train a small projector `P`
(`mine_jepa/ebwm/value_head.py::DistanceProjector`, 2-layer MLP, `in_dim=4096` →
`proj_dim=32`, ~1.06M params) so Euclidean distance in `P`'s output space approximates
true action-count-to-goal, following the paper's actual validated design (a shared
projector applied independently to `z_t`/`z_goal`, not an MLP over their concatenation).

**Implementation.** `scripts/train_value_projector.py` + `configs/train_value_projector.yaml`:
`ebwm.pt` loaded and frozen (`requires_grad_(False)` verified on all 49 params — no
gradient ever reaches the main WM, same isolation discipline as `rnd.py`/`curiosity.py`).
Training data: the same Treechop demos `ebwm.pt` itself trained on
(`data/minerl_goal/episodes.npz`, 453K frames, 210 episodes) plus the attempt #3 coverage
episodes (`data/minerl_coverage/episodes.npz`, 8K frames). Targets: near pairs `(x_t,
x_{t+k})`, `k ~ U[1,75]`, same episode → MSE(pred_dist, k); far pairs (cross-episode,
within-episode beyond `k_max=75`, and coverage-frame-vs-Treechop-goal-centroid, the
centroid reused verbatim from `scripts/play_ebwm.py::build_goal_latents`) → one-sided
hinge `max(0, k_max - pred_dist)²` (only penalises predicting closer than the known
lower bound, never penalises "too far"). `_score()` in `planner.py` gained an optional
`distance_projector` param (default `None` = original raw-L2 path, **verified bit-for-bit
identical under a fixed seed**: same action, same `goal_score_std`, to the last printed
digit).

**Bug found and fixed en route:** `collect_minerl_multi.py`'s shard merge concatenates
per-episode shards without forcing `done=True` at shard boundaries (the same class of bug
`merge_craft_coverage.py` already patches at the demos/coverage junction) — the coverage
npz's `dones` is entirely `False`, so its 8000 frames were one single 8000-step episode
instead of the ~20 independent 400-step ones they actually are. Fixed with a documented
chunk-size fallback in `episode_ranges()` (config-driven, `coverage_chunk_size: 400`,
matching `collect_minerl_coverage.yaml`'s `max_steps_per_episode`) — no collection script
or data file touched.

**Mandatory offline validation gate (run before any live time, per this project's own
smoke-test discipline) — PASSED clearly.** Held-out episodes (10% by episode, no frame
leakage): near pairs (true k≤5, n=2560) `pred_dist` mean=**12.317**, std=11.568 (true k
mean=3.04); far/coverage-vs-goal pairs (n=2560) `pred_dist` mean=**97.257**, std=15.568.
**Separation ratio 7.896** (gate required ≥1.3). `checkpoints/value_projector.pt` saved.

**Dry run before spending live time:** the full `play_craft.py` setup path (load
`craft_wm_v4.pt` → build chop goal → build `SwitchingCraftPlanner` → load `ebwm.pt` →
build Treechop goal-centroid → load `value_projector.pt` → build the two-brain
`DiscreteLatentPlanner` with `distance_projector` set → one `plan()` call) ran clean with
no MineRL/Java process involved.

**Live result, N=6 (`logs/coldstart_commit4_value.log`, seed 0,
`configs/play_craft_commit4_value.yaml` = `commit4` clone, `distance_projector:
checkpoints/value_projector.pt` added, everything else — sticky 0.5, scan off,
`commit_length=4` — unchanged): exit code 0, no crashes, 0/6 successes** (0 logs, 0
planks, `chop=X craft=0` in all six episodes — the craft mode never triggered because no
episode ever obtained a log).

| Ep | steps | top action | reward |
|---|---|---|---|
| 1 | 3000 | a14=23% a6=16% a13=13% | 0 |
| 2 | 1600 | a6=40% a14=13% a7=11% | 0 |
| 3 | 1279 | a14=22% a13=18% a6=11% | 0 |
| 4 | 2014 | a6=33% a7=21% a14=15% | 0 |
| 5 | 2114 | a6=39% a7=20% a14=13% | 0 |
| 6 | 1147 | a7=25% a6=21% a14=18% | 0 |

Mean steps 1859. Top-action concentration 16-40%, in line with the `commit4`-alone
baseline's 19-69% range — **not** CEM's pathological ≥50% average, no over-commitment
signature this time. At the pooled `commit_length=4` base rate (3/31, 9.7%), 0/6 alone is
not surprising (expected ≈0.58); by itself this would be inconclusive.

**But the offline/online gap itself is the finding, and the GIF/log analysis explains
it.** `play_minerl_multi.py` only keeps a GIF from the best-*successful* episode; with 0/6
successes the "best" logic never triggers and only the LAST episode's raw frames survive
on disk (`assets/agent_play_craft_commit4_value.gif` = episode 6, 1147 steps, 1144
frames — the other five episodes' frames were overwritten in place and are unrecoverable).
Episode 6 ended well short of the 3000-step budget, and its final frames (steps 1120-1147)
are near-black, high-frequency textured close-ups — consistent with the agent falling into
a dark cave/ravine and dying, matching attempt #2's earlier "spawned in a treeless rocky
ravine" finding. None of the sampled frames across the whole episode (steps 0, 112, 240,
336, 480, 608, 672, 928, 992, 1100-1147) show a tree.

Extracting frames at this episode's scan-log steps and correlating with `goal_score_std`
(now on a very different absolute scale than the raw metric's ~0.001-0.06, per the
coordinator's observation — here ~0.02-2.9, a real ~150× dynamic range within one
episode) gives a specific, quantitative answer:

- **Pearson corr(goal_score_std, frame brightness) = -0.565** over the 72 scan readings
  in episode 6.
- Frames with brightness > 60 (visually confirmed daytime, open grass/sky, steps 0-464):
  mean std = **0.499**.
- Frames with brightness ≤ 60 (visually confirmed dusk/night — a moon becomes visible in
  the sky from step 480 onward, plus later cave-dark frames, steps 480-1136): mean std =
  **1.174**, more than double.
- **Not monotonic**: the single darkest, most extreme frames of the whole episode (steps
  1120/1136, brightness ~14-15, right before the episode ends) have the LOWEST std of
  the entire trace (0.019/0.030) — even lower than the daytime baseline. So the relationship
  isn't simply "darker → higher std"; it looks like the projector is unstable/erratic once
  scene composition leaves its training distribution, not tracking a single stable nuisance
  variable in one direction.
- A brightness check on the training data itself shows this OOD gap is real: Treechop
  demos (`minerl_goal`) are already fairly dark on average (mean brightness 45.5, 81% below
  the 60 threshold — mostly dense forest-canopy shade, all still shot in daytime) and the
  coverage episodes are brighter (mean 92.4, only 31% below 60, open plains, also daytime).
  **Neither source contains true night-sky or cave-interior frames** — the specific visual
  regime episode 6 spent roughly half its steps in.

> **LESSON — this is a THIRD, more specific finding than either prior category
> ("doesn't discriminate" like offline-frozen-ensemble curiosity in `docs/09`, or
> "discriminates correctly but that's still not the bottleneck" like the raw-latent
> attempts #2/#3/#5). The trained metric DOES discriminate — it has real, large dynamic
> range, the opposite of RND-style collapse — but what it discriminates is dominated by a
> lighting/scene-composition nuisance axis (day/dusk/night, forest-shade vs open-sky vs
> cave-dark) that the offline validation gate never tested, because BOTH its near-pair and
> far-pair validation sets were drawn from the training distribution (predominantly
> daytime Treechop + daytime coverage). A strong same-distribution held-out separation
> (7.9×) is consistent with the metric having learned SOMETHING real and generalisable
> within that distribution, while being silent on whether it generalises correctly outside
> it — and in this deployment the two-brain chop planner spent much of its time exactly
> outside it (dusk, night, caves — the random-spawn/`ObtainIronPickaxeDense` regime attempt
> #2 already flagged as harder than Treechop's always-in-forest spawn). A large,
> non-monotonic, OOD-driven signal is arguably WORSE for MPC than the raw metric's honest
> flatness: flatness at least fails gracefully (all candidates score equally, argmax is
> arbitrary but harmless); a confidently-wrong signal can actively steer the plan toward
> whatever spuriously looks "close" under the lighting artefact, which is indistinguishable
> from noise to the planner.**

**VERDICT: no-go on the N=15-20 batch, with this checkpoint as-is.**

- **0/6, no success** — first criterion not met, though not damning alone at this N.
- **No evidence of "more coherent/less erratic" behaviour** — action-profile concentration
  stayed in the normal baseline range (not a CEM-style regression), but the qualitative
  mechanism this attempt was supposed to fix (flat/undiscriminating `goal_score_std` with
  no tree in view) is not what actually happened live: the signal was *not* flat, it swung
  by two orders of magnitude, and the swing tracks a lighting artefact rather than
  tree-proximity — a diagnosed, specific new problem, not "no effect."
- Spending 15-20 more live episodes on the exact same checkpoint would not resolve this:
  the root cause (training data lacks night/cave frames, so the metric is unconstrained —
  and empirically erratic — exactly where the live episodes actually go) is a data problem,
  not a sample-size problem.
- **If this lever is revisited**: either (a) explicitly collect/augment training pairs
  covering the dusk/night/cave visual regime (a targeted coverage-collection pass, not more
  daytime episodes), or (b) add photometric augmentation (brightness/contrast jitter) during
  projector training so `P` is constrained to be invariant to lighting rather than free to
  key off it, before spending another live batch.

No checkpoint touched except the new, separate `checkpoints/value_projector.pt`
(`ebwm.pt`, `craft_wm_v4.pt`, and their backups were only read). `distance_projector=None`
stays the exact original behaviour, bit-for-bit verified — `configs/play_craft_commit4.yaml`
is unchanged; `configs/play_craft_commit4_value.yaml` is a new, separate comparison config.

*Previous: `docs/09_curiosity_coldstart.md`; commit_length (attempt #4, first non-zero
result 3/31); online RND (attempt #4B, ruled out mechanistically); scan re-enabled
(attempt #5); real CEM (attempt #6, new action-concentration regression, no-go). Current:
trained distance metric (attempt #7) — the first attempt to pass its own offline gate
convincingly and still find nothing live, with a diagnosed and specific reason (an
OOD lighting confound the offline gate structurally could not catch, because both its
near- and far-pair validation sets share the same training-time visual distribution). The
standing lead (Defect 2, "no tree in view" / approach-behaviour under a flat-or-now-erratic
signal) is unchanged; this attempt adds a concrete, actionable data gap (no night/cave
training frames) rather than ruling out trained metrics as a class.

## Cold-start attempt #8 (PC, 2026-07-21) — Proposal A (action-pool priming) + Proposal C
(bushwhack macro) on top of commit_length=4: NO-GO, and a VERIFIED (not just alleged)
action-concentration regression

The standing diagnosis after attempts #4-#7 (CLAUDE.md) is that the wall is
BEHAVIOURAL (action generation), not perceptual: three independent score/search-quality
fixes (online RND, real CEM, a trained cost-to-reach metric) each landed differently, but
none moved the outcome, while `commit_length=4` (a pure execution fix, attempt #4) is the
only lever that has ever produced a non-zero result. Proposal A injects hand-authored
"clean" macros (sustained forward+attack, continuous camera-turn, walk-backward) directly
into the 512-candidate pool (`mine_jepa/ebwm/planner.py::_build_primed_macros`,
`planner.action_pool_priming`, config-gated, disabled/default bit-for-bit verified).
Proposal C replaces the scan macro's turn-in-place reflex with a bounded
forward-sprint+jump "bushwhack" cruise (`scan.macro: bushwhack`) for spawns where turning
alone can never find anything (attempt #5's treeless underground episode). Both combined
with `commit_length=4`, two-brain chop planner, sticky 0.5, scan on (calibrated
`flat_threshold: 0.003`, wiring confirmed correct in attempt #5), `configs/play_craft_commit4_ac.yaml`.

**Result, N=8 (seed 0, `MineRLObtainIronPickaxeDense-v0`, `logs/play_ep_001.txt`
through `play_ep_008.txt`): 0/8 logs, 0/8 planks, reward 0.**

| Ep | steps | action distribution | scan/bushwhack triggers |
|----|-------|---|---|
| 1 | 3000 | a7=49% a6=26% a14=21% | 0 |
| 2 | 3000 | a1=42% a14=17% a6=8% | 2 |
| 3 | 3000 | a14=60% a6=34% a7=3% | 1 |
| 4 | 3000 | **a14=97%** a6=1% a7=1% | 0 |
| 5 | 3000 | a14=61% a7=21% a6=10% | 1 |
| 6 | 3000 | **a14=100%** a4=0% a0=0% | 0 |
| 7 | 1856 | a6=29% a13=28% a14=11% | 8 |
| 8 | 3000 | a14=83% a7=4% a6=3% | 0 |

At the pooled `commit_length=4`-alone base rate (3/31, 9.7%), the expected count in 8
trials is ≈0.78 — 0/8 is not surprising by itself, so per this project's own standing
rule the call rests on the qualitative evidence, not the outcome count.

**Verified finding (not asserted): this echoes attempt #6's CEM concentration
regression, and is quantitatively close to it — but it is a NEW extreme, not a
restatement of something already present.** Before writing that claim down, every
`commit_length=4`-ALONE batch from attempts #4-#7 (no A/C priming active) was pulled —
`coldstart_commit4.log`, `coldstart_commit4_fix_verify_n6.log`,
`coldstart_commit4_n20.log`, `coldstart_commit4_n20_clean.log`,
`coldstart_commit4_rnd_falsify_n7.log`, `coldstart_commit4_rnd_diag.log` — and every
per-episode top-action percentage across all of them (59 non-degenerate episodes; one
1-step episode with a trivial 100% is excluded as a launch/reset artefact, not a
gesture) was compared against attempt #8's 8:

| | N | mean top-action % | max top-action % |
|---|---|---|---|
| `commit_length=4` alone, all pooled batches | 59 | — (not previously computed as a mean) | **72%** (one single outlier, `fix_verify_n6` ep1) |
| `commit_length=4` alone, `n20_clean` only (CLAUDE.md's own CEM-comparison baseline) | 20 | 35.8% | 69% |
| CEM (`cem_iters=3`, attempt #6) | 8 | 66.3% | 89% |
| **Attempt #8 (A+C priming)** | 8 | **65.1%** | **100%** |

Two things are both true and worth separating:

- **The echo is real, not superficial**: attempt #8's mean concentration (65.1%) is
  within 1.2 points of CEM's (66.3%) — both roughly DOUBLE the unprimed
  `commit_length=4`-alone baseline's 35.8% average. This is not a coincidence of
  wording; it is the same magnitude of regression on the same metric, from a
  mechanically unrelated change.
- **Two of attempt #8's episodes (97%, 100%) are a genuinely NEW extreme**, exceeding
  even CEM's most concentrated episode (89%) and far exceeding anything ever seen in 59
  pooled `commit_length=4`-alone episodes without any priming active (max 72%, and that
  72% is a single outlier, not a typical value). So the correct statement is: **attempt
  #8 reproduces CEM's regression in magnitude, and in its two worst episodes goes
  further than CEM ever did** — not merely "similar," and not "already present in the
  baseline, priming changed nothing."

**A distinct mechanism from CEM's, converging on the same symptom.** CEM's elite-refit
loop *amplifies* noise generation-over-generation from a flat score. Action-pool priming
does something structurally different: `a14`'s "sprint+forward+attack" macro
(`n_forward_attack`, half the priming budget) is placed in the SAME fixed slice of
30-of-512 candidate slots on **every single replan**, not resampled. Once that exact
macro scores best in one replan (easy when the frame is genuinely salient — both episode
4 and episode 6's raw `goal_score_std` traces show elevated values, 0.007-0.03, from
early in the episode, i.e. *something* was visible, not a flat/lost scene), it is
mechanically guaranteed to be available and near-identically competitive on the very next
replan too, because the pool always contains it again — unlike sticky sampling, where a
similarly-good sequence has to be independently redrawn or get lucky. This is a different
FAILURE ROUTE (guaranteed-recurrence-in-the-menu vs. iterative-noise-amplification) to
the same OUTCOME (near-total single-action lock-in) — a second, independent way for an
intervention aimed at the candidate pool to over-commit once one candidate looks good by
chance, on top of CEM's.

**Episode 7 — the direct behavioural replication, this time with the scan/bushwhack
signal confirmed correctly inert.** This episode ended early (1856/3000 steps, no death
message logged, cause unknown) but its `goal_score_std` trace is the most informative of
the eight: from step 1152 to step 1840 (688 of its 1856 steps, roughly 37% of the whole
episode) std sits at 0.010-0.025 — the "salient scene" band this chapter's own Treechop
calibration associates with canopy filling the frame — and the scan/bushwhack macro
correctly stays inert throughout (no `SCANNING` tag), exactly as designed: back off when
something is genuinely in view. **The agent still did not chop a single log during that
entire 688-step stretch.** This is a direct, in-run replication of the standing diagnosis
from attempts #2, #5, and the two-brain experiment: "surrounded by (or near) something
salient and still doesn't chop" — now observed under attempt #8's combined
priming+bushwhack configuration, the fourth independent confirmation of the same wall.

**VERDICT: NO-GO on a larger batch.**

- **0/8, not "any success"** — the first criterion is not met, though not damning alone
  at this N (expected ≈0.78 by the pooled base rate).
- **A verified, not merely suspected, regression on action-profile concentration** —
  quantitatively matching CEM's regression in its mean, and exceeding CEM's own worst
  episode in its two most extreme cases (97%, 100% vs CEM's 89% ceiling).
- **No qualitative sign of the intended improvement** — Proposal A/C were meant to make
  a genuine sustained gesture available and to cover ground when nothing is found; episode
  7's high-std stretch shows the opposite failure mode is still occurring even when the
  macros ARE available and something IS salient.
- Per the task's own decision rule (a wash-or-regression on outcome plus a
  mechanistically explained concentration regression, with no compensating positive
  signal, is a stop): spending N=15-20 here would confirm a symptom already visible in
  the N=8 action-profile data, not discover new information.

> **LESSON: two structurally different interventions on the candidate-generation side
> (CEM's iterative elite-refit, action-pool priming's fixed always-available macros) can
> independently converge on the SAME failure signature — near-total single-action
> lock-in — for two DIFFERENT mechanical reasons (noise amplification vs.
> guaranteed-recurrence). This is now the fourth independent line of evidence (after
> RND, CEM, and the trained distance metric) that the standing wall survives, and can be
> made measurably worse by, interventions aimed at what gets proposed or how scores are
> refined — episode 7's 688-step high-std/scan-correctly-inert stretch shows the deficit
> is not "nothing good was ever on the menu," it is what happens once something IS on the
> menu and IS salient.**

No checkpoint touched (`ebwm.pt`, `craft_wm_v4.pt` read-only). `configs/play_craft_commit4.yaml`
(both `action_pool_priming` and `scan.macro` unset → original behaviour) is unchanged;
`configs/play_craft_commit4_ac.yaml` is a new, separate comparison config.

### Follow-up, same dispatch — spawn-viability diagnostic and Proposal B (BC actor prior) built, not yet batch-evaluated

Two pieces of follow-up work were built in the same pass that produced the attempt #8
verdict above, to be evaluated in a later dispatch rather than folded into attempt #8's
own N=8 (per the task's own scope limit):

- **Spawn-viability diagnostic** (`scripts/play_craft.py`, config block `spawn_diag:`,
  disabled by default): dumps a first-frame thumbnail per episode to
  `assets/spawn_thumbs/` and tracks the max chop-mode `goal_score_std` reached over the
  whole episode against a configured "something was visible at some point" threshold —
  neither claims to be definitive alone (attempt #7's lighting-confound finding is a
  direct warning against trusting an untested automatic proxy), but together they let a
  future batch's zero-success episodes be split into "the algorithm never found a tree"
  vs. "there plausibly wasn't one within reach," which no earlier attempt could
  distinguish. Enabled in `configs/play_craft_commit4_ac.yaml` and the new
  `configs/play_craft_commit4_actor.yaml` (below) for the next batches that use them.
- **Proposal B — BC actor candidate prior** (`mine_jepa/ebwm/actor.py::BCActor`,
  `scripts/train_actor_bc.py`, `checkpoints/actor_bc.pt`): a small MLP classifier on
  frozen `ebwm.pt` latents, trained by behavioural cloning on Treechop demos + the
  attempt #3 coverage episodes, whose predicted action distribution seeds a further
  slice of `_sample_actions()`'s candidate pool — a LEARNED prior in the same role as
  Proposal A's hand-authored macros, not a replacement for the MPC's own scoring (not a
  repeat of Phase 4's failed pure-BC policy: the actor only proposes, the world-model
  MPC still evaluates and re-plans every step). `actor=None` (default) verified
  bit-for-bit identical to the pre-existing sampling on both `DiscreteLatentPlanner` and
  `SwitchingCraftPlanner`, fixed-seed comparison, same discipline as every prior
  config-gated change in this chapter.
  - **Training-data composition mattered, concretely, not just in principle.** Two
    actors were trained: `actor_bc.pt` (Treechop + coverage) passed the mandatory
    anti-collapse gate (top-action argmax fraction 0.863, mean entropy 1.296 nats);
    `actor_bc_treechop_only.pt` (Treechop demos alone) FAILED it (0.964, entropy 1.102)
    and the training script correctly refused to write the checkpoint — the same
    refusal-to-save discipline as `train_value_projector.py`/`train_craft_wm_v4.py`. The
    held-out validation split happened to draw zero coverage episodes (16 of 226 total
    episodes are coverage; a 10%-by-episode split can miss them by chance), so a direct
    post-hoc check was run instead: feeding the coverage-trained actor 2000 held-out-style
    coverage frames vs. 2000 Treechop frames shows genuinely context-dependent behaviour,
    not just a different average — mean predictive entropy 2.448 nats on coverage frames
    (near the 2.833 maximum) vs. 1.259 nats on Treechop frames, and the argmax
    distribution shifts from Treechop's `a6 (attack) 85%` to a much flatter coverage
    spread (`a1=35% a6=28% a10=23%` plus several others >1%) — the actor learned to
    propose attack-heavy sequences when the scene looks like an expert Treechop frame and
    a more exploratory mix when it looks like a random-spawn coverage frame, exactly the
    context-sensitivity the training data mix was meant to provide, though at a modest
    absolute classification accuracy (48.3% held-out, vs. 58.7% for the collapsed
    Treechop-only actor — the more diverse actor is a WORSE next-action classifier by
    accuracy alone, expected, since coverage's random-policy targets are less
    predictable than expert demos, and not disqualifying for a proposal-only role).
  - **Live sanity check** (`configs/play_craft_commit4_actor.yaml`, N=3, seed 0,
    isolated from Proposal A/C to attribute any effect to the actor alone): results in
    the next dispatch's report, not this one — scope here was implementation, training,
    the bit-for-bit and anti-collapse verification above, and a crash/reachability check
    only, per the task's explicit instruction not to run a full evaluation batch in this
    pass.

*Previous: `docs/09_curiosity_coldstart.md`; commit_length (attempt #4, first non-zero
result 3/31); online RND, scan re-enabled, real CEM, and a trained distance metric
(attempts #4B-#7) — three independent score/search-quality fixes, none moved the
outcome. Current: Proposal A (action-pool priming) + Proposal C (bushwhack macro),
attempt #8 — NO-GO, with a verified action-concentration regression (matching CEM's in
magnitude, exceeding it in two episodes) via a distinct mechanism
(guaranteed-recurrence vs. noise-amplification), and a fourth independent confirmation
(episode 7) that the wall survives even when something salient is genuinely in view and
the search/scan machinery is correctly inert. Spawn-viability diagnostic and Proposal B
(BC actor prior) built and passing their own construction-time checks, live evaluation
pending a future dispatch.

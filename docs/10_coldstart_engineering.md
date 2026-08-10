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
  - **Bit-for-bit default and reachability verification** (a follow-up dispatch,
    `verify_actor_prior.py`, scratchpad, read-only on `checkpoints/ebwm.pt` and
    `checkpoints/actor_bc.pt`, no MineRL env): `actor=None`/`actor_n_samples=0` was
    checked, not just asserted by analogy to the other config-gated changes in this
    chapter — fixed-seed `_sample_actions()` calls with the actor arguments entirely
    absent vs. present-but-inert (`actor=actor, actor_n_samples=0`) are tensor-equal,
    and `DiscreteLatentPlanner.plan()` returns the identical action and
    `goal_score_std` in both configurations. Separately, a reachability check (actor
    enabled, `n_actor_samples=128` of 512, 40 Treechop-demo frames, one `plan()`-style
    scoring call per frame) found the winning (argmax) candidate landed inside the
    actor-proposed slice on 6/40 calls (15.0%) vs. a 25.0% uniform-chance baseline
    (128/512) — below chance on this particular sample, but nonzero: the actor's
    candidates are demonstrably live and reachable in the executed stream, not silently
    dead code, just not (on this small check) outperforming the sticky/i.i.d. slice.
  - **Anti-collapse gate independently re-run for this report** (not just read off
    the original training output, which had no persisted log): `train_actor_bc.py`
    was re-run seed 0 for both configs and reproduced the exact previously-quoted
    numbers — `actor_bc.pt` (Treechop+coverage): val_acc 0.483, mean entropy 1.296,
    top_action_frac 0.863 → gate PASS; `actor_bc_treechop_only.pt` (Treechop-only):
    val_acc 0.587, mean entropy 1.102, top_action_frac 0.964 → gate FAIL, checkpoint
    correctly refused (confirmed absent from `checkpoints/`). Logs now persisted at
    `logs/train_actor_bc.log` and `logs/train_actor_bc_treechop_only.log`.
  - **Live sanity check** (`configs/play_craft_commit4_actor.yaml`, N=3, seed 0,
    isolated from Proposal A/C to attribute any effect to the actor alone,
    `logs/coldstart_commit4_actor_sanity.log`): **3/3 episodes completed without a
    crash** (the concrete blocker this pass was scoped to rule out) — **0/3 planks,
    0/3 logs**, not evaluated further per this task's explicit N=2-3 scope limit.
    Action profiles: ep1 `a14=45% a13=14% a7=5%` (3000 steps), ep2 `a7=25% a6=25%
    a13=9%` (1339 steps, episode ended early, no death logged), ep3 `a6=64% a12=5%
    a11=4%` (3000 steps) — none shows attempt #8's extreme 97-100% single-action
    lock-in; ep3's 64% is inside the `commit_length=4`-alone baseline's normal range
    (max 72% pooled). `spawn_diag` (also enabled in this config) recorded
    `max_chop_std` 0.030, 0.029, 0.019 across the three episodes — all above the
    0.005 viability threshold, i.e. by this diagnostic's own signal something
    findable was plausibly in view in all three episodes; thumbnails saved to
    `assets/spawn_thumbs/ep001_*.png` (3 files) for human eyeballing. **This is a
    stability/reachability check only, not a verdict on the actor's effect** — N=3
    is far too small to compare against the 9.7% `commit_length=4`-alone base rate
    (expected ≈0.29 successes at this N) or to say whether the actor helps, hurts,
    or is neutral. A confirmation batch (N=15-20, per this project's own rule) is
    the next dispatch, not this one.

*Previous: `docs/09_curiosity_coldstart.md`; commit_length (attempt #4, first non-zero
result 3/31); online RND, scan re-enabled, real CEM, and a trained distance metric
(attempts #4B-#7) — three independent score/search-quality fixes, none moved the
outcome. Current: Proposal A (action-pool priming) + Proposal C (bushwhack macro),
attempt #8 — NO-GO, with a verified action-concentration regression (matching CEM's in
magnitude, exceeding it in two episodes) via a distinct mechanism
(guaranteed-recurrence vs. noise-amplification), and a fourth independent confirmation
(episode 7) that the wall survives even when something salient is genuinely in view and
the search/scan machinery is correctly inert. Spawn-viability diagnostic and Proposal B
(BC actor prior) built, anti-collapse and bit-for-bit-default/reachability verified, and
N=3 live-stability-checked (3/3 no crash, 0/3 planks, no new action-concentration
regression) — a full N=15-20 confirmation batch on the actor alone is the next dispatch.

## Cold-start attempt #9 (PC, 2026-07-21) — Proposal B confirmation batch (BC actor as MPC
candidate proposer): NO-GO, but the sharpest negative result of the campaign

Attempt #8's follow-up left Proposal B (`BCActor`, behaviourally cloned on Treechop +
attempt #3 coverage frames, `checkpoints/actor_bc.pt`) at an N=3 stability check only:
3/3 episodes ran without a crash, 0/3 planks, and — the one open question at the time —
no evidence either way on whether a genuinely diverse, non-collapsed learned proposal
source changes the outcome. This attempt is that confirmation batch.

**Setup**: `configs/play_craft_commit4_actor.yaml` (the same config exercised at N=3 in
attempt #8's follow-up, unchanged), N=8, seed 0, two-brain chop planner, `commit_length: 4`,
sticky 0.5, scan on (calibrated `flat_threshold: 0.003`), `spawn_diag` enabled,
goal-centroid scoring only — no trained distance signal in this batch. A repair attempt for
attempt #7's lighting-confound finding (photometric `ColorJitter` augmentation added to
`train_value_projector.py`, meant to constrain the projector to be invariant to
brightness) was tried before this batch and made the day/night confound **worse, not
better** (held-out near/far separation on the augmented projector dropped and the
brightness correlation did not shrink) — not adopted, so no working distance signal
exists yet, and this batch stays on the same raw goal-centroid path as attempts
#1-#6 and #8.

**Result, N=8 (`MineRLObtainIronPickaxeDense-v0`, seed 0, no crashes): 0/8 logs, 0/8
planks, reward 0 in all eight episodes.** Fisher's exact test, one-sided, against the
pooled `commit_length=4`-alone baseline (3/31, 9.7%): **p ≈ 0.21** — not significant at
this N (expected count ≈0.78, same as every other N=8 batch in this campaign).

On outcome count alone this is indistinguishable from attempts #6, #8, or a dozen other
0/N batches. What makes this one different is that every alternative explanation this
project has used to discount a null result elsewhere was checked directly, on this exact
batch, and **each one came back negative** (i.e. ruled out, not just assumed away):

| Candidate explanation for 0/8 | Checked how | Result |
|---|---|---|
| Proposals lock the planner onto one degenerate action (attempt #8's regression) | Top-action concentration across all 8 episodes | **16-54% peak**, inside the `commit_length=4`-alone baseline's normal 19-69%/35.8%-mean range — attempt #8's 83-100% lock-in did **not** recur |
| Spawns were structurally unwinnable (no tree reachable at all) | `spawn_diag`'s `max_chop_std` per episode vs. the 0.005 viability floor | **0.017-0.047 in all 8 episodes** — every spawn cleared the floor by 3-9× |
| Proposal source lacks diversity / is a collapsed classifier | Re-checked against attempt #8's already-passed anti-collapse gate (`actor_bc.pt`: top_action_frac 0.863, mean entropy 1.296 nats) plus a manual visual spot-check of spawns this batch | Gate already passing (unchanged, same checkpoint); spot-check below |

**Manual visual spot-check (4 of 8 first-frame thumbnails, `assets/spawn_thumbs/`):**
genuine scene diversity, not four variations on one biome — a beach/water spawn, a
forest-clearing spawn with trees visibly in frame, a dark cave/ravine-like spawn, and an
open grassland spawn with trees visible at a distance. **At least 2 of the 4 checked have
a tree plausibly reachable within a short walk at frame 0** — this is not the "spawned in
a treeless rocky ravine" excuse that closed attempts #2, #5, and #8's worst episode. Two
of eight is a small, human-eyeballed sample (not a claim about all 8, and not a substitute
for `spawn_diag`'s own quantitative floor above), but it directly contradicts "there was
nothing to chop."

**VERDICT: NO-GO on a larger batch — and the sharpest negative result of the whole
campaign.** Every batch since attempt #4 has had at least one confound available to
explain away a null: attempt #6's CEM and attempt #8's priming had a verified
action-concentration regression to point to; attempt #7's trained metric had a
diagnosed OOD lighting confound; the RND batches had an inert diagnostic. **This batch
has none of those.** The proposal source is expert-trained, demonstrably non-collapsed
(entropy 1.296 nats, context-sensitive per attempt #8's coverage-vs-Treechop entropy
check), the live action profile stayed inside the normal baseline range with no
lock-in, the spawns quantitatively cleared the viability floor in all 8 episodes, and a
manual check confirms genuine scene diversity including trees visibly in frame in at
least 2 of 4 spot-checked spawns — and the batch still produced **zero** chops.

> **LESSON: this result rules out two explanations at once, cleanly, for the first time
> in the campaign.** "The candidate pool isn't diverse enough" (attempts #1, #6, #8's
> standing concern) and "the spawns are unwinnable" (attempts #2, #5, #8's recurring
> excuse) both required a genuinely diverse, non-degenerate, expert-trained proposal
> source evaluated on confirmed-viable, confirmed-diverse spawns with trees actually
> visible — which is exactly what this batch is, checked rather than assumed on every
> count — and the outcome was still 0/8. What's left standing, by elimination rather
> than by direct test, is the one component nothing in attempts #1-#9 has yet varied:
> **`ebwm.pt`'s own scoring of candidates**, trained exclusively on `MineRLTreechop-v0`
> (spawns guaranteed inside a forest) and never exercised end-to-end on
> `MineRLObtainIronPickaxeDense-v0`'s free-spawn visual distribution (open plains,
> beaches, caves, dusk) until it is asked to rank candidate futures against exactly that
> distribution live. This is flagged as a hypothesis pushed forward by elimination, not
> a confirmed finding — no experiment in this campaign has yet isolated the world
> model's cross-distribution scoring behaviour directly (attempt #7 diagnosed an OOD gap
> in a *trained add-on* distance metric, not in `ebwm.pt`'s own latent space or
> prototype-similarity scoring).**

No checkpoint touched (`ebwm.pt`, `craft_wm_v4.pt`, `actor_bc.pt` all read-only).
`configs/play_craft_commit4.yaml` (actor unset → original sampling, bit-for-bit per
attempt #8's own verification) is unchanged; `configs/play_craft_commit4_actor.yaml`
remains a separate comparison config, now with a real N=8 confirmation batch instead of
the N=3 stability check.

*Previous: `docs/09_curiosity_coldstart.md`; commit_length (attempt #4, first non-zero
result 3/31); online RND, scan re-enabled, real CEM, and a trained distance metric
(attempts #4B-#7); action-pool priming + bushwhack macro (attempt #8, NO-GO with a
verified concentration regression). Current: the BC actor confirmation batch (attempt
#9) — NO-GO on outcome (0/8), but with every standing alternative explanation (proposal
lock-in, unwinnable spawns, proposal collapse) checked and ruled out on this exact batch,
the first time a cold-start null has been reached with none of those confounds
available. The standing diagnosis shifts, by elimination, toward `ebwm.pt`'s own
candidate-scoring behaviour under `ObtainIronPickaxeDense`'s free-spawn visual
distribution — untested directly, the natural next hypothesis rather than another
action-generation-side patch.

## Cold-start attempt #10 (PC, 2026-07-21) — offline diagnostic: does `ebwm.pt`'s own
scoring generalize from Treechop to Obtain? Hypothesis CONFIRMED, sharper than expected

Attempt #9 ended by elimination, not by direct test: every action-generation-side lever
(RND, CEM, a trained distance metric, action-pool priming, a BC actor) had been tried and
none moved the outcome, leaving `ebwm.pt`'s own untrained raw-latent goal-centroid
distance — the mechanism every attempt from #1 onward built around and never once tested
in isolation — as the last unexamined component. This attempt tests it directly, **purely
offline**: `checkpoints/ebwm.pt` loaded frozen (`requires_grad_(False)` verified), no
MineRL/Java process, no training, no checkpoint written.

**Method** (`scripts/diagnose_score_generalization.py`,
`configs/diagnose_score_generalization.yaml`): reuses `DiscreteLatentPlanner`'s own
`_sample_actions()` + `_score()` — the exact code the live scan/spawn_diag machinery
already runs every replan — over 251 saved starting frames instead of live play: 160
Treechop frames (`data/minerl_goal/episodes.npz`, the data `ebwm.pt` itself trained on,
40 episodes × 4 within-episode offsets for varying tree distance), 11 real
`MineRLObtainIronPickaxeDense` cold-start spawn frames (attempt #9's
`assets/spawn_thumbs/`), and 80 Obtain-sourced coverage-episode frames (attempt #3's
`data/minerl_coverage/episodes.npz`, chunked at 400 steps to work around the known
shard-merge `dones`-all-False bug, attempt #7's fix reused verbatim). Same planner
hyperparameters as the live two-brain chop planner (horizon=12, n_candidates=512,
sticky_prob=0.5), seed 0.

**Bulk aggregate result — a wash, and by itself would have DISCONFIRMED the hypothesis:**

| Group | n | mean | median | std | min | max | p10 | p90 |
|---|---|---|---|---|---|---|---|---|
| treechop | 160 | 0.00742 | 0.00459 | 0.00716 | 0.00022 | 0.03484 | 0.00126 | 0.01996 |
| obtain_spawn | 11 | 0.01085 | 0.00977 | 0.00565 | 0.00165 | 0.01900 | 0.00572 | 0.01794 |
| obtain_coverage | 80 | 0.00833 | 0.00610 | 0.00700 | 0.00055 | 0.04225 | 0.00185 | 0.01625 |

Obtain's median and p90 are comparable to, if anything slightly *higher* than, Treechop's
— no simple "the score goes flat on Obtain" story survives the raw numbers alone.

**But a paired, human-eyeballed tree-visible-vs-not check across all 3 independently
sampled sources reveals a clean, consistent REVERSAL, not a flattening.** (Treechop's
offset=0.0 "spawn" frames turned out to mostly show sky/underwater views at random camera
orientation — an incidental finding in itself, worth noting for future frame-sampling
choices — so the Treechop comparison uses offset=0.5 frames instead, which land mid an
actual chopping demonstration.)

| Source | Tree clearly visible/close | `goal_score_std` | No tree / distant / open | `goal_score_std` |
|---|---|---|---|---|
| Treechop (offset 0.5, native distribution) | ep007 canopy fills frame | **0.0274** | ep015 grass+hut, distant trees | 0.0027 |
| | ep012 canopy tunnel | **0.0171** | ep016 open grass, distant tree line | 0.0037 |
| | | | ep033 grass, no tree | 0.0017 |
| | | | ep037 open grass, distant tree line | 0.0064 |
| Obtain real spawn (attempt #9) | forest clearing, close trees | 0.0060 | open grassland | **0.0190** |
| | dense jungle, close trees | 0.0057 | open grassland | **0.0179** |
| | | | beach, no tree | 0.0130 |
| | | | dark cave, no tree | 0.0069 |
| Obtain coverage (true env resets) | trunk fills frame | 0.0030 | open grassland | **0.0176** |
| | dense jungle canopy | 0.0098 | open plains | **0.0146** |

On Treechop, close-canopy frames score **~6x higher** than distant/no-tree frames (0.017-
0.027 vs 0.002-0.007) — reproducing this same chapter's original live calibration
(`flat_threshold` section, "tree/canopy fills view" band 0.02-0.056 vs "lost" band
0.0002-0.002) from a completely independent, offline sample. On both independently
gathered Obtain samples, the direction **reverses**: the closest, most canopy-filling
frames score at or below the Obtain group's low end (0.003-0.010), while open,
tree-absent grassland/plains frames reach the group's high end (0.013-0.019) — matching
or exceeding Treechop's own "tree visible" band despite showing no tree at all.

**VERDICT: hypothesis CONFIRMED, in a sharper and more specific form than the "goes flat"
framing every prior attempt (#1-#9) assumed.**

> **LESSON: the failure is not a magnitude collapse (RND's failure mode, chapter 09) — it
> is a directional confound in `ebwm.pt`'s own native, untrained raw-latent scoring.** On
> `MineRLObtainIronPickaxeDense`'s free-spawn visual distribution, the goal-centroid
> distance is still measurably discriminating something (the aggregate spread is not
> flatter than Treechop's) — it just is not tree-proximity, and in every frame pair
> checked here it points the WRONG way: closer trees score as less promising than open,
> treeless scenes. This is the same "a confidently-wrong signal is worse than an honestly
> flat one" pattern attempt #7 diagnosed for a *trained add-on* distance projector
> (there, a lighting/day-night confound) — now shown to hold for the mechanism every
> attempt from #1 onward built the MPC scoring around and never tested in isolation until
> now. It closes attempt #9's "flagged as a hypothesis pushed forward by elimination, not
> a confirmed finding" note with a direct answer: yes, and the mechanism is a directional
> confound, not a collapse.

No checkpoint touched (`ebwm.pt` read-only throughout, both in this diagnostic and
carried over from every prior attempt). Full per-frame CSV and a boxplot comparing the
three groups: `assets/diagnostics/score_generalization.csv`,
`assets/diagnostics/score_generalization.png`. This is a diagnostic, not a fix, per the
dispatch's own scope — no planner or scoring change was made as a result.

**Next, if pursued**: the standing wall is now confirmed from two independent angles —
attempts #4-#9 (action generation, exhaustively varied, never moved the outcome) and
attempt #10 (the score itself, direct test, confirmed wrong-axis on Obtain) — which
argues for an encoder/scoring-side fix trained WITH genuine Obtain-spawn supervision
(near/far pairs collected on `MineRLObtainIronPickaxeDense` itself, not Treechop-only,
under the project's own anti-collapse discipline) rather than another
action-generation-side patch layered on a scoring mechanism now shown to point the wrong
way on this specific distribution.

*Previous: `docs/09_curiosity_coldstart.md`; commit_length through the BC actor
confirmation batch (attempts #4-#9), each ruling out a different action-generation-side
explanation without moving the outcome. Current: attempt #10, the first DIRECT offline
test of `ebwm.pt`'s own scoring under the Obtain distribution — hypothesis confirmed, and
sharper than assumed (a directional confound, not a flattening). Next: a scoring/encoder
fix trained with real Obtain-distribution supervision, not another search/generation-side
patch.

## Cold-start campaign status after attempt #10 — paused, four candidate directions on the table

Attempt #10 left the campaign with two independent, confirmed findings: (a) action-generation
quality is not the bottleneck (attempts #4-#9: three mechanistically different fixes — hand-
authored macros, real CEM, a trained BC actor — all failed to move the outcome, including on
demonstrably viable spawns with trees visible); (b) `ebwm.pt`'s own native goal-centroid scoring,
the mechanism every attempt was built around, **actively reverses direction** on
`MineRLObtainIronPickaxeDense`'s spawn distribution — closer trees score LOWER than open/treeless
views, the opposite of its behaviour on Treechop. Four candidate directions were ranked by
cost/risk, none pulled at the time:

1. **Targeted Obtain-domain score correction** — cheapest, most directly targeted: a small trained
   adapter/distance head with genuine near/far supervision collected FROM Obtain itself.
2. **Topological/episodic frontier memory** — a visited-state map driving the planner toward
   frontier sub-goals, contingent on NOT reusing the same broken centroid-distance metric to judge
   "how close am I to a frontier point."
3. **H-JEPA — hierarchical world model** — highest cost/risk, deprioritised pending cheaper options.
4. **BC fine-tuning on human search footage** — deprioritised (attempt #9 already showed better
   proposals don't help when the evaluator scores them backwards).

Attempts #11 and #12 below are the first two of these four, taken in priority order.

## Cold-start attempt #11 (PC, 2026-07-21) — candidate direction 1, Obtain-domain score
correction: NO-GO, third and sharpest confirmation of a frozen-encoder brightness shortcut

Attempt #10 pinpointed exactly what was broken in `ebwm.pt`'s native scoring (direction, not
magnitude) and on which distribution (Obtain, not Treechop) — candidate direction 1 turns that
into a precisely-scoped experiment: retrain the attempt #7 distance-projector idea, but with
near/far supervision sourced **entirely from Obtain**, not Treechop+coverage.

**Implementation.** `scripts/train_value_projector_obtain.py`: near/far pairs drawn from the 40
real `MineRLObtainIronPickaxe-v0` expert demos plus the attempt #3 coverage episodes — zero
Treechop data anywhere in training. A genuinely new mandatory gate was added on top of the usual
offline separation check: a hand-labeled, held-out real-frame direction check (attempt #7 never
had the means to run this — its offline gate only ever validated same-distribution near/far pairs,
never a human-eyeballed tree-close-vs-not judgment).

**Offline gates looked like the best result yet:**

| Metric | Attempt #7 (Treechop+coverage) | Attempt #11 (Obtain-only) |
|---|---|---|
| Separation ratio | 7.9 | **11.26** |
| Obtain-direction ratio | — (not measured this way) | **1.21** |
| Pairwise correct-direction (hand-labeled) | — (gate didn't exist) | **21/24 (87.5%)** |

This was the first distance metric in the campaign to apparently get tree-proximity right on
Obtain frames at all — on the numbers alone, a clean pass.

**The brightness confound, checked, is worse than every prior variant:**

| Variant | Brightness correlation |
|---|---|
| Attempt #7, original (Treechop+coverage) | 0.117 |
| Attempt #7, live play | -0.57 |
| ColorJitter-"repaired" (attempt #8 follow-up) | 0.498 |
| **Attempt #11, Obtain-domain sourcing** | **0.643** |

**The developer went one step further than the dispatch brief asked, and that step is what
actually closes this attempt.** Rather than stopping at "the offline gate passed, the confound
number is high but the direction check passed," the apparent 87.5% correct-direction result was
itself checked for whether it was brightness in disguise: `corr(is_tree_close, brightness) =
-0.917` on the hand-labeled gate-2 set — the "tree-close" frames (forest/jungle) were
systematically much darker than the "no-tree" frames (grassland/beach) **by construction** of how
the hand-labeled set was assembled. The apparent win was very likely the same shortcut
re-detected — brightness happens to correlate almost perfectly with the label in this particular
validation set — not genuine geometric (tree-proximity) learning. Correctly called NO-GO on this
basis; the live sanity play run was deliberately skipped per the attempt's own instructions (no
live eval spent on a self-diagnosed-confounded checkpoint). `checkpoints/value_projector_obtain.pt`
kept, parked, not deployed — the same status as `value_projector_colorjitter.pt`.

> **LESSON, now confirmed three independent ways (attempt #7 original, ColorJitter, and this
> attempt's Obtain-domain sourcing): any small trained head bolted onto `ebwm.pt`'s frozen latent
> space keeps finding brightness as the cheapest available shortcut, regardless of which domain
> supplies the training/validation pairs — because the confound most plausibly lives in the
> frozen encoder's representation itself, which none of these three attempts touched. Changing
> the downstream training data changes the story the projector tells about itself, not the
> shortcut it actually uses.**

Candidate direction 1 is now closed unless revisited as an encoder-side fix (an adapter fine-tune
or an explicit brightness-invariance constraint on `ebwm.pt` itself, under the project's strict
anti-collapse guardrails) — out of scope for a downstream-only patch. No checkpoint touched except
the new, separate `checkpoints/value_projector_obtain.pt` (`ebwm.pt`, `craft_wm_v4.pt` read-only
throughout).

*Previous: `docs/09_curiosity_coldstart.md`; commit_length through the offline scoring diagnostic
(attempts #4-#10). Current: attempt #11, candidate direction 1 — NO-GO, the third and sharpest
confirmation that the brightness shortcut lives upstream, in the frozen encoder, not in any
downstream training recipe. Next: candidate direction 2 (attempt #12, below), or an encoder-side
fix to direction 1 if revisited.

## Cold-start attempt #12 (PC, 2026-07-21) — candidate direction 2, topological frontier memory:
built and sanity-verified, awaiting a real confirmation batch

Candidate direction 2 was scoped to sidestep both of the campaign's known coverage-signal failure
modes by construction: RND (attempt #4B) converges on elapsed ticks, not scene content; any
frontier metric built on `ebwm.pt`'s latent distance would inherit attempt #10's confirmed
backwards-direction confound. The fix: a coverage signal with **no learned function and no
frozen-encoder dependency** at all.

**Implementation.** `mine_jepa/ebwm/frontier.py`'s `FrontierTracker`: a pure dead-reckoned
`(x, y, yaw)` position, integrated purely from the executed discrete actions' own known semantics
(no learned function, no dependency on `ebwm.pt` or `craft_wm_v4.pt`'s latent space), binned into
a visit-count grid. When triggered, it targets the least-visited nearby heading. Wired as a new
`scan.macro: "frontier"` option (`configs/play_craft_commit4_frontier.yaml`) — `planner.py` itself
is untouched (this is a pure macro, no scoring change), and every other `scan.macro` value stays
byte-identical to before.

**Sanity check, N=3: clean, no crashes.** The mechanism visibly activates and behaves distinctly
from the existing turn/bushwhack macros — confirmed via log: it turns toward the least-visited
heading, then cruises, and `unique_cells_visited` grows across an episode (419 / 939 / 970 across
the three runs). No lock-in (max single-action share 45%, well inside the normal baseline range).
**0/3 successes** — uninformative at this N and not the point of a sanity check.

**A pre-existing gap flagged along the way, not introduced by this dispatch:** `scripts/play_craft.py`
never wires `agent.seed` into the MineRL env for ANY config — `agent.seed: 0` in these YAMLs is
currently a no-op. Standing reproducibility debt across the whole campaign, not specific to
attempt #12, worth fixing before the next batch that needs to claim reproducibility.

**VERDICT: sanity-passed, no verdict on effectiveness yet.** The sanity check's qualitative signal
— clean activation, real coverage growth (unique cells visited climbing across the episode), no
action-concentration lock-in — clears the project's own "don't scale up without a positive signal
first" bar (the same bar attempts #6 and #8's regressions failed to clear before their own
larger batches, which is why those stopped at N=8). A real confirmation batch (N≥15-20, per the
project's own threshold) is warranted and has already been dispatched separately — not part of
this task.

No checkpoint touched (`ebwm.pt`, `craft_wm_v4.pt` read-only; `frontier.py` has no learned
parameters to touch). `configs/play_craft_commit4.yaml` (`scan.macro` unset) is unchanged;
`configs/play_craft_commit4_frontier.yaml` is a new, separate comparison config.

**Confirmation batch, N=20 (PC, 2026-07-21) — the real result.** Seed nominally 0 (subject to
the unwired-seed caveat noted above): **1/20 logs chopped + planks crafted (5.0%), mean reward
0.45 (+12% vs. MineRL's ~0.4 random baseline)**. This is the second non-zero result in the
entire cold-start campaign — after `commit_length=4` alone's pooled 3/31 (9.7%) — and the first
to come from a mechanism entirely outside action-generation/scoring (pure coverage-driven
search, no learned function, no encoder dependency). The one success: reward=9, +4 planks,
`unique_cells_visited=908` (among the highest in the batch), action profile a14=42% — healthy,
not a lock-in spike. Across all 20 episodes, action concentration stayed normal throughout (max
single-action share 63%, most episodes 20-45%): **no lock-in anywhere in this batch**, a direct
contrast with attempts #6 and #8's lock-in pathology (CEM's elite-refit and action-pool priming
both regressed toward concentrated, spinning action profiles; this mechanism did not).

**Framing, honestly.** 1/20 (5%) is the same order of magnitude as the 9.7% baseline, not a
statistically proven improvement at this N (a Fisher exact test would not distinguish the two)
— but it is clearly ahead of attempts #8 and #9's 0/8 each, and it is notable for producing a
real success with zero behavioural pathology, making it the second independent mechanism (after
`commit_length`) to do so. Not a confirmed breakthrough; a genuine positive data point worth
keeping and building on rather than shelving.

One process note on this batch: the tester dispatch that ran it hit an infrastructure
session-limit error before it could write its own formal report. The numbers above were
independently verified directly from the raw log by a separate process, not taken from that
report.

*Previous: `docs/09_curiosity_coldstart.md`; commit_length through the offline scoring diagnostic
(attempts #4-#10); attempt #11, candidate direction 1 (NO-GO, brightness confound). Current:
attempt #12, candidate direction 2 — built, sanity-verified at N=3, and now confirmed at N=20:
1/20 (5.0%) success, mean reward 0.45, no lock-in anywhere in the batch — the second non-zero,
non-pathological result in the campaign. Same order of magnitude as the `commit_length=4`
baseline (9.7%), not a proven improvement at this N, but a genuine positive data point. Next:
build on this mechanism (larger N, or combine with `commit_length`/other non-pathological
levers) rather than shelving it.

### Free diagnostic on attempt #12's batch — drowning confirmed as the dominant early-termination cause

Read-only follow-up, no new run: each early-terminated episode's per-episode Malmo client log
(`logs/mc_*.log`, one per `play_minerl_multi.py` subprocess) was correlated against the master
attempt #12 batch log by file timestamp, then grepped for death messages.

**12 of the ~20 episodes' Malmo logs contain an explicit `MineRLAgent0 drowned` server
message** — independently re-verified directly against the raw logs, not just taken from the
batch's own summary output. Sampled files show the drown message immediately preceding the
episode's final lines, i.e. a genuine episode-ending death, not a transient damage tick the
agent shrugged off. The remaining episodes that ran the full 3000-step cap show **no** drown
message at all — a clean, bimodal split, not a fuzzy trend.

**Consequence for reading the 5.0% headline number.** On the subset of episodes that survived
long enough to search fairly (i.e. weren't cut short by drowning), the success rate looks
meaningfully different from the raw 1/20 — closer to 1-in-7-8, not 1-in-20. Both framings are
honest: the raw 1/20 is the real deployed number, but attributing the whole gap to a
search/approach deficiency would be wrong — a large share of it is a spawn-hazard problem the
frontier mechanism's own design explicitly left unhandled (no collision/hazard awareness in
heading selection, an acknowledged limitation of attempt #12 itself, not a new finding about it).

**Concrete, motivated next fix**: hazard-awareness in the frontier heading selection, or a
simple "currently taking drown damage → swim toward dry land" reflex, before spending more
effort on search/coverage refinements — this diagnostic makes the target precise instead of
speculative. This directly motivates attempt #13, below.

## Cold-start attempt #13 (PC, 2026-07-21) — hazard-awareness for the frontier scan macro:
drowning genuinely fixed after three rounds, chopping itself unaffected

The free diagnostic above pinned 12/20 of attempt #12's early terminations on drowning, not on
a search/approach failure. Attempt #13 builds a hazard-detection-and-escape reflex on top of
the frontier scan macro (`scan.macro: "frontier"`) to address that specific failure mode,
config-gated (`hazard_avoidance:` block, `configs/play_craft_commit4_hazard.yaml`) and additive
— it does not touch `commit_length`, sticky sampling, or the frontier tracker's own coverage
logic.

**Detector: a calibrated pixel heuristic, not a proxy for a real observable.** No
health/breath/air value exists anywhere in `MineRLObtainIronPickaxeDense-v0`'s observation
space (checked against `minerl.herobraine.env_specs.obtain_specs.Obtain` directly, not assumed)
— there is nothing for `detect_underwater()` (`mine_jepa/ebwm/hazard.py`) to read off cleanly,
so it works from the raw POV frame instead. An initial version used absolute RGB thresholds and
caught a real daytime drowning but missed a real night one; it was replaced with
lighting-invariant ratios (`ratio = B / max(R, G)`, `rel_rg = |R - G| / max(R, G)`), re-validated
on ~5900 pooled frames plus both real drowning events: **zero false positives, ~100% catch rate
in daylight, ~81% at night** (the missed 19% are near-black frames where all three channels
collapse together — an inherent limit of a pixel heuristic in the dark, not a tuning gap).

**Round 1 — blind escape (alternating jump + fixed retreat direction), N=5.** Three episodes ran
full-length with the hazard mechanism never triggering (chopping was not the point of this
check). One death (step 750) occurred with the hazard never firing at all — confirming it was
an *unrelated* death class (fall/mob/lava), not a false negative on a real drowning. **One
episode (died step 922) is the informative one: the detector fired continuously for 260+
ticks — correctly identifying the hazard — but the blind escape motor pattern (alternate jump
+ fixed-direction retreat) never got the agent back to dry land, and the episode still ended in
death.** Detector correct, escape action insufficient.

**Round 2 — steered escape (turn toward the last-known-dry `FrontierTracker` position), N=6 —
WORSE, with two specific bugs identified, not just "still doesn't work."**
`logs/coldstart_attempt13_hazard_steered_n6.log`: **4/6 died**, and critically, **all 4 died
while the escape reflex was actively engaged** (`died_during_escape=True` on every one,
independently cross-checked against 4 real `MineRLAgent0 drowned` messages in the raw Malmo
logs) — a worse ratio than round 1's single drowning death out of two early deaths. The
mechanism was genuinely wired correctly (a real dry position is recorded, a real bearing is
computed, turn-then-forward switching happens as designed, jump is interleaved throughout), and
one episode showed real measurable progress — distance to the remembered dry point shrank from
over 50 units to ~5.6 before death, something the blind round-1 retreat could structurally never
do — it simply wasn't fast enough. Two distinct root causes were found for the rest, from
reading the actual per-replan trace, not inferred:
1. **Turn/alignment granularity mismatch.** Each replan's turn action covers roughly 80° (a
   `commit_length`-sized block executed at ~10°/tick) while the alignment window
   (`align_deg`) was only 20° — the turn structurally overshoots the alignment window on
   almost every replan, so the heading delta flips sign and the agent ping-pongs between two
   headings ~80-100° apart. Seen directly in the trace: -52.2°/+27.8° over 18 replans in one
   episode, +20.0°/-60.0° over 11 replans in another — a bang-bang hunting bug, never settling
   into "forward" long enough to close distance, not a conceptual failure of "steer toward dry
   land."
2. **Anchor corruption.** The remembered dry position occasionally jumped to a point
   immediately next to the agent's own still-submerged position, rather than staying a stable,
   distant point — most plausibly a single-tick false "not underwater" reading (a surface wave
   or lighting artifact at the water's edge) corrupting the memory, not staleness of an
   otherwise-good anchor.

**Round 3 — widened `align_deg` + debounced dry-anchor (require two consecutive dry readings
before updating memory), N=6 — GO, drowning genuinely fixed at this N.**
`logs/coldstart_attempt13_hazard_fixed_n6.log`: **6/6 episodes survived the full 3000 steps,
zero deaths** — versus 3/5 and 2/6 survival in the two prior rounds. The hazard fired heavily
and repeatedly across the batch (7/4/0/5/11/9 triggers per episode, 36 triggers total) and
resolved every single one, not just the easy cases. The trace directly confirms the oscillation
is gone: turn deltas now shrink monotonically in one direction
(e.g. -180°→-100°→...→0°/"forward") instead of ping-ponging between two far-apart headings as
in round 2. This does **not** fix chopping or crafting itself (0 planks across the batch, a
separate axis from drowning) but it resolves the specific spawn-hazard/drowning failure mode
the free diagnostic identified in attempt #12 (12/20 drowned in that batch). N=6 with 36 real
trigger events and zero failures is a stronger signal than this campaign's usual small-N
noise — a real confirmation batch (N≥15-20) would be justified if this line of work continued,
unlike every earlier hazard round — but it was not run; the user chose to move on rather than
spend more time confirming at scale.

> **LESSON: the same shape as attempt #5, now for a hazard reflex instead of a search
> macro — a correctly-calibrated detector is not itself a fix if the action it dispatches
> doesn't resolve the situation it detects.** Round 1's blind escape had no sense of *which
> way* was land, only "am I currently wet," and that alone was not enough even with 260+ ticks
> of continuous, correctly-fired detection. Round 2's fix (steer toward a remembered dry point)
> was the right idea but initially made things WORSE due to two independent implementation bugs
> (a granularity mismatch causing oscillation, and a corruptible anchor) that looked, from
> outside, exactly like "the idea doesn't work" — indistinguishable from a conceptual failure
> until the actual per-replan trace was read. Only round 3, after both bugs were fixed, showed
> the underlying idea was sound: 6/6 survival with 36 real trigger-and-resolve events.

**Process note.** The dispatching agent for this attempt was interrupted mid-write-up and
delivered no formal conclusion; the numbers above were independently re-verified directly from
`logs/coldstart_attempt13_hazard_sanity.log`, `logs/coldstart_attempt13_hazard_steered_n6.log`,
`logs/coldstart_attempt13_hazard_fixed_n6.log`, and the GIF
(`assets/agent_play_craft_commit4_hazard.gif`), not taken from that agent's own summary.
`hazard_avoidance: false` (default) is structurally guarded — every new code path in
`mine_jepa/ebwm/hazard.py` and `scripts/play_craft.py` is wrapped in `if hazard_enabled:` — but
was not re-confirmed with a dedicated disabled-vs-baseline bit-for-bit run in this attempt, a
gap worth closing before this mechanism is relied on further.

No checkpoint touched (`ebwm.pt`, `craft_wm_v4.pt` read-only throughout; the hazard detector and
escape reflex have no learned parameters). `configs/play_craft_commit4_frontier.yaml`
(`hazard_avoidance` unset) is unchanged; `configs/play_craft_commit4_hazard.yaml` is a new,
separate comparison config.

*Previous: `docs/09_curiosity_coldstart.md`; commit_length through candidate direction 2's
confirmed 1/20 success (attempts #4-#12), plus the free diagnostic pinning 12/20 of that
batch's early terminations on drowning. Current: attempt #13, hazard-awareness for the frontier
scan macro — three rounds (blind escape inconclusive/negative at N=5; steered escape WORSE at
N=6 with two identified implementation bugs; widened-alignment + debounced-anchor fix GO at
N=6, 6/6 survival, 36/36 hazard triggers resolved) — drowning is now a solved sub-problem at
this N, chopping/crafting itself unaffected and unconfirmed at a larger scale. Next: attempt
#14, below, tests a different branch of the campaign (H-JEPA reconsidered) rather than scaling
up the hazard-avoidance confirmation batch, per the user's own choice to move on.

## Cold-start attempt #14 (PC, 2026-07-22) — H-JEPA reconsidered: a cheaper Occam's-razor test
first (CLIP zero-shot, then a direct `ebwm.pt` fine-tune) — MIXED, leaning NO-GO

**Motivation: an external review before any code was written.** An Explorer proposal for
literal H-JEPA (a second, slower hierarchical world model, candidate direction 3 from the
post-attempt-#10 menu) was reviewed externally before implementation began. The review's key
point: across 13 attempts, `ebwm.pt` itself has **never been retrained or fine-tuned** — every
earlier fix (attempts #7, the attempt #8 follow-up, #11) trained a small head ON TOP of its
frozen latents, never applied augmentation to the encoder's own pretraining. So "the confound
lives in the frozen encoder" (the working assumption since attempt #11) was an untested
inference, not a confirmed fact — and per Occam's razor, retraining `ebwm.pt` itself is cheaper
than building a second hierarchical model, and had not yet been ruled out. The reviewed decision
was to test this cheaper alternative first, in two phases, before committing to H-JEPA.

**Phase 1 — cheap, offline, no training: does an off-the-shelf zero-shot model already get this
right?** `scripts/diagnose_clip_score_generalization.py` runs CLIP (Radford et al.,
arXiv:2103.00020, ViT-B/32) — zero Minecraft-specific training of any kind — over the exact
251-frame set attempt #10 used, asking whether a 400M-image pretrained model already separates
tree-close from no-tree correctly where `ebwm.pt` reverses.

- **Direction gate PASSED**: separation ratio 1.807, above the 1.3 threshold required.
- **Brightness-independence gate FAILED badly**: r = -0.947 on the hand-labeled set, r = -0.74
  across the full 251-frame population — **including on Treechop's own home distribution**,
  where `ebwm.pt`'s native score already works correctly. A model with no Minecraft-specific
  training at all, trained on 400M general images, shows the same brightness shortcut, and a
  worse one than every prior variant in this campaign (0.117 → 0.498 → 0.643 → 0.947 across
  attempts #7 → ColorJitter → #11 → this one).
- **A nuance that keeps the causal story open, flagged rather than resolved**: a dark cave frame
  (no tree) scored similarly to bright open scenes (also no tree) rather than like a dark
  forest would — pure brightness alone cannot fully explain that pairing, so something beyond
  raw luminance is still involved. Any causal story about *why* `ebwm.pt` specifically reverses
  on Obtain is flagged as an unverified hypothesis here, not asserted as confirmed fact.

**Decision: proceed to Phase 2 anyway.** Phase 1's result is a mixed gate outcome (direction
passed, brightness failed), not a clean pass or fail — but per the reviewed decision rule this
does not itself block Phase 2, because Phase 2's own acceptance gate was never the
brightness-decorrelation target (that was only ever Phase 1's cheap CLIP-specific check). Phase
2's corrected gate is: does attempt #10's actual diagnostic reversal go away on real Obtain
frames, checked directly against the fine-tuned checkpoint — not a brightness-correlation
number.

**Phase 2 — fine-tune `ebwm.pt` itself, resumed from its own weights.** Same architecture
(embed_dim=64, 664K params), low LR (3e-5), 5 epochs — deliberately honoring the Phase 4
T=8/20-epoch-sweet-spot lesson (never select by loss/ratio alone), on Treechop demos + the 40
Obtain expert demos (`data/minerl_craft`) + attempt #3's coverage episodes
(`data/minerl_coverage`) merged, with Obtain data oversampled ~4x, and per-window (not
per-frame) photometric augmentation applied to the encoder's own training for the first time in
the campaign. One technical catch handled correctly: the coverage data was collected with a
22-action random policy, but `ebwm.pt` has only 17 action slots — windows touching action
indices ≥17 were **filtered out, not remapped**, to avoid silently mislabeling actions.
`batch_var` stayed healthy (1.15-1.17) every epoch — no collapse — and the prediction ratio
barely moved (0.9265 → 0.946-0.951 across epochs), exactly as intended for a low-LR nudge rather
than a full retrain.

**The real gate — re-running attempt #10's diagnostic against all 5 epoch snapshots — MIXED,
not a clean pass.** Excluding one dark/underwater cave frame, the reversal is genuinely fixed
in every one of the 5 epochs checked: tree-close frames beat open/no-tree frames by 2.1-4.6x,
versus the unmodified baseline's inverted 0.58x (tree-close scoring lower). **But including that
one dark frame flips the ratio back below 1 in every epoch**, because that specific frame's
score got *worse* after fine-tuning (0.0130 → 0.025-0.031) — a new brightness-linked anomaly, in
a different place, but the same family as attempts #7's and #11's confound. No checkpoint was
promoted to the unsuffixed `checkpoints/ebwm.pt` name; the 5 epoch snapshots
(`checkpoints/ebwm_v2_treechop_obtain_aug_epoch{1..5}.pt`) are kept as comparison-only artifacts.
No Treechop sanity batch and no cold-start live batch was run, correctly withheld per this
attempt's own contingency rule (only proceed to live testing on a clear pass) — the gate did not
clearly pass. `ebwm.pt` itself was confirmed untouched throughout (a pre-fine-tune backup,
`checkpoints/ebwm_backup_20260722.pt`, confirmed md5-identical beforehand). One self-flagged
gap: Treechop's own close-canopy-vs-distant paired direction was not independently re-verified
post-fine-tune (only bulk score-distribution statistics were checked, and those stayed
healthy) — neither confirmed fine nor confirmed broken on Treechop specifically.

> **LESSON: this is now the 4th independent confirmation of a brightness-linked confound, via
> four completely different mechanisms** — a small head trained on frozen latents (attempt #7),
> the same kind of head with Obtain-domain-sourced training data (attempt #11), an off-the-shelf
> 400M-image model this project never trained or touched (this attempt's Phase 1, CLIP), and
> now direct retraining of the encoder itself with real photometric augmentation on its own
> pretraining (this attempt's Phase 2) — the most direct attack on the problem attempted so
> far, and it still produced a *new* anomaly on a low-light frame instead of a clean fix. This
> substantially weakens "the encoder just needs more diverse/augmented training data" as a
> sufficient standalone fix — the pattern looks broader and more stubborn than a training-data
> gap that more data or augmentation alone can close.

**VERDICT: MIXED, leaning NO-GO — but a genuinely informative one, not a shrug.** Phase 1
(CLIP) shows the shortcut is not specific to `ebwm.pt`'s own small training set; Phase 2 shows
direct, careful encoder fine-tuning (the cheapest remaining lever per Occam's razor, and the
one thing 13 prior attempts had never actually tried) still lands on a mixed result rather than
a clean win. Per the Explorer's own proposal, which explicitly named "the cheaper fine-tune
attempt fails or produces a mixed result" as its own condition for revisiting H-JEPA, that
condition is now met with a real, executed result — not a hypothetical one. Candidate direction
3 (H-JEPA) is therefore the better-justified next step of the four from the post-attempt-#10
menu, though the decision to actually pursue it had not been made at the time of writing.

No checkpoint touched destructively (`ebwm.pt` untouched, backup md5-verified;
`ebwm_v2_treechop_obtain_aug_epoch{1..5}.pt` are new, separate comparison files; `craft_wm_v4.pt`
not involved in this attempt at all).

*Previous: `docs/09_curiosity_coldstart.md`; commit_length through the hazard-avoidance fix
(attempts #4-#13), including candidate direction 1's closure (attempt #11, brightness confound)
and candidate direction 2's confirmed non-zero success (attempt #12). Current: attempt #14,
the cheaper Occam's-razor alternative to H-JEPA — Phase 1 (CLIP zero-shot) shows the brightness
shortcut is not specific to this project's own training data; Phase 2 (direct `ebwm.pt`
fine-tune with real photometric augmentation) genuinely fixes the attempt #10 reversal on 4 of
5 test frames but relocates the same brightness-linked confound to a 5th, dark frame — MIXED,
leaning NO-GO, the 4th independent confirmation of the confound. Of the four post-attempt-#10
candidate directions: #1 is closed (attempt #11), #2 has the campaign's only two non-zero
chopping successes plus attempt #13's hazard-avoidance fix, #3 (H-JEPA) is now the
better-justified next direction per the Explorer's own stated condition for revisiting it
(not yet actioned), and #4 (BC fine-tuning) remains deprioritized.

## Cold-start attempt #15 (PC, 2026-07-22) — H-JEPA proposal reassessed with all new evidence,
plus one narrower idea tested directly: ratio-normalized chromaticity per spatial tile — a 5th
confirmation that closes the "smarter feature engineering" line of inquiry

Attempt #14 left candidate direction 3 (H-JEPA) as the better-justified next step per the
Explorer's own stated condition. Before committing engineering effort to it, a reassessment
pass reconsidered the whole post-attempt-#10 menu with all evidence gathered since, including
one narrower, cheaper idea the H-JEPA proposal itself had raised in passing.

**Reassessment, read-only, no code written.** Given that CLIP (Radford et al., arXiv:2103.00020)
— a 400M-image model built and pretrained specifically to be robust to photometric variation —
had already failed the exact same dual gate (direction + brightness-independence) a hand-rolled
hue/edge heuristic would face, building that heuristic was judged very likely to just be a 5th
confirmation of the same confound at real engineering cost, not new information. **Recommendation:
do not build the hand-rolled visual heuristic.** The reassessment also recommended that the
campaign's only two working, non-visual-scoring mechanisms — `FrontierTracker` coverage and
`commit_length` — are the better-justified place to invest next, rather than grafting still more
visual content bias onto them.

**One narrower, cheaper idea from the reassessment WAS tested directly**, because it was cheap
enough to check before ruling out the whole feature-engineering line: does
`mine_jepa/ebwm/hazard.py`'s proven trick — lighting-invariant channel RATIOS rather than raw
RGB values, which works for detecting water because underwater tint is a uniform frame-global
cast — also work for foliage if computed **per spatial tile** instead of over the whole frame at
once? A per-tile ratio could in principle pick out a patch of green canopy against a bright sky
the same way the whole-frame version picks out a uniform blue-tinted underwater frame.
`scripts/diagnose_chroma_tile_generalization.py` tests this over the same 251-frame set and
hand-labeled ground truth every prior diagnostic in this campaign has used.

**Result: MIXED, but the brightness gate failed almost as badly as CLIP's worst case.**

| Gate | Threshold | Result |
|---|---|---|
| Direction (separation ratio) | ≥ 1.3 | **PASSED — 1.482** |
| Brightness-independence, labeled set | low \|r\| | **FAILED — r = -0.925** |
| Brightness-independence, full population | low \|r\| | **FAILED — r = -0.585** (treechop -0.748, obtain_spawn -0.600, obtain_coverage -0.671) |

The labeled-set brightness correlation (-0.925) is essentially tied with CLIP's worst-in-campaign
result (-0.947, opposite sign) — this is not a marginal failure, it is close to the ceiling of how
bad the confound has looked anywhere in this campaign. Critically, the full-population failure
(-0.585) is not confined to the small hand-labeled subset — it holds broadly, including within
each of the three separately-sampled frame sources individually.

> **LESSON — the sharpest interpretation yet of why this keeps happening**: ratio-normalization
> removes GLOBAL brightness scaling exactly as designed, which is why it works for water (a
> uniform frame-wide tint is precisely the kind of variation a ratio cancels). But it cannot
> remove a COMPOSITIONAL confound, where the ground-truth labels themselves correlate scene
> type with brightness — dark forests versus bright open fields is the actual scene composition
> of this domain, not an artifact of any one scoring mechanism's math. **This means the
> brightness confound is not fixable by ANY purely photometric single-frame feature — learned,
> off-the-shelf, or hand-designed to be lighting-invariant — without additional structure
> (multiple frames, spatial/geometric reasoning, or a different modality entirely).** This closes
> the "maybe a cleverer feature trick fixes it" line of inquiry definitively, for a stronger
> reason than attempt #14 left it: not just "every mechanism tried so far has failed" but "the
> class of purely photometric single-frame features cannot succeed here by construction of the
> domain's own scene composition."

No checkpoint touched — this is a pure offline read-only diagnostic (`ebwm.pt`, `craft_wm_v4.pt`
never loaded). Candidate direction 1 (encoder/scoring correction) stays closed, now for a
structurally stronger reason than before attempt #15.

*Previous: `docs/09_curiosity_coldstart.md`; commit_length through attempt #14's mixed
encoder-fine-tune result. Current: attempt #15 — the H-JEPA proposal reassessed and the
hand-rolled heuristic it suggested was judged not worth building; the one cheaper narrower idea
(per-tile ratio-normalized chromaticity) it did motivate was tested directly and failed the
brightness gate almost as badly as CLIP, the 5th independent confirmation of the confound and
the first to pin down WHY purely photometric single-frame features cannot fix it (a compositional,
not a magnitude, confound). Next: a real confirmation batch of the frontier+hazard combination
(below), then attempt #16, candidate direction 3's first concrete probe.

## Confirmation batch (PC, 2026-07-22) — frontier + hazard combined at N=20, measuring real chop
rate for the first time on this combination: drowning fix holds at scale, chopping still 0/20

Attempts #12 and #13 individually validated coverage-driven search (frontier, 1/20 at N=20) and
drowning avoidance (hazard, 6/6 survival at N=6) separately. This batch runs both together
(`configs/play_craft_commit4_hazard.yaml`, frontier search plus the final, round-3 fixed
hazard-avoidance from attempt #13) at N=20, the first time the combination is measured at the
project's own confirmation-batch scale rather than a small sanity check.

**Process note, corrected after independent verification.** The Tester's own report on this
batch claimed a "hard infrastructure failure" halting the run at episode 4. This was **wrong**:
`play_minerl_multi.py` launches one Java/Malmo process per episode by design, so one episode's
transient Malmo state-machine error does not kill the orchestrator, which simply moves on to the
next episode. The raw log shows the batch ran all 20 episodes end-to-end (`FINAL RESULTS —
20/20 episodes succeeded`) with no intervention required. **Lesson: a per-episode error in this
harness is not the same as a batch-level failure — confirm the orchestrator process's own exit
status before declaring a hard stop**, not just the presence of an error message in the stream.

**Drowning: fixed, and holds at scale.** 3/20 (15%) drowned, confirmed via real `MineRLAgent0
drowned` Malmo server messages — down from attempt #12's original, un-hazard-protected 12/20
(60%) baseline. **The attempt #13 fix generalizes from the N=6 it was confirmed at to a real
N=20 confirmation batch, not just the small sample it was built on.** Other early terminations
(unrelated causes — fall/mob/etc., out of scope for this fix): 5/20 (25%). Full-length "fair
shot" episodes: 12/20 (60%), up from roughly 8/20 (40%) in attempt #12's original batch.

**Chopping/crafting: 0/20 logs, 0/20 planks** — despite more episodes getting a fair, undrowned
shot at searching, no chops occurred in this batch (versus attempt #12's 1/20). This is not a
significant regression at this N (a Fisher exact test would not distinguish 0/20 from 1/20) — it
is this campaign's usual small-N variance. **It does confirm the standing diagnosis again**:
removing the drowning confound increases the number of episodes that get a fair search
opportunity, but does not by itself convert into chopping — survival and search/approach
effectiveness remain separate problems, with diminishing returns from improving coverage/survival
alone.

**A `reward=144.000` anomaly from this line of work, investigated and not reproduced.**
`scripts/play_craft.py` gained an optional `logging.full_inventory` diagnostic (config-gated,
default off, bit-for-bit unchanged when unset) that tracks and prints the max value of EVERY
inventory key per episode, not just log/planks, specifically to chase down an anomalous
reward=144 reading that had appeared once in this line of work with no wood ever recorded. A
fresh N=12 batch with the diagnostic enabled (same config) showed: reward=0.000 on all 12
episodes, and the **only** inventory item ever non-zero across the entire batch was `dirt`
(1-30 per episode, picked up incidentally while walking/attacking). Dirt is **not** in the
reward table (`RewardForPossessingItem` covers only log, planks, stick, crafting_table,
wooden_pickaxe, cobblestone, furnace, stone_pickaxe, iron_ore, iron_ingot, iron_pickaxe) — it
earns zero reward and is a red herring for the original mystery, not an explanation of it. The
original anomalous episode's process had already exited before this diagnostic existed, so its
exact internal state is unrecoverable — the mechanism that produced 144 did not recur across 12
fresh attempts and remains a one-off, uncharacterized event. It does not affect any campaign
conclusion (the chop rate is what matters, and this is orthogonal to it) — parked as a documented
curiosity, not pursued further absent a much larger sample that reproduces it.

No checkpoint touched (`ebwm.pt`, `craft_wm_v4.pt` read-only throughout; frontier and hazard
have no learned parameters). `configs/play_craft_commit4_hazard.yaml` is the same config attempt
#13 introduced, unchanged.

*Previous: `docs/09_curiosity_coldstart.md`; commit_length through attempt #15's closure of the
feature-engineering line. Current: the frontier+hazard combination confirmed at real N=20 scale
— drowning down from 60% to 15% (the attempt #13 fix generalizes), fair-shot episodes up from
~40% to 60%, chopping unchanged at effectively zero (0/20 vs. attempt #12's 1/20, not a
significant difference) — diminishing returns from coverage/survival improvements alone,
motivating a different kind of mechanism next. A separate reward=144 anomaly was investigated
and not reproduced, parked as an unexplained one-off. Next: attempt #16, candidate direction 3's
first concrete, non-photometric probe.

## Cold-start attempt #16 (PC, 2026-07-22) — Coverage-Value Predictor (CVP): candidate
direction 3's first mechanism built under the "no single-frame photometric scoring" constraint
— offline aggregate gates encouraging, per-trial trained regressor NO-GO at this sample size

With candidate direction 1 (scoring fixes) closed five-fold by attempt #15 and candidate
direction 2 (coverage/execution alone) showing diminishing returns in the frontier+hazard
confirmation batch above, an Explorer proposal — externally reviewed and refined before
implementation — designed the campaign's first candidate-3-flavoured mechanism: a **Coverage-
Value Predictor (CVP)**, a small learned model that predicts *which direction is worth exploring*
without ever looking at a single raw frame's photometric content, deliberately built to avoid
the exact failure mode that closed direction 1.

**Design.** A small MLP predicts `Δunique_cells` (the exploration payoff `FrontierTracker` would
gain) per candidate heading, from two non-photometric feature families only: classical
per-quadrant frame-DIFFERENCE optical flow (motion, not appearance) and `FrontierTracker`'s own
local visitation histogram (where has this episode already been). This is a genuinely
JEPA-shaped predictor — input state plus candidate action predicting a future outcome — with the
prediction target swapped from pixels to geometry, feeding into the already-validated frontier
scan macro rather than replacing its handoff to the chop planner.

**Instrumentation and data collection.** `scan.frontier.log_transitions` (config-gated, default
off) was added to `scripts/play_craft.py` to record per-trigger transition rows. The first
collection batch (N=12 episodes, 57 rows) hit a real, previously-unnoticed bug:
`FrontierTracker.frontier_heading_deg()`'s tie-break defaults to the smallest heading index, and
because sparse-grid cells are almost always tied at zero visits early in exploration, 54 of 57
triggers "chose" heading 0.0° purely by construction of the tie-break rule, not genuine
preference among headings. This made Gate 1 (dynamic range of the target across headings)
uncertifiable on this data — with 54/57 rows all at the same heading, there was no real spread to
measure. **Fix**: a config-gated `tie_break="random"` option (seeded, default `"first"` verified
unchanged from the prior behaviour), followed by a re-collection (N=14 episodes, 44 rows, with
real diversity — all 12 possible headings represented, 1-7 rows each).

**Offline gates on the re-collected data.**

- **Gate 2 (brightness does not dominate the prediction target) passed on BOTH batches
  independently**: r ≈ 0.10 in each, with opposite signs between the two batches — the most
  reproducible non-confound result anywhere in this campaign's history, and a direct contrast
  with every direction-1 attempt's confound.
- **Gate 1 (dynamic range across headings) improved substantially after the tie-break fix**, but
  rests on small per-heading samples (1-7 rows each) — assessed honestly as "encouraging, not a
  rock-solid confirmation," not inflated into a pass it hadn't fully earned.

**The actual trained model — NO-GO, and thoroughly checked, not just a tuning failure.**
Combining both CSVs (~101 rows total), a small MLP (~1.9K parameters) was trained with mandatory
5-fold cross-validation against a trivial "always predict the mean" baseline.

| Configuration | MAE | vs. baseline |
|---|---|---|
| Trivial mean-prediction baseline | 1.169 | — |
| Default MLP | 1.590 | worse |
| Best of an 8-way hyperparameter sweep (smaller nets, heavier regularization) | best ratio 1.06 | still worse |
| Linear Ridge-regression sweep, from scratch | approaches baseline only as regularization forces a near-constant prediction | never surpasses it |

The Ridge sweep in particular rules out "this is just an MLP overfitting artifact" — as
regularization strength increases and the model is forced toward predicting something closer to
a constant, it approaches the trivial baseline's error but never beats it, at any point on the
sweep.

> **LESSON: predicting one specific noisy trial's outcome from four coarse scene-level features
> is a substantially harder task than the aggregate statistics Gates 1-2 checked, and is not
> learnable at N≈100 with this feature set.** This is not evidence that the aggregate signal
> (Gate 2's brightness-independence, in particular) is fake — it is evidence that per-row
> prediction needs substantially more data, likely several hundred rows rather than roughly a
> hundred, to be learnable at all with these features, if it is learnable with them at any
> sample size.

Per the campaign's own honesty discipline, the model was correctly **not** wired into
`scripts/play_craft.py` — no `scan.macro: "learned_frontier"` option was added, and no live
episode was spent testing a model the cross-validation gate had already shown does not work. No
checkpoint was written (`checkpoints/coverage_predictor.pt` does not exist). `ebwm.pt` and
`craft_wm_v4.pt` were untouched throughout.

*Previous: `docs/09_curiosity_coldstart.md`; commit_length through the frontier+hazard N=20
confirmation batch and attempt #15's closure of the feature-engineering line. Current: attempt
#16, candidate direction 3's first concrete, non-photometric probe — real, reproducible aggregate
signal on brightness-independence (Gate 2, twice) and improved but not yet rock-solid dynamic
range (Gate 1), but the actual trained per-trial regressor does not beat a trivial mean-prediction
baseline at any point in an 8-way sweep or a from-scratch linear sanity check — a thoroughly
checked NO-GO, not a tuning artifact, and not deployed. Next: see the campaign status recap below.

## Cold-start campaign status after attempt #16 — sixteen attempts in, three of four candidate
directions assessed, the central chop-planner metric still the one major mechanism never
directly fixed

- **Candidate direction 1 (encoder/scoring correction) is closed, five-fold confirmed.**
  Attempts #7, #11, #14 (both its CLIP and its direct-fine-tune phases), and #15 (ratio-normalized
  chromaticity) each independently hit a brightness/domain-composition confound, via five
  mechanistically different approaches — a small head on frozen latents, the same head sourced
  from Obtain data, an off-the-shelf 400M-image model this project never trained, direct
  retraining of the encoder itself with real photometric augmentation, and a hand-designed
  lighting-invariant per-tile feature. Attempt #15 additionally pinned down *why*: the confound is
  compositional (scene type correlates with brightness in this domain) rather than a magnitude
  artifact of any one scoring mechanism, which no purely photometric single-frame feature can fix
  by construction.
- **Candidate direction 2 (coverage/execution) has the campaign's only real positive results, but
  shows diminishing returns.** `commit_length=4` alone (9.7% pooled), attempt #12's frontier
  search (1/20, no lock-in), and attempt #13's hazard-avoidance fix (drowning 60%→15% at N=6,
  reconfirmed at 60%→15% in the N=20 combined batch above) are all genuine, verified wins on their
  own narrow terms. But layering the hazard fix on top of frontier search — more episodes getting
  a fair, undrowned shot at searching — did not convert into more chopping (0/20 vs. attempt #12's
  1/20): the ceiling on pure coverage/survival improvement without touching search intelligence or
  scoring appears to have been reached.
- **Candidate direction 3 (H-JEPA proper) has had its first concrete probe, not yet a deployable
  mechanism.** Attempt #16 (CVP) tested whether a small non-photometric predictor could learn
  exploration payoff per heading — real aggregate signal on the brightness-independence gate
  (reproduced twice, opposite-signed, the most reproducible non-confound result in the campaign)
  but no learnable per-trial model at N≈100. The door on this direction is not closed the way
  direction 1 is: the failure was a data-scale limitation, not a confound. The next-cheapest step
  if resumed is collecting substantially more transition rows (several hundred) before retraining,
  per the CVP dispatch's own recommendation, rather than a literal hierarchical H-JEPA model from
  scratch.
- **The named-but-still-untouched issue.** Attempt #10 confirmed that `ebwm.pt`'s own
  goal-centroid score — the mechanism still used live by the two-brain chop planner once search
  finds something — reverses direction on Obtain's spawn distribution. Every attempt from #11
  through #16 has worked AROUND this fact (via search mechanisms, hazard avoidance, or coverage
  prediction) rather than fixing it directly. Attempt #15's reassessment explicitly named this as
  "the next branch, not to be silently dropped" once search-side options were exhausted. With
  direction 1 closed and directions 2 and 3 both showing either diminishing returns or an
  unresolved data-scale gap without ever touching it, this is now the single most load-bearing
  unexamined mechanism in the entire campaign. Not yet decided whether or how to attack it
  directly.

## Cold-start attempt #17 (PC, 2026-07-22) — two-pronged direct attack on `ebwm.pt`'s central,
never-fixed goal-centroid score: an OOD-gated fallback (Prong A) and a data-coverage-gap check
(Prong B) — both NO-GO, and together more conclusive than two more failures

Attempt #16 closed with the central issue still untouched: attempt #10's confirmed reversal of
`ebwm.pt`'s own goal-centroid score on Obtain has been worked AROUND by every attempt since
(#11-#16), never fixed or bypassed directly. This attempt takes two independent, cheap shots
directly at it before committing to anything more expensive.

### Prong A — OOD-gated fallback: detect when the score should not be trusted, defer to search

**Idea, orthogonal to "fix the score."** If `ebwm.pt`'s frozen latent can be shown to be
measurably out-of-distribution on an Obtain frame, a later dispatch could fall back to the
already-working `FrontierTracker` coverage search (attempt #12) instead of trusting a compass
attempt #10 proved points backwards there. This needs no gradient training and no loss function
for a downstream head to shortcut through — a meaningful contrast with every trained-head
attempt (#7, #11, #14 Phase 2) that has hit the brightness confound so far.

`scripts/diagnose_ood_gate.py` (config: `configs/diagnose_ood_gate.yaml`) fits a single Gaussian
(mean, covariance) over 4,000 random Treechop frames' pooled `ebwm.pt` latents — Lee et al., "A
Simple Unified Framework for Detecting Out-of-Distribution Samples and Adversarial Attacks,"
arXiv:1807.03888 (NeurIPS 2018), closed-form statistics, no training loop — evaluated at the
exact `vpool` feature `CraftPlannerV4`/`SwitchingCraftPlanner` already compute every replan
(`mine_jepa/ebwm/planner.py`), then flags test frames by their Mahalanobis distance to that fit.
Three gates on the same 251-frame diagnostic set every prior attempt in this campaign has used
(160 Treechop, 11 real Obtain spawn thumbnails, 80 Obtain coverage frames):

| Gate | Threshold | Result |
|---|---|---|
| A — separation (Obtain vs. Treechop mean Mahalanobis distance) | ≥ 1.3x | **FAILED — 1.294x** (missed by a hair; reverified directly from the raw CSV: obtain mean 9.905 vs. treechop mean 7.657, n=91/160) |
| B — specificity (elevated specifically on attempt #10's hand-labeled wrong-direction frames, not uniformly across all of Obtain) | ≥ 1.2x | **FAILED — 1.105x** |
| C — negative control (correlation with raw frame brightness) | \|r\| < 0.3 | **FAILED — r = 0.56** |

Gate A missing by a hair means the detector barely distinguishes "this is Obtain" from "this is
Treechop" at all. Gate B failing more clearly means that even the weak separation it does have
isn't concentrated on the frames where the score is confirmed wrong — it would flag "this is
Obtain," not "this score should not be trusted here," a materially less useful signal for a
fallback dispatch. Gate C is the sharpest result of the three:

> **LESSON: this is the 6th independent confirmation of the brightness/scene-composition
> confound, and the most structurally decisive one yet.** r=0.56 sits squarely inside the range
> every trained-head attempt has landed in (0.117-0.947, attempts #7/#11/#14/#15) — but this
> detector has **no gradient, no loss function, and no way to "learn" a shortcut**: it is a
> plain closed-form Gaussian fit and a distance computation. The fact that it still lands in the
> same confound range shows the shortcut is not something downstream heads learn to exploit — it
> is baked into the raw geometry of `ebwm.pt`'s frozen latent space itself, inherited by any
> statistic built on top of it without retraining the encoder's own objective.

**VERDICT: NO-GO on all three gates.** Not wired into `mine_jepa/ebwm/planner.py` or
`scripts/play_craft.py` — no live batch was spent on a mechanism that failed its own offline
gates. `ebwm.pt` loaded frozen and `requires_grad_(False)`-verified throughout; no checkpoint
touched. Artifacts kept as diagnostics only: `assets/diagnostics/ood_gate.csv`,
`assets/diagnostics/ood_mahalanobis_stats.npz`.

### Prong B — is attempt #14 Phase 2's anomalous frame a data-coverage gap after all?

Attempt #7's original hypothesis — never directly tested until now — was that `ebwm.pt`'s
brightness confound might trace back to a gap in its training data's lighting diversity
(dark/underwater/cave frames underrepresented). Before collecting any new data to test this, a
read-only check: how much of the data actually involved already matches that description?

Using `mine_jepa/ebwm/hazard.py`'s calibrated underwater/cave detector (the lighting-invariant
channel-ratio heuristic validated in attempt #13 — chosen over raw brightness, which turned out
to be a poor discriminator here since Treechop is actually darker on average due to canopy
shade):

- `ebwm.pt`'s **original** Treechop-only training data: only **1.0%** underwater/cave-flagged
  frames — attempt #7's flagged gap was real, for the original model.
- The Obtain-domain data attempt #14 Phase 2 actually fine-tuned on (`data/minerl_craft` +
  `data/minerl_coverage`, ~4x oversampled): **16-22%** such frames, even after oversampling.

The specific anomalous frame from attempt #14 Phase 2 (the one dark cave/underwater frame whose
score got *worse*, 0.0130 → 0.025-0.031, after fine-tuning) was tentatively identified by visual
and numeric match — with one unreconciled discrepancy honestly flagged rather than papered
over — and sits well inside the range of already-present training examples, not as an extreme
outlier the model had never seen anything like.

> **LESSON: the gap that motivated Prong B is already closed for the data actually used in
> attempt #14 Phase 2.** New data collection is not well-supported as the next step for this
> specific anomaly. If the encoder-retraining line is revisited, a reweighting or
> training-objective fix — nothing in the current VICReg + prediction loss explicitly rewards
> correct *relative distance ordering* across biomes, only local prediction accuracy — is the
> better-motivated next question, not more data.

### Standing diagnosis, now on its firmest footing yet

Six independent, mechanistically diverse approaches now agree on the same brightness/
scene-composition confound: two trained heads on frozen latents (#7, #11), one off-the-shelf
400M-image model never touched by this project (#14 Phase 1, CLIP), one direct fine-tune of the
encoder itself (#14 Phase 2), one hand-designed lighting-invariant feature (#15), and now one
untrained closed-form statistic (#17 Prong A). Combined with Prong B closing the "just needs more
data" theory for the specific case it was raised for, the confound looks **structural** to
`ebwm.pt`'s frozen representation and/or its training objective — not fixable by anything built
on top of the existing checkpoint without retraining its core objective, a materially more
expensive undertaking than anything tried in attempts #7-#17.

**Not yet decided whether that is worth pursuing, or whether to consolidate around the
mechanisms that already work (`commit_length`, frontier coverage, hazard avoidance) and accept
the central score as a permanent known limitation.**

*Previous: `docs/09_curiosity_coldstart.md`; commit_length through attempt #16's Coverage-Value
Predictor (real aggregate signal, no learnable per-trial model at N≈100). Current: attempt #17 —
two independent, cheap, direct attacks on the never-fixed central score (an untrained OOD
detector, and a check of whether attempt #14 Phase 2's anomaly was a data-coverage gap) both come
back NO-GO — the 6th confirmation of the confound via the most structurally decisive mechanism
yet (a closed-form statistic with no way to learn a shortcut), and the closure of the "more data"
theory for the case that raised it. Next: not yet decided — retrain `ebwm.pt`'s core training
objective (expensive, never attempted) vs. consolidate around the campaign's working
coverage/execution mechanisms and accept the central score as a permanent limitation.*

## Cold-start attempt #18 (PC, 2026-07-27 to 2026-07-28) — literature-motivated: a same-day
correction of the campaign's first apparent GO, plus a genuinely new non-photometric factor,
plus a live sanity test that surfaced an unrelated regression signal

A dedicated arXiv search pass (2026-07-27, covering the prior two weeks) surfaced 5 new JEPA
papers, added to `docs/references/index.md`. Two reopened concrete, cheap sub-questions ahead of
the retrain-vs-consolidate decision attempt #17 left open. This attempt is unusual in the
campaign's history: its most important event is not a result but a **correction issued the same
day**, exactly the kind of self-check this project's honesty discipline exists for.

### Diagnostic 1 — pseudo-depth generalization: an apparent first-ever GO that did not survive
a larger sample

Motivated by Khan, "Depth-Regularized JEPA World Models Learn More Transferable Representations
from Real Outdoor Robot Data" (arXiv:2607.16314) — a JEPA world model gets measurably better
in-domain AND out-of-domain generalization from a depth-supervision auxiliary term, the first
published instance of attempt #15's own conclusion that the brightness confound needs "a
different modality entirely." `scripts/diagnose_depth_gate.py` runs MiDaS_small (torch.hub
`intel-isl/MiDaS`, off-the-shelf, zero Minecraft-specific training — same "outside model" logic
as attempt #14 Phase 1's CLIP test) over the campaign's standard 251-frame diagnostic set,
scoring each frame by the mean of its closest 10% of MiDaS-predicted pixels (a nearest-object
proxy, per-frame or per-column).

**First pass, the campaign's usual tiny hand-labeled sample (tree_close n=4, no_tree n=6):**

| Gate | Threshold | Result |
|---|---|---|
| A — separation | ≥ 1.3x | **PASS — 1.304x** |
| B — brightness-independence | \|r\| < 0.3 | **PASS — r = 0.0451** (campaign's best by far; prior confounds ranged 0.117–0.947) |

Read at face value, this was the first mechanism in 7 independent tests (#7, #11, #14
Phase1/Phase2, #15, #17 Prong A, and this) to pass both established gates — flagged at the time
as "a thin margin on a small sample," not a declared victory, because that margin looked fragile
on inspection (Gate A cleared the 1.3x bar by 0.004).

**Same-day follow-up: the hand-labeled set was expanded from 10 to 27 frames** (21 new
candidates visually inspected — the *entire* remaining gate-eligible population in
`data/minerl_coverage/episodes.npz` and `assets/spawn_thumbs/`, not a cherry-picked subset; 4
discarded as genuinely ambiguous, a 19% discard rate, reported rather than hidden).

| Gate | Original (n=10) | Expanded (n=27) |
|---|---|---|
| A — separation | 1.304x (PASS) | **1.086x (FAIL)** |
| B — brightness-independence | r=0.0451 (PASS) | r=0.0451 (PASS, unchanged) |

> **LESSON: the original 1.304x pass was a small-sample artifact, not a robust separation.**
> Tree-close frames still score higher than no-tree frames on average (644.3 vs. 593.5) — the
> *direction* is still correct — but the margin collapsed well below the 1.3x bar once the
> sample nearly tripled. Gate B's brightness-independence result is real and unaffected: depth
> genuinely is not a brightness shortcut, the best result of any mechanism this campaign has
> tested. But independence from one confound is not the same as being a working tree-detector.

**Corrected VERDICT: MIXED, not GO.** The standing diagnosis from attempt #17 — that no
mechanism has yet cleanly separated tree-close from open scenes while staying
brightness-independent at a trustworthy sample size — still holds. What genuinely changed: depth
is now a confirmed non-photometric, non-brightness-confounded signal, even though it isn't (yet,
alone) a working separator. This is being corrected in the same session it was found, not left
standing as a false first GO — the campaign's honesty discipline applied to itself, not just to
each new mechanism.

### Diagnostic 2 — Treechop/Obtain action-coverage overlap: a genuinely new, non-photometric
factor, still standing

Motivated by Zhang, Guan, Zhang, Zhang, Li, "On the Identifiability of Controlled World Models"
(arXiv:2607.22430): an action-conditioned JEPA only recovers reliable state/dynamics when the
training action distribution has adequate coverage. `scripts/diagnose_action_coverage.py`
measured this directly — no GPU, pure action-array statistics, seeded, self-calibrated against a
Treechop-vs-Treechop split-half null rather than an invented threshold.

- **Out-of-vocabulary fraction**: only 2.33% of pooled Obtain-domain actions use an index outside
  `ebwm.pt`'s trained 17-action vocabulary — far lower than the naive "5/22≈22.7%" estimate this
  diagnostic started from (the craft-heavy expert demos rarely invoke crafting actions relative
  to movement; the random-policy coverage set alone is 22.6% OOV).
- **Jensen-Shannon divergence on shared indices**: Treechop vs. pooled Obtain = **0.1453**,
  against a Treechop-vs-Treechop-split-half null of **0.0014** — a **104x** ratio, not
  explainable by sampling noise. Treechop's own demos are 58.5% attack / 14.7% forward / 12.0%
  noop ("walk to a tree, hold attack"); Obtain is comparatively noop/forward-heavy and
  attack-light (33%/31%/25%).
- **Bonus finding, more specific than what was asked**: Treechop's *own* training data only ever
  exercises 8 of `ebwm.pt`'s 17 trained action indices — strafe, jump, and both camera-tilt
  directions are never sampled during training at all, an internal coverage gap independent of
  the Obtain domain entirely.

> **LESSON, held to the campaign's "hypothesis vs. confirmed" discipline**: this establishes a
> real, large, non-photometric distributional gap — the first diagnostic in 18 attempts to
> surface a candidate factor outside the brightness/scene-composition family — but does NOT by
> itself prove this causes attempt #10's score reversal. The paper's claim concerns
> state-action-next-state identifiability; this diagnostic only measured the marginal
> action-usage histogram. A plausible contributing factor, not a confirmed cause.

This finding reframes "retrain the core objective" from a vague, expensive idea into two
concrete, scoped candidates: broaden Treechop's own action coverage, and/or reweight training
toward the actions Obtain actually exercises. Unaffected by Diagnostic 1's correction.

### Live sanity test — `scan.macro: "depth"` (N=6): no chopping, mechanism barely exercised,
one regression signal flagged not buried

Dispatched against Diagnostic 1's ORIGINAL (since-corrected) result, before the larger sample
came back. Correctly re-scoped once the correction landed: read as "does a depth-driven heading
behave sanely," not as validating a fix. `mine_jepa/ebwm/depth.py` (new module — MiDaS loading,
per-column depth scoring, heading-delta computation) feeds a new scan-macro variant
(`configs/play_craft_commit4_depth.yaml`, built on the already-validated commit_length=4 +
hazard-avoidance baseline). By design it never touches `CraftPlannerV4`/`SwitchingCraftPlanner`'s
latent-space scoring — MiDaS needs real pixels, the planner's candidate rollouts are imagined
latents with no pixels to decode, so depth can only inform a navigation heading on the real
current frame, not a rollout score.

- **0/6 logs, 0/6 planks, mean reward 0.000** (below MineRL's ~0.4 random-policy baseline) —
  expected, not the question this batch was asked.
- **The scan macro triggered only 3 times across all 6 episodes** — `goal_score_std` rarely
  dropped low enough to invoke it. The sanity question is only weakly answered by this batch,
  independent of the small-N caveat that applies everywhere in this campaign.
- Of the 3 triggers: no severe lock-in (unlike attempt #6's CEM or attempt #8's action-pool
  priming, both >80% single-action concentration); one converged in 2 ticks; one held a
  consistent rightmost-column heading across 4 of 6 ticks with one detour; **one reversed from
  the rightmost column (delta +26.2°) to the leftmost (delta -26.2°) in a single 16-tick step** —
  not the campaign's classic ping-pong-every-replan oscillation bug (attempt #13's first steered-
  escape round), but a real, unexplained full reversal on too small a sample (2 data points) to
  characterize further.
- **Regression signal, flagged rather than buried**: 2/6 episodes ended `died_during_escape=True`
  (death while the hazard-avoidance reflex was actively trying to escape water) — the exact
  failure mode attempt #13's final round (widened `align_deg` + debounced dry-anchor) believed
  fixed at 6/6 survived, 0 deaths, the same N=6. This batch reused that identical hazard config,
  only adding the new depth scan macro alongside it. Not established as causal at this N — could
  be batch-to-batch noise recurring by chance — but plausible: monocular depth models are known
  to behave unpredictably on reflective/transparent surfaces like water, so a depth-driven
  heading could steer toward or linger near water in a way `"turn"`/`"frontier"` didn't. **Before
  trusting the attempt #13 hazard fix as robust across scan-macro choices, this deserves a
  dedicated check.**

GIF: `assets/agent_play_craft_commit4_depth.gif`. Full log:
`logs/coldstart_attempt18_depth_sanity_n6.log`.

### Standing diagnosis after attempt #18

The "encoder/scoring confound is structural and unfixable short of retraining" conclusion from
attempt #17 **still stands on the separation question** — no mechanism has yet cleanly separated
tree-close from open scenes while staying brightness-independent at a trustworthy sample size.
What genuinely changed: depth's brightness-independence is real and reproducible (a non-
photometric signal that isn't itself a brightness shortcut, even if not yet a working detector
alone), and Diagnostic 2's action-coverage gap is a separate, still-standing, genuinely new
non-photometric factor — the first of its kind in 18 attempts. Neither is a proven live fix.
Diagnostic 2 reframes "retrain the core objective" into two concrete, scoped candidates (broaden
Treechop's own action coverage; reweight toward Obtain's actual action mix) rather than a vague,
expensive idea. The live sanity test's drowning-regression signal is a new, separate open
question about mechanism interaction (scan macro choice vs. hazard avoidance), unrelated to the
central score. **Decision on how to proceed (retrain vs. consolidate) still belongs to the user —
this attempt records results, not a commitment to any next step.**

*Previous: `docs/09_curiosity_coldstart.md`; commit_length through attempt #17's two-pronged
confirmation of the brightness confound. Current: attempt #18 — a same-day self-correction (an
apparent first GO on the central score did not survive a larger sample), a new non-photometric
action-coverage factor that does still stand, and a live sanity test that stayed inconclusive on
its own question but surfaced an unrelated hazard-interaction regression signal worth checking.
Next: not yet decided — retrain `ebwm.pt`'s core training objective vs. consolidate around the
campaign's working coverage/execution mechanisms, now with two more concrete candidate levers
(action-coverage reweighting; SIGReg in place of VICReg) than attempt #17 left on the table.*

---

## Attempt #20 — Context Collapse: is the world model's rollout responsive to actions at all?

> ⚠️ **Documentation gap, flagged not smoothed over**: attempt #19 (the first real retrain of
> `ebwm.pt`'s core objective — Run A action-coverage, Run B SIGReg, both NO-GO) was never written
> up in this file. `CLAUDE.md` remains its only record. This section jumps from #18 to #20;
> read `CLAUDE.md`'s Phase 5+ section for #19 before treating this file as continuous.

### Where this came from

A bibliography refresh (2026-08-10, covering 2026-07-27 onward, arXiv + Google Scholar) surfaced
Gan et al., "ActSWM: Action-Sensitive World Models for Long-Horizon Planning in Open-World Games"
([arXiv:2607.26712](https://arxiv.org/abs/2607.26712)) — whose baseline is **LeWM, the same
architecture family as `mine_jepa/ebwm`**, evaluated on closed-loop Minecraft planning.

It names a failure mode called **Context Collapse**: an autoregressive latent predictor keeps
high cosine similarity to the true future while producing *nearly indistinguishable futures under
different action sequences*. A model in that state has a healthy prediction `ratio` and a blind
planner, because MPC can only rank candidate action sequences by the differences their rollouts
produce.

That is a candidate mechanical explanation for this campaign's standing diagnosis. In 19 attempts
nobody had ever measured whether `ebwm.pt`'s rollouts respond to actions at all — every attempt
targeted the *score* (attempts #7-#11, #14, #15, #17) or the *search/execution* (#2-#6, #8, #12,
#13, #16).

### Method

`scripts/diagnose_context_collapse.py` + `configs/diagnose_context_collapse.yaml`. Fully offline:
no MineRL, no Java, `ebwm.pt` loaded frozen with `requires_grad_(False)` and md5-reverified
(`ac14e65361fbddeb057963362ea1382d`, unchanged).

ActSWM's Eq. 10, adapted: from one encoded context frame, roll out K=12 steps twice from the same
context, comparing each against the encoded true future `z_{t+k}`:

- `s_gt_k = cos(z_hat_gt, z)` — recorded actions
- `s_zero_k = cos(z_hat_zero, z)` — all-noop counterfactual (action index 0)
- `delta_k = s_gt_k - s_zero_k` — the action gap

Two deliberate departures from ActSWM, reported separately rather than blended into their number:

1. A **random-action arm**. The planner never compares "recorded vs. noop"; it compares many
   non-noop candidates against each other.
2. A **planner-matched spread arm**: the std, across 64 candidate sequences, of the exact
   final-step latent distance `planner.py::_score` ranks on — the offline counterpart of the live
   `goal_score_std` logged since attempt #2.

**Treechop is its own positive control.** This project has no established threshold for `delta_k`
(never measured before), but the agent demonstrably plans successfully on Treechop (Phase 4,
25-50% chop). A healthy delta there and a collapsed one on Obtain would be interpretable without
an external bar.

**A near-zero delta is ambiguous**, and ActSWM's metric alone cannot disambiguate it, so a second
measurement was added: the L2 spread of the 1-step prediction across all 17 action choices from
the same frame, divided by the true 1-step latent change `||z_{t+1} - z_t||`. This separates
"the predictor ignores the action" (share ~ 0) from "it responds, but not usefully" (share > 0,
delta still ~ 0).

### Result — neither Context Collapse as defined, nor a healthy model

n=400 windows/domain (266 for `obtain_coverage` — the only windows surviving the `max_action=17`
filter, so that column is noisier than the other two and is not treated as equal evidence).

| domain | real 1-step move | action spread | action share | delta@k=1 win-rate | delta_zero@K | delta_rand@K |
|---|---|---|---|---|---|---|
| treechop | 16.22 | 0.615 | 3.8% | 35.5% | -0.00028 | +0.00012 |
| obtain_craft | 4.82 | 0.520 | 10.8% | 13.0% | -0.00055 | +0.00204 |
| obtain_coverage | 11.31 | 0.703 | 6.2% | 28.2% | -0.00150 | +0.00011 |

**The action pathway is not dead.** The 17 actions genuinely move the prediction, and the action
embedding table is healthy (near-orthogonal, mean pairwise cosine -0.014). So this is *not*
ActSWM's Context Collapse as literally defined.

**But conditioning on the true action does not beat assuming the agent did nothing.** `delta_zero`
is negative in every domain, and significantly so at k=1 — the exact regime `ebwm.pt` was trained
on (`train_eb_jepa.py` uses `nsteps=1`), so this cannot be blamed on multi-step rollout drift:

- treechop: -0.000444 +/- 0.000178, t=-2.49, p=0.0130, true action wins in **35.5%** of windows
- obtain_craft: -0.000113 +/- 0.000026, t=-4.37, p<0.0001, wins in **13.0%**
- obtain_coverage: -0.000149 +/- 0.000059, t=-2.51, p=0.0126, wins in **28.2%**

The consistent ordering across all three domains is **noop > true action > random action**. The
model has learned something real (the true action beats a random one) but not enough to clear the
trivial copy-last baseline that the noop rollout approximates — consistent with `ratio=0.9265`,
i.e. prediction only beats copy-last by ~7%.

**Internal consistency check that supports the mechanism**: the win-rate is perfectly monotone in
how *dynamic* the domain is (real 1-step move 4.82 → 13.0%, 11.31 → 28.2%, 16.22 → 35.5%). The
more static the footage, the stronger copy-last is as a baseline, and the more the miscalibrated
action perturbation costs. This is the expected signature if the action response is a net
liability against a strong copy baseline, and it was not designed for — it fell out of the data.

**Negative control**: corr(delta, frame brightness) = -0.048 / +0.031 / -0.225 — the first
mechanism in this campaign essentially uncorrelated with brightness (prior range 0.117-0.947).
Expected by construction: delta is a difference between two rollouts from the *same* frame, so
frame-level confounds cancel. Worth stating anyway, since six prior mechanisms failed here.

### What this does and does not establish

**Established**: `ebwm.pt` is, for planning purposes, close to a copy-last predictor carrying an
action-dependent perturbation that does not track true consequences. This holds on **Treechop,
its own training domain** — so unlike attempt #10's score reversal, it is not a domain-shift
effect. It is a second, independent defect on the **dynamics** side, whereas attempts #7-#19
targeted the **scoring** side almost exclusively.

**NOT established — and this is a genuine tension, not a footnote**: this cannot by itself be the
cause of the cold-start wall, because the agent chops trees 25-50% on Treechop *with this exact
deficit present*. Any account of the cold-start failure that leans on this finding has to explain
that too. No such account is offered here; it would be a hypothesis, not a measurement.

**NOT established**: that ActSWM's fix transfers. Their predictor carries H=32 context and their
causal story ("long context lets the predictor extrapolate scene progression while ignoring the
action") cannot apply unchanged to `ACConvPredictor`'s `context_length=1`.

**What it reframes**: `commit_length=4` remains the only lever that ever produced a non-zero
result (9.7% pooled). If per-step action information is at noise level against copy-last, then
committing to a block of actions instead of re-ranking every tick on a noise-dominated score is
exactly the right compensation. The campaign found that empirically without knowing why.

### Concrete lever this opens

ActSWM's `L_readout` term (Eq. 8) makes "the action associated with each local transition
recoverable" — precisely the property measured broken here. **Half that machinery already exists
in this repo, disabled since the beginning**: `mine_jepa/eb_jepa/losses.py::InverseDynamicsLoss`
takes `(state_t, state_t+1) -> action` and is wired into `VC_IDM_Sim_Regularizer`, but
`build_ac_jepa` passes `idm_coeff=0.0, idm=None` (`mine_jepa/ebwm/__init__.py:146`), so it has
never been instantiated. Missing versus ActSWM: parameter freezing (their `idm.stop_grad=true`
excludes phi_0 from the optimizer while still backpropagating through the latent inputs),
application to rollout-predicted transitions (Eq. 8b), and the hinge term (Eq. 5) entirely.

Whether to spend a retrain on that is the user's call — attempt #19 spent two retrains for two
NO-GOs, and this diagnostic does not on its own promise that a third would land.


### Campaign closed on attempt #20 (decision, 2026-08-10)

The cold-start campaign is **closed here**, by the user's decision, with attempt #20 as its
concluding result rather than a 21st attempt.

The reasoning, stated plainly so a later reader does not mistake this for exhaustion:

- **The campaign as structured was working on the wrong layer.** Attempts #2-#19 tuned the search,
  the scoring, and the execution on top of a frozen `ebwm.pt`. Attempt #20 measured that
  `ebwm.pt`'s own action conditioning is a net liability against copy-last — so an MPC planner
  sitting on it ranks candidate action sequences by differences that do not track consequences.
  That retrospectively explains why three score fixes (#7, #11, #17), two search fixes (#5, #6),
  and two retrains (#19 Run A/B) each failed differently: none of them addressed the dynamics.
- **The remaining lever is a rebuild, not a patch.** ActSWM's `L_readout`/hinge terms target
  exactly the measured defect, and half the machinery is already present but disabled
  (`InverseDynamicsLoss`). But applying it well plausibly also means changing
  `ACConvPredictor`'s `context_length=1` — their causal story depends on a 32-frame context. That
  is a world-model rebuild, not another attempt in this campaign's idiom.
- **The project's stated purpose is already met.** `CLAUDE.md` line 1: "spectacular packaging of
  existing open-source building blocks, not from-scratch research." Phases 0-4 are validated with
  real gates, the agent chops trees in real Minecraft (25-50%), the live craft demo runs at 100%
  over 6+ episodes, and the campaign itself is documented end to end.

**What is NOT claimed by closing here**: not that cold-start chopping is impossible, and not that
the remaining lever would fail. ActSWM demonstrates a LeWM-family model planning successfully in
closed-loop Minecraft (mining 19/20), so the capability is real for this architecture family at a
larger scale. What is claimed is narrower and better supported: **this campaign's approach — fix
the planner around a frozen 664K-parameter world model with `context_length=1` — is exhausted,
and attempt #20 explains why.**

**Standing baseline if work ever resumes.** The three mechanisms that demonstrably work, all
non-photometric, all outside the broken score: `commit_length=4` (9.7% pooled, the campaign's best
result), `FrontierTracker` coverage search (attempt #12), and the hazard-avoidance drowning fix
(attempt #13, confirmed at N=20: drowning 60% → 15%, fair-shot episodes 40% → 60%). The
deferred open question from attempt #18's live sanity test (2/6 `died_during_escape` with the
depth scan macro, a possible regression of the #13 fix under a different scan macro) is left
open, not resolved.

*Previous: attempt #18 (see also `CLAUDE.md` for the undocumented attempt #19). Current: attempt
#20 — the first measurement in the campaign of whether the world model's rollouts respond to
actions, motivated by a paper whose baseline is our own architecture family. Result: they respond,
but not usefully; conditioning on the true action is significantly worse than assuming noop, on
the training domain itself. Offline gates only — nothing wired into the live planner, no
checkpoint written or modified.*

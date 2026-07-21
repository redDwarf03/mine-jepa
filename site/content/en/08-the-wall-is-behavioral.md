---
title: "The wall is behavioral: a real first success, then four proofs that sharpening the signal isn't enough — and a fifth that confirms the diagnosis"
slug: "08-the-wall-is-behavioral"
lang: "en"
order: 8
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft", "07-broken-curiosity"]
source_docs: ["docs/10_coldstart_engineering.md", "CLAUDE.md#Phase 5+"]
---

::: beginner

## Where we were

Chapter 7 ended on a frustrating realization: sharpening the "am I lost?" signal (by feeding the model more examples of genuinely lost states) changed nothing in the end — still zero logs chopped from a random spawn point. This chapter tells the continuation of the investigation: a genuine discovery that unlocks a first real result (modest, but real), followed by a series of further attempts that each fail in distinct and instructive ways, until a clear diagnosis emerges — followed by a fresh attempt testing that diagnosis directly, yielding a negative yet deeply informative result: **the wall is not in perception, it is in behavior.**

## The discovery: the planner was throwing away its own good plan

While reading through the planner's code line by line (the Chapter 4 planner imagining 512 stories of 12 actions and picking the best), a bug was discovered — not a program crash, but a silent flaw in the logic itself. The planner correctly imagined a 12-action story, correctly identified the best one... and then executed **only the very first action**, throwing away the rest and starting from scratch on the next step. Even when the imagined plan was excellent — "turn toward trunk, step forward, strike, strike, strike" — the agent executed only the first step, discarded the remaining 11, and re-sampled 512 fresh stories on the next frame. A good sustained gesture was systematically diluted into a series of isolated, independent decisions.

The fix was tiny: execute the first 4 actions of the winning plan instead of just 1, before re-planning. Across a combined pool of 31 episodes (grouped across several test runs), this single fix yielded **3 successes out of 31 (about 10%)** — whereas all previous attempts in this and the preceding chapter combined (27 episodes total) had produced **zero** successes. It is not a massive number, and it isn't yet statistically airtight at this sample size — but it is the first non-zero result in the project's history on this specific problem.

The lesson is funny and slightly disorienting: **a scoring bug and a call-convention bug look identical from the outside.** Previous chapters spent considerable effort sharpening the quality of the *signal* used by the planner (sticky sampling, search reflexes, data fine-tuning) — all of which was real and necessary, but none of which touched the core flaw: the planner was picking correctly, but acting on only a twelfth of its own choice.

## A reinforcement attempt: curiosity again, but "live" this time

Building on this minor breakthrough, the project tried re-introducing curiosity (Chapter 7), but in a different version: instead of training the predictor ensemble once and for all on static demo files (which had caused it to collapse), the ensemble was trained **continuously, while the agent played**, on what it actually saw, frame by frame.

First run: three out of seven episodes crashed due to a technical bug (fixed along the way). Across the remaining four valid episodes, zero successes — though with so few episodes, that alone wasn't surprising (expected success rate over 4 trials was under half an episode). The real problem discovered afterward: **the diagnostic needed to tell whether the curiosity signal worked hadn't even been enabled.** A simple lesson worth repeating: a diagnostic tool present in the codebase but left disabled is equivalent to having no tool at all.

Once instrumented and enabled on a fresh batch of six episodes, the answer became clear — negative, but in a precise and interesting way: the "novelty" signal started relatively high at the start of each episode, then **decayed smoothly and steadily** down to 10 to 60 times lower, **regardless of what happened on screen**. The most visually striking moment in an entire episode (a full tree canopy scene, where the "I see something important" signal peaked) coincided with curiosity novelty at its **absolute lowest point**. The cause: the curiosity system's short-term memory filled quickly with visually similar frames (the agent often stays within a small visual area), and its predictor adapted to them in a few hundred steps — after which nothing surprised it anymore, independent of actual task relevance. The signal tracked elapsed time, not scene content. The project halted this track without running a larger confirmation batch, as the mechanics were already clear.

## Second attempt: re-enabling the search reflex, properly wired

Chapter 7 had disabled the "turn head when lost" reflex for crafting mode because its threshold didn't match the crafting model. But in the meantime, the two-brain agent had been introduced: the component searching for the tree still used the original model, where the reflex calibration was valid. This experiment re-enabled the reflex right where calibration applied.

Result over 7 episodes: still **zero successes**. And the most telling sign: in the episode where behavior was easiest to observe, the agent went through a long window (~900 steps) where the "I see something important" signal remained elevated — comparable to Chapter 5's top canopy scene — and the search reflex remained correctly dormant the whole time (knowing it wasn't lost). **And yet, the agent still did not chop a single log during that entire window.** This was the clearest possible echo of Chapter 7's takeaway: properly wiring the "I am lost" detector accomplishes nothing if the real bottleneck is turning "I see something" into "I act on it".

## Third attempt: a "smarter" planning method

Research literature recommended a planning method more refined than Chapter 4's simple random shooting: instead of sampling 512 stories once, sample an initial batch, keep the best ones (the "elites"), then resample a second batch *centered on what the elites had in common*, repeating across several iterations. The idea: iteratively converge toward better candidate futures rather than relying on a single raw sample.

Result over 8 episodes: zero successes, and more importantly, a **distinct qualitative regression**: the agent began repeating a single action far more aggressively than usual — on average, the dominant action occupied twice as much episode time as normal, with one episode showing the agent striking empty air while standing still 89% of the time.

The explanation fits in one sentence: **this method requires a signal that genuinely distinguishes good stories from bad ones in order to converge toward the good ones.** When no tree is in view (the most common situation in a cold start), the score landscape is almost flat — small differences between candidate stories are just statistical noise. An iterative refinement method takes that residual noise for genuine signal and locks onto it harder with every iteration, rather than staying diverse like simple random sampling does across steps. The "smarter" the method, the more *confidently wrong* it gets when there is ultimately nothing to learn from the situation.

## Fourth attempt: training a true distance metric

Final track in this campaign: up to now, the distance used to compare an imagined future to the goal was raw mathematical distance between embeddings — never trained to represent anything precise like "how many action steps actually separate me from the goal". This attempt trained a small auxiliary function so that distance in this transformed space better approximated the true step count.

Tested offline first (before spending real play time), this new distance metric passed with flying colors: genuinely close image pairs received a much smaller predicted distance than genuinely distant pairs, with a gap of about 8x — well above the required threshold. A promising sign, very different from the flat collapse observed with curiosity.

In real play, however, over 6 episodes: still zero successes. And frame analysis revealed a new, precise explanation: the trained distance signal reacted heavily to **scene lighting** (daylight, dusk, cave interiors) rather than true proximity to a tree — and not in a simple way: the darkest frames in an episode paradoxically produced the lowest predicted distance, not the highest. The cause: neither the expert demos nor the coverage episodes used to train this distance metric contained true night or cave scenes — so this rule never learned to distinguish "it is night" from "I am close to the goal", two very different things in the real game. A flat signal (like curiosity) fails cleanly, breaking nothing; a **confidently wrong** signal actively misleads the planner toward what *looks* close without being close — in a sense worse than a total lack of signal.

## Fifth attempt: seeding good gestures into the menu, plus a terrain-covering maneuver

The diagnosis framed after the fourth attempt offered a precise explanation: the problem wasn't that the planner evaluated poorly, but that the right gesture was almost never *proposed* among the 512 candidate futures it imagined. Two ideas to fix this directly were tested together, alongside the `commit_length=4` fix already in place:

- **Seeding pre-built good gestures into the candidate set**: instead of sampling all 512 candidate futures randomly (with or without sticky sampling), about 90 of them were replaced with hand-crafted macro gestures — sustained forward-plus-attack, continuous camera rotation, stepping backward.
- **A cruising maneuver**: when the "I am lost" signal remained flat for too long, instead of turning in place (the reflex tested earlier, which finds nothing where nothing exists), the agent sprinted straight ahead and jumped over obstacles for a set duration before handing control back to the normal planner.

Across 8 episodes: still **zero logs, zero planks, zero reward**. But both mechanisms **verifiably triggered in real play**, rather than being added without effect: the pre-built forward-plus-attack macro was picked by the planner in 3 of 8 episodes (occupying up to half the episode steps in one case); the cruising maneuver triggered in 1 episode, occupying about a quarter of its steps. This was not a case of new tools sitting unused.

The truly interesting result of this attempt was not the zero, but this: in 3 out of 8 episodes, the agent locked onto **a single action** between 83% and 100% of the time — near-total behavioral lock-in. This strongly echoed what happened with the "smarter" CEM planning method in the third attempt, which also produced extreme action lock-in when the signal was flat. However, this similarity is noted here as an **observation**, not yet proof of an identical mechanism — further quantitative analysis is underway before asserting it as established fact.

This result sharpened the diagnosis once more: when the "how good is this imagined story" score is flat (no tree in view), the planner has **nothing to guide correction**. Feeding it pure random noise (earlier attempts) makes it fidget in place without purpose. Feeding it a concentrated menu of good candidate futures (CEM) or pre-built continuous gestures (this attempt) makes it **blindly lock in** on one of them instead — because nothing in a flat score ever forces it to change its mind. Hand-writing good gestures or refining the sampling algorithm attack the problem from opposite ends, but neither gives the planner what it actually lacks: having *learned*, from real human gameplay, how a player actually searches when nothing interesting is in view — rather than being handed a rigid hand-coded menu of gestures.

## The diagnosis that stands, after these five attempts

Four independent attempts tried to improve the *quality of the signal* used by the planner to judge where to search or go: live curiosity (flat), the properly wired search reflex (useless against a valid signal), a more refined planning algorithm (counter-productive on a flat signal), a trained distance metric (wrong outside its training distribution). A fifth attempt directly targeted the *generation* of candidates rather than their evaluation — two zero-cost ideas tested together — and failed as well, but in a way that confirmed and sharpened the diagnosis rather than undermining it: both new tools triggered as intended, yet the agent still locked blindly onto single actions across multiple episodes. The only modification that ever produced a real non-zero result across this entire campaign remains the call-convention fix from Chapter 8, which changes **nothing** about how well the planner evaluates — it changes only **how much of its own good plan it actually executes.**

The diagnosis now established: **the wall is not that the model's imagined world is inaccurate — it already evaluates scenes correctly, as proven by the offline distance test. The wall is that the candidate futures imagined at each step — whether sampled randomly, stickily, refined via CEM, or seeded with hand-crafted macros — almost never contain the learned gesture required to actually search for and approach a tree — and when the candidate menu is too narrow or concentrated, the planner locks onto it blindly instead of continuing to explore.** This is a problem of candidate action *generation*, not candidate *evaluation* — and the most promising path forward is no longer "hand-writing better gestures", but "learning those gestures from real human play". Chapter 9 outlines where this path stands, along with two complementary ideas not yet tested at this stage.

:::

::: expert

## Framing: Four Independent Signal Attacks, One Actual Lever

Following Chapter 7 (sticky sampling, scan, coverage fine-tuning — all signal/perception side fixes), this chapter covers attempts #4-#7 from `docs/10_coldstart_engineering.md` on `MineRLObtainIronPickaxeDense-v0`, two-brain, seed 0.

## Attempt #4A — `commit_length`: The Bug Was in Call Convention

Re-reading `plan()`: each replan samples 512 fresh sequences and **returns only the first action** of the winning sequence — even when sticky sampling proposes a correct multi-step gesture (turn to trunk, advance, strike), steps 2..12 are discarded every tick.

Fix: `commit_length` (`mine_jepa/ebwm/planner.py`, wired in `DiscreteLatentPlanner.plan()` and `SwitchingCraftPlanner.plan()`) returns the `min(commit_length, horizon)` first actions of the winning sequence. `commit_length=1` (default) = original code path, verified bit-for-bit.

**Results, `commit_length=4` alone, two-brain, sticky 0.5, scan off, seed 0 (pooled across batches, N=31):**

| | N | Logs | Craft Success |
|---|---|---|---|
| `commit_length=4` (pooled) | 31 | 3 | 3/31 (9.7%) |
| `commit_length=1` (pooled, attempts #2-#3) | 27 | 0 | 0/27 (0%) |

Every success identical: 1 log → craft-planks → +4 planks, reward 9 (known WM v4 rule, Chapter 6). One-tailed Fisher exact 3/31 vs 0/27: **p ≈ 0.15** — non-significant at this N, but the **first reproducible non-zero result in project history on this milestone.**

> **Lesson: A scoring bug and a call convention bug look identical from the outside.** Attempts #2-#3 improved *signal* (sticky, scan, coverage) — real and necessary, but individually insufficient. Real bottleneck was not a better plan, but *executing more of the plan already correctly chosen*.

At 9.7%, far below 30% milestone threshold; each success remains dependent on lucky spawn (mean steps-to-success ≈3000 — most episodes never see an actionable tree within budget). Retained as default in `configs/play_craft_commit4*.yaml`; `play_craft.yaml` (`commit_length` unset → 1) unchanged.

## Attempt #4B — Online RND: Inconclusive, Then Mechanically Dismissed

Predictor/target RND trained continuously on visited states during gameplay (`mine_jepa/ebwm/rnd.py`), z-scored bonus (`novelty_coeff=0.5`) in two-brain chop planner.

**Launch bug found & fixed mid-batch** (not Java flakiness): `ResNet5.out_dim` missing — fixed to read `state_dim` from checkpoint config. N=7: episodes 1-3 crash pre-fix, episodes 4-7 run cleanly.

**Valid data: N=4, 0/4 success.** At pooled base rate of 9.7%, expectation over 4 trials is ≈0.4 — non-informative alone. **Diagnostic that would have decided this was unlogged**: `novelty_mean` existed in `plan(return_info=True)` but `scan.log_std: false` suppressed output. Verdict: **Inconclusive, halted without confirmation batch** (no N=15-20 without prior positive qualitative signal, project rule).

**Instrumented re-run, `scan.log_std: true`, N=6:** 0/6 success (expected ≈0.6, non-surprising). `novelty_mean` across 6 episodes systematically shows **same pattern**: rise or plateau over first ~50-130 steps, then **smooth monotonic decay** to 10-60x lower value at episode end — independent of episode length, survival, or `goal_score_std` (validated independent signal). Correlation between the two signals inconsistent in sign and magnitude across episodes (-0.83 to +0.15).

**Clearest data point**: Episode 5 (188 replans), `goal_score_std` hits absolute episode peak (0.045-0.046, comparable to Treechop "canopy" band) exactly when `novelty_mean` is at its **lowest values** (0.0015-0.0017).

> **Takeaway: Not offline smoke test separation appearing in game, but its own early convergence phase.** 256-slot ring buffer fills in ~130 steps with visually homogeneous frames (dense canopy, spawn area); predictor converges on this narrow distribution, after which novelty is low almost everywhere the trajectory actually goes — because trajectory itself visits nothing the buffer hasn't repeatedly shown the predictor. Moment breaking this homogeneity (step 2480 peak) was not detected as novel, because "different from recent buffer" and "most salient scene per `goal_score_std`" are not the same criterion.

**VERDICT: STOP.** Same symptom as Chapter 7 (no discrimination where it matters — lost vs found), via different mechanism: not ensemble collapse (offline), but over-fast convergence on overly narrow state distribution (online). Advantage of RND over offline ensemble is "predictor doesn't collapse to constant", not "predictor tracks state distribution agent actually needs to discriminate".

## Attempt #5 — Re-enabled Scan in Two-Brain Mode: Wiring Confirmed Correct, Result Still Negative

Wiring audit (pre-run): `chop_planner.plan(..., return_info=True)` reads `goal_score_std` on `ebwm.pt`, never on `craft_wm_v4` (structurally excluded by `if scan_enabled and mode == "chop"`). Config: `flat_threshold: 0.003`, `patience: 3`, `max_replans: 40` (Chapter 7 Treechop calibration), combined with `commit_length=4`.

**Result N=7: 0/7 success.** 2/7 episodes reproduce bounded version (by `max_replans`, not entire episode) of "spinning agent" pathology (`a12` 51%/87%). One episode spends ~880 of 3000 steps in "salient scene" band (0.008-0.026) with scan correctly dormant — **and agent still does not chop** during this window. One episode ends in rocky/cave-like passage with zero trees — case scan cannot resolve by construction.

**VERDICT: Wiring hypothesis confirmed, utility unconfirmed — NO-GO.** Most detailed data point (episode 1 high-std stretch) shows wall is not "agent doesn't know tree is there" but "knowing doesn't convert to chopping" — exact two-brain diagnostic from Chapter 7, here on confirmed well-calibrated signal.

## Attempt #6 — Categorical CEM (Iterative Refinement): Regression, Not Just Failure

`DiscreteLatentPlanner` gains `cem_iters`, `cem_elite_frac`, `cem_smoothing`: Gen 1 via standard `_sample_actions()`, subsequent generations resampled from categorical table over elite action frequencies (+Laplace smoothing). `cem_iters<=1` = original path, verified bit-for-bit across 8 cases (`ebwm.pt`/`craft_wm_v4`, sticky {0.0/0.5}, commit_length {1/4}). Measured overhead: 2.94x per `cem_iters=3` call (~41% real throughput drop).

**Result N=8: 0/8 success**, `chop=188 craft=0` — mode never switches. **Clear qualitative regression**: mean dominant action concentration **66.3%** (50-89%) vs **35.8%** mean for `commit_length=4` alone (19-69%, single episode exceeds 51%). Episode 8: 89% static attack (`a6`); episodes 2/4/5: 74-81% sprint-attack frozen in single direction (`a14`), near-zero turn actions in top 3.

> **Lesson: CEM refinement requires a discriminating score to refine — it has no way of knowing score is flat.** Random/sticky sampling degrades gracefully when score landscape is flat (each replan samples fresh diverse pool); iterative refinement does opposite: takes residual noise of flat ranking as real signal and concentrates generation after generation on that noise — finer the method, more confidently it commits in wrong direction when underlying signal has nothing to say.

**NO-GO**: 0/8, regression in only qualitative axis CEM was meant to improve, real fps cost — zero of three criteria met.

## Attempt #7 — Trained Distance Metric (Destrade et al., arXiv:2601.00844): Offline Gate PASSED, Live Result NO-GO, New Precise Diagnosis

Small projector `P` (`mine_jepa/ebwm/value_head.py::DistanceProjector`, 2 layers, `in_dim=4096` → `proj_dim=32`, ~1.06M params) trained so `||P(z_t)-P(z_goal)||` approximates true step distance to goal; `ebwm.pt` frozen (49 params frozen, verified). Data: Treechop demos + coverage episodes (Chapter 7) as censored "far" pairs (one-sided hinge).

**Offline Gate (Mandatory Pre-Play) — PASSED Decisively**: Close pairs (k≤5, n=2560) mean `pred_dist` = 12.317; far/coverage pairs (n=2560) mean = 97.257. **Separation Ratio 7.896** (required threshold ≥1.3).

**Live N=6: 0/6 success**, zero crashes, normal action concentration (16-40%, no CEM regression). Preserved GIF (only final non-success episode survives on disk; "best successful episode" logic never triggers at 0/6) shows agent finishing near dark — cave/ravine — consistent with Chapter 7 deaths.

Pearson correlation(`goal_score_std`, frame brightness) = **-0.565** across 72 episode readings. Daylight frames (brightness>60): mean std 0.499; dark frames (≤60, dusk/night by step 480): mean std 1.174 — more than double. **Yet non-monotonic**: darkest frames of entire episode (brightness ~14-15, right near end) hit **lowest** std of trace. Cause: neither Treechop demos (mean brightness 45.5, already fairly dark — canopy shadow, but daylight) nor coverage episodes (mean 92.4, full day) contain true night or cave scenes — exact visual regime where this episode spends significant time.

> **Lesson: THIRD category of finding, more specific than "does not discriminate" (Chapter 7 offline ensemble) or "discriminates correctly but still not the bottleneck" (raw metric attempts). Trained metric discriminates well — true wide dynamic range, opposite of RND collapse — but along a lighting/scene-composition nuisance axis that offline gate structurally could not detect, since close AND far pairs all came from same training distribution (predominantly daylight). Flat signal fails cleanly (all candidates tied, argmax arbitrary but harmless); confident-but-false signal actively directs plan toward what *looks* close without being close — indistinguishable from noise to planner, in a sense worse than zero signal.**

**NO-GO** on expanded batch with this checkpoint as-is. Concrete path if resumed: targeted dusk/night/cave data collection, or photometric augmentation during projector training — not more daylight episodes.

## Attempt #8 — Proposal A (Pool Priming) + Proposal C (Bushwhack Maneuver), Combined with `commit_length=4`: NO-GO, But Most Informative Negative of Campaign

`planner.action_pool_priming` (new block in `_sample_actions()`, `mine_jepa/ebwm/planner.py`) seeds ~30 sustained forward+attack macro lines, ~30 continuous camera rotation lines, ~30 backward lines into 512 candidate pool (Proposal A); `scan.macro: bushwhack` (`scripts/play_craft.py`) replaces turn-in-place reflex with bounded forward sprint-jump, triggered by same flat `goal_score_std` on chop planner (Proposal C). Both code paths verified bit-for-bit identical when disabled. Config: `configs/play_craft_commit4_ac.yaml`.

**N=8, seed 0: 0/8 logs, 0/8 planks, reward 0.** Against pooled base rate of `commit_length=4` alone (3/31 ≈ 9.7%, ≈0.8 expected successes on N=8): neither significant regression nor confirmation.

**Both mechanisms verifiably triggered** (not just wired-and-unused): primed forward+attack macro (`a7`) hits 21-49% share in 3/8 episodes; bushwhack macro (`a13`) hits 28% with 8 scan triggers in 1/8 episode (only when flat signal persisted long enough to fire).

**Finding mattering more than 0/8**: 3/8 episodes show single action (`a14`, pre-existing "forward+attack" gesture) at 83-100% share — near-total behavioral lock-in. This **recalls** action concentration regression of real CEM attempt #6 (66.3% mean vs 35.8% for `commit_length=4` alone) on a *different* mechanism (fixed menu + terrain-covering macro, not iterative refinement) hitting structurally similar failure mode.
⚠️ **Not yet quantitatively verified against action distributions specific to `commit_length=4` alone before asserting "same lock-in" as established fact — noted for verification, not yet confirmed conclusion.**

> **Refinement of Diagnosis: MPC argmax has nothing to correct itself with when `goal_score_std` is flat (no tree in view).** i.i.d. noise (attempts #1-3) makes it fidget in place; concentrated menu (real CEM attempt #6) or continuous macros (attempt #8) make it blindly lock onto one instead, because nothing in flat score ever corrects choice. Hand-written action generation (A/C) and score refinement applied to hardcoded macros hit same wall from two opposite directions. Mechanism that should not blindly lock in is one that *learned* full contextual behavior distribution (including how experts search), not one handed a rigid fixed menu.

**NO-GO**, but informative: confirms lack of gradient in flat score, not candidate source (noise vs fixed menu), is common cause of three failure modes observed since attempt #6 (fidgeting, CEM-lock, macro-lock).

## Diagnosis That Stands, After Five Independent Attacks

**Wall is behavioral (action generation), not perceptual (score quality) — and attacking candidate generation directly (attempt #8) confirms diagnosis without solving it.** Three fixes targeting signal/search quality (online RND, real CEM, trained distance metric) failed differently — one flat, one actively regressive, one real-but-misaligned. Attempt #8, attacking generation itself via hand-crafted macro menu rather than score, produces **third form of failure linked to lack of gradient in flat score**: behavioral lock-in, not fidgeting or noisy refinement. Only lever ever producing non-zero result (`commit_length=4`, attempt #4) remains purely execution fix: changes nothing about *choice* quality, only duration choice is *held*. World model already knows how to evaluate scene correctly (attempt #7 offline gate proves it); what 512 candidate sequences — sampled randomly, stickily, refined via CEM, or partially pre-filled with macros — almost never contain is learned gesture to hold to actually search for and approach a tree. Proposal B (latent policy prior trained via behavioral cloning) is now top priority; Chapter 9 details its status and two unexecuted complementary refinements.

## References (Verified, from docs/references/index.md)

- Terver, Yang, Ponce, Bardes, LeCun, *What Drives Success in Physical Planning with Joint-Embedding Predictive World Models?*, arXiv:2512.24497 (2025) — recommendation of real CEM tested and invalidated in this precise regime (attempt #6).
- Destrade, Bounou, Le Lidec, Ponce, LeCun, *Value-guided action planning with JEPA world models*, arXiv:2601.00844 (2026) — trained distance metric (attempt #7).
- Burda, Edwards, Storkey, Klimov, RND, arXiv:1810.12894 (2018) — online mechanism tested in attempt #4B.

:::

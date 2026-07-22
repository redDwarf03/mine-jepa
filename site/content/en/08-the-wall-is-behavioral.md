---
title: "The wall is behavioral: one real success, then four proofs that refining the signal is not enough — and a fifth that confirms the diagnosis"
slug: "08-the-wall-is-behavioral"
lang: "en"
order: 8
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft", "07-broken-curiosity"]
source_docs: ["docs/10_coldstart_engineering.md", "CLAUDE.md#Phase 5+"]
---

::: beginner

## Where we left off

Chapter 7 ended with a frustrating observation: sharpening the "am I lost?" signal (by giving the model more examples of situations where one is truly lost) did not change the final result at all — still zero logs chopped from a random starting point. This chapter tells the rest of the investigation: a real discovery that finally unlocks a first result (not huge, but real), followed by a series of additional attempts that each fail in a different and instructive way, until a clear diagnosis emerges — and then a brand new attempt that tests this diagnosis itself directly, with a negative but highly informative result: **the wall is not in perception, it is in behavior.**

## The discovery: the planner was throwing its own good plan in the trash

While rereading the planner's code line by line (the one from Chapter 4, which imagines 512 stories of 12 actions and keeps the best one), a bug appeared — not a bug that crashes the program, but a silent bug in the logic itself. The planner correctly imagines a 12-action story, correctly identifies the best one... and then executes only **the very first action**, before starting all over from scratch on the next turn. Even when the imagined plan was excellent — "turn toward the trunk, step forward, strike, strike, strike" — the agent only executed the first step of this plan, threw away the next 11, and drew 512 completely new stories on the next turn. A good sustained gesture was thus systematically diluted into a sequence of isolated, independent decisions.

The fix is tiny: execute the first 4 actions of the best found plan, instead of just one, before replanning. Over a combined batch of 31 episodes (several grouped runs), this single fix produces **3 successes out of 31 (about 10%)** — whereas all previous attempts from this chapter and the previous one combined (27 episodes in total) had produced **zero** successes. It is not a huge number, and it is not statistically solid yet at this sample size — but it is the very first non-zero result in the entire history of the project on this specific problem.

The lesson is amusing and a bit unsettling: **a notation bug and a reasoning bug look the same from the outside.** The previous chapters had spent a lot of time improving the quality of the *signal* used by the planner (sticky sampling, search reflex, data refinement) — all of this was real and necessary, but none of it touched the real flaw: the planner was choosing correctly, but then only acting on one-twelfth of its own choice.

## A reinforcement attempt: curiosity, again, but "live" this time

Emboldened by this small success, the project tried adding curiosity (Chapter 7) back in, but in a different version: instead of training the committee of guessers once and for all on frozen recordings (which had caused its collapse), it is trained **continuously, while the agent plays**, on what it actually sees, moment to moment.

First launch: three episodes out of seven crashed due to a real technical bug (fixed along the way). On the four remaining valid episodes, zero successes — but with so few episodes, this is not surprising in itself (the expected success rate at this level, on only 4 tries, would be less than half a success). The real problem, discovered after the fact: **the diagnostic that would have told us if the curiosity signal was working hadn't even been recorded.** A simple lesson but worth repeating: a diagnostic tool that exists in the code but that you forget to enable is equivalent to having no tool at all.

Once this setting was fixed and the diagnostic enabled on a new batch of six episodes, the answer became clear — and negative, but in a precise and interesting way: the "novelty" signal starts relatively high at the beginning of each episode, and then **slowly and steadily decreases** until it becomes ten to sixty times weaker, and this **regardless of what happens on screen**. The most visually striking moment of an entire episode (a tree canopy scene, the "I see something important" signal at its highest) coincides with a curiosity signal at its **lowest**. The cause: the curiosity system's short-term memory fills up very quickly with visually similar images (the agent often stays in the same small visual area), and its predictor gets used to them in a few hundred instants — after which, nothing surprises it anymore, regardless of what actually matters. The signal follows elapsed time, not scene content. The project stopped this avenue without launching a larger batch, the mechanics of the problem already being clear.

## Second attempt: reactivate the search reflex, but wired correctly

Chapter 7 had disabled the "turn your head when you are lost" reflex for the crafting mode, because its threshold didn't match the right model. But meanwhile, the two-brain agent had been introduced: the one searching for the tree still uses the old model, the exact one where the reflex had been correctly calibrated. This experiment therefore reactivates the reflex, exactly where the calibration should be valid.

Result over 7 episodes: still **zero successes**. And the most telling sign: in the episode where we can best observe what is happening, the agent goes through a long period (nearly 900 instants) where the "I see something important" signal is indeed high — comparable to the best canopy scene from Chapter 5 — and the search reflex correctly remains inactive during this whole time (it knows it is not lost). **And yet, the agent still chops zero logs during this entire period.** This is the clearest possible replica of Chapter 7's observation: correctly wiring the "I am lost" detector is useless if the real problem is converting "I see something" into "I act on it".

## Third attempt: a more "intelligent" planning method

The project's bibliography recommends a more refined planning method than the simple random draw of Chapter 4: instead of drawing 512 stories once, draw a first batch, keep the best ones (the "elites"), then do a second draw *centered on what the elites have in common*, and repeat several times. The idea: progressively converge towards better imagined stories rather than settling for a single raw draw.

Result over 8 episodes: zero successes, and above all, a **real visible regression** in behavior: the agent starts repeating a single action much more extremely than usual — on average, the most frequent action takes up twice as much time as in normal episodes, with one episode where the agent strikes empty air, motionless, 89% of the time.

The explanation fits in one sentence: **this method needs a signal that truly distinguishes good stories from bad ones in order to converge towards the good ones.** When no tree is visible (the most frequent situation in a cold-start), the signal is almost flat — the small differences between stories are just statistical noise. A method that *refines* its draw over iterations mistakes this noise for a real signal and clings to it stronger and stronger at each iteration, instead of remaining varied like a simple random draw repeated at each turn does. The more "intelligent" the method is, the more *confidently* it gets it wrong when there is, fundamentally, nothing to learn from the situation.

## Fourth attempt: train a real distance rule

Last avenue of this campaign: until now, the distance used to compare an imagined story to the goal was a simple raw mathematical distance between two embeddings — never trained to represent something precise like "how many actions actually separate me from the goal". This attempt trains an extra small function so that the distance in this transformed space more closely approximates the true number of necessary steps.

Tested offline first (before spending real gameplay time), this new distance rule passes the test with flying colors: truly close pairs of images get a distance much smaller than truly distant pairs, with a gap of about 8 times — well above the required minimum threshold. A good sign, very different from the flat collapse observed with curiosity.

But in real gameplay, over 6 episodes: still zero successes. And analyzing the images reveals a precise and novel explanation: the trained distance signal reacts very strongly to the **brightness of the scene** (daytime, twilight, inside a cave) rather than to the actual proximity of a tree — and not in a simple way: the darkest images of the whole episode yield, paradoxically, the lowest signal, not the highest. The cause: neither the expert recordings nor the random episodes used to train this distance rule contain real nighttime or cave scenes — this rule therefore never learned to distinguish "it is night" from "I am far from the goal", two very different things in the real game. A flat signal (like curiosity) fails cleanly, without breaking anything; a **confidently wrong** signal can actively mislead the planner towards what *looks* close without being close — worse, in a sense, than simply lacking a signal.

## Fifth attempt: put good gestures on the menu, and a maneuver to cover ground

The diagnosis sketched after the fourth attempt offered a precise explanation: the problem is not that the planner judges poorly, it's that the right gesture is almost never *proposed* among the 512 stories it imagines. Two ideas to directly fix this were tested together, on top of the `commit_length=4` fix already in place:

- **Put ready-made good gestures in the list**: instead of drawing the 512 stories entirely at random (with or without "sticky"), about 90 of them are now hand-written gestures — sustained forward-striking, continuous camera rotation, walking backward.
- **A cruising maneuver**: when the "I am lost" signal remains flat for too long, instead of turning its head in place (the reflex seen earlier, which cannot find anything where there is nothing), the agent sprints straight ahead and jumps over obstacles for a limited time, before handing control back to the usual planner.

Over 8 episodes: still **zero logs, zero planks, zero reward**. But the two mechanisms did **work for real**, not just get added without effect: the ready-made forward-strike gesture was indeed chosen by the planner in 3 out of 8 episodes (up to about half the playtime in one episode); the cruising maneuver triggered in one episode, where it occupied about a quarter of the time. So this is not a case where the new tools sit idle unused.

The really interesting result of this attempt is not the zero, it's this: in 3 episodes out of 8, the agent started repeating **a single action** between 83% and 100% of the time — an almost total lockdown on a single gesture. This strongly resembles what happened with the more "intelligent" planning method of the third attempt (the CEM), which also produced extreme lockdown on one action when the signal was flat. Caution, however: this resemblance is noted here as an **observation**, not yet as proof that it is exactly the same mechanism — deeper verification is underway before stating it as established fact.

This result refines the diagnosis once again: when the "how good is this imagined story" signal is flat (no tree in sight), the planner has **nothing to correct itself with**. Giving it pure random noise (previous attempts) just makes it fidget in place aimlessly. Giving it a concentrated menu of good candidates (the CEM) or ready-made continuous gestures (this attempt) makes it, conversely, **lock blindly** onto one of them — because nothing, in a flat signal, ever makes it change its mind. Hand-writing good gestures or refining the drawing method attack the problem from opposite ends, but neither gives the planner what it truly lacks: having *learned*, from real games, how a player actually searches when they see nothing interesting — rather than being handed a small frozen menu of gestures.

## The diagnosis that holds, after these five attempts

Four independent attempts each tried to improve the *quality of the signal* used by the planner to judge where to look or go: live curiosity (flat), properly wired search reflex (useless in the face of an actually correct signal), a more refined planning method (counter-productive on a flat signal), a trained distance (wrong outside its training zone). A fifth attacked the *generation* of candidates directly rather than their judgment — two zero-cost ideas, tested together — and failed too, but in a way that confirms and refines the diagnosis rather than challenging it: the two new tools worked fine, and the agent still locked blindly onto a single gesture in several episodes. The only modification that ever produced a real non-zero result, in this entire chapter and the previous one, remains the Chapter 8 fix which changes **nothing** about the quality of the planner's judgment — it only changes **how much of its own good plan it actually executes.**

The now established diagnosis: **the wall is not that the world imagined by the model is bad — it already knows how to judge a situation correctly, as proven by the offline test of the trained distance. The wall is that the stories imagined at each turn, whether drawn at random, sticky, refined by CEM, or partially pre-filled with hand-written gestures, almost never contain the right learned gesture to truly search and approach a tree — and when the proposed menu is too narrow or too concentrated, the planner locks onto it instead of continuing to explore.** It is a problem of *generating* candidate actions, not of *judging* those candidates — and the most likely path forward is no longer "hand-write better gestures" but "learn these gestures from real games". Chapter 9 explains where this path stands, and the two complementary ideas still untested at this stage.

:::

::: expert

## Framing: Four Independent Attacks on the Signal, Only One Real Lever

Following Chapter 7 (sticky sampling, scan, coverage fine-tune — all fixes on the *signal/perception* side), this chapter covers attempts #4-#7 from `docs/10_coldstart_engineering.md` on `MineRLObtainIronPickaxeDense-v0`, two-brains, seed 0.

## Attempt #4A — `commit_length`: The Fault Was in the Calling Convention

Rereading `plan()`: each replan draws 512 fresh sequences and **returns only the first action** of the best sequence — even when sticky sampling proposes a correct multi-step gesture (turn toward trunk, advance, strike), steps 2..12 are thrown away at each tick.

Fix: `commit_length` (`mine_jepa/ebwm/planner.py`, wired into `DiscreteLatentPlanner.plan()` and `SwitchingCraftPlanner.plan()`) returns the first `min(commit_length, horizon)` actions of the winning sequence. `commit_length=1` (default) = original code path, verified bit-for-bit.

**Results, `commit_length=4` alone, two-brains, sticky 0.5, scan off, seed 0 (pooling several batches, N=31):**

| | N | Logs | Successful Craft |
|---|---|---|---|
| `commit_length=4` (pooled) | 31 | 3 | 3/31 (9.7%) |
| `commit_length=1` (pooled, attempts #2-#3) | 27 | 0 | 0/27 (0%) |

Every success identical: 1 log → craft-planks → +4 planks, reward 9 (the known WM v4 rule, Chapter 6). One-sided exact Fisher 3/31 vs 0/27: **p ≈ 0.15** — not significant at this N, but **first non-zero, reproducible result in the project's history on this milestone.**

> **Lesson: a scoring bug and a calling convention bug are indistinguishable from the outside.** Attempts #2-#3 had improved the *signal* (sticky, scan, coverage) — real and necessary, but individually insufficient. The true missing piece was not a better plan but *executing more of the already correctly chosen plan*.

At 9.7%, far from the 30% milestone threshold; each success remains dependent on a lucky spawn (mean steps-to-success ≈3000 — most episodes never see an exploitable tree within the budget). Kept as default in `configs/play_craft_commit4*.yaml`; `play_craft.yaml` (`commit_length` undefined → 1) unchanged.

## Attempt #4B — Online RND: Inconclusive, Then Mechanically Ruled Out

RND predictor/target trained continuously on states visited during gameplay (`mine_jepa/ebwm/rnd.py`), z-scored bonus (`novelty_coeff=0.5`) in the two-brain's chop planner.

**Launch bug found and fixed mid-batch** (not Java flakiness): `ResNet5.out_dim` non-existent — fixed to read `state_dim` from checkpoint config. N=7: episodes 1-3 crash before fix, episodes 4-7 run cleanly.

**Valid data: N=4, 0/4 successes.** At the pooled base rate of 9.7%, the expectation over 4 trials is ≈0.4 — uninformative on its own. **The diagnostic that would have settled it was never recorded**: `novelty_mean` existed in `plan(return_info=True)` but `scan.log_std: false` suppressed the print. Verdict: **inconclusive, stop without confirmation batch** (no N=15-20 without positive qualitative signal first, a strict project rule).

**Instrumented re-run, `scan.log_std: true`, N=6:** 0/6 successes (expected ≈0.6, unsurprising). `novelty_mean` over the 6 episodes systematically shows the **same shape**: rise or plateau over the first ~50-130 steps, then **smooth monotonic decay** towards a value 10-60× lower at episode's end — regardless of episode length, survival, and what `goal_score_std` (the already validated independent signal) is doing. Correlation between the two signals inconsistent in sign and magnitude across episodes (-0.83 to +0.15).

**The sharpest data point**: episode 5 (188 replans), `goal_score_std` hits its absolute peak for the episode (0.045-0.046, comparable to the Treechop "canopy" band) exactly when `novelty_mean` is among its **lowest** values (0.0015-0.0017).

> **Reading: this is not the separation of the smoke test appearing in-game, it is its own early convergence phase.** The 256-slot ring buffer fills up in ~130 steps with visually homogeneous frames (dense canopy, spawn area); the predictor converges on this narrow distribution, after which novelty is low almost everywhere the trajectory actually goes — because the trajectory itself visits nothing that the buffer hasn't already repeatedly shown the predictor. The moment that broke this homogeneity (the peak at step 2480) wasn't detected as novel, because "different from recent training batch" and "most salient scene according to `goal_score_std`" are not the same criterion.

**VERDICT: STOP.** Same symptom as Chapter 7 (no discrimination where it counts — lost vs. found), but via a different mechanism: not an ensemble collapse (offline), but too-fast convergence on too-narrow a state distribution (online). RND's advantage over the offline ensemble is "the predictor does not collapse to a constant", not "the predictor tracks the state distribution the agent actually needs to discriminate".

## Attempt #5 — Scan Reactivated in Two-Brain Mode: Wiring Confirmed Correct, Result Still Negative

Wiring verification (before any run): `chop_planner.plan(..., return_info=True)` properly reads `goal_score_std` from `ebwm.pt`, never from `craft_wm_v4` (structurally excluded by `if scan_enabled and mode == "chop"`). Config: `flat_threshold: 0.003`, `patience: 3`, `max_replans: 40` (Treechop calibration from Chapter 7), combined with `commit_length=4`.

**Result N=7: 0/7 successes.** 2/7 episodes reproduce a bounded version (bounded by `max_replans`, not by the whole episode) of the "agent spins in circles" pathology (`a12` 51%/87%). One episode spends ~880 of the 3000 steps in the "salient scene" band (0.008-0.026) with the scan correctly inactive — **and the agent still does not chop** during this window. One episode ends in a treeless rocky/cave-type passage — a case the scan cannot solve by design.

**VERDICT: wiring hypothesis confirmed, utility unconfirmed — NO-GO.** The most detailed data point (the high-std stretch of episode 1) shows that the wall is not "agent doesn't know a tree is there" but "knowing does not convert to chopping" — exactly the two-brain diagnostic from Chapter 7, this time on a confirmed well-calibrated signal.

## Attempt #6 — True CEM (Categorical Iterative Refinement): Regression, Not Just a Failure

`DiscreteLatentPlanner` gains `cem_iters`, `cem_elite_frac`, `cem_smoothing`: generation 1 via usual `_sample_actions()`, subsequent generations resampled from a categorical table built on elite action frequencies (+Laplace smoothing). `cem_iters<=1` = original path, verified bit-for-bit on 8 cases (`ebwm.pt`/`craft_wm_v4`, sticky {0.0/0.5}, commit_length {1/4}). Measured cost: ×2.94 per call at `cem_iters=3` (~41% real throughput drop).

**Result N=8: 0/8 successes**, `chop=188 craft=0` — mode never switches. **Clear qualitative regression**: average dominant action concentration **66.3%** (50-89%) versus **35.8%** on average for `commit_length=4` alone (19-69%, only one episode exceeds 51%). Episode 8: 89% motionless attack (`a6`); episodes 2/4/5: 74-81% fixed-direction sprint-attack (`a14`), almost no rotation action in top-3.

> **Lesson: CEM refinement needs a discriminating score to refine — it has no way of knowing the score is flat.** Draw/sticky degrades gracefully when the score landscape is flat (each replan draws a still-varied pool); iterative refinement does the opposite: it mistakes the residual noise of a flat ranking for a true signal and concentrates generation after generation on that noise — the finer the method, the more confidently it commits in the wrong direction when the underlying signal has nothing to say.

**NO-GO**: 0/8, regression on the exact qualitative axis CEM was supposed to improve, real fps cost — none of the three criteria met.

## Attempt #7 — Trained Distance Metric (Destrade et al., arXiv:2601.00844): Offline Gate PASSED, Live Result NO-GO, New and Precise Diagnostic

Small projector `P` (`mine_jepa/ebwm/value_head.py::DistanceProjector`, 2 layers, `in_dim=4096` → `proj_dim=32`, ~1.06M params) trained so that `||P(z_t)-P(z_goal)||` approximates the true steps-to-goal; `ebwm.pt` frozen (49 frozen params, verified). Data: Treechop demos + coverage episodes (Chapter 7) as censored "far" pairs (one-sided hinge).

**Offline Gate (mandatory before any playtime) — PASSED cleanly**: close pairs (k≤5, n=2560) mean `pred_dist`=12.317; far/coverage pairs (n=2560) mean=97.257. **Separation ratio 7.896** (required threshold ≥1.3).

**Live N=6: 0/6 successes**, no crashes, normal action concentration (16-40%, no CEM regression). The kept GIF (only the last unsuccessful episode survives on disk, the "best successful episode" logic never triggers at 0/6) shows the agent ending up near pitch black — cave/ravine — consistent with the death noted in Chapter 7.

Pearson correlation(`goal_score_std`, frame brightness) = **-0.565** over 72 readings of an episode. Day frames (brightness>60): mean std 0.499; dark frames (≤60, twilight/night from step 480): mean std 1.174 — more than double. **But non-monotonic**: the darkest frames of the entire episode (brightness ~14-15, right before the end) have the **lowest** std of the whole trace. Cause: neither the Treechop demos (mean brightness 45.5, already fairly dark — canopy shade, but still daytime) nor the coverage episodes (mean 92.4, bright daylight) contain real night or cave scenes — the exact visual regime where this episode spends a good chunk of its time.

> **Lesson: this is a THIRD category of finding, more specific than "does not discriminate" (the Chapter 7 offline ensemble) or "discriminates correctly but it's still not the bottleneck" (the raw metric attempts). The trained metric discriminates well — a real wide dynamic range, the opposite of the RND collapse — but along a lighting/scene composition nuisance axis that the offline gate structurally could not detect, since both its close AND far pairs come from the same (mostly daytime) training distribution. A flat signal fails cleanly (all candidates tie, argmax is arbitrary but harmless); a confident-but-wrong signal can actively steer the plan toward what *appears* close without being it — indistinguishable from noise to the planner, in a sense worse than simply no signal.**

**NO-GO** on an expanded batch with this checkpoint as-is. Concrete path if revisited: targeted twilight/night/cave data collection, or photometric augmentation during projector training — no more daytime episodes.

## Attempt #8 — Proposal A (pool priming) + Proposal C (bushwhack maneuver), combined with `commit_length=4`: NO-GO, but the most informative negative of the campaign

`planner.action_pool_priming` (new block in `_sample_actions()`, `mine_jepa/ebwm/planner.py`) injects ~30 sustained forward+attack macros, ~30 continuous camera rotation, ~30 walk backward into the 512 candidate pool (Proposal A); `scan.macro: bushwhack` (`scripts/play_craft.py`) replaces the turn-in-place reflex with a bounded forward sprint-jump, triggered by the same flat `goal_score_std` on the chop planner (Proposal C). Both code paths verified bit-for-bit identical when disabled. Config: `configs/play_craft_commit4_ac.yaml`.

**N=8, seed 0: 0/8 logs, 0/8 planks, reward 0.** Against the pooled base rate of `commit_length=4` alone (3/31 ≈ 9.7%, ≈0.8 successes expected on N=8): neither significant regression, nor confirmation.

**Both mechanisms verifiably triggered** (not just wired-but-unused): the primed forward+attack macro (`a7`) hits 21-49% share in 3/8 episodes; the bushwhack macro (`a13`) hits 28% with 8 scan triggers in 1/8 episode (only when the flat signal persisted long enough to trigger).

**The finding that matters more than the 0/8**: 3/8 episodes show a single action (`a14`, the pre-existing "forward+attack" gesture) at 83-100% share — near total behavioral lockdown. This **resembles** the concentration regression of the true CEM from attempt #6 (66.3% mean versus 35.8% for `commit_length=4` alone) on a *different* mechanism (fixed menu + ground coverage macro, not iterative refinement) reaching a structurally similar failure mode.
⚠️ **Not yet quantitatively verified against the action distributions specific to `commit_length=4` alone before stating "the same lockdown" as established fact — flagged for verification, not yet a confirmed conclusion.**

> **Diagnostic Refinement: the MPC argmax has nothing to correct itself with when `goal_score_std` is flat (no trees in sight).** i.i.d. noise (attempts #1-3) makes it fidget in place; a concentrated menu (true CEM, attempt #6) or continuous macros (attempt #8) conversely make it lock blindly onto one of them, because nothing in a flat score ever comes along to correct the choice. Hand-written action generation (A/C) and score refinement applied to hardcoded macros hit the same wall from two opposite directions. The mechanism that shouldn't lock blindly is the one that *learned* the full distribution of contextual behavior (including how experts search), not the one handed a small frozen menu.

**NO-GO**, but informative: confirms that the lack of gradient in a flat score, not the source of the candidates (noise vs. frozen menu), is the common cause of the three failure modes observed since attempt #6 (fidgeting, CEM-lockdown, macro-lockdown).

## The Diagnosis That Holds, After These Five Independent Attacks

**The wall is behavioral (action generation), not perceptual (score quality) — and directly attacking candidate generation (attempt #8) confirms the diagnosis without solving it.** Three fixes targeting signal/search quality (online RND, true CEM, a trained distance metric) each failed differently — one flat, one actively regressive, one real-but-misaligned. Attempt #8, which attacks generation itself via a menu of hand-written macros rather than the score, produces a **third form of failure tied to the lack of gradient in a flat score**: behavioral lockdown, not fidgeting or noisy refinement. The only lever that ever produced a non-zero result (`commit_length=4`, attempt #4) remains a purely execution-side fix: it changes nothing about the quality of the *choice*, only the duration a choice is *held*. The world model already knows how to evaluate a situation correctly (attempt #7's own offline gate proves it); what the 512 candidate sequences — drawn randomly, sticky, refined by CEM, or partially pre-filled with macros — almost never contain is the *learned* good gesture to hold to truly search and approach a tree. Proposal B (latent policy prior trained via behavioral cloning) is now the top priority; Chapter 9 details its status and two complementary refinements yet unexecuted.

## References (Verified, from docs/references/index.md)

- Terver, Yang, Ponce, Bardes, LeCun, *What Drives Success in Physical Planning with Joint-Embedding Predictive World Models?*, arXiv:2512.24497 (2025) — the true CEM recommendation tested and invalidated in this precise regime (attempt #6).
- Destrade, Bounou, Le Lidec, Ponce, LeCun, *Value-guided action planning with JEPA world models*, arXiv:2601.00844 (2026) — the trained distance metric (attempt #7).
- Burda, Edwards, Storkey, Klimov, RND, arXiv:1810.12894 (2018) — the mechanism tested online in attempt #4B.

:::

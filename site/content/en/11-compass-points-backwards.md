---
title: "The campaign takes a pause: the compass did not turn off, it points backwards"
slug: "11-compass-points-backwards"
lang: "en"
order: 11
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft", "07-broken-curiosity", "08-the-wall-is-behavioral", "09-next-directions", "10-the-cleanest-negative"]
source_docs: ["docs/10_coldstart_engineering.md", "CLAUDE.md#Phase 5+"]
---

::: beginner

## Where we left off

Chapter 10 ended with a new suspect, not yet confirmed: what if the problem was not the way the agent proposes gestures (tested and retested throughout Chapter 8), but the way the imagined world itself **judges** those gestures once placed in a situation it knows poorly? This chapter tells the story of the test that settled this question — and closes, for now, a whole investigation campaign conducted over several chapters. The result is more precise, and a bit more concerning, than what was expected.

## The test: look at the compass itself, without making the agent play

This whole investigation, since Chapter 6, rests on a single idea: the planner compares each story it imagines to a landmark — the **centroid** (Chapter 4 explains this idea: the average of many images that represent the goal, for example "a chopped tree"). The closer the imagined story is to this landmark, the better it is judged. This comparison is the project's compass.

Until now, no one had ever directly checked, without making the agent play, if this compass gave good directions once taken out of its training ground. This chapter does exactly that: take static images, some from the expert games the model learned on (Chapter 5), others from real random starting points of the crafting game (Chapter 6) — and ask the compass to score each one, without any character moving. Nothing is trained in this test, nothing is modified in the model: it is a measurement, not a repair.

## First result, misleading if we stop there

Looking only at global averages, nothing stands out: the scores on the random starting points are not "flatter" than on the expert games — if we just compare raw averages, the random starting point would even seem, at first glance, a little *more* discriminating. That could have closed the investigation on a disappointing verdict: "the compass is fine, it's not it."

## The true result: it's not off, it's inverted

But by comparing, image by image, scenes where a tree is clearly visible very close up against scenes where there are none, a clear pattern emerges — and it is very different from what everyone had assumed since Chapter 8.

On the expert games (the compass's training ground): an image where a tree canopy fills the whole screen gets a significantly higher score (about 6 times higher) than an image of an open, treeless meadow. This is exactly what was expected — the compass works where it learned.

On real starting points of the crafting game: a forest clearing with trees nearby, or a dense jungle right in front of the agent, gets a **lower** score than an open meadow without a single tree, or even an empty beach. Same thing on other images taken from real game restarts: a tree trunk filling the whole frame gets the lowest score of its entire comparison group, while an empty meadow gets one of the highest.

So it is not that the compass turns off and indicates nothing anymore (which was the hypothesis since Chapter 6) — **it indicates something very clearly, but in the wrong direction.** Bringing the agent closer to a tree, in this specific situation, makes its score *drop* instead of rising.

## Why this is worse than a flat signal

A flat signal ("I don't know," like the broken curiosity of Chapter 7) is honest: it fools no one, it just says "no idea". A signal pointing in the wrong direction is worse: it gives the planner false confidence, and actively pushes it away from what it is looking for, without ever letting on that something is wrong. It is the same kind of trap that Chapter 10 had already spotted for a small distance rule trained separately (confused by scene brightness) — except that this time, it is the core mechanism of the entire project, the one used since the very beginning of the investigation, that is at fault.

## What this closes, and what it doesn't

This result finally answers the question left open at the end of Chapter 10: does the problem come from the generation of candidate gestures, or from the judgment passed on them by the imagined world? The answer, now confirmed by direct measurement and not just deduced by elimination: **it's the judgment.** The wall is not "the agent doesn't know what to do", it is "the compass points the wrong way as soon as it leaves its training ground."

After seven attempts to refine or replace the way gestures are proposed (Chapter 8), then this direct test on the judgment itself, the investigation campaign on this specific problem **takes a pause here** — not an abandonment, a pause. Two solid findings emerge:

1. **Gesture generation is not the true bottleneck.** Three very different methods for proposing better candidate gestures all failed to move the needle, including on confirmed playable starting points where a tree was clearly visible (Chapters 9-10).
2. **The imagined world's compass actively points backwards** once taken out of the terrain it was trained on.

## The menu for what's next (nothing is launched yet)

Four paths now exist to resume this work, ranked from the cheapest and most targeted to the most expensive and uncertain — none has been launched yet, it is a menu, not an action plan:

1. **Fix the compass exactly where it gets it wrong** (the cheapest). This test pinpointed exactly what is broken (the direction, not the intensity of the signal) and on which images (those from the crafting game, not the expert games). We can therefore collect real "close" and "far" examples directly on this specific game, and train a small correction on them — without necessarily touching the model's main weights.
2. **A memory of already visited places.** Instead of comparing every image to the same fixed landmark, the agent could remember the areas it has already explored during the episode and target unknown areas in priority — but only if this choice is made by counting visited places, not by reusing the same broken compass to judge "how close am I to an unknown area" (otherwise the same problem reappears under another name).
3. **A second, slower brain for searching.** A separate model that would plan on a longer timeline ("find a forest") before handing control to the fast model already used to chop the tree once close. The most ambitious idea of the four, but also the most expensive: it would require training a new model, and we would have to ensure it learns properly on realistic starting points, not just on the same expert games that produced the current problem.
4. **Copying real human search games** — relegated to last place, for a simple reason: this test just showed that the problem is not the lack of good gesture proposals, but their poor judgment. Copying more human behaviors does not fix a backward judgment, unless combined with one of the previous three paths.

## And now

As with every previous chapter in this project, this result is reported exactly as it is: neither dressed up as a victory, nor presented as a definitive failure. It is a pause in the work after a long and honest investigation, with a clear diagnosis and a clear menu for resuming it.

:::

::: expert

## Context

Chapter 10 (attempt #9) ended on a hypothesis posited by elimination, not directly confirmed: after three mechanically different candidate generation mechanisms (hand-written macros + bushwhack maneuver, true CEM, BC actor) all failed to move the needle — including on confirmed viable spawns with a visible tree (`spawn_diag`) — the only component never tested in isolation remained the native goal-centroid scoring of `ebwm.pt` itself, the mechanism upon which every attempt since attempt #1 has been built without ever verifying it directly. This chapter covers attempt #10 from `CLAUDE.md`/`docs/10_coldstart_engineering.md`: a purely offline diagnostic that tests this scoring directly, then the (provisional) closure of the campaign that follows.

## Method (attempt #10, PC, 2026-07-21, no MineRL/Java, no training)

`scripts/diagnose_score_generalization.py` + `configs/diagnose_score_generalization.yaml` reuse `DiscreteLatentPlanner._sample_actions()`/`_score()` exactly as is — the exact code already used live by the scan and `spawn_diag` — applied offline on 251 static images: 160 Treechop frames (`data/minerl_goal/episodes.npz`, the training data of `ebwm.pt` itself, 40 episodes × 4 internal offsets to vary distance to tree), 11 true `MineRLObtainIronPickaxeDense` cold-start spawn frames (`assets/spawn_thumbs/` from attempt #9), and 80 frames from attempt #3's coverage episodes (`data/minerl_coverage/episodes.npz`, sliced in 400-step blocks to bypass the known all-`False` `dones` bug from shard merging, attempt #7 fix reused as-is). Same hyperparameters as the live two-brain chop planner (horizon=12, n_candidates=512, sticky_prob=0.5), seed 0. `ebwm.pt` loaded frozen, `requires_grad_(False)` verified on all parameters — no checkpoint modified, no training.

## Raw Aggregate Result — a near-wash, and alone would have DISPROVED the hypothesis

| Group | n | mean | median | std | min | max | p10 | p90 |
|---|---|---|---|---|---|---|---|---|
| treechop | 160 | 0.00742 | 0.00459 | 0.00716 | 0.00022 | 0.03484 | 0.00126 | 0.01996 |
| obtain_spawn | 11 | 0.01085 | 0.00977 | 0.00565 | 0.00165 | 0.01900 | 0.00572 | 0.01794 |
| obtain_coverage | 80 | 0.00833 | 0.00610 | 0.00700 | 0.00055 | 0.04225 | 0.00185 | 0.01625 |

Median and p90 for Obtain are comparable, if not slightly *higher*, than those for Treechop — no simple "the score flattens on Obtain" story survives the raw numbers alone. Read in isolation, this table would have been an argument against the hypothesis of a problem on Obtain.

## Paired, Frame-by-Frame Result — a sharp inversion, not a flattening

| Source | Tree clearly visible/close | `goal_score_std` | Treeless / open / distant | `goal_score_std` |
|---|---|---|---|---|
| Treechop (offset 0.5, native dist.) | canopy fills frame (ep007) | **0.0274** | meadow+hut, distant trees (ep015) | 0.0027 |
| | canopy tunnel (ep012) | **0.0171** | open meadow, distant treeline (ep016) | 0.0037 |
| | | | meadow, no trees (ep033) | 0.0017 |
| | | | open meadow, distant treeline (ep037) | 0.0064 |
| True Obtain Spawn (attempt #9) | forest clearing, close trees | 0.0060 | open meadow | **0.0190** |
| | dense jungle, close trees | 0.0057 | open meadow | **0.0179** |
| | | | beach, no trees | 0.0130 |
| | | | dark cave, no trees | 0.0069 |
| Obtain Coverage (true restarts) | trunk fills frame | 0.0030 | open meadow | **0.0176** |
| | dense jungle canopy | 0.0098 | open plains | **0.0146** |

Methodological note: Treechop frames at offset=0.0 ("spawn") actually mostly show sky or underwater views with random camera orientation — an incidental finding in itself — so the Treechop comparison uses offset=0.5 frames, taken right in the middle of an actual chopping demonstration.

On Treechop, close-canopy frames score about **6× higher** than distant/treeless frames (0.017-0.027 vs 0.002-0.007) — reproducing, from a totally independent offline sample, the original live calibration of this very project ("canopy fills frame" band 0.02-0.056 vs "lost" band 0.0002-0.002, Chapter 8). On both Obtain samples, gathered independently, the direction **inverts**: frames closest to a tree/canopy score at or below the bottom of the group's range (0.003-0.010), while open, treeless frames hit the top of the range (0.013-0.019) — matching or exceeding Treechop's "visible tree" band, without showing a single tree.

## Verdict: hypothesis confirmed, in a more precise form than expected

> **Lesson: this is not a magnitude collapse (RND's failure mode, Chapter 7) — it is a directional confusion in the native, raw, untrained goal-centroid scoring of `ebwm.pt` itself.** On the free spawn visual distribution of `MineRLObtainIronPickaxeDense`, the goal-centroid distance measurably discriminates something — the aggregate spread is not flatter than on Treechop — just not proximity to a tree, and in every pair of images verified here, it points in the WRONG direction: a closer tree scores as less promising than an open, treeless scene. This is the same "a confident-but-wrong signal is worse than an honestly flat signal" pattern already diagnosed in Chapter 10 for a *separately* trained distance metric (there, a brightness confusion) — shown here for the first time on the very mechanism that every attempt since attempt #1 has built upon and never tested in isolation. This closes the note from attempt #9 ("flagged as a hypothesis pushed by elimination, not yet as established fact") with a direct answer: yes, and the mechanism is a directional confusion, not a collapse.

No checkpoints modified (`ebwm.pt` loaded read-only throughout the diagnostic, as in every previous attempt). Full per-frame CSV and boxplot comparing the three groups: `assets/diagnostics/score_generalization.csv`, `assets/diagnostics/score_generalization.png`. A diagnostic, not a repair — no planner or scoring changes resulted from this test, by design of the protocol.

## The Campaign Takes a Pause: Synthesis of the Two Convergent Findings

The campaign (attempts #4 to #10) converged on two independent and confirmed findings:

**(a) the quality of action generation is not the bottleneck** — three mechanically different fixes (hand-written macros, true CEM, a trained BC actor) all failed to move the needle, including on demonstrably viable spawns with visible trees (attempt #9);

**(b) the native goal-centroid scoring of `ebwm.pt`**, the mechanism upon which every attempt was built, **actively inverts** on the spawn distribution of `MineRLObtainIronPickaxeDense` — a closer tree scores lower than an open/treeless view, the opposite of its behavior on Treechop (attempt #10).

The wall is not "the agent doesn't know what to decide" — it is "the compass points backwards outside of its training distribution."

## Four Candidate Tracks, Ranked by Cost/Risk — none launched yet

1. **Targeted score correction on the Obtain domain (new, cheapest, most directly targeted).** Attempt #10 identifies exactly what is broken (direction, not magnitude) and on which distribution (Obtain, not Treechop) — a small trained fix (adapter or distance head) with true close/far supervision collected FROM Obtain itself (not Treechop+coverage, which the failed attempt #7 repair used) is now a precisely scoped experiment rather than a shot in the dark. The cheapest of the four; does not require touching `ebwm.pt`'s main weights if implemented as a small adapter head, under the project's standard anti-collapse discipline.
2. **Topological memory / episodic frontier.** Build a map of visited states during the episode and target frontier sub-goals instead of a single fixed centroid — but only if frontier selection is driven by state visitation/coverage (Go-Explore style), NOT by latent distance to a fixed goal. If it reuses the same broken centroid distance metric to judge "how close am I to a frontier point", it inherits finding (b) and fails the same way. Does not require retraining `ebwm.pt`. Second cheapest, contingent on making this design choice correctly.
3. **H-JEPA — hierarchical world model.** A second, slower world model that would plan "find a forest" on a long horizon, before handing control to the existing fast model to "chop the tree" once close. Conceptually the most direct answer to an authentically long-horizon, sparse-goal problem, but must be trained deliberately on an Obtain-type spawn distribution, otherwise it risks inheriting the same Treechop-only calibration flaw one floor up. The highest cost/risk of the four (a new model to train, and "what counts as a sub-goal" is itself a non-trivial design problem).
4. **BC fine-tuning on human search frames.** Deprioritized — attempt #9 already showed that better/more diverse candidate proposals do not help when the evaluator scores them backwards; this option improves proposals, not evaluation, so it does not attack finding (b) at all, unless combined with one of the preceding tracks.

None of these four tracks is launched — it is a menu for future resumption of work, not a committed plan. The campaign stops here with a clean diagnosis, not an abandonment: after seven attempts on action generation (attempts #4-#9) and a direct test on the evaluation itself (attempt #10), both halves of the planning mechanism have each been isolated and measured separately — a discipline of honesty unchanged since the first chapter of this site.

## References (Already verified, from `docs/references/index.md`, no new citations in this chapter)

This chapter relies on no new bibliographic references: attempt #10 is a direct measurement diagnostic, not the application of a published method — it reuses the planning code already motivated by the references cited in Chapters 8 and 10 (Terver et al. arXiv:2512.24497, Destrade et al. arXiv:2601.00844, Burda et al. arXiv:1810.12894).

:::

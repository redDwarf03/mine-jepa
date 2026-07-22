---
title: "Two paths from the menu put to the test: repairing the compass fails a third time, memory of visited places produces the second real success of the campaign"
slug: "12-memory-of-visited-places"
lang: "en"
order: 12
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft", "07-broken-curiosity", "08-the-wall-is-behavioral", "09-next-directions", "10-the-cleanest-negative", "11-compass-points-backwards"]
source_docs: ["docs/10_coldstart_engineering.md", "CLAUDE.md#Phase 5+"]
---

::: beginner

## Where we left off

Chapter 11 ended with a pause in the work and a menu of four paths to resume the investigation into the cold start (the agent having to find its first tree without ever having seen one). None of these paths had been launched yet — it was a menu, not a committed plan. This chapter tells what happened when the first two, the cheapest, were finally tested for real — both dated July 21, 2026, in the project log. The results are very different from each other: one closes a door for the third time in a row, the other opens a new one with a real success — modest, but real and honest.

## Path 1: Repairing the compass precisely where it goes wrong — failed again, and in a more precise way

Recall from Chapter 11: the project's compass (the score comparing each imagined story to the memory of "a chopped tree", see Chapter 4) turned out to point **backwards** once taken out of its training ground — a close tree received a lower score than an empty meadow. The cheapest path on the menu proposed fixing this with a small additional rule, trained this time with real "close" and "far" examples taken directly from the crafting game (not from the expert Treechop games, as in the previous attempts of Chapter 8).

On paper, the result looked like the best of the entire investigation: the new rule separated "close" images from "far" images better than all previous attempts, and it even passed a brand-new test — manually judging, on real game screenshots, if a close tree indeed received a better score than a treeless scene. It was correct 21 times out of 24 (87.5%).

But a deeper test dismantled this result. This project has long followed a simple rule: any new path must be checked for a trap already spotted twice (Chapter 8, then again in Chapter 9 when a planned repair had worsened the same problem) — a distance rule that, instead of truly judging the distance to the tree, actually contents itself with detecting whether the image is bright or dark (the scene's brightness). This time, the verification was pushed one step further than planned: someone had the idea to check if the **test set itself**, the one used to grade the rule "good" or "bad", was biased. The result: yes, it was, almost completely — the images chosen as "close tree" were, almost systematically, much darker (dense forest) than the images chosen as "no tree" (open meadow, beach). The link between brightness and label was almost perfect.

In other words: the beautiful 87.5% result was most likely not real proof that the rule finally understands where the tree is — it was the same old shortcut (brightness) detected for a third time, hidden behind a test that, unintentionally, measured the exact same thing as the shortcut itself. This is the **third time** this precise trap has appeared, with three different ways tried to correct it (artificially varying the light during training in Chapter 9, changing the training examples here) — and each time, the "brightness" shortcut remains stronger than ever. The lesson that now stands out: this shortcut most likely lives **within the vision model itself**, the one that learned to see in the first place (Chapters 1-2) and which these small repairs never touch — not in the way we train the small rule placed on top. This specific path on the menu is therefore closed, unless we attack the starting vision model directly, which is a much heavier project, set aside for now.

## Path 2: A memory of already visited places — built, tested, and a real second success

The second path on the menu proposed a different idea: instead of comparing each image to a fixed landmark (the compass, which we just confirmed for the third time goes wrong outside its training ground), why not give the agent a simple memory of the places it has already explored during the current episode, and push it to go look elsewhere?

The important point, respected to the letter since Chapter 11: this memory must owe **nothing** to the broken compass. It is constructed in a completely different way, without any learning: at each step, the agent already knows the effect of its own action (move forward, turn left, turn right — like a player who counts their own steps and turns with their eyes closed). By adding up these known effects over the course of the episode, we reconstruct an approximate position on an invisible grid, and we count how many times each cell of this grid has already been visited. When the agent seems to turn in circles without a goal, instead of making it spin in place (the old reflex of Chapter 7, which can find nothing where there is nothing) or dashing straight ahead blindly (Chapter 8), we now push it towards the least-visited direction on the grid.

First test, very small (3 episodes): the mechanism triggers properly, behaves visibly differently from the old reflexes, and the coverage map indeed grows over time. No sign of the problem seen several times before (the agent starting to repeat a single action almost all the time). This test was only meant to verify that nothing was broken — not yet to judge if it works.

The real test, larger (20 episodes): **1 log chopped and planks crafted out of 20 trials (5%)**, average reward 0.45 — about 12% better than the MineRL baseline for an agent playing at random. This is the **second non-zero result of this entire long investigation**, after the small correction in Chapter 8 ("execute its own good plan longer", 9.7% success rate on its own batch of tests) — and it is the first to come from a completely different mechanism: not a better way to choose actions, not a better judgment, but a simple memory of "where have I already been". In the successful episode, the agent had indeed explored a large part of the map before finding its tree — and its behavior, at the moment of chopping, resembled that of a real lumberjack (the same actions that had already worked in Chapter 6), not an action repeated by accident.

## Honesty on what this 1 out of 20 proves, and what it does not prove

We must be clear, as with every figure in this project: a 5% success rate is of the same order of magnitude as the 9.7% of Chapter 8 — not statistical proof that this new path is better at this sample size. A classic statistical test would not distinguish these two figures from each other with confidence.

But this result has two qualities that make it truly interesting, not just another number: it is clearly above the two previous attempts that had yielded zero out of eight trials each (Chapters 9 and 10), and above all, across the 20 episodes of this batch, **none** show the action-locking problem that had ruined several previous attempts (Chapter 8). It is therefore the second independent method — after the correction of Chapter 8 — to produce a real success without ever showing this broken behavior. It is not a confirmed breakthrough. It is a real positive point, honest, which deserves to be kept and extended rather than tucked away in a drawer.

One last honest detail: the batch of 20 episodes was managed by a process that encountered a technical infrastructure issue before it could write its own formal report — the figures above were therefore verified directly, episode by episode, in the raw execution logs, rather than copied from a final report that could not be produced.

## Where the Chapter 11 menu stands now

Of the four paths proposed in Chapter 11: the first (repairing the compass) is now closed for good, unless a much heavier repair is made to the vision model itself. The second (memory of visited places) is built, tested, and yields a real positive signal to extend. The last two — a second, slower brain to search for a forest, or copying real human search play — remain, as in Chapter 11, unlaunched.

:::

::: expert

## Context

Chapter 11 closed the investigation campaign on cold start with two converging findings (action generation is not the bottleneck, native goal-centroid scoring of `ebwm.pt` is inverted outside the Treechop distribution) and a menu of four candidate tracks ranked by cost/risk, none launched. This chapter covers attempts #11 and #12 from `CLAUDE.md`/`docs/10_coldstart_engineering.md` (PC, 2026-07-21) — the first two paths of the menu, executed in the announced order of priority.

## Attempt #11 — score correction targeted at the Obtain domain (candidate direction 1): NO-GO, third and clearest confirmation of a brightness shortcut in the frozen encoder

**Implementation.** `scripts/train_value_projector_obtain.py`: reuses the distance projector idea from attempt #7 (Destrade et al., arXiv:2601.00844), but with close/far pairs sourced **entirely from Obtain** — the 40 real `MineRLObtainIronPickaxe-v0` demos plus the coverage episodes from attempt #3, zero Treechop data. Added an unprecedented mandatory gate: a direction verification on real manually-labeled frames kept in reserve (attempt #7 never had the means to run this test).

**Offline gates — the best apparent result of the entire campaign:**

| Metric | Attempt #7 (Treechop+coverage) | Attempt #11 (Obtain only) |
|---|---|---|
| Separation ratio | 7.9 | **11.26** |
| Obtain direction ratio | — (not measured this way) | **1.21** |
| Correct direction per pair (manual labeling) | — (gate non-existent) | **21/24 (87.5%)** |

**The brightness shortcut, verified, is worse than all previous variants:**

| Variant | Correlation with brightness |
|---|---|
| Attempt #7, original | 0.117 |
| Attempt #7, in real play | -0.57 |
| ColorJitter "repaired" (follow-up attempt #8) | 0.498 |
| **Attempt #11, sourced from Obtain** | **0.643** |

The developer pushed the verification one step further than the instruction: the apparent 87.5% correct direction result was itself tested against the brightness shortcut — `corr(is_tree_close, brightness) = -0.917` on the manually labeled test set itself. The "close tree" frames (dense forest, jungle) were systematically much darker than the "no tree" frames (open meadow, beach) **by construction** of how this test set was assembled. The apparent result was therefore very likely the same shortcut re-detected, not authentic geometric learning of proximity to the tree. NO-GO correctly pronounced; the live play run was intentionally skipped (no live evaluation spent on a checkpoint self-diagnosed as confounded). `checkpoints/value_projector_obtain.pt` retained, shelved, not deployed — same status as `value_projector_colorjitter.pt`.

> **Lesson, now confirmed three times independently (original attempt #7, ColorJitter, and this Obtain source): any small head trained on top of the frozen latent space of `ebwm.pt` finds brightness as the cheapest available shortcut, regardless of the domain supplying the training/validation pairs — because the shortcut very likely lives in the representation of the frozen encoder itself, which these three attempts never touched. Changing the downstream training data changes the story the projector tells about itself, not the shortcut it actually uses.**

Path 1 of the Chapter 11 menu is closed, unless resumed as a fix on the encoder side (adapter fine-tuning or explicit brightness invariance constraints on `ebwm.pt` itself, under the project's strict anti-collapse discipline) — outside the scope of a simple downstream fix. No checkpoints modified except the new `value_projector_obtain.pt` (`ebwm.pt`, `craft_wm_v4.pt` read-only).

## Attempt #12 — topological frontier memory (candidate direction 2): built, verified, then confirmed at N=20

**Framing.** Designed to avoid by construction the two known failure modes of a coverage signal: RND (attempt #4B) converges on time elapsed, not scene content; any frontier metric built on the latent distance of `ebwm.pt` would inherit the directional confusion confirmed in attempt #10. The choice: a coverage signal **without any learned function and without any dependency on the frozen encoder**.

**Implementation.** `mine_jepa/ebwm/frontier.py::FrontierTracker`: position `(x, y, yaw)` reconstructed via dead reckoning from the already known semantics of the executed discrete actions — no learned function, no dependency on `ebwm.pt` or `craft_wm_v4.pt`. Binned into a grid of visit counters; when triggered, targets the least-visited neighboring heading. Wired as a new option `scan.macro: "frontier"` (`configs/play_craft_commit4_frontier.yaml`) — `planner.py` itself is untouched (pure macro, no scoring changes), and any other value of `scan.macro` remains bit-for-bit identical.

**Sanity check N=3:** clean, no crashes. Mechanism visibly distinct from existing turn/bushwhack macros (log confirmed: turn to least-visited heading, then cruise); `unique_cells_visited` grows over the course of the episode (419/939/970). No action-locking (maximum share of a single action 45%). 0/3 successes — uninformative at this N, which was not the purpose of the sanity check.

**Debt flagged along the way, not introduced by this attempt**: `scripts/play_craft.py` never wires `agent.seed` into the MineRL environment for any config — `agent.seed: 0` in these YAMLs is currently a no-op. Reproducibility debt already present across the entire campaign, not specific to attempt #12.

**Confirmation batch, N=20, seed nominally 0 (subject to the caveat above) — the result that counts.**

- **1/20 logs chopped + planks crafted (5.0%), average reward 0.45 (+12% against the random MineRL baseline of ~0.4).**
- Second non-zero result of the entire campaign, after `commit_length=4` alone (pooled 3/31, 9.7%) — and the first to come from a mechanism entirely outside action generation / scoring (pure coverage, no learned function, no dependency on the encoder).
- The single success: reward=9, +4 planks, `steps=3000`, `unique_cells_visited=908` (among the highest in the batch), action profile a14=42%/a13=12%/a6=10% — healthy, no action-locking spike.
- Across the 20 episodes, normal action concentration throughout (maximum share of a single action 63%, most between 20-45%) — **no action-locking anywhere in this batch**, in direct contrast to attempts #6 and #8 (CEM refinement and pool priming had both regressed towards frozen, concentrated action profiles).

**Honest framing.** 1/20 (5%) is of the same order of magnitude as the 9.7% base rate — not a statistically proven improvement at this N (a Fisher's exact test would not distinguish the two). But it is clearly above the 0/8 of attempts #8 and #9, and it is notable for producing a real success without any behavioral pathology — the second independent mechanism (after `commit_length`) to do so. Not a confirmed breakthrough; a real positive data point, to be kept and extended rather than shelved.

**Process note.** The launch of the 20-episode batch encountered an infrastructure error (session limit) before it could produce its own formal report. The figures above were extracted and verified independently, episode by episode, directly from the raw execution log (`logs/coldstart_attempt12_frontier_n20.log`), not copied from a report that could not be delivered.

## Where the Chapter 11 menu stands now

1. **Targeted Obtain score correction** — closed (attempt #11, NO-GO), unless resumed on the encoder side.
2. **Topological frontier memory** — built, verified, confirmed at N=20: real positive signal, not statistical proof, without behavioral pathology; path to extend (larger N, or combination with `commit_length`/other non-pathological levers).
3. **Hierarchical H-JEPA** — unlaunched, highest cost/risk on the menu.
4. **BC fine-tuning on human search** — unlaunched, already deprioritized in Chapter 11.

`ebwm.pt` and `craft_wm_v4.pt` remain intact across both attempts in this chapter: attempt #11 only trained a separate, undeployed projector; attempt #12 introduces no learned parameters.

## References (Already verified, from `docs/references/index.md`, no new citations in this chapter)

- Destrade, Bounou, Le Lidec, Ponce, LeCun, *Value-guided action planning with JEPA world models*, arXiv:2601.00844 (2026) — the distance projector method adopted (with a new source of supervision) in attempt #11.
- Burda, Edwards, Storkey, Klimov, RND, arXiv:1810.12894 (2018) — the coverage mechanism discarded by construction during the design of attempt #12 (`docs/09_curiosity_coldstart.md`).

This chapter relies on no new bibliographic references: the frontier memory mechanism of attempt #12 (dead-reckoning visit counts, without a learned function) is described informally in `CLAUDE.md`/`docs/10_coldstart_engineering.md`, in the spirit of state-coverage-driven exploration methods (e.g., Go-Explore) — this family of methods has no verified entry in `docs/references/index.md` to date and is therefore not cited here with an arXiv identifier.

:::

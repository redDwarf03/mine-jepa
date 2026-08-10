---
title: "A fifth confirmation for the brightness shortcut, a false alarm that wasn't one, and a 144-point riddle still unanswered"
slug: "15-fifth-confirmation-false-alarm"
lang: "en"
order: 15
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft", "07-broken-curiosity", "08-the-wall-is-behavioral", "09-next-directions", "10-the-cleanest-negative", "11-compass-points-backwards", "12-memory-of-visited-places", "13-blind-rescue", "14-a-web-giant-put-to-the-test"]
source_docs: ["CLAUDE.md#Phase 5+"]
---

::: beginner

## Where we left off

Chapter 14 ended on a decision: the heaviest option on Chapter 11's menu (building a second,
slower world model whose job is to "find a forest" — an idea nicknamed **H-JEPA**) was now
justified by real evidence rather than by a merely plausible argument, because even the most
direct and most careful retraining of the existing model had failed to cleanly fix the brightness
shortcut. Before starting that expensive piece of work, this chapter covers three things that
happened just before and just after that decision: a re-reading that avoided building a useless
tool, one last cheap test that closed the door for good, and two separate findings from re-running
a Chapter 13 mechanism at larger scale.

## A re-reading before building anything

One idea, already floated but never tested, was to hand-build a small vision tool that would spot
tree foliage by its distinctive colouring (the greens and browns typical of a trunk and its
leaves) instead of using the project's broken compass. Before spending time building it, someone
calmly re-read everything the previous chapters had already established. The reasoning: CLIP, in
Chapter 14, is a giant model trained specifically to resist lighting changes across hundreds of
millions of photos — and it still hit the same shortcut. A home-made tool, far simpler, was
therefore very likely to do nothing but repeat the same lesson a fifth time, at a real cost in
work, without producing new information. Recommendation: do not build it, and invest instead in
the only two project mechanisms that have already produced real results without relying on a
direct visual judgement — the memory of visited places (Chapter 12) and longer execution of a
good plan (Chapter 8).

## One last cheap test, all the same

A narrower and far less expensive idea was nonetheless tested directly, because it reused a tool
already built and already validated: the small drowning detector from Chapter 13 works by
comparing colour **ratios** (blue against red and green) rather than raw values — which is
precisely what lets it spot a drowning as well by day as by night. Could that same trick, applied
no longer to the whole screen but to each small patch of the image taken separately, spot tree
foliage in the same way, independently of how bright the scene is?

The test reused exactly the same 251 frames already used in every previous diagnostic
(Chapters 11 and 14), with the same hand-placed labels ("tree close" or "no tree").

## The result: half good, and worse than ever on the other half

The first half of the test passes: this patch-by-patch calculation does separate frames with a
nearby tree from frames without one — a genuinely correct directional result, within the expected
range.

But the second half — checking that this score is not just a roundabout way of measuring
brightness — fails almost as badly as the worst result seen so far, CLIP's in Chapter 14. On the
small hand-labelled set, the correlation with brightness is nearly as strong, in the opposite
direction. And crucially, this time the problem is not confined to the small test set: it shows up
broadly, across all 251 frames, on the original tree-chopping environment as much as on the
crafting one.

## The clearest explanation of the whole investigation

The colour-ratio trick works for water because the water's tint covers **the entire screen** in
the same way — exactly the kind of global shift that dividing colours by one another cancels out.
But the problem here is not a global shift: it is that, in this game as in reality, **dense
forests are by nature darker scenes, and open meadows brighter ones**. That is not an artefact of
one particular calculation, it is a feature of the world the game imitates. No colour calculation,
however clever — learned, off-the-shelf, or hand-built to resist lighting changes — can
disentangle "this is dark" from "this is a forest" when, in the available data, the two are
almost the same thing.

This result closes, this time for good, the entire "maybe a cleverer colour calculation would fix
it" line. Five different ways of attacking it — a small learned module, that same module retrained
on other examples, an artificial variation of brightness during training, a giant off-the-shelf
model, and now this patch-by-patch calculation — have all hit the same wall. Fixing the compass
(option 1 on Chapter 11's menu) stays closed, and this time for a stronger reason than before: it
is not that no attempt has yet found the right setting, it is that this kind of fix has
structurally no chance of working on this particular problem.

## Separately: the anti-drowning rescue re-run at scale

Chapter 13 left the anti-drowning rescue move with an encouraging verdict, but tested on only 6
runs. A much larger batch — 20 runs, combining Chapter 12's memory of visited places with
Chapter 13's corrected anti-drowning rescue — has now been executed, with a precise goal: does
that rescue still hold at this scale, and — the question left open until now — does cutting down
the drownings finally let the agent chop wood?

**Drowning really is fixed at scale**: 3 runs out of 20 end in a drowning (15%), against 12 out
of 20 (60%) in the very first batch from Chapter 12. Runs that go all the way through without
being cut short rise from 8 out of 20 (40%) to 12 out of 20 (60%). The rescue therefore holds, not
just on the 6 runs where it was validated, but at a much larger scale.

**But chopping wood stays at zero**: 0 logs out of 20, 0 planks out of 20 — even though more runs
now get a genuinely fair chance to look for a tree. This is not a significant step backwards from
the previous chapter (1 success out of 20) — the difference between 0 and 1 out of 20 tries says
nothing reliable at that sample size — but it confirms, once more, what was already established:
surviving longer and knowing how to search and approach effectively are two separate problems.
Fixing one did not automatically fix the other.

## A lesson in method: a false alarm is not a real stop

The report accompanying this batch of 20 runs originally claimed the test had been interrupted by
a "serious infrastructure failure" after only 4 episodes. An independent check showed this was
**false**: the program driving these runs launches a separate Minecraft process for each episode,
one at a time. A passing technical incident on a single episode therefore never stops the program
orchestrating the whole batch — it simply moves on to the next episode. The raw logs confirm that
all 20 episodes ran from start to finish, without any intervention. The lesson taken away: an
error affecting a single episode in this harness is not the same thing as a failure that halts the
whole batch — you have to verify that the orchestrating program really did continue before
declaring a full stop.

## The reward=144 riddle

A curious detail was already sitting in the logs of that same batch of tests, without having been
dug into: one episode had shown, just once, a reward of 144 — a figure far higher than anything
ever seen elsewhere in this campaign (a normal success is worth a reward of 9). The game program
was given a new observation tool, switchable at will, which now displays the maximum reached for
**every** inventory item over an episode, not just the wood and planks tracked so far. A new batch
of 12 runs was launched with that tool enabled, on the same configuration: reward of 0.000 on all
12 episodes, and the only item ever to appear in an inventory across the whole batch was
**ordinary dirt** (between 1 and 30 units per episode, picked up unintentionally while walking or
attacking) — an item that earns strictly no reward in this game. The original episode that had
shown 144 had already ended before this tool existed, so its exact state at that precise moment
remains unrecoverable. That figure never recurred across these 12 new attempts and remains, for
now, an isolated and unexplained event — parked as a documented curiosity, with no effect on the
campaign's conclusions, rather than pursued without a much larger sample.

## What happens next

This chapter closes a long line of investigation (score fixes based on colour or brightness) while
separately delivering one solid piece of good news at scale (the anti-drowning rescue) and one
unresolved riddle that changes nothing about the main diagnosis. As always in this project: good
results and disappointing results are reported with the same precision, and nothing is dressed up
to look better than it is.

:::

::: expert

## Context

Chapter 14 concluded that the condition set for committing to candidate direction 3 from
Chapter 11's menu (hierarchical H-JEPA) was met by empirical evidence, not merely by a plausible
argument: even direct fine-tuning of `ebwm.pt` with photometric augmentation had produced only a
mixed result. This chapter covers attempt #15 (`CLAUDE.md#Phase 5+`; no corresponding entry in
`docs/10_coldstart_engineering.md` to date — a documentation gap flagged explicitly in `CLAUDE.md`
itself): a reassessment of the H-JEPA proposal, a narrow offline test that followed from it, and an
N=20 confirmation batch combining the mechanisms of Chapters 12-13.

## Reassessing the H-JEPA proposal, without code

An Explorer proposal for literal H-JEPA had been submitted. Before any development, a cold
reassessment noted that CLIP (Chapter 14) — a 400M-image model built specifically to resist
photometric variation — had already failed the same dual gate that a hand-built hue/edge heuristic
would face. Consequently, building that heuristic was judged very likely to produce nothing but a
5th confirmation, at a real engineering cost, without new information — **recommendation not to
build it**. Complementary recommendation: the campaign's only two working mechanisms that do not
rest on a visual judgement (`FrontierTracker`, `commit_length`) are the better next investment,
rather than grafting more visual content bias onto them.

## Narrow offline test: chrominance ratios per spatial tile

A more targeted and cheaper idea arising from that reassessment was tested directly:
`mine_jepa/ebwm/hazard.py` uses **lighting-invariant channel ratios** (not raw values) — a choice
that works for water because the underwater tint is a global, uniform cast across the whole frame.
Does that same trick work for foliage, computed **per spatial tile** rather than whole-frame?
`scripts/diagnose_chroma_tile_generalization.py`, on the same 251-frame set and the same manual
labelling as every prior diagnostic (attempts #10, #14).

**Result: MIXED, but the brightness gate fails almost as badly as CLIP's worst case.**

- Direction gate: **PASSED** (separation ratio 1.482, ≥ the 1.3 bar).
- Brightness-independence gate: **FAILED**. r = -0.925 on the hand-labelled set (against -0.947
  for CLIP — essentially tied for the campaign's worst, opposite sign); r = -0.585 across all 251
  frames (treechop -0.748, obtain_spawn -0.600, obtain_coverage -0.671) — a broad effect, not
  confined to the small labelled set.

## Interpretation, the sharpest of the campaign

> **Lesson: ratio normalisation removes GLOBAL brightness scaling exactly as designed (why it works
> for water) — but it cannot remove a COMPOSITIONAL confound where the ground-truth labels
> themselves correlate scene type with brightness (dark forests versus bright open fields is this
> domain's actual scene composition, not an artefact of any one scoring mechanism). This means the
> brightness confound is not fixable by ANY purely photometric single-frame feature — learned,
> off-the-shelf, or hand-designed-invariant — without additional structure (multi-frame,
> spatial/geometric, or a different modality entirely).**

This definitively closes the "maybe a cleverer feature trick fixes it" line; candidate direction 1
from Chapter 11's menu stays closed, for a stronger reason than before.

## N=20 confirmation batch: frontier + hazard combined, chop rate measured for the first time on this combination

`configs/play_craft_commit4_hazard.yaml` (Chapter 12's frontier search + attempt #13's corrected
anti-drowning rescue, Chapter 13) run at N=20.

**Process note, corrected.** The Tester dispatch's report claimed a "hard infrastructure failure"
halting the batch at episode 4 — **false**, independently verified: `play_minerl_multi.py` launches
one Java/Malmo process per episode, so a transient Malmo state-machine error on a single episode
does not kill the orchestrator, which simply moves on to the next episode. The batch ran all 20
episodes end to end ("FINAL RESULTS — 20/20 episodes succeeded") without any intervention. Lesson:
a per-episode error in this harness is not the same as a batch-level failure — confirm the
orchestrator process itself before declaring a hard stop.

**Drowning: 3/20 (15%)**, confirmed via real `MineRLAgent0 drowned` Malmo messages — down from
attempt #12's original baseline (12/20, 60%). Attempt #13's fix holds at N=20, not just at the N=6
where it was confirmed. Other early terminations (unrelated causes — fall, mob, and so on, outside
the scope of this fix): 5/20 (25%). Full-length ("fair-shot") episodes: 12/20 (60%), up from ~8/20
(40%) in attempt #12's original batch.

**Chopping/crafting: 0/20 logs, 0/20 planks** — despite more episodes getting a fair shot, no chops
this batch (against 1/20 for attempt #12). Not a significant regression at this N (a Fisher test
would not distinguish 0/20 from 1/20) — this campaign's usual small-N variance. Confirms the
standing diagnosis again: removing the drowning confound increases fair-shot episodes but does not
by itself convert into chopping — survival and search/approach effectiveness remain separate
problems.

## The reward=144.000 anomaly — investigated, not reproduced, unresolved

`play_craft.py` gained an optional `logging.full_inventory` diagnostic (default off, bit-for-bit
unchanged when unset) that tracks and prints the maximum value reached for **every** inventory key
per episode, not just log/planks. A fresh N=12 batch with it enabled (same config) showed:
reward=0.000 on all 12 episodes, and the ONLY inventory item ever non-zero across the whole batch
was `dirt` (1-30 per episode, picked up incidentally while walking/attacking) — `dirt` is NOT in
the reward table (`RewardForPossessingItem` covers only log/planks/stick/crafting_table/
wooden_pickaxe/cobblestone/furnace/stone_pickaxe/iron_ore/iron_ingot/iron_pickaxe), so it earns
zero reward and is a red herring for the original mystery. The original episode's process had
already exited before this diagnostic existed, so its exact state is unrecoverable — the mechanism
that produced 144 did not recur across 12 fresh attempts and remains a one-off, uncharacterised
event. It affects no campaign conclusion (chop rate is what matters, and this is orthogonal to it)
— parked as a documented curiosity, not pursued absent a much larger sample.

## Where this leaves the campaign

`ebwm.pt` and `craft_wm_v4.pt` remain untouched throughout this chapter: the per-tile chrominance
test is an offline diagnostic with no learned parameter; the N=20 confirmation batch and the
`full_inventory` diagnostic reuse already-trained/already-wired mechanisms without modifying any
main checkpoint.

## References

This chapter rests on no new bibliographic reference: the per-tile chrominance test reuses the
colour heuristic already built and calibrated for attempt #13 (Chapter 13), with no underlying
published method; the N=20 confirmation batch and the `reward=144` diagnostic are the project's own
empirical runs and instrumentation, not the application of an external reference.

:::

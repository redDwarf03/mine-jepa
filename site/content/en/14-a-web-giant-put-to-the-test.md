---
title: "A web giant put to the test: CLIP does spot the forest — but it confuses that with brightness too"
slug: "14-a-web-giant-put-to-the-test"
lang: "en"
order: 14
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft", "06-learning-to-craft", "07-broken-curiosity", "08-the-wall-is-behavioral", "09-next-directions", "10-the-cleanest-negative", "11-compass-points-backwards", "12-memory-of-visited-places", "13-blind-rescue"]
source_docs: ["CLAUDE.md#Phase 5+", "docs/10_coldstart_engineering.md"]
---

::: beginner

## Where we left off

Chapter 11 delivered the single most important diagnosis of this long investigation into the
cold start: the project's compass (the score that compares each story imagined by the world
model against a memory of "a tree being chopped" — see Chapter 4) does not simply switch off
once it leaves its training ground. It **points backwards**. A tree right in front of the agent
gets a lower score than an empty meadow. Chapter 12 dug further and showed that a good part of
this problem very probably comes from a hidden shortcut inside the project's very first vision
model (Chapters 1-2): instead of genuinely understanding "there is a tree here", the model seems
mostly to be spotting whether the image is bright or dark — a shortcut confirmed three times in
a row, in three different forms.

Before committing to the heaviest option on the menu left by Chapter 11 (building a second
brain — a separate, slower model whose only job is to "find a forest"), someone from outside the
project, consulted by the project owner, proposed a simpler and far cheaper question to test
first: **does a very large, off-the-shelf AI model, never trained on Minecraft at all, already
spot a forest correctly?** If so, there would be nothing new to build — it could simply be reused
as is. This chapter tells the story of that test, and what it revealed: a result that is half
encouraging, half worrying, and honestly not yet fully understood.

## The idea: borrow a giant's eyes instead of building new ones

The proposed model is called **CLIP**. It has never seen anything from this project or from
Minecraft: it was trained by another team on hundreds of millions of photos and captions taken
from the internet — the kind of thing you find when searching for images on the web. What CLIP
can do, once trained: compare any image to any sentence and say how well they "go together",
without needing to be retrained for each new task (this is called a "zero-shot" comparison —
literally "without a single extra training attempt").

The test was simple: take exactly the same real game frames that were used to discover the
backwards-compass problem in Chapter 11, and ask CLIP to compare each one against two sentences:
"a dense forest with many trees" versus "an open grassy field with no trees". Two conditions had
to be met for the test to count as a genuine success:

1. **CLIP must agree with common sense**: an image with a nearby tree must score more favourably
   towards "forest" than an image with no tree. (This is exactly the opposite of what the
   project's broken compass was doing in Chapter 11.)
2. **That score must not actually be just a roundabout way of measuring the brightness of the
   scene** — otherwise it would be the same old shortcut already spotted three times
   (Chapter 11), simply hidden behind a much bigger and much more impressive model.

## The result: half the test clearly passes, the other half fails badly

**The first condition passes, and clearly**: CLIP does give a better "forest" score to images
that really do show nearby trees than to images that show none. On that specific point, CLIP does
better than the project's broken compass — it does not invert.

**The second condition fails, and badly.** CLIP's score is very strongly tied to the overall
brightness of the image — almost as if the two were measuring nearly the same thing. And this is
not only true on the difficult frames from the crafting environment (where the project's compass
inverts): it is true **even on the easy frames from the original tree-chopping environment**, the
one where the project's home-made compass has been working correctly since Chapter 6.

## What this means, honestly — and what remains a genuine mystery

Care is needed here, because this is an open question, not an established certainty.

This result **weakens, without completely demolishing**, an idea that had seemed reasonable up to
now: that the project's small model confuses brightness with forest simply because it did not see
enough varied scenes (day, night, different weather) during training. If a giant model, trained on
hundreds of millions of photos far more varied than anything this project could ever collect,
makes the **same** confusion — and even slightly worse — then a lack of diversity may not explain
everything.

There is even a possible explanation that would not be a "bug" at all: a genuinely dense forest,
in real life as in a game imitating it, **really is darker** than an open field in full sunlight,
because of the shade cast by the canopy. Picking that up could be a useful and sensible signal,
not a reasoning error.

But one precise observation stops us settling for that simple explanation: among the frames
tested, a **dark cave scene with no tree whatsoever** was placed by CLIP in the same group as the
bright, open scenes — "no forest" — instead of being confused with a dark forest, as a
"darkness = forest" story would have predicted. So something other than plain brightness is going
on, but exactly what remains, to this day, a genuinely unanswered question.

## Phase 2: retraining the world model directly — a mixed result, not a clean one

The decision taken after the CLIP test was not to demand that any future fix become completely
independent of brightness (at the risk of stripping out a possibly legitimate signal), but to
check directly whether the real original problem — the compass pointing backwards on real random
starting points — disappears, no matter which mechanism achieves it. That work is now finished,
and here is what it produced.

The project took the existing world model (not from scratch — a simple adjustment of already
trained weights) and retrained it on a mixture: the original guaranteed-forest frames, plus real
free-spawn demonstrations, plus random exploration episodes. What was new compared with every
previous attempt: this time a **photometric augmentation** (the colours, brightness and contrast
of each short sequence are altered at random, but consistently across the whole sequence rather
than frame by frame, to force the model to stop leaning blindly on brightness) was applied
directly to the training of the world model itself — not to a small module bolted on top, as in
previous attempts. This is the first time in the whole investigation that this particular move has
been made directly on the main model.

The usual safety checks (no representation collapse — see Chapter 2 — and prediction quality
barely moving, which was intended: the goal was a light adjustment, not a full retraining) passed
without a hitch across all 5 training rounds.

**The real test was to re-run, on each of the 5 adjusted versions, exactly the same diagnostic
that had uncovered the backwards-compass problem.** The result is genuinely split, not merely
"it almost worked":

- **Leaving out one specific frame** — a dark scene, like a cave or an underwater passage, with no
  tree at all — the fix looks clean: across the 5 adjusted versions, scenes with a nearby tree now
  score several times higher than open scenes with no tree. That is a real reversal of the
  original inverted direction.
- **But putting that single frame back into the calculation flips the result the wrong way again
  on all 5 versions**, because that specific frame's score **got worse** after the adjustment, not
  better. This is a new anomaly, tied to low brightness, appearing somewhere different from before
  — but clearly belonging to the same family of problem as the brightness shortcut already spotted
  earlier (Chapter 12, and the first half of this chapter with CLIP).

None of the 5 adjusted versions was promoted to replace the reference model, and no new real-game
test was run: the project's rule is to spend a live test only on a candidate that has clearly
passed its offline test first — and this one did not clearly pass.

**Why this matters, stated precisely**: this is the fourth time, with four genuinely different
approaches, that a brightness-linked anomaly has appeared — a small bolted-on module trained on
the model's already-frozen features; that same module retrained specifically on free-spawn data;
a giant off-the-shelf model never trained for this project (CLIP, earlier in this chapter); and
now a direct retraining of the world model itself, with real photometric augmentation — the most
direct attack yet on this precise problem. That seriously weakens the idea that "the model simply
hasn't seen enough different lighting yet" explains everything — even the most direct and most
carefully done attempt to fix exactly that still produced a new anomaly, not a clean fix.

## What happens next

The condition the project had set itself for committing to the heaviest option on the menu left in
Chapter 11 — a second, slower world model dedicated to "finding a forest" before handing back to
the existing fast model to chop the tree, called **H-JEPA** — was: "only if the direct, cheaper fix
fails". That has now happened, with real evidence behind it rather than a merely plausible
argument. The project therefore turns towards this structurally different option as its next
direction, rather than continuing to hunt for a direct fix on the existing model.

:::

::: expert

## Context

Chapter 11 established that `ebwm.pt`'s native goal-centroid scoring inverts outside the Treechop
distribution (nearby tree → lower score than an open scene). Chapter 12 confirmed, for a third
independent time, that a brightness shortcut very probably lives in the frozen visual encoder
itself (attempt #11: score/brightness correlation 0.643, and an `is_tree_close`/brightness
correlation of -0.917 on the gate's own hand-labelled set, demonstrating that the 87.5% direction
gate was in reality measuring that same shortcut). This chapter covers phase 1 of attempt #14: a
purely offline diagnostic, with no Minecraft-specific training, testing whether a generic,
entirely out-of-domain pretrained vision-language model already solves the direction problem —
before committing to the cost of Chapter 11's candidate direction 3 (hierarchical H-JEPA).

## Method

An external expert consulted by the project owner proposed testing **CLIP** (Radford et al.,
OpenAI) zero-shot, ahead of any other intervention — a model never touched or fine-tuned for this
project, trained on hundreds of millions of web image-text pairs. Protocol: zero-shot CLIP
similarity between each frame and two text descriptions, "a dense forest with many trees" versus
"an open grassy field with no trees", applied to the **same set of real frames** used to discover
the inversion in attempt #10 (Chapter 11) — no new data, no resampling, for a directly paired
comparison with the previous diagnostic.

Two passing conditions were required, not one:

**(a)** CLIP must score tree-close frames above no-tree frames — the direction test that
`ebwm.pt`'s native scoring fails (attempt #10).

**(b)** CLIP's score must not be a simple function of overall scene brightness — otherwise it
would be the same shortcut confirmed three times in attempt #11, rediscovered behind a bigger
model rather than solved.

## Result

**(a) clearly passed**: a real, correctly oriented separation, unlike `ebwm.pt`'s native scoring on
the same distribution.

**(b) failed, badly.** CLIP's score correlates strongly with scene brightness — a relationship
close to near-collinearity between the two variables. Notably, this correlation holds **on the
original Treechop environment too**, the one where `ebwm.pt`'s native scoring already works
correctly (Chapter 6, Chapter 8) — not only on the difficult free-spawn distribution where the
problem was discovered.

## A cautious reading — hypothesis, not established fact

This result **weakens, without refuting**, the hypothesis carried since attempts #9/#11 that the
brightness shortcut is caused by a lack of lighting diversity in the project's Minecraft-specific
training data (Treechop, almost exclusively daytime). A model trained on a web corpus several
orders of magnitude more lighting-diverse than any corpus collectable within this project
reproduces — and even exceeds in intensity — the same shortcut. If data diversity alone were
enough to eliminate this shortcut, we would not expect to find it this strong in CLIP.

An alternative reading, not excluded: "a dense forest is physically darker than an open field"
could be a real and legitimate signal to pick up, not a reasoning error — brightness and forest
presence are authentically correlated in the world (and in the game's imitation of it).

But that alternative reading does not explain everything: a specific **dark cave frame, with no
tree**, was grouped by CLIP with the bright open scenes ("no forest"), and not with a "dark
forest" profile — which is what a pure-brightness story would have predicted. Something other than
raw brightness is therefore involved in CLIP's score, without our being able to say precisely what
at this stage. **This is explicitly left as an open question, not as an established fact** —
consistent with the project's honesty discipline on unresolved results.

## Phase 2: direct fine-tuning of `ebwm.pt` with photometric augmentation — a mixed result

Rather than pursuing the zero-shot CLIP direction itself, or demanding that a future fix become
explicitly invariant to brightness (at the risk of stripping out a potentially legitimate signal,
as discussed above), the decision taken at the end of phase 1 was to proceed directly to a
fine-tuning of the project's world model on a mixture of guaranteed-forest data (Treechop) and
real free-spawn data (expert Obtain demonstrations + random exploration episodes), **then to
re-check directly whether the original inversion problem (attempt #10, Chapter 11) disappears —
whatever mechanism mediates that change** — rather than imposing brightness-independence as the
success criterion. That phase is now concluded.

**Method**: warm-start from `ebwm.pt` — same architecture, not a from-scratch retraining — on the
Treechop + expert free-spawn + random exploration mixture described above, with **photometric
augmentation** (brightness/contrast/saturation jitter, randomised but applied consistently across
a whole short sequence, not frame by frame) injected directly into the world model's own training
— not into an additional module as in previous attempts (attempt #7's ColorJitter repair, then
attempt #11). This is the first time in the entire campaign that this augmentation has been applied
to the main model rather than to a grafted-on component.

**Safety gates**: passed cleanly across all 5 training epochs — no representation collapse (see
Chapter 2), prediction quality nearly unchanged (expected: the goal was a light adjustment, not a
full retraining).

**The real test**: re-running attempt #10's exact diagnostic on each of the 5 fine-tuned
snapshots. Authentically mixed result, not a clean win:

- Excluding one specific frame — a dark cave/underwater-type scene with no tree — the fix looks
  clean: across the 5 snapshots, tree-close scenes now correctly score several times higher than
  open/no-tree scenes — a real reversal of the original inverted direction.
- Including that same frame, the result flips the wrong way again on each of the 5 snapshots,
  because that specific frame's score **degraded** after fine-tuning rather than improving — a new
  anomaly, tied to low brightness, appearing somewhere different from attempt #11, but recognisable
  as belonging to the same family of brightness-linked shortcut (Chapter 12 / attempt #11, and this
  chapter's own CLIP phase 1).

No fine-tuned snapshot was promoted to reference-checkpoint status; no live real-game test was run,
in line with the project's rule of reserving a live test for a candidate that has clearly passed
its offline gate first — which is not the case here.

**Why this is significant**: this is the fourth time, with four mechanically different approaches,
that a brightness-linked anomaly has appeared — a small additional module trained on frozen
features (attempt #7); that same module retrained specifically on Obtain data (attempt #11); a
giant, out-of-domain, never-touched vision-language model (CLIP, phase 1 of this chapter); and now
a direct retraining of the world model itself with real photometric augmentation — the most direct
attack yet attempted on this precise problem. This appreciably weakens the "the model simply hasn't
seen enough lighting diversity" hypothesis: even the most direct and most careful attempt to fix
exactly that gap produced a new anomaly rather than a clean fix.

## Decision for what follows

The condition the project had set for committing to candidate direction 3 from Chapter 11's menu —
**H-JEPA**, a second, slower, hierarchical world model planning "find a forest" over a long horizon
before handing back to the existing fast model for the chopping gesture — was explicitly "only if
the direct, cheaper fix fails". That condition is now met by empirical evidence (phase 2 above
being the project's most thorough direct-fix attempt to date), and no longer merely by a plausible
argument. The project therefore turns towards H-JEPA as its next direction, rather than continuing
to iterate on direct fixes to `ebwm.pt` or its add-on modules.

`ebwm.pt` (the reference checkpoint) is modified neither by the CLIP diagnostic (a third-party
model, never loaded for planning) nor by phase 2's fine-tuning: the 5 snapshots produced are kept
separately versioned, following the convention already used for every variant in this project
(`craft_wm_v4_coverage.pt`, `value_projector_obtain.pt`, and so on) — no silent replacement of the
reference checkpoint.

## References

CLIP (Radford, Kim, Hallacy, Ramesh, Goh, Agarwal, Sastry, Askell, Mishkin, Clark, Krueger,
Sutskever, *Learning Transferable Visual Models From Natural Language Supervision*, 2021) is used
here zero-shot, out of domain, as an external diagnostic — this project does **not** have a
verified arXiv identifier for CLIP in `docs/references/index.md` to date, and invents none here, in
line with the project's rule of citing only references already verified in that file. This chapter
otherwise builds on attempt #10's diagnostic (Chapter 11) and the brightness shortcut confirmed
three times in attempt #11 (Chapter 12), already documented without further bibliographic citation.

:::

# Phase 5 — Teaching the world model to craft

> This phase asks a harder question than chopping a tree: can the JEPA world model learn
> a **game mechanic** — "1 log → 4 planks" — and can an agent plan a *crafting* action
> from it? The honest answer: **the world model learns the rule cleanly; the bottleneck
> is getting the first log, not the crafting.**

---

## The goal (and why it's a pickaxe, not a sword)

The dream was "an agent that figures out how to craft a wooden sword." But MineRL 0.4.4
has **no sword handler** — the crafting actions are hard-coded to the diamond tech tree:

```python
CraftAction([none, 'torch', 'stick', 'planks', 'crafting_table'])
CraftNearbyAction([none, 'wooden_axe', 'wooden_pickaxe', 'stone_axe', ...])  # no sword
```

The supported equivalent is the **wooden pickaxe**, which needs the exact same recipe
chain: `log → planks → stick → crafting_table → wooden tool`. So the goal became the
first rung of that ladder: **chop a log, then craft it into planks.**

---

## The environment: why ObtainIronPickaxeDense fits JEPA

`MineRLObtainIronPickaxeDense-v0` gives three things Treechop does not:

| Feature | Why it matters |
|---------|----------------|
| **Inventory in the observation** (`log, planks, stick, …`) | the structured game state |
| **Dense per-item reward** (log=1, planks=2, stick=4, …) | no sparse-reward problem |
| **GUI-free crafting** (`craft` is a discrete action) | crafting isn't a mouse-in-a-menu task |

Human demos (Zenodo `MineRLObtainIronPickaxe-v0`, 2.8 GB) show the full chain. We
prepare 40 of them (`scripts/prepare_demos_obtain.py`): 84,902 frames, **144 craft-planks
steps**, 37/40 reaching a wooden pickaxe, with inventory extracted alongside frames and a
**22-action space** (17 movement + 5 craft) in `configs/minerl_actions_obtain.yaml`.

---

## Attempt 1 — WM v3: inventory as a prediction head → **fails**

The first idea: keep the visual eb-JEPA, and bolt on a head that predicts the inventory
from the visual latent.

```
frame → [visual encoder] → latent → [inventory head] → predicted inventory
```

**It can't work, and the reason is fundamental: the POV frame does not contain the
inventory count.** When you craft planks, the screen barely changes — "planks: 36" is a
separate observation, never rendered in the 64×64 view. So:

- the inventory head can only learn **scene-stage correlations** ("forest scene → few
  planks", "near a table → more planks"), never the actual mechanic;
- the visual scene is static during crafting, so the predictor just **copies** the latent
  (ratio ≈ 0.98);
- at plan time, the craft action leaves the predicted latent unchanged → the head reads
  the **same** inventory → predicted planks gain = 0 → **the planner is blind to crafting.**

In play, the v3 agent does nothing useful. Dead end — but an instructive one.

---

## The key insight

> **Crafting is a discrete-inventory-state problem, not a pixel problem.**

You cannot recover the inventory from pixels, so the inventory must be a **state variable
of the world model**, not something predicted from the frame. This is exactly why MineRL
exposes the inventory as a separate observation in the first place.

---

## Attempt 2 — WM v4: inventory as a state variable → **the rule is learned**

WM v4 splits the world model in two:

```
Perception (pixels)              Discrete state (inventory)
─────────────────                ──────────────────────────
visual eb-JEPA                   InventoryDynamics (MLP)
"tree ahead? near a table?"      inv_{t+1} = inv_t + g(inv_t, action, visual_latent)
```

The inventory is now an **input**. The dynamics `g` is conditioned on the visual latent,
so it learns both chopping (attack + tree-visual → log+1) and crafting (craft + log →
planks+4). Crafting rules are near-deterministic → easy to learn once inventory is in the
state.

**Result — the model discovered the recipe:**

```
dPlanks@craft  (predicted Δplanks on real craft-planks steps)
  epoch 1: +1.24    epoch 4: +4.01    epoch 20: +3.81
```

`dPlanks@craft ≈ +4` is the exact Minecraft recipe (1 log → 4 planks), learned purely
from demonstrations. The world model *understands* the craft mechanic.

---

## The precondition trap (the expert-demo gap)

A model that knows "craft → +4 planks" is not enough. In play, the v4 agent **crafted
constantly on an empty inventory** (`a17 = 30%`), getting nothing.

Why: **humans never press "craft" with an empty inventory**, so the demos contain *zero*
examples of a failed craft. The model learned "craft → +4 planks" **unconditionally** —
it never saw that you need a log first. `dPlanks@craft = +4` looked perfect precisely
because it was measured on craft steps, which always had a log.

This is the classic expert-only-demonstration gap: **no negative examples → no
preconditions learned.** It is the strongest possible argument for curiosity / self-play
(an agent that crafts on empty inventory and sees nothing happen *learns* the
precondition from its own prediction error).

### The fix: synthetic negatives + balanced weighting

Without waiting for a full self-play loop, we taught the precondition directly:

- **Synthetic negative**: at craft steps, assert `g(empty inventory, craft, visual) ≈ 0`
  (crafting from nothing produces nothing).
- **Balance**: craft transitions are rare (144 / 85k). A naive precondition weight (5.0)
  *crushed* the positive signal — the model took the lazy route and predicted ~0 planks
  always (`dPlanks` collapsed +4 → +0.4). The fix: **upweight the rare positive craft
  transitions ×30** and use a moderate precondition weight (2.0).

**Balanced result:** `dPlanks@craft ≈ +3.8` **and** `precond ≈ 0.0001`. The model now
knows *both* "craft + log → +4 planks" *and* "craft + empty → nothing." In play, the
agent stopped crafting uselessly.

---

## The planner: switch objective by inventory state

One MPC planner, two objectives (`SwitchingCraftPlanner`):

```
no log   → CHOP  : steer the visual latent toward a goal-centroid of "log obtained"
                   scenes (the Treechop trick that drives the lumberjack gesture)
has log  → CRAFT : maximise predicted inventory gain (Δlog, Δplanks) via the dynamics
```

This combines two validated pieces — chopping (goal-centroid) and crafting (WM v4).

---

## Live craft demo — the agent crafts planks in real Minecraft

To prove the craft loop end-to-end *in a live episode* (isolated from the hard cold-start
chopping), we run the agent in `MineRLObtainTest-v0`, a debug env that starts the agent
**with wood** (log=5, planks=3) on a flat world. Given logs, the switching planner enters
craft mode and executes the recipe:

```
start log=5 planks=3  →  agent crafts  →  planks crafted: YES (+20)   reward=10   ✅
6/6 episodes: 100% success, +16 to +20 planks each (5 logs × 4 planks)
```

This is the world model + planner **actually crafting in real Minecraft** — a live agent
turning logs into planks. The only thing handed to it is the wood; the crafting itself is
planned and executed by the agent. Once the logs run out it correctly switches to chop mode
and (on the treeless flat world) just wanders — exactly the expected behaviour.

> Note (and a callback to the whole v3→v4 lesson): **crafting is invisible in the POV.** The
> screen barely changes when you craft — so the proof is the inventory/reward (+20 planks,
> reward 10), *not* a GIF. The frame never showed the inventory; that is exactly why the
> inventory had to become a world-model state variable.

---

## The remaining wall: cold-start chopping in survival

With the switching planner, the agent behaves sensibly: it spends every plan in **chop
mode** (no log yet), and moves forward purposefully (`a1`/`a13` dominant) instead of
randomly. But across 5 episodes it chopped **0 logs**.

Why this is hard — and honest:

- **Treechop spawns in a dense forest** (trees guaranteed in view) → our Treechop agent
  chops 25–50%. **ObtainIronPickaxeDense spawns in a random survival biome** — trees may
  be far, behind hills, or absent from the starting view. The agent must *find* a tree
  first.
- The visual predictor copies (ratio ≈ 0.98) on near-static frames, so the planner can't
  vividly "imagine" turning to face a tree → the chop objective is a weak steering signal.
- Episodes often end early (~750–1500 steps) because the agent wanders into survival
  hazards and dies.

Obtaining the full tech tree from a cold start in MineRL was a **multi-year community
grand challenge** — the chopping/navigation half, not the crafting, is the wall.

---

## Honest status

| Component | Status |
|-----------|--------|
| WM learns the craft rule (1 log → 4 planks) | ✅ `dPlanks@craft = +3.8` |
| WM learns the precondition (no log → no craft) | ✅ `precond ≈ 0`, no more useless crafting |
| Inventory-as-state world model (v4) | ✅ `checkpoints/craft_wm_v4.pt` |
| Switching planner (chop ↔ craft) | ✅ correct mode switching in live play |
| Agent crafts planks **live, given wood** | ✅ 100% over 6 ep, +16–20 planks/ep (`MineRLObtainTest`) |
| Agent crafts planks end-to-end from a **cold start** | ❌ blocked by cold-start chopping in survival |

**The crafting is solved at the world-model level. Getting the first log in a random
survival world is the open problem** — the same family as Treechop's 25–50%, harder here.

---

## Lessons

1. **Crafting ≠ pixels.** The inventory isn't in the frame; it must be a world-model state
   variable. (v3 → v4 is this lesson made concrete.)
2. **A world model can learn symbolic game rules** from demonstrations — `dPlanks = +4` is
   the Minecraft recipe, learned, not coded.
3. **Expert demos teach actions but not preconditions.** No failed-craft examples → the
   model thinks crafting always works. Negatives (synthetic, or via curiosity/self-play)
   are required.
4. **Rare-but-critical signals must be upweighted.** 144 craft steps in 85k were drowned
   until weighted ×30; a too-strong precondition then crushed them — balance matters.
5. **Know your bottleneck.** We proved the hard conceptual part (crafting) and named the
   real wall (cold-start chopping) instead of claiming an end-to-end milestone we didn't
   reach.

---

## Where curiosity / self-play comes in (future work)

The precondition gap and the chopping wall both point to the same missing piece: an agent
that **generates its own experience** and is driven by **intrinsic reward = world-model
prediction error**. Crafting on an empty inventory and seeing nothing happen is a
prediction error → it teaches the precondition. Exploring toward surprising states is how
an agent finds trees without a forest handed to it. WM v4 is the foundation that makes
this loop possible; building it is the next chapter.

> **Update — we built it and ran the first experiment.** A 3-agent dev loop
> (explore/develop/test) implemented a Plan2Explore-style novelty bonus for cold-start
> chopping. It **failed**: the offline ensemble collapsed (all heads agreed → no novelty
> signal), so curiosity-ON ≈ OFF. The full diagnosed negative result and what it teaches
> about offline-vs-online curiosity is in [`docs/09_curiosity_coldstart.md`](09_curiosity_coldstart.md).

---

*Previous: `docs/06_minecraft_port.md` (chopping, eb-JEPA, the 25–50% result).*
*Next: `docs/09_curiosity_coldstart.md` (curiosity for cold-start — attempt #1).*
*Architecture: `docs/01_jepa.md`. Planning: `docs/05_planning.md`.*

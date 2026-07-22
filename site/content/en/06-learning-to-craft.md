---
title: "Learning to craft: the rule is understood, the first tree remains out of reach"
slug: "06-learning-to-craft"
lang: "en"
order: 6
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination", "05-real-minecraft"]
source_docs: ["docs/08_crafting.md", "CLAUDE.md#Phase 5 gates"]
---

::: beginner

## The next goal: crafting a tool

Chapter 5 ended with a real victory: the agent chops wood in real Minecraft, about one time out of four. The logical next step is to teach it to do something *with* that wood — turn it into planks, then into a tool. The initial dream was "an AI that crafts a wooden sword". A funny little setback: in the version of Minecraft used by this project (MineRL 0.4.4), **the wooden sword simply does not exist** as a crafting action — only the tech tree leading to the pickaxe is wired into the game. So the new goal becomes: chop a log, turn it into planks, then sticks, place a crafting table, and craft a wooden pickaxe. The full crafting chain.

To do this, the project changes environment: instead of Treechop ("chop a tree, nothing else"), it switches to `MineRLObtainIronPickaxeDense`, a version of Minecraft that gives access to the player's inventory (how many logs, planks, sticks they have) and rewards every obtained item (a log is worth 1 point, a plank 2, etc.).

## First try: guess the inventory from the image → doomed to fail

The first idea seemed natural: keep the encoder that summarizes the image (Chapter 1), and attach a small extension to it that tries to *guess* the inventory from that embedding (the number-summary of the image).

It was doomed to fail, and the reason is almost obvious once you see it: **the screen never shows how many planks you have.** When you craft planks in Minecraft, the image on screen barely changes — the "planks: 36" counter is separate data, never drawn in the first-person view. Result: this extension only learns vague scenery correlations ("forest scene → few planks", "near a table → more planks"), never the actual rule. And since the image barely changes while crafting, the world model simply "copies" the previous embedding — its prediction changes almost nothing. In-game, this agent does nothing useful. A clean failure, but one that teaches something important.

## The core insight of this chapter

> **Crafting an item is not an image problem. It is a discrete state problem — the counter of items you own.**

Since the inventory cannot be guessed from the image, the inventory must become an **input** to the world model — data provided directly to it, instead of asking it to extract it from pixels. This is exactly why Minecraft, in this version of the environment, provides the inventory as a separate observation: the game knows perfectly well it is not visible on screen.

## Second try: inventory as model memory → it works

The new version of the world model (called WM v4 in the project) splits into two parts:

- a **visual** part — the eb-JEPA from Chapter 5, which understands "is there a tree in front of me? am I near a table?";
- an **inventory** part — a small function added to the model that takes the current inventory, the chosen action, and what the visual part sees, and predicts the *new* inventory.

Practically: `new_inventory = old_inventory + change(old_inventory, action, what_i_see)`. By training this function on human gameplay, the model learned, all on its own, a simple but very concrete rule: **crafting with a log produces four planks** — exactly the real Minecraft recipe, learned without ever being hardcoded, just observed in the data.

## The trap of human demonstrations: nobody ever fails a craft

A model that knows "craft → +4 planks" is not enough. Once put into the game, the agent started **pressing "craft" in a loop, even with zero logs in its pockets** — which, of course, produces nothing.

The reason is funny and instructive: **no human player tries to craft something without having the ingredients.** The recordings of human games used for training therefore contained *zero* examples of failed crafts. The model learned "craft → +4 planks" as an absolute truth, never seeing that a log was required beforehand. This is a classic trap in learning from expert demonstrations: **experts never show their failures**, so the model never learns the conditions that must be met before acting.

The chosen solution here, without waiting for a full autonomous exploration loop (the subject of the next chapters): artificially create **negative examples**. We explicitly tell the model: "if you craft with an empty inventory, the result is zero". This addition had to be dosed carefully — the first attempt, too heavy-handed, crushed the positive signal (the model started predicting almost zero planks *all the time*, even on real successful crafts). The right balance: giving much more weight to the rare moments of actual crafting in the data (144 out of 85,000 instants, otherwise easily drowned out) and a more moderate penalty for crafting with an empty inventory. Final result: the model knows *both* "craft + log → +4 planks" *and* "craft + empty inventory → nothing". The agent stops crafting air.

## A planner that switches goals based on what is in its pockets

The planner (the one from Chapter 4, which imagines multiple futures and picks the best) now receives two possible goals, and chooses based on the inventory:

- **no logs** → "chop wood" goal (the same trick as in Chapter 5);
- **at least one log** → "maximize predicted inventory gain" goal (planks, sticks...).

## The proof that crafting works, in real Minecraft

To verify that crafting *actually* works, independently of the "finding the first tree" problem (which remains hard, we will get to that), the project launches the agent in a test version of the environment that starts directly with wood in its pockets (5 logs, 3 planks). Over 6 episodes, **100% success**: the agent crafts between 16 and 20 additional planks every single time, with a reward of 10 points. This is an agent that plans and executes the entire crafting chain itself — it is only handed the starting wood.

A fun note, consistent with everything in this chapter: **you see nothing on screen while the agent crafts.** The proof of success is not a visually impressive image — it is the inventory counter and the reward going up. Exactly the reason why the inventory had to become model memory rather than something to guess from the image.

## The remaining wall: finding the first tree, alone

Here is the honesty that closes this chapter. Once released into the real game, in survival mode, with no starting wood, the agent behaves sensibly — it spends all its time in "chop wood" mode, moves purposefully rather than randomly — but over 5 episodes, it chopped **zero logs**.

Why it's harder than in Chapter 5: in Treechop (Chapter 5), the player always spawns in the middle of a dense forest, with trees guaranteed in its field of view. Here, the player spawns **anywhere** in a randomly generated survival world — trees might be far away, hidden behind a hill, or completely absent from the initial view. The agent must first **search** for a tree before it can chop it, a skill that nothing, so far, has taught it.

**The honest takeaway of this chapter**: the "understanding the crafting rule" part is solved — the world model genuinely learned the recipe, and the agent crafts perfectly once it has wood. The real, open problem is finding that first tree from a random starting point. That is the subject of the following chapters.

:::

::: expert

## Phase 5 Objective and Environment Choice

`MineRLObtainIronPickaxeDense-v0` replaces Treechop as the testbed. `wooden_sword` has no craft handler in MineRL 0.4.4 (`CraftNearbyAction` only covers the pickaxe branch); the goal therefore becomes the equivalent chain `log → planks → stick → crafting_table → wooden pickaxe`. The environment brings three elements absent from Treechop: the inventory in the observation space, a dense per-item reward (log=1, planks=2, stick=4, ...), and a discrete `craft` action (no GUI menu). Demonstrations: Zenodo `MineRLObtainIronPickaxe-v0.zip` (2.8 GB), 40 demos prepared via `scripts/prepare_demos_obtain.py` → 84,902 frames, **144 craft-planks steps**, 37/40 demos reaching a wooden pickaxe, action space expanded to **22 classes** (17 movement + 5 craft, `configs/minerl_actions_obtain.yaml`).

## Attempt 1 — WM v3: Inventory as a prediction head → structural failure

```
frame → [visual encoder] → latent → [inventory head] → predicted inventory
```

Fundamental flaw: the first-person view (64×64) never contains the inventory counter — "planks: 36" is never rendered on screen. Measured consequences:

- the head only learns scene correlations (game stage ↔ probable inventory), never the causal mechanism;
- since the scene is quasi-static during a craft, the predictor **copies** (ratio ≈ 0.98, the same `val_pred/val_copy` metric defined in Chapter 3);
- at planning time, the `craft` action does not change the predicted visual latent → the inventory head reads the *same* predicted inventory → predicted plank gain = 0 → **planner blind to crafting.**

## The Structuring Insight

> **Crafting is a discrete inventory state problem, not a pixel problem.**

The inventory must be a **world model state variable** (an input), not a quantity predicted from the frame — consistent with MineRL exposing it as a separate observation rather than rendering it on screen.

## Attempt 2 — WM v4: Inventory as state variable → rule is learned

```
Perception (pixels)              Discrete State (inventory)
─────────────────                ──────────────────────────
visual eb-JEPA                   InventoryDynamics (MLP)
"tree ahead? table near?"         inv_{t+1} = inv_t + g(inv_t, action, visual_latent)
```

The inventory becomes an **input**; the dynamics `g` (small MLP) are conditioned on the visual latent, thus learning both chopping (attack + visual-tree → log+1) and crafting (craft + log → planks+4). Measured result, `dPlanks@craft` (predicted Δplanks on actual craft-planks steps):

```
epoch 1: +1.24    epoch 4: +4.01    epoch 20: +3.81
```

`dPlanks@craft ≈ +4` is exactly the Minecraft recipe (1 log → 4 planks), learned purely from demonstrations — not hardcoded. This result directly aligns with Yu et al. (arXiv:2509.12249, *Why and How Auxiliary Tasks Improve JEPA Representations*, NeurIPS 2025): an auxiliary head (`InventoryDynamics`) trained jointly with the latent dynamics keeps non-equivalent observations well-separated — their *No Unhealthy Representation Collapse* theorem is exactly the mechanism underlying WM v4's design.

## The Precondition Trap (the hole in expert demos)

In-game, the v4 agent **crafts continuously on an empty inventory** (`a17 = 30%` of steps), obtaining nothing. Cause: no human demo shows a failed craft (`craft` on empty inventory) — the model learns "craft → +4" **unconditionally**, and `dPlanks@craft = +4` looks perfect precisely because it is only measured on craft steps that always possessed a log. This is the most direct argument for curiosity/self-play (upcoming chapters): an agent that crafts on an empty inventory and observes the lack of effect **learns** the precondition through its own prediction error.

### The fix: synthetic negatives + balanced weighting

- **Synthetic negative**: enforce `g(empty inventory, craft, visual) ≈ 0` on craft steps.
- **Balancing**: craft transitions are rare (144/85k). A naive precondition weight (5.0) **crushed** the positive signal — the model took the shortcut "always predict ~0 planks" (`dPlanks` collapsed from +4 to +0.4). Fix: **overweight ×30** the rare positive craft transitions, use a moderate precondition weight (2.0).

**Balanced result**: `dPlanks@craft ≈ +3.8` **and** `precond ≈ 0.0001`. The model now knows *both* "craft + log → +4 planks" *and* "craft + empty → nothing". In-game, the agent stops uselessly crafting.

## The Planner: switching goals based on inventory state

`SwitchingCraftPlanner`, a single MPC (Chapter 4), two goals:

```
no log       → CHOP  : pull visual latent closer to "log obtained" centroid
                       (the Treechop trick from Chapter 5)
log present  → CRAFT : maximize predicted inventory gain (Δlog, Δplanks) via g
```

Combines two blocks already validated separately — chopping (goal centroid) and crafting (WM v4).

## Live Crafting Demo — successful crafting in real Minecraft

To isolate proof of the crafting loop *without* the difficulty of cold-start chopping, the agent is launched on `MineRLObtainTest-v0` (debug env, log=5 planks=3 at spawn, flat world). Result over 6/6 episodes: **100% success, +16 to +20 planks per episode (5 logs × 4 planks), reward 10.** Crafting is planned and executed by the agent — only the starting wood is gifted.

> Important reminder: **crafting is invisible in the first-person view** — the screen barely changes. The proof is the inventory/reward (+20 planks, reward 10), not a GIF. This is exactly why the inventory had to become a world model state variable rather than a visual target.

## The Remaining Wall: survival cold-start chopping

With the switching planner, the behavior is sensible (dominant chop mode, `a1`/`a13` actions majority, no random wandering) but over 5 episodes: **0 logs chopped.**

Identified reasons:

- **Treechop spawns in a dense forest** (trees guaranteed in view) → the Treechop agent chops 25-50% (Chapter 5). **`ObtainIronPickaxeDense` spawns in a random survival biome** — trees potentially far, behind a hill, or absent from the initial view. The agent must first *find* a tree.
- The visual predictor copies (ratio ≈ 0.98) on nearly static frames → the planner cannot vividly "imagine" turning toward a tree → the chop goal provides a weak steering signal.
- Episodes often end early (~750-1500 steps) due to survival hazards.

## Honest Assessment

| Component | Status |
|-----------|--------|
| WM learns craft rule (1 log → 4 planks) | ✅ `dPlanks@craft = +3.8` |
| WM learns precondition (no log → no craft) | ✅ `precond ≈ 0` |
| Inventory-as-state world model (v4) | ✅ `checkpoints/craft_wm_v4.pt` |
| Switching planner (chop ↔ craft) | ✅ correct switching in real game |
| Crafting **live, given wood** | ✅ 100% over 6 ep., +16-20 planks/ep. |
| End-to-end crafting from **cold start** | ❌ blocked by survival cold-start chopping |

**Crafting is solved at the world model level. Obtaining the first log in a random survival world is the open problem** — of the same family as Treechop's 25-50%, but harder here.

## Lessons

1. **Crafting ≠ pixels.** The inventory is not in the frame; it must be a world model state variable (v3 → v4 makes this lesson concrete).
2. **A world model can learn a symbolic game rule** from demonstrations — `dPlanks = +4` is the Minecraft recipe, learned, not coded.
3. **Expert demos teach actions, not preconditions.** Without an example of a failed craft, the model believes crafting always works. Negatives (synthetic, or via curiosity/self-play) are required.
4. **Rare but critical signals must be overweighted** — and balance matters: 144 craft steps buried in 85k were invisible until a ×30 weight; a too-strong precondition then crushed that same signal.
5. **Know your bottleneck.** The conceptually hard part (crafting) is solved; the real wall (cold-start chopping) is named honestly rather than buried under a "full milestone" title.

## References (Verified, from docs/references/index.md)

- Yu et al., *Why and How Auxiliary Tasks Improve JEPA Representations*, arXiv:2509.12249 (NeurIPS 2025) — directly justifies the design of `InventoryDynamics` as an auxiliary head anchored to the latent dynamics.
- Maes, Le Lidec, Scieur, LeCun, Balestriero, LeWorldModel, arXiv:2603.19312 (2026) — the `ratio = val_pred/val_copy` convention reused to diagnose WM v3's failure.

:::

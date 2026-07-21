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

Chapter 5 ended on a real victory: the agent chops wood in real Minecraft, roughly once every four tries. The next logical step is to teach it to do something *with* that wood — convert it into planks, then into a tool. The original dream was "an AI that crafts a wooden sword". An amusing minor hiccup: in the version of Minecraft used by this project (MineRL 0.4.4), **the wooden sword simply does not exist** as a craftable action — only the technology tree leading to the pickaxe is wired into the game environment. The new goal thus becomes: chop a wood log, convert it into planks, then sticks, place a crafting table, and craft a wooden pickaxe. The complete crafting chain.

To do this, the project switches environments: instead of Treechop ("chop a tree, nothing else"), it moves to `MineRLObtainIronPickaxeDense`, a version of Minecraft that exposes player inventory (how many logs, planks, sticks the player holds) and rewards each item acquired (a log is worth 1 point, a plank 2, etc.).

## First try: guessing inventory from the image → this cannot work

The first idea seemed natural: keep the image-summarizing encoder (Chapter 1), and attach a small extension that tries to *guess* the inventory from that embedding (the image's numerical summary).

It couldn't work, and the reason is almost obvious once pointed out: **the screen never displays the number of planks in your inventory.** When you craft planks in Minecraft, the on-screen image barely changes — the "planks: 36" counter is a separate data point, never rendered in first-person view. Result: this extension only learns vague scene correlations ("forest scene → few planks", "near crafting table → more planks"), never the actual rule. And because the image barely changes while crafting, the world model simply copies the previous embedding — its prediction changes almost nothing. In-game, this agent does nothing useful. A clean failure, but one that teaches an important lesson.

## The core insight of this chapter

> **Crafting an item is not an image problem. It is a discrete state problem — tracking the count of items you hold.**

Since we cannot guess inventory from the image, inventory must become an **input** to the world model — data fed to it directly, rather than trying to reconstruct it from pixels. That is precisely why Minecraft, in this environment version, provides inventory as a separate observation: the game engine knows full well it isn't rendered on screen.

## Second try: inventory as model state → it works

The new world model version (named WM v4 in the project) splits into two components:

- A **visual** component — the eb-JEPA from Chapter 5, which understands "is there a tree in front of me? am I near a table?"
- An **inventory** component — a small auxiliary function added to the model that takes current inventory, the chosen action, and what the visual component sees, and predicts the *new* inventory.

Concretely: `new_inventory = old_inventory + change(old_inventory, action, what_I_see)`. By training this function on human gameplay recordings, the model learned, all by itself, a simple yet very concrete rule: **crafting with one log yields four planks** — exactly the real Minecraft recipe, learned without ever being written in code, observed purely in the data.

## The expert demonstration trap: nobody ever fails a craft

A model that knows "craft → +4 planks" is not enough. Once deployed in-game, the agent started **pressing "craft" in a loop, even with zero logs in its pocket** — which, of course, produces nothing.

The reason is both funny and insightful: **no human player ever tries to craft something without having the ingredients.** The human gameplay recordings used for training contain *zero* examples of failed crafts. The model learned "craft → +4 planks" as an absolute truth, without ever seeing that a log was required beforehand. This is a classic trap of learning from expert demonstrations: **experts never show their mistakes**, so the model never learns the preconditions required before taking action.

The solution adopted here, without waiting for a full autonomous exploration loop (the subject of upcoming chapters): synthetically generate **negative examples**. We tell the model explicitly: "if you craft on an empty inventory, the result is zero". This addition had to be calibrated carefully — the first attempt, applied too aggressively, overwhelmed the positive signal (the model started predicting near-zero planks *all the time*, even on valid successful crafts). The right balance: apply heavy re-weighting to the rare moments of actual crafting in the data (144 out of 85,000 frames, otherwise hopelessly drowned out) and a moderate penalty for crafting on empty inventory. Final result: the model knows *both* "craft + log → +4 planks" *and* "craft + empty inventory → nothing". The agent stops crafting into thin air.

## A planner that switches goals based on what it carries

The planner (the one from Chapter 4, imagining multiple futures and picking the best) now receives two possible goals, switching based on inventory state:

- **No log** → goal "chop wood" (the same trick as Chapter 5);
- **At least one log** → goal "maximize inventory gain" (planks, sticks...).

## Proof that crafting works in real Minecraft

To verify that crafting *actually* works, independently of the "find the first tree" problem (which remains hard, discussed next), the project runs the agent in a test version of the environment starting with wood in inventory (5 logs, 3 planks). Over 6 episodes, **100% success rate**: the agent crafts between 16 and 20 additional planks every single time, with a 10-point reward. This is an agent planning and executing the entire crafting chain by itself — we simply provide the starting wood.

A minor detail that aligns with this chapter's theme: **you see nothing happening on screen while the agent crafts.** The proof of success is not a dramatic video — it is the inventory counter and reward increasing. Exactly why inventory had to become model state rather than something guessed from images.

## The remaining wall: finding the first tree, alone

Here is the honest note closing this chapter. When released into the real survival game from a cold start, with no initial wood, the agent behaves sensibly — spending all its time in "chop wood" mode, moving with clear intent rather than at random — but over 5 episodes, it chops **zero logs**.

Why this is harder than Chapter 5: in Treechop (Chapter 5), the player always spawns in a dense forest, with trees guaranteed in view. Here, the player spawns **anywhere** in a randomly generated survival world — trees might be far away, hidden behind a hill, or absent from the initial view entirely. The agent must first **search** for a tree before it can chop it, a capability nothing so far has taught it.

**The honest summary of this chapter**: the "understand the crafting rule" part is solved — the world model truly learned the recipe, and the agent crafts perfectly once it holds wood. The true open problem is locating that first tree from a random spawn point. That is the subject of the next chapters.

:::

::: expert

## Phase 5 Objective and Environment Choice

`MineRLObtainIronPickaxeDense-v0` replaces Treechop as the test harness. `wooden_sword` lacks a craft handler in MineRL 0.4.4 (`CraftNearbyAction` covers only the pickaxe branch); the goal thus becomes the equivalent chain `log → planks → stick → crafting_table → wooden pickaxe`. The environment brings three elements absent from Treechop: inventory in observations, dense per-item rewards (log=1, planks=2, stick=4, …), and a discrete `craft` action (no GUI menu). Demonstrations: Zenodo `MineRLObtainIronPickaxe-v0.zip` (2.8 GB), 40 demos prepared via `scripts/prepare_demos_obtain.py` → 84,902 frames, **144 craft-planks steps**, 37/40 demos reaching wooden pickaxe, **22-class action space** (17 movement + 5 craft, `configs/minerl_actions_obtain.yaml`).

## Attempt 1 — WM v3: Inventory as Prediction Head → Structural Failure

```
frame → [visual encoder] → latent → [inventory head] → predicted inventory
```

Fundamental flaw: first-person view (64×64) never contains the inventory counter — "planks: 36" is never rendered on screen. Measured consequences:

- Head learns only scene correlations (game stage ↔ probable inventory), never causal mechanics;
- Scene being quasi-static during craft, predictor **copies** (ratio ≈ 0.98, same `val_pred/val_copy` metric from Chapter 3);
- At planning time, `craft` action does not change predicted visual latent → inventory head reads *same* predicted inventory → predicted plank gain = 0 → **planner blind to crafting.**

## The Structural Insight

> **Crafting is a discrete inventory state problem, not a pixel problem.**

Inventory must be a **world model state variable** (an input), not a quantity predicted from frames — consistent with MineRL exposing it as a separate observation rather than rendering it on screen.

## Attempt 2 — WM v4: Inventory as State Variable → Rule Learned

```
Perception (pixels)              Discrete State (inventory)
─────────────────                ──────────────────────────
Visual eb-JEPA                   InventoryDynamics (MLP)
"tree in front? table nearby?"   inv_{t+1} = inv_t + g(inv_t, action, visual_latent)
```

Inventory becomes an **input**; dynamics `g` (small MLP) are conditioned on visual latent, learning both chopping (attack + tree-visual → log+1) and crafting (craft + log → planks+4). Measured result, `dPlanks@craft` (predicted Δplanks on true craft-planks steps):

```
epoch 1: +1.24    epoch 4: +4.01    epoch 20: +3.81
```

`dPlanks@craft ≈ +4` is precisely the Minecraft recipe (1 log → 4 planks), learned purely from demonstrations — zero hand-coding. This result aligns directly with Yu et al. (arXiv:2509.12249, *Why and How Auxiliary Tasks Improve JEPA Representations*, NeurIPS 2025): an auxiliary head (`InventoryDynamics`) trained jointly with latent dynamics prevents non-equivalent observations from collapsing together — their *No Unhealthy Representation Collapse* theorem is the exact mechanism behind WM v4's design.

## The Precondition Trap (Expert Demo Gap)

In-game, agent v4 **crafts continuously on an empty inventory** (`a17 = 30%` of steps), obtaining nothing. Cause: zero human demos show failed crafts (`craft` on empty inventory) — model learned "craft → +4" **unconditionally**, `dPlanks@craft = +4` looking perfect precisely because measured solely on craft steps that always possessed logs. This is the direct argument for curiosity/self-play (upcoming chapters): an agent crafting on empty inventory and observing zero effect **learns** the precondition through its own prediction error.

### Fix: Synthetic Negatives + Balanced Reweighting

- **Synthetic Negative**: Enforce `g(empty_inventory, craft, visual) ≈ 0` on zero-log steps.
- **Reweighting**: Craft transitions are rare (144/85k). Naive precondition weight (5.0) **overwhelmed** positive signal — model took shortcut "always predict ~0 planks" (`dPlanks` collapsed from +4 to +0.4). Fix: **over-weight ×30** rare positive craft transitions, moderate precondition weight (2.0).

**Balanced Result**: `dPlanks@craft ≈ +3.8` **and** `precond ≈ 0.0001`. Model now knows *both* "craft + log → +4 planks" *and* "craft + empty → nothing". In-game, agent stops useless crafting.

## The Planner: Switching Goals Based on Inventory State

`SwitchingCraftPlanner`, single MPC (Chapter 4), dual goals:

```
No log   → CHOP  : Pull visual latent toward "log acquired" centroid
                   (Chapter 5 Treechop trick)
Log held → CRAFT : Maximize predicted inventory gain (Δlog, Δplanks) via g
```

Combines two previously validated blocks — chopping (goal centroid) and crafting (WM v4).

## Live Craft Demo — Successful Crafting in Real Minecraft

To isolate proof of crafting loop *without* cold-start chopping difficulty, agent is launched on `MineRLObtainTest-v0` (debug env, log=5 planks=3 at spawn, flat world). Result over 6/6 episodes: **100% success rate, +16 to +20 planks per episode (5 logs × 4 planks), reward 10.** Crafting planned and executed by agent — only starting wood provided.

> Crucial reminder: **crafting is invisible in first-person view** — screen barely changes. Proof is inventory/reward (+20 planks, reward 10), not a GIF. Exactly why inventory had to become world model state rather than a visual target.

## The Remaining Wall: Cold-Start Chopping in Survival

With switching planner, behavior is sensible (chop mode dominant, `a1`/`a13` majority, no random wandering) but over 5 episodes: **0 logs chopped.**

Identified reasons:

- **Treechop spawns in dense forest** (trees guaranteed in view) → Treechop agent hits 25-50% (Chapter 5). **`ObtainIronPickaxeDense` spawns in random survival biome** — trees potentially far, behind hills, or absent from initial view. Agent must first *find* a tree.
- Visual predictor copies (ratio ≈ 0.98) on near-static frames → planner cannot "imagine" vividly turning toward a tree → chop goal provides weak steering signal.
- Episodes frequently terminate early (~750-1500 steps) from survival hazards.

## Honest Scorecard

| Component | Status |
|-----------|--------|
| WM learns crafting rule (1 log → 4 planks) | ✅ `dPlanks@craft = +3.8` |
| WM learns precondition (no log → no craft) | ✅ `precond ≈ 0` |
| Inventory-as-state world model (v4) | ✅ `checkpoints/craft_wm_v4.pt` |
| Switching planner (chop ↔ craft) | ✅ Correct switching in real game |
| Live craft **with initial wood provided** | ✅ 100% over 6 ep, +16-20 planks/ep |
| End-to-end craft from **cold start** | ❌ Blocked by survival cold-start chopping |

**Crafting is solved at world model level. Obtaining the first log in a random survival world is the open problem** — same family as Treechop's 25-50%, but harder here.

## Lessons

1. **Crafting ≠ pixels.** Inventory is not in frame; it must be a world model state variable (v3 → v4 makes this concrete).
2. **A world model can learn a symbolic game rule** from demonstrations — `dPlanks = +4` is the Minecraft recipe, learned, not coded.
3. **Expert demos teach actions, not preconditions.** Without failed craft examples, model believes crafting always works. Negatives (synthetic or via curiosity/self-play) are required.
4. **Rare critical signals must be over-weighted** — and balance matters: 144 craft steps drowned in 85k were invisible until ×30 weight; overly strong precondition then crushed positive signal.
5. **Know your bottleneck.** Conceptually hard part (crafting) is solved; real wall (cold-start chopping) is named honestly rather than hidden under a "complete milestone" label.

## References (Verified, from docs/references/index.md)

- Yu et al., *Why and How Auxiliary Tasks Improve JEPA Representations*, arXiv:2509.12249 (NeurIPS 2025) — directly justifies `InventoryDynamics` auxiliary head design anchored on latent dynamics.
- Maes, Le Lidec, Scieur, LeCun, Balestriero, LeWorldModel, arXiv:2603.19312 (2026) — ratio convention reused to diagnose WM v3 failure.

:::

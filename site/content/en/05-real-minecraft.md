---
title: "The big leap to real Minecraft: four failures, then an agent that chops trees"
slug: "05-real-minecraft"
lang: "en"
order: 5
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination"]
source_docs: ["docs/06_minecraft_port.md", "CLAUDE.md#Phase 4 gates"]
---

::: beginner

## Crafter was training wheels

Up until now, everything built by the project — the encoder (Chapter 1), anti-collapse safeguards (Chapter 2), world model (Chapter 3), and planner (Chapter 4) — was tested on **Crafter**, a lightweight game resembling Minecraft in simplified pixel graphics. It was the right choice for rapid debugging. But the true goal of the project, the one that gives it its name, is **real** Minecraft — the 3D game with actual textures, the one everyone imagines when you say "an AI plays Minecraft".

This chapter tells the story of what happened when the project made that leap. And to be completely honest: **it didn't work on the first try. Nor the second. Nor the third. Nor the fourth.** The fifth attempt worked — and understanding *why* the first four failed is at least as educational as the final success.

## First, the good news: nothing to rebuild

The core point of this chapter: **the architecture does not change**. The encoder, world model, planner — in principle, these are the exact same building blocks as on Crafter. Only the game changes. If the JEPA concept (compress first, predict second, in a summary rather than pixels) is solid, it should work on any video game, not just Crafter. This chapter puts that premise to the test.

## The technical pipe connecting Python to real Minecraft

Real Minecraft isn't written in Python. The project uses **MineRL**, a library that drives Minecraft via a mod named **Malmo** (originally developed by Microsoft). The technical path looks like this: Python code sends commands to a Java server running a real instance of Minecraft, and receives back a 64×64 pixel image — the exact same size as Crafter images, so nothing else needs to change.

This Python ↔ Java bridge is fragile. The project ran into a particularly stubborn bug nicknamed **MALMOBUSY**: after a first game episode finished, whenever it tried to launch the next one, everything froze for three minutes before crashing. In short: when an episode ends, Minecraft takes a moment to return to a "ready for next" state, but Python, impatient, sends the next command immediately. Minecraft responds "busy", closes the connection... and Python keeps waiting for a response on a line that no longer exists.

The solution retained, not elegant but reliable: **relaunch Minecraft completely for every episode** rather than attempting to reuse the same instance. Each Minecraft game starts in 30 to 60 seconds; collecting 20 episodes takes about half an hour — slow, but robust.

## First attempt: agent spins in circles, zero reward

Once the technical connection was stabilized, the first real test yielded an undeniable result: over 20 game episodes ("chop a tree"), the agent obtained **zero reward, zero achievements**. It doesn't crash, it plays — but it never does anything useful.

Two reasons, both stemming from the same underlying issue:

**1. The goal contained no signal.** The goal (the centroid from Chapter 4) had been built from images of an agent wandering at random — and a random agent never chops trees. Result: the goal pointed to nothing in particular, like asking directions from someone who has never been where you want to go.

**2. The world model was too weak.** On images recorded by an agent wandering aimlessly, Minecraft changes very little from frame to frame — so the world model mainly learned that "nothing ever changes", leaving the planner blind: imagining 12 steps into the future almost never leads anywhere different.

## The fix: learning from real human gameplay

The project retrieved recordings of real games played by humans — players who actually know how to chop trees. The official servers hosting these recordings were no longer online (404, the site shut down), but the community had created a backup on Zenodo (a public scientific archive): 210 recorded gameplay sessions, complete with video and actions.

By re-training the encoder and world model on these 453,496 images from real games (including 12,056 frames showing a moment where a player had just chopped wood), the project obtained a goal *with actual signal* — and yet, that still wasn't enough.

## Four attempts, four failures — and a recurring lesson

**The crucial detail**: in this game, breaking a tree trunk requires **holding the "strike" button fixed, aimed at the exact same trunk, for about twenty consecutive frames**. Moving at the same time changes the aimed target every instant — the chop never completes. In real human games, 76% of moments where a player just obtained wood show the action "strike, without moving" — not "walk forward while striking". Any method incapable of *holding* a precise action over time is doomed from the start.

- **Attempts 1 & 2** — the same planner from Chapter 4, reconnected to Minecraft: failure, zero reward. The world model was still not good enough to distinguish different futures on near-static images.
- **Attempt 3** — learning directly, frame by frame, which key to press ("imitation" of a human player, with no world model or planning): failure. The agent froze in a loop on a single action. Two reasons: as soon as it deviates once from human behavior, it lands in a situation never seen during training and drifts; and Chapter 1's encoder had learned to summarize *scenes*, not spot "where the tree trunk is to aim at it".
- **Attempt 4** — a pure neural network, pixels to action, bypassing JEPA embeddings entirely: failed as well, for a different but related reason. A policy with zero memory of the recent past cannot express "I am currently breaking this block, I must keep going" — every frame is processed in isolation.

## What finally worked

The fifth attempt adopts Meta's action-conditioned architecture (`eb_jepa`) with five changes at once, none sufficient on its own:

1. Keep a **spatial map** of embeddings rather than a simple flat vector — preserving "where in the image the trunk is located", information flattened out by a simple vector.
2. Train encoder and predictor **jointly**, conditioned on action, rather than freezing the encoder first — embeddings structure themselves directly around action *consequences*.
3. Have the predictor predict only the **change** between two images rather than the full next image — "do nothing" then becomes literally "predict zero change", an automatically sensible fallback.
4. Keep Chapter 2's anti-collapse safeguards — and they had to be fixed along the way (see below).
5. **Repeat every decided action for 4 game frames** rather than just 1 — allowing sustained strikes at last.

## Collapse almost ruined everything here, too

On the first trial of this new architecture, the anti-collapse signal (Chapter 2's `batch_var`) collapsed to zero by training epoch 3 — a genuine collapse. The cause: the safeguard was checking variance *across pixels within a single spatial map*, which stays almost always non-zero, instead of checking variance *across different images in the batch*, which is the only variance that truly matters. The safeguard was monitoring the wrong thing — once fixed, `batch_var` remained stable around 1.2 across 20 full epochs.

## The result: the agent actually chops trees

With these five ingredients, the resulting agent actually chops wood in real Minecraft — not 100% of the time, but a genuine, measured, honest success: over 20 episodes with the published version, 25% of episodes obtain at least one wood log, with an average reward of 0.30 (one episode even chopped two logs). It's a modest result in absolute terms, but it's the very first time the pipeline works on real Minecraft — after four clean, well-understood failures.

## The honesty that followed: this number moves, and not for the reasons you think

Once this result was achieved, the project tried to understand *why* — and reproduce it. The first explanation that seemed obvious ("a larger embedding breaks MPC search coverage") turned out to be **false**: re-running the experiment with a small embedding but the same "more aggressive" training recipe (more epochs, longer sequences), the agent failed as well. Model size is not what mattered.

What actually matters is **the training recipe** — measured by Chapter 3's famous ratio (predictor error / lazy solution error). The original recipe converges to a ratio of about **0.93**, and it is the only one producing a functioning agent. Training *longer* (more epochs, longer sequences) drops this ratio to about 0.88 — which looks "better" according to Chapter 3's metric — but **breaks the agent**, regardless of model size. An overtrained world model learns to copy the *static pose* that accompanies success (standing still while striking) instead of the *gesture* leading to success (approaching then striking) — the agent ends up freezing while striking empty air.

And there is a final layer of even more uncomfortable honesty: **even with the exact same recipe and ratio (0.93), two different training runs yielded 50% success once, and 25% another time**. Training was not seeded with a fixed random seed (a number that fixes all internal randomness so you can replay the exact same sequence of events): each training run draws slightly different randomness, and that difference suffices to alter the "shape" of latent space in a way that doesn't show up in the ratio, but drastically alters final game success. The officially published checkpoint gets 25% — honest, not the highest number ever observed, but the one actually available and reproducible as-is.

:::

::: expert

## Phase 4 Objective and Architectural Invariance

This chapter port Phase 1-3 pipeline (encoder, action-conditioned world model, random-shooting MPC) from Crafter to **MineRL**, maintaining architectural design — only the input domain changes (real 3D Minecraft rendering 64×64 RGB vs pixel-art Crafter). The explicit objective is testing whether the JEPA hypothesis (predictive low-dimensional features over exhaustive pixel reconstruction) holds on a visually richer, less stylized domain.

## The MineRL/Malmo Technical Bridge

```
Python ──► Malmo (JVM, Java 8) ──► Minecraft Forge ──► 64×64 rendering
```

Notable setup constraints: strict JDK 8 required (incompatible with JVM 11+), `gradlew.bat` requires `shell=True` under Python 3.12, JitPack MixinGradle repository unavailable (replaced with `org.spongepowered:mixingradle:0.6-SNAPSHOT`), Forge compilation ~15-30 min (~500 MB). The MineRL action space is a **dict of continuous actions** (`forward`, `attack`, `jump`, `camera: [pitch, yaw]`, …), discretized into 17 classes via a fixed table (`configs/minerl_actions.yaml`) — analogous to the 17-action discrete space used on Crafter, enabling reuse of the action-conditioned predictor without changing interface signatures.

## The MALMOBUSY Bug

Symptom: `TimeoutError: Mission didn't start after 180 seconds` on the second `env.reset()`. Root cause: MineRL 0.4.4 communicates over TCP socket; at episode end, Python immediately sends the next `MissionInit`, but the JVM responds `MALMOBUSY` (not yet returned to DORMANT) and **closes the server-side socket**. Python retries on the orphaned socket and blocks until timeout:

```
Python                     Minecraft (JVM)
  │── <MissionInit> ────────────►│ (RUNNING→DORMANT in progress)
  │◄─────────────── MALMOBUSY ──│
  │── <MissionInit> (retry) ───►│  ← socket closed Java-side
  │  (blocked on recv, 180s)     │
  TimeoutError ✗
```

Failed fix attempts: increasing `SOCKTIME` (240s→1200s, timeout still hit after ~20 min); patching socket reconnection in `_multiagent.py` (Minecraft ignores new connection). **Retained workaround**: fresh Python process per episode (`scripts/collect_minerl_multi.py --shards 15`, `scripts/play_minerl_multi.py --episodes N`) — the first episode of a fresh process always succeeds since it involves zero `reset()` calls. Cost: ~30-60s Minecraft startup overhead per episode.

## Diagnostic of First Failure (Random Agent → Demos)

```
scripts/play_minerl_multi.py --episodes 20 → 19/20 completed, mean reward 0.000
```

Two shared causes: (1) goal embedding, built from frames collected by a random policy that never chops trees, points in no useful direction; (2) world model, evaluated via `ratio = val_pred/val_copy = 0.983` on random data — a quasi-static agent produces transitions where "nothing changes" is already near-optimal, so predictor learns zero causal action→consequence dynamics, only identity.

## Human Demonstrations (Zenodo)

Official MineRL S3 servers dead (`404`); community backup on Zenodo (`zenodo.org/records/12659939`, `MineRLTreechop-v0.zip`, 1.5 GB, 210 demonstrations). Per-demo format: `recording.mp4` (raw video), `rendered.npz` (rewards + discrete actions, **without frames**), `metadata.json`. `scripts/prepare_demos.py` extracts MP4 frames via `cv2.VideoCapture`, resizes to 64×64, discretizes actions, aligns MP4↔NPZ (1-2 frame shift possible). Output:

```
Total frames    : 453,496
Frames reward>0 : 12,056 (2.7%)
Demos loaded    : 210
```

Re-training (`train_encoder_demos`, `train_wm_demos`) on this expert corpus.

## Reward Mechanism — The Constraint Dictating Architecture

Chopping a trunk in Treechop requires **holding `attack` fixed, aimed at the same block, over ~20 consecutive ticks**. Empirical proof from the 12,056 reward>0 frames in human demos:

```
a6  (attack only)      : 76.2%
a0  (noop)              : 8.8%
a1  (forward)           : 5.1%
a7  (forward+attack)    : 4.7%
```

Any policy incapable of producing **sustained, precise action over time** is structurally doomed — this finding directly motivates the `action_repeat=4` ingredient in the final architecture.

## Four Failed Approaches — Causal Analysis

**Approaches 1-2 — MPC + 1-step World Model (Flat Vector).** Ratio capped at 0.959 on quasi-static data: "change nothing" is already near-optimal, so after 12 rollout steps all 512 candidate latents converge to near-identical vectors → argmax becomes arbitrary. A 1-step Markovian predictor also cannot represent "attack same block 20 times" — temporal dependence exceeds single-step horizon.

**Approach 3 — Behavioral Cloning on Frozen Encoder + Classification Head.** `val_acc` ≈ 64% offline, but in-game agent freezes on a single action (a0 or a7 at ~100%). Two intertwined causes: *covariate shift* (first deviation leads agent to states never seen in demos → wild predictions → uncorrected drift); and JEPA encoder, trained frame→frame without action conditioning, encodes *scenes* rather than actionable cues ("where to aim"). Corrective attempt (reweighting class a6, 58% of data): counter-productive — penalizing the very action producing reward.

**Approach 4 — End-to-End CNN pixels→action.** `val_acc` ≈ 49%, still frozen. Distinct but related cause: memoryless policy cannot express temporal commitment ("I am breaking this block, keep going") — every frame processed independently.

## Breakthrough Architecture: Action-Conditioned eb-JEPA

Five simultaneous differences from earlier approaches, each insufficient alone:

| # | Ingredient | Why |
|---|------------|-----|
| 1 | **Spatial** latents `[64,8,8]` (vs flat vector 128) | Preserves "where the trunk is in the frame" |
| 2 | Encoder + predictor trained **jointly**, action-conditioned | Latent structured around action *consequences* |
| 3 | **Residual** predictor (predicts `s_{t+1}-s_t`) | "Do nothing" = copy → ratio ≤ 1 guaranteed by design |
| 4 | **Fixed** VICReg (`spatial_as_samples=False`) | Measures variance *across batch samples*, not map pixels |
| 5 | `action_repeat=4` | Re-plans every 4 ticks, repeats action → produces sustained attack |

### Collapse Trap Revisited

First eb_jepa run: `batch_var` 0.0018 → 0.0000 by epoch 3 (total collapse). Cause: regularizer configured with `spatial_as_samples=True`, measuring variance *across pixels of a single spatial map* (always non-zero by design), instead of variance *across batch entries* (which was collapsing) — regularizer was **active yet blind to actual collapse**. Fix: `spatial_as_samples=False` + `std_coeff` 1→10, `cov_coeff` 0.04→1. Post-fix: `batch_var` stable ~1.2 across 20 epochs.

```
Pre-fix : batch_var 0.0018 → 0.0000 (epoch 3)   ⚠️ COLLAPSE
Post-fix: batch_var ~1.2 stable over 20 epochs   ✅
```

## Phase 4 Gate Result

```bash
scripts/train_eb_jepa.py   →  checkpoints/ebwm.pt  (ratio 0.929, batch_var ~1.2)
scripts/play_minerl_multi.py --script scripts/play_ebwm.py
```

| Approach | Mean Reward | Success Rate | Status |
|----------|------------|--------------|--------|
| 1-2. MPC + 1-step WM (ratio ≈0.96) | 0.000 | 0% | ✗ |
| 3. Frozen Encoder BC + Head | 0.000 | 0% | ✗ |
| 4. End-to-End CNN BC | 0.000 | 0% | ✗ |
| 5. Action-Conditioned eb-JEPA MPC | 0.30–0.75 | 25–50% | ✅ |

Final published result (20/20 episodes, published checkpoint, ratio 0.927): **mean reward 0.30, success rate 25.0% (5/20)**, one episode chopping 2 logs. Executed actions are **varied and shift with scene** (mix of a14/a13/a1/a6), contrasting BC policies frozen on single actions — confirming planner actually leverages world model rather than memorizing a single gesture.

> **Honest Caveat on Number**: Success rate varies **25-50% between training runs** with near-identical prediction ratio (~0.93). Best observed run hits 50% (10/20); published checkpoint gets 25% (5/20). Training was **unseeded** — each run yields distinct latent geometry, and downstream planning success is only **weakly coupled** to reproducible prediction metrics (see ablation below). The "random baseline ~0.4" printed by script is a legacy estimate, never re-measured on this harness — treat absolute result (agent chops trees, up to 2 logs/episode) as solid claim, not baseline comparison.

## Ablation: What Actually Drives Performance

Four training runs on the same 453K demo frame corpus:

| Run | embed_dim | Recipe | Params | Ratio | Success Rate |
|-----|-----------|--------|--------|-------|--------------|
| Original (lost) | 64 | T=8, 20 ep | 664K | 0.929 | **50%** |
| WM v2 | **128** | T=12, 25 ep | 2.47M | 0.890 | 5% |
| v1-retrain | 64 | T=12, 25 ep | 664K | 0.882 | ~0% |
| v1-restored | 64 | **T=8, 20 ep** | 664K | 0.927 | **25%** |

**First Hypothesis (False): "Larger latent breaks MPC search coverage".** When WM v2 (embed_dim=128) regressed to 5%, natural explanation was that doubling latent `[128,8,8]` made space too large for 512 random-shooting candidates. **v1-retrain disproved this**: reverting architecture alone (embed_dim=64) while keeping v2 recipe (T=12, 25 epochs) still failed (~0%). Small latent, still broken — model size was not the cause.

**What Actually Matters: Training Recipe via Prediction Ratio.** The only configuration producing a functional agent is the original recipe (sequences T=8, 20 epochs), converging to ratio **~0.93**. Both overtrained variants (T=12, 25 epochs → ratio ~0.88), at *any* embed_dim, produce a broken agent. Training world model *harder* (more epochs, longer sequences → lower ratio) causes planner to learn the **static pose** of success frames (a6 = attack-only, 76% of reward>0 frames) instead of the **gesture** producing reward — agent stands still swinging at empty air. A **sweet spot** exists around ratio 0.93; "lower is better" does not hold.

**And Even at Sweet Spot, Run-to-Run Variance Remains High.** Original run hit 50%; restored run (same recipe, near-identical ratio 0.927) hit 25%. Training was unseeded, so each run produces distinct latent geometry, and downstream planning success is only **weakly coupled** to reproducible prediction metrics. The 50% was a favorable draw, not a recipe guarantee.

**Honest Takeaway**: A world model predicting *better* offline (lower ratio) can produce a *worse* agent, and two runs at identical recipe/ratio can differ by 2x in game success. Prediction quality is necessary but far from sufficient — latent *geometry* governing planning is not captured by prediction loss alone.

## Phase 4 Lessons

1. **Reward dictates architecture.** Treechop = sustained precise attack → required temporal commitment policy (`action_repeat` + world model).
2. **World model architecture matters as much as data.** Frozen frame→frame encoder (ratio 0.96) vs joint action-conditioned encoder+predictor (ratio 0.929 with *actionable* latents): difference between 0% and 50%.
3. **Collapse is sneaky.** A regularizer can appear active (low `reg_loss`) while blind to actual collapse. Always monitor `batch_var` (inter-sample variance), not just regularizer loss.
4. **Honest diagnostics beat blind iteration.** Three deeply analyzed failures led to working architecture; blind iteration never would have.
5. **Better prediction ≠ better agent — and recipe, not size, is the lever.** Overtraining world model (more epochs/data → ratio 0.88) breaks agent at both tested embed_dims; only original recipe (ratio ~0.93) works. Ratio sweet spot exists; "lower is better" is false.
6. **Planning success is weakly coupled to prediction metric, with high run-to-run variance.** Same recipe, same ratio 0.927 → 50% on one draw, 25% on another. Unseeded training; latent geometry governing planning is unconstrained by prediction loss alone. Report ranges, not single best numbers — and seed training before claiming reproducibility.

## References (Verified, from docs/references/index.md)

- Meta FAIR, eb_jepa (github.com/facebookresearch/eb_jepa) — action-conditioned backbone vendored in `mine_jepa/eb_jepa/`, foundation of approach 5.
- Bardes, Ponce, LeCun, VICReg, arXiv:2105.04906 (ICLR 2022) — regularizer misconfiguration (`spatial_as_samples=True`) causing collapse in this chapter.
- Maes, Le Lidec, Scieur, LeCun, Balestriero, LeWorldModel, arXiv:2603.19312 (2026) — ratio convention origin used to characterize ~0.93 sweet spot.

:::

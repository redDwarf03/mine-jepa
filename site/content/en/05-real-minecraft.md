---
title: "The leap to real Minecraft: four failures, then an agent that chops trees"
slug: "05-real-minecraft"
lang: "en"
order: 5
prerequisites: ["01-what-is-jepa", "02-the-collapse-trap", "03-the-world-model", "04-planning-in-imagination"]
source_docs: ["docs/06_minecraft_port.md", "CLAUDE.md#Phase 4 gates"]
---

::: beginner

## Crafter was just training wheels

Up to this point, everything the project has built — the encoder (Chapter 1), the anti-collapse safeguards (Chapter 2), the world model (Chapter 3), the planner (Chapter 4) — has been tested on **Crafter**, a lightweight game that looks like a simplified 2D version of Minecraft. It was the right choice for rapid debugging. But the true goal of the project, the one that gives the project its name, is **real** Minecraft — the 3D game with real textures, the one everyone thinks of when you say "an AI playing Minecraft."

This chapter tells the story of what happened when the project made that leap. And let's be honest: **it did not work on the first try. Nor the second. Nor the third. Nor the fourth.**
The fifth attempt worked — and understanding *why* the first four failed is at least as instructive as the final success.

## First, the good news: nothing to rebuild

The key point of this chapter: **the architecture does not change**. The encoder, the world model, the planner — in principle, these are exactly the same building blocks as on Crafter. Only the game changes. If the JEPA idea (compress first, predict later, in a summary rather than in pixels) is solid, it should work on any video game, not just Crafter. This is exactly what this chapter tests.

## The technical pipe connecting Python to real Minecraft

Real Minecraft is not written in Python. The project uses **MineRL**, a library that drives Minecraft via a mod called **Malmo** (originally developed by Microsoft). The technical path looks like this: the Python code sends commands to a Java server running a real Minecraft instance, and receives a 64×64 pixel image back — the same size as Crafter images, so nothing else needs to change.

This Python ↔ Java bridge is fragile. The project encountered a particularly nasty bug, nicknamed **MALMOBUSY**: after a first game episode, as soon as the code tried to launch the next one, everything would freeze for three minutes before crashing. The reason, in short: when an episode ends, Minecraft takes a little time to return to a "ready for the next one" state, but Python, impatient, already sends the next command. Minecraft replies "busy", closes the connection... and Python keeps waiting for an answer on a line that no longer exists.
The chosen solution, inelegant but reliable: **relaunch Minecraft entirely for each episode** rather than trying to reuse the same instance. Each Minecraft session takes 30 to 60 seconds to boot; collecting 20 episodes therefore takes about half an hour — slow, but robust.

## First attempt: the agent spins in circles, zero reward

Once the technical connection was stabilized, the first real test yielded a stark result: over 20 gameplay episodes ("chop a tree"), the agent obtained **zero reward, zero achievements**. It doesn't crash, it plays — but it never does anything useful.

There were two reasons, both tied to the same underlying problem:

**1. The goal had no signal.** The goal (the centroid from Chapter 4) had been constructed from images of an agent wandering at random — and an agent wandering at random never chops a tree. Result: the goal didn't point to anything in particular, like asking for directions from someone who has never been where you want to go.

**2. The world model was too weak.** On images recorded by an aimlessly wandering agent, Minecraft changes very little from one frame to the next — so the world model mostly learned that "nothing ever changes", making planning blind: imagining 12 steps into the future almost never leads anywhere different.

## The solution: learning from real human gameplay

The project retrieved recordings of real games played by humans — players who actually know how to chop trees. The official servers hosting these recordings no longer existed (404, site closed), but the community had made a backup copy on Zenodo (a public scientific archive): 210 recorded games, with video and actions.

By retraining the encoder and the world model on these 453,496 images from real human play (12,056 of which showed a moment where a player had just obtained wood), the project got a goal *with real signal* — and yet, that still wasn't enough.

## Four attempts, four failures — and a recurring lesson

**The crucial detail**: in this game, breaking a tree trunk requires **holding the "attack" button down, aimed at the exact same trunk, for about twenty consecutive instants**. Moving at the same time changes the aimed target at every instant — the breaking process resets and never finishes. In real human games, 76% of the moments where the player just got wood show the action "attack, without moving" — not "move forward while attacking". Any method incapable of *holding* a precise action over time is doomed from the start.

- **Attempts 1 and 2** — the exact same planner as in Chapter 4, plugged into Minecraft: failure, zero reward. The world model was still not good enough to distinguish different futures on nearly static images.
- **Attempt 3** — learning directly, frame by frame, which button to press ("imitating" a human player, without a world model or planning): failure. The agent froze on a single action repeated endlessly. Two reasons: as soon as it deviates even once from human behavior, it finds itself in a situation never seen during training and drifts; and the Chapter 1 encoder had learned to summarize *scenes*, not to pinpoint "where is the trunk so I can aim at it".
- **Attempt 4** — a pure neural network, pixels directly to actions, completely bypassing JEPA embeddings: also a failure, for a different but related reason. A policy without any memory of the recent past cannot express "I am currently breaking this block, I must continue" — each frame is processed in isolation.

## What finally worked

The fifth attempt took Meta's action-conditioned architecture (`eb_jepa`) with five changes applied all at once, none of which were sufficient on their own:

1. Keep a **spatial map** of embeddings rather than a simple flat vector — to preserve "where in the image the trunk is", information that gets crushed by a flat vector.
2. Train the encoder and the predictor **together**, conditioned on the action, rather than freezing the encoder first — the embeddings structure themselves directly around the *consequences* of actions.
3. Have the predictor predict only the **change** between the two images rather than the entire next image — "doing nothing" then literally becomes "predicting zero change", an automatically reasonable fallback solution.
4. Keep the anti-collapse safeguards from Chapter 2 — and they had to be fixed along the way (see below).
5. **Repeat every decided action for 4 game ticks** rather than just one — this is what finally allows the agent to hold a sustained swing.

## A collapse almost ruined everything, here too

On the first try of this new architecture, the anti-collapse signal (the `batch_var` from Chapter 2) plummeted to zero by the third training epoch — a true collapse. The cause: the safeguard was checking the variance *between the pixels of the same map*, which almost always stays non-zero, instead of checking the variance *between different images in the batch*, the only one that actually matters. The safeguard was monitoring the wrong thing — once fixed, `batch_var` remained stable around 1.2 for 20 full epochs.

## The result: the agent actually chops trees

With these five ingredients, the resulting agent actually chops wood in real Minecraft — not 100% of the time, but a real, measured, and honest success: over 20 episodes with the published version, 25% of episodes obtain at least one log, with an average reward of 0.30 (one episode even chopped two logs). It is a modest result in absolute terms, but it is the very first time the pipeline works on real Minecraft — after four clean, well-understood failures.

## The honesty that followed: this number moves, and not because of luck as you might think

Once this result was achieved, the project tried to understand *why* — and to reproduce it.
The first explanation that seemed obvious ("a larger embedding breaks the planner's coverage") turned out to be **false**: when re-running the experiment with a small embedding but the same "harder" training recipe (more epochs, longer sequences), the agent failed too. So it is not the size of the model that matters.

What really matters is **the training recipe** — measured by the famous ratio from Chapter 3 (predictor error / lazy solution error). The original recipe converges to a ratio of about **0.93**, and it is the only one that produces an agent that plays correctly. Training *longer* (more epochs, longer sequences) lowers this ratio to about 0.88 — which seems "better" according to the Chapter 3 metric — but **breaks the agent**, regardless of the model size. An overtrained world model learns to copy the *static pose* that accompanies success (standing perfectly still while attacking) instead of the *action* that leads to success (approaching then attacking) — the agent ends up freezing and swinging at empty air.

And there is a final layer of honesty, even more uncomfortable: **even with exactly the same recipe and the same ratio (0.93), two different training runs yielded 50% success once, and 25% another time**. The training was not fixed with a static random seed (a "seed" — a number that fixes all internal randomness, so you can replay the exact same sequence of events): every training run draws slightly different randomness, and this difference is enough to change the "shape" of the latent space in a way that doesn't show up in the ratio, but vastly changes the final success rate. The officially published checkpoint achieves 25% — honest, not the highest number ever observed, but the one that is actually available and reproducible as-is.

:::

::: expert

## Phase 4 Objective and Architectural Invariance

This chapter ports the Phase 1-3 pipeline (encoder, action-conditioned world model, random-shooting MPC) from Crafter to **MineRL**, without changing the architectural design — only the input domain changes (real 64×64 RGB Minecraft 3D rendering vs Crafter pixel-art). The explicit goal is to test whether the JEPA hypothesis (predictive and low-dimensional features rather than exhaustive pixel reconstruction) holds on a visually richer and less stylized domain.

## The MineRL/Malmo Technical Bridge

```
Python ──► Malmo (JVM, Java 8) ──► Minecraft Forge ──► 64×64 render
```

Notable setup constraints: strict JDK 8 required (JVM 11+ incompatible), `gradlew.bat` requires `shell=True` under Python 3.12, MixinGradle JitPack repo unavailable (replaced by `org.spongepowered:mixingradle:0.6-SNAPSHOT`), Forge compilation takes ~15-30 min (~500 MB). The MineRL action space is a **dict of continuous actions** (`forward`, `attack`, `jump`, `camera: [pitch, yaw]`, ...), discretized into 17 classes via a fixed lookup table (`configs/minerl_actions.yaml`) — directly analogous to the 17-action space already used on Crafter, allowing the action-conditioned predictor to be reused without changing its signature.

## The MALMOBUSY Bug

Symptom: `TimeoutError: Mission didn't start after 180 seconds` on the second `env.reset()`. Root cause: MineRL 0.4.4 communicates via TCP socket; at the end of an episode, Python immediately sends the next `MissionInit`, but the JVM replies `MALMOBUSY` (not yet back to DORMANT) and then **closes the server-side socket**. Python retries on the now-orphaned socket and blocks until timeout:

```
Python                     Minecraft (JVM)
  │── <MissionInit> ────────────►│ (RUNNING→DORMANT in progress)
  │◄─────────────── MALMOBUSY ──│
  │── <MissionInit> (retry) ───►│  ← socket already closed Java-side
  │  (blocked on recv, 180s)     │
  TimeoutError ✗
```

Failed fix attempts: increasing `SOCKTIME` (240s→1200s, timeout still hit after ~20 mins); patching the socket reconnection in `_multiagent.py` (Minecraft ignores the new connection). **Adopted workaround**: a fresh Python process per episode (`scripts/collect_minerl_multi.py --shards 15`, `scripts/play_minerl_multi.py --episodes N`) — the first episode of a fresh process always succeeds since it does not involve any `reset()`. Cost: ~30-60s of Minecraft boot time per episode.

## First Failure Diagnostic (random agent → demos)

```
scripts/play_minerl_multi.py --episodes 20 → 19/20 completed, mean reward 0.000
```

Two shared causes: (1) the goal embedding, constructed from frames collected by a random policy that never chops a tree, points in no useful direction; (2) the world model, evaluated via `ratio = val_pred/val_copy = 0.983` on those same random data — a quasi-static agent produces transitions where "nothing changes" is already almost optimal, so the predictor learns no causal action→consequence dynamics, only a near-identity mapping.

## Human Demonstrations (Zenodo)

The official MineRL S3 servers are dead (`404`); community backup on Zenodo (`zenodo.org/records/12659939`, `MineRLTreechop-v0.zip`, 1.5 GB, 210 demonstrations). Per-demo format: `recording.mp4` (raw video), `rendered.npz` (rewards + discrete actions, **without frames**), `metadata.json`. `scripts/prepare_demos.py` extracts frames from the MP4 via `cv2.VideoCapture`, downscales to 64×64, discretizes actions, and aligns MP4↔NPZ (possible 1-2 frame drift). Result:

```
Total frames    : 453,496
Frames reward>0 : 12,056 (2.7%)
Loaded demos    : 210
```

Retraining (`train_encoder_demos`, `train_wm_demos`) on this expert corpus.

## The Reward Mechanism — The Constraint That Dictates Architecture

Breaking a trunk in Treechop requires **holding `attack` fixed, aimed at the exact same block, for ~20 consecutive ticks**. Empirical proof, from the 12,056 reward>0 frames of human demos:

```
a6  (attack only)      : 76.2%
a0  (noop)              : 8.8%
a1  (forward)           : 5.1%
a7  (forward+attack)    : 4.7%
```

Any policy incapable of producing a **sustained and precise action over time** is structurally doomed — this finding directly motivates the `action_repeat=4` ingredient in the final architecture.

## The Four Failing Approaches — Causal Analysis

**Approaches 1-2 — MPC + 1-step world model (flat vector).** Ratio capped at 0.959 on near-static data: "change nothing" is already near-optimal, so after a 12-step rollout the 512 candidates converge to almost identical latents → the argmax becomes an arbitrary choice. Furthermore, a 1-step Markovian predictor cannot represent "attack the same block 20 times" — the temporal dependency exceeds the horizon of a single conditioned step.

**Approach 3 — Behavioral Cloning on frozen encoder + classification head.** `val_acc` ≈ 64% offline, but in-game the agent freezes on a single action (a0 or a7 at ~100%). Two intertwined causes: *covariate shift* (at the very first deviation, the agent reaches states never seen in demos → aberrant predictions → uncorrected drift); and the JEPA encoder, trained frame→frame without action conditioning, encodes *scenes* rather than actionable cues ("where to aim"). Corrective attempt (upweighting class a6, 58% of data): counterproductive effect — it ends up penalizing the exact action that produces the reward.

**Approach 4 — CNN end-to-end pixels→action.** `val_acc` ≈ 49%, still freezes. Distinct but related cause: a memoryless policy cannot express temporal commitment ("I am breaking this block, I must continue") — each frame is processed independently.

## The Unlocking Architecture: action-conditioned eb-JEPA

Five simultaneous differences from the previous approaches, none sufficient on their own:

| # | Ingredient | Why |
|---|------------|----------|
| 1 | **Spatial** latents `[64,8,8]` (vs flat 128 vector) | preserves "where the trunk is in the image" |
| 2 | Encoder + predictor trained **jointly**, action-conditioned | latent structured around action *consequences* |
| 3 | **Residual** predictor (predicts `s_{t+1}-s_t`) | "do nothing" = copy → ratio ≤ 1 guaranteed by design |
| 4 | **Fixed** VICReg (`spatial_as_samples=False`) | measures variance *between batch samples*, not between map pixels |
| 5 | `action_repeat=4` | replans every 4 steps, repeats action → produces the sustained attack |

### The Collapse Trap, Again

First eb_jepa training run: `batch_var` 0.0018 → 0.0000 at epoch 3 (total collapse). Cause: the regularizer was configured with `spatial_as_samples=True`, measuring the variance *between pixels of the same spatial map* (always non-zero by construction), instead of the variance *between batch inputs* (the one that was actually collapsing) — an **active regularizer, but blind to the collapse that mattered**. Fix: `spatial_as_samples=False` + `std_coeff` 1→10, `cov_coeff` 0.04→1. After fix: `batch_var` stable at ~1.2 over 20 epochs.

```
Before fix : batch_var 0.0018 → 0.0000 (epoch 3)   ⚠️ COLLAPSE
After fix  : batch_var ~1.2 stable over 20 epochs   ✅
```

## Gate 4 Result

```bash
scripts/train_eb_jepa.py   →  checkpoints/ebwm.pt  (ratio 0.929, batch_var ~1.2)
scripts/play_minerl_multi.py --script scripts/play_ebwm.py
```

| Approach | Mean Reward | Success | Status |
|----------|-------------|--------|--------|
| 1-2. MPC + 1-step WM (ratio ≈0.96) | 0.000 | 0% | ✗ |
| 3. BC frozen encoder + head | 0.000 | 0% | ✗ |
| 4. BC end-to-end CNN | 0.000 | 0% | ✗ |
| 5. Action-conditioned eb-JEPA MPC | 0.30–0.75 | 25–50% | ✅ |

Final published result (20/20 episodes, published checkpoint, ratio 0.927): **mean reward 0.30, success rate 25.0% (5/20)**, with one episode chopping 2 logs. Executed actions are **varied and change with the scene** (mix of a14/a13/a1/a6), contrasting with BC policies frozen on a single action — a sign that the planner genuinely exploits the world model rather than memorizing a single gesture.

> **Honest caveat on the number.** The success rate varies **25-50% between training runs** with nearly identical prediction ratios (~0.93). The best run observed hit 50% (10/20); the published checkpoint gets 25% (5/20). Training is **not seeded** — each run yields a different latent geometry, and downstream planning success is only **weakly coupled** to the reproducible prediction metric (see ablation below). The "random ~0.4" baseline printed by the script is an inherited estimate, never re-measured on this harness — treat the absolute result (the agent chops trees, up to 2 logs/episode) as the solid claim, not the comparison to the baseline.

## Ablation: what actually determines performance

Four training runs on the same corpus of 453K demo frames:

| Run | embed_dim | recipe | Params | Ratio | Success |
|-----|-----------|---------|--------|-------|--------|
| Original (lost) | 64 | T=8, 20 ep | 664K | 0.929 | **50%** |
| WM v2 | **128** | T=12, 25 ep | 2.47M | 0.890 | 5% |
| v1-retrain | 64 | T=12, 25 ep | 664K | 0.882 | ~0% |
| v1-restored | 64 | **T=8, 20 ep** | 664K | 0.927 | **25%** |

**First hypothesis (false): "the larger latent breaks MPC coverage".** When WM v2 (embed_dim=128) regressed to 5%, the natural explanation was that doubling the `[128,8,8]` latent made the space too large for 512 random shooting candidates. **v1-retrain refutes this**: reverting purely to the architecture (embed_dim=64) while keeping the v2 recipe (T=12, 25 epochs) still fails (~0%). Small latent, still broken — size was not the cause.

**What actually matters: the training recipe, via the prediction ratio.** The only setup producing a functional agent is the original recipe (sequences T=8, 20 epochs), converging to a **~0.93** ratio. Both overtrained variants (T=12, 25 epochs → ratio ~0.88), at *any* embed_dim, produce a broken agent. Training the world model *harder* (more epochs, longer sequences → lower ratio) causes the planner to learn the **static pose** of success frames (a6 = attack-only, 76% of reward>0 frames) rather than the **gesture** producing the reward — the agent freezes, attacking empty air. There is a **sweet spot** around a 0.93 ratio, not a "lower is better" rule.

**And even at this sweet spot, run-to-run variance remains high.** The original draw hit 50%; the restored draw (same recipe, near-identical 0.927 ratio) hit 25%. Training is not seeded, so each run produces a distinct latent geometry, and downstream planning success is only **weakly coupled** to the reproducible prediction metric. The 50% was a favorable draw, not a guarantee of the recipe.

**Honest takeaway**: a world model that predicts *better* during training (lower ratio) can produce a *worse* agent, and two runs with identical recipes and ratios can differ by a factor of 2 in success. Prediction quality is necessary but far from sufficient — the latent *geometry* that planning relies on is not captured by the prediction loss alone.

## Phase 4 Lessons

1. **Reward dictates architecture.** Treechop = sustained, precise attack → a policy capable of temporal commitment (`action_repeat` + world model) was required.
2. **World model architecture matters as much as data.** Frame→frame frozen encoder (ratio 0.96) vs joint action-conditioned encoder+predictor (ratio 0.929 but *actionable* latents for planning): the difference between 0% and 50%.
3. **Collapse is insidious.** A regularizer can appear active (low `reg_loss`) while being blind to the collapse that actually matters. Always monitor `batch_var` (inter-sample variance), not just the regularizer loss.
4. **An honest diagnostic beats blind iteration.** Three deeply analyzed failures led to the right architecture; blind iteration would not have found it.
5. **Better prediction ≠ better agent — and recipe, not size, is the lever.** Overtraining the world model (more epochs/data → ratio 0.88) breaks the agent at both tested embed_dims; only the original recipe (ratio ~0.93) works. There is a ratio sweet spot, not a "lower is better" rule.
6. **Planning success is weakly coupled to the prediction metric, with high run-to-run variance.** Same recipe, same 0.927 ratio → 50% on one draw, 25% on another. Training is not seeded; latent geometry, which planning relies on, is not fixed by the prediction loss. Report ranges, not the most favorable number — and seed training before claiming reproducibility.

## References (Verified, from docs/references/index.md)

- Meta FAIR, eb_jepa (github.com/facebookresearch/eb_jepa) — the action-conditioned backbone vendored into `mine_jepa/eb_jepa/`, foundation of approach 5.
- Bardes, Ponce, LeCun, VICReg, arXiv:2105.04906 (ICLR 2022) — the regularizer whose misconfiguration (`spatial_as_samples=True`) caused the collapse in this chapter.
- Maes, Le Lidec, Scieur, LeCun, Balestriero, LeWorldModel, arXiv:2603.19312 (2026) — origin of the `ratio = val_pred/val_copy` convention used to characterize the ~0.93 sweet spot.

:::

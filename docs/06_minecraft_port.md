# Phase 4 — Porting to real Minecraft

> This doc explains how Mine-JEPA moves from Crafter (lightweight Python game) to **real
> Minecraft** via MineRL, without changing a single line of the JEPA architecture.
> This is the final validation: the same building blocks work on real pixels.

---

## Why move to Minecraft?

Crafter (Phases 1-3) validated the entire pipeline with a lightweight, pip-installable,
fast-running environment. That's the correct approach for debugging an architecture.

But the key question remains open: **are the representations learned on real Minecraft
pixels (64×64 RGB, 3D rendering, real textures) equally rich?**

MineRL gives the answer. It's the same game, the same survival mechanics, but with
Minecraft's real graphical assets — what everyone visualizes when you say
"AI plays Minecraft".

---

## The architecture doesn't change

This is the key point of Phase 4: **the encoder, world model, and planner are
identical**. Only the environment changes.

```
                    Phase 3 (Crafter)          Phase 4 (MineRL)
                    ─────────────────          ────────────────
Input pixels        64×64 pixel-art style      64×64 real 3D Minecraft
Actions             17 discrete                17 (treechop, forward, attack…)
Encoder             CrafterJEPA (15M params)   MineJEPA (same arch)
World Model         ActionConditionedPredictor  same
Planner             LatentMPCPlanner            same (horizon=12, N=512)
```

The JEPA idea — learning to predict in latent space rather than in pixels — is
**domain-agnostic**. If representations capture game structure, the planner works the same.

---

## MineRL — how it works

MineRL (MineRL Learning Lab) is a Python wrapper around **Malmo** (Microsoft),
itself a Minecraft mod. The pipeline is:

```
Python ──► Malmo Java ──► Minecraft Forge ──► 64×64 render
          (JVM server)    (mod + mechanics)
```

### Installation on Windows

Specific prerequisites:
- **Java 8 (JDK)** — Malmo runs on JVM 8, not compatible with 11+
- **Gradle** (bundled in MineRL via `gradlew.bat`)
- Python 3.12 with patches (see CLAUDE.md for the complete procedure)

Issues encountered and resolved:
1. `gym==0.19.0` rejected by modern setuptools → patch `opencv-python>=3.0` in source
2. `gradlew.bat` not executable without `shell=True` on Python 3.12
3. MixinGradle JitPack offline → replaced by `org.spongepowered:mixingradle:0.6-SNAPSHOT`
4. Malmo compilation: ~15-30 min, downloads Minecraft Forge (~500 MB)

### Available environments

```python
import minerl, gym

env = gym.make("MineRLTreechop-v0")        # chop a tree — simple task
env = gym.make("MineRLNavigateDense-v0")   # navigate to objective
env = gym.make("MineRLObtainIronPickaxe-v0")  # full survival
```

We only use `obs["pov"]` — a `[64, 64, 3]` uint8 tensor, identical to Crafter frames.
Everything else in the observation (inventory, health) is ignored.

---

## Code adaptation

### Action space

MineRL uses a **dict** of continuous actions, not an integer:

```python
# Crafter: action = 3  (an integer)
# MineRL:  action = {"forward": 1, "attack": 0, "jump": 0, "camera": [0, 0], ...}
```

We **discretize** into 17 actions via a fixed mapping (`configs/minerl_actions.yaml`):

| Index | Name             | forward | sprint | attack | camera  |
|-------|------------------|---------|--------|--------|---------|
| 0     | noop             | 0       | 0      | 0      | [0,0]   |
| 1     | forward          | 1       | 0      | 0      | [0,0]   |
| 6     | attack           | 0       | 0      | 1      | [0,0]   |
| 7     | forward+attack   | 1       | 0      | 1      | [0,0]   |
| 11    | turn left        | 0       | 0      | 0      | [0,-5]  |
| 12    | turn right       | 0       | 0      | 0      | [0,5]   |
| 13    | sprint+forward   | 1       | 1      | 0      | [0,0]   |
| 14    | sprint+fwd+atk   | 1       | 1      | 1      | [0,0]   |

### Initial collection

```bash
scripts/collect_minerl_multi.py --shards 15
→ 119,852 transitions (frames, discrete actions)
```

### Encoder + WM training (first iteration)

```bash
scripts/train_encoder.py --config configs/train_encoder_minerl.yaml
scripts/train_wm.py --config configs/train_wm_minerl.yaml
```

---

## MALMOBUSY bug — reset between episodes impossible

This is the hardest problem encountered in Phase 4. It deserves its own section
because it illustrates well the complexity of a Python ↔ JVM stack.

### The symptom

```
TimeoutError: Mission didn't start after 180 seconds
```

The script blocks completely after the first episode, during `env.reset()`.

### The cause

MineRL 0.4.4 uses **TCP sockets** to communicate between Python and the Minecraft JVM.
When an episode ends, Python immediately sends the next mission configuration via
`_send_mission()`. Minecraft responds `MALMOBUSY` — it hasn't returned to DORMANT state yet.

MineRL then retries on the **same TCP socket**. But after sending `MALMOBUSY`,
the Java handler (`EnvServerSocketHandler`) **closes this connection server-side**
and waits for a new connection. Python blocks indefinitely on `recv_message()` on
an orphan socket, until timeout.

```
Python                     Minecraft (JVM)
  │                              │
  │── <MissionInit> ────────────►│ (state: RUNNING→DORMANT in progress)
  │◄─────────────── MALMOBUSY ──│
  │── <MissionInit> (retry) ───►│  ← socket already closed Java-side
  │                              │
  │  (blocking on recv...)       │
  │  (180s pass...)              │
  TimeoutError ✗
```

### Failed attempts

| Attempt | Result |
|---------|--------|
| Increase `SOCKTIME` 240s → 1200s | Still times out (~20 min) |
| Patch socket reconnect on `MALMOBUSY` in `_multiagent.py` | Minecraft ignores new connection |

### Retained workaround: 1 process per episode

Episode 1 of a **fresh** Python process always succeeds — there's no reset,
just a first `env.reset()` on a fresh Minecraft.

```bash
scripts/play_minerl_multi.py --episodes 20   # launches N sequential subprocesses
scripts/collect_minerl_multi.py --shards 15  # same for collection
```

```
Process 1: Minecraft boot → episode 1 OK → Python exit
kill java.exe
Process 2: Minecraft boot → episode 2 OK → Python exit
kill java.exe
...
```

Downside: each Minecraft takes ~30-60s to start. For 20 episodes: ~30 min.

---

## First agent attempt — reward=0 diagnosis

### Results

```
scripts/play_minerl_multi.py --episodes 20
→ 19/20 episodes completed (1 Java crash)
→ mean reward: 0.000
→ achievements: 0.000
```

The agent runs without crashing, but chops no trees. Two identified causes.

### Problem 1 — Goal embedding with no signal

The MPC planner looks for the action that brings the latent state closer to the
**goal** (centroid of "good" states). This goal was built from random frames collected
by a random agent — which never chopped a tree.

```python
# Result: goal = centroid of arbitrary frames
# Signal: zero — the planner has no useful direction
```

### Problem 2 — World model too weak (ratio=0.983)

The world model is evaluated by the ratio `val_pred / val_copy`:
- `val_copy`: error if we copy the current state (naive baseline)
- `val_pred`: WM prediction error

A ratio < 1.0 means the WM does better than copying. But:

| Ratio   | Interpretation |
|---------|----------------|
| 0.38    | Useful WM (Phase 2 Crafter) |
| 0.983   | WM barely better than copying → planner blind |

On random data (119k frames of an aimlessly wandering agent), the WM doesn't learn
action consequences — it learns that "the next state looks like the current state"
(true for a stationary agent).

### Solution

Both problems share the same root: **training data with no signal**.
A random agent doesn't chop trees → no reward>0 frames → no goal →
no action→consequence dynamics to learn.

The solution: train on **human demonstrations** where players chop trees.

---

## Human demo dataset — Zenodo

### Why the official servers are dead

MineRL historically provided demos via Amazon S3:

```bash
curl https://minerl.s3.amazonaws.com/v4/MineRLTreechop-v0.tar
# → 404 Not Found (servers decommissioned)
```

### Zenodo backup

The community archived the demos on Zenodo (official backup, citable DOI):

```
https://zenodo.org/records/12659939
→ MineRLTreechop-v0.zip (1.5 GB)
→ 210 human demonstrations
```

### Demo format

Each demo is a folder `<stream_name>/` containing:

```
recording.mp4    — high-resolution video (all player frames)
rendered.npz     — rewards + discrete actions (numpy format)
metadata.json    — episode info (duration, seed, etc.)
```

The peculiarity: **frames are not in the npz** (contrary to what one might expect).
They must be extracted from the MP4 video.

### Preparation with prepare_demos.py

```bash
scripts/prepare_demos.py --data data/MineRL_demos/MineRLTreechop-v0 --out data/minerl_goal
```

The script:
1. Reads `rendered.npz` for rewards and actions
2. Reads `recording.mp4` frame by frame via `cv2.VideoCapture`
3. Resizes each frame to 64×64 (identical to live MineRL frames)
4. Discretizes actions (forward/sprint/attack/camera → 17 classes)
5. Aligns MP4 ↔ NPZ lengths (possible 1-2 frame offset)

```
Result: data/minerl_goal/episodes.npz
  Total frames    : 453,496
  Frames reward>0 : 12,056 (2.7%)  ← quality goal embedding
  Total wood      : 12,056 logs chopped
  Demos loaded    : 210
```

### Retraining on demos

```bash
# Encoder on the 453k expert frames
scripts/train_encoder.py --config configs/train_encoder_demos.yaml
→ checkpoints/encoder_demos.pt

# World model with new encoder
scripts/train_wm.py --config configs/train_wm_demos.yaml
→ checkpoints/wm_demos.pt
```

---

## Phase 4 Results

### Gate 1 — MineRL installed

```
✅ import minerl → 33 environments available including MineRLTreechop-v0
✅ env.reset() → 64×64 frame received
```

### Gate 2 — Dataset collected

```
scripts/collect_minerl_multi.py --shards 15
→ 119,852 transitions (RGB frames + discretized actions)
```

### Gate 3 — Encoder + WM trained

Two iterations of Phase-3-style WM (frozen frame→frame encoder + 1-step predictor):

| Config                  | Dataset        | val_loss | batch_var | WM ratio |
|-------------------------|----------------|----------|-----------|----------|
| `train_encoder_minerl`  | 119k random    | 0.0528   | 1.168     | 0.983    |
| `train_encoder_demos`   | 453k expert    | ~0.050   | ~1.17     | 0.959    |

`batch_var` > 1 confirms no collapse. But the **WM ratio stays ≈ 0.96**:
even on expert demos, this world model barely beats copying the current state.
This is the core problem of Phase 4, explained below.

---

## The journey: 4 approaches, only 1 works

Phase 4 required **four successive architectures**. The first three all fail at
`reward=0` — and analyzing *why* is the real lesson of this phase.

### The reward mechanism (the key to everything)

In Treechop, breaking a log requires **holding `attack` stationary, aimed at the same
trunk, for ~20 consecutive ticks**. Moving (forward+attack) changes the targeted block
every tick → the break never completes. Proof, from human demos:

```
Actions on the 12,056 reward>0 frames:
  a6 (attack only)  : 76.2%   ← vast majority: stationary + sustained attack
  a0 (noop)         :  8.8%
  a1 (forward)      :  5.1%
  a7 (forward+atk)  :  4.7%
```

Any policy that can't produce **sustained, precise action** is doomed.

### Approaches 1 & 2 — MPC + 1-step world model → `reward=0`

The MPC planner unrolls the WM over 12 steps and chooses the action leading to the
latent goal. But the WM caps at **ratio 0.959**: on near-static Minecraft frames,
"state doesn't change" (copying) is already near-optimal. After 12 steps, the 512
candidate sequences yield near-identical latents → planner chooses randomly. And a
Markovian 1-step predictor can't represent "attack the same block 20 times".

### Approach 3 — Behavioral Cloning (frozen encoder + head) → `reward=0`

Direct frame→action imitation on the frozen JEPA encoder. `val_acc` appears 64%,
but in play the agent **freezes on one action** (a0 or a7 at ~100%). Two causes:
- **covariate shift**: once the agent deviates once, it reaches states never seen
  in demos → aberrant predictions → drift;
- the JEPA encoder (trained frame→frame) encodes *scenes*, not action info
  ("where is the trunk").

Attempting to fix class imbalance (a6 = 58% of data) additionally **penalized a6**
— the action that earns reward. Counterproductive.

### Approach 4 — End-to-end CNN → `reward=0`

A pixels→action CNN (no JEPA), `val_acc` 49%. Still frozen: a memoryless policy
can't express temporal commitment ("I'm currently breaking this block, I continue").
Same wall, different door.

---

## The solution: action-conditioned world model (eb_jepa)

The architecture that unlocks everything is Meta's **action-conditioned JEPA**
(vendored in `mine_jepa/eb_jepa/`), assembled in `mine_jepa/ebwm/`. Five decisive
differences from previous approaches:

| # | Ingredient | Why it matters |
|---|------------|--------------------|
| 1 | **Spatial latents** `[64,8,8]` (vs flat vector 128) | Preserves "where is the trunk in the image" |
| 2 | **Encoder + predictor trained *jointly*, conditioned on action** | Latent is structured around action *consequences* (≠ frozen encoder) |
| 3 | **Residual predictor** (predicts delta `s_{t+1}−s_t`) | "Do nothing" = copy → ratio ≤ 1 guaranteed, backbone only learns the action-induced correction |
| 4 | **Fixed VICReg anti-collapse** (`spatial_as_samples=False`) | Measures variance *between batch samples*, not between pixels |
| 5 | **Action repeat = 4** | Re-plans every 4 steps and repeats action → produces **sustained attack** + 4× faster |

### The collapse trap (risk #1)

First eb_jepa training: `batch_var → 0.0000` by epoch 3 (total collapse).
Cause: the regularizer was configured with `spatial_as_samples=True` → it checked
variance *between pixels of a map* (always non-zero), not variance *between batch
inputs* (which was collapsing). The regularizer was **blind to the collapse that mattered**.
Fix: `spatial_as_samples=False` + std_coeff 1→10, cov 0.04→1.

```
Before fix: batch_var 0.0018 → 0.0000 (epoch 3)  ⚠️ COLLAPSE
After fix:  batch_var ~1.2 stable over 20 epochs  ✅
```

### Training pipeline

```bash
scripts/train_eb_jepa.py     # encoder + action-conditioned WM (sequences T=8)
→ checkpoints/ebwm.pt  (ratio 0.929, batch_var ~1.2, no collapse)
```

### Gate 4 — Agent plays real Minecraft ✅

```bash
play_ebwm.bat     # = play_minerl_multi.py --script scripts/play_ebwm.py
```

| Approach                         | mean reward | success | Status |
|----------------------------------|-------------|---------|--------|
| 1-2. MPC + 1-step WM (ratio ≈0.96)| 0.000       | 0%      | ✗      |
| 3. BC frozen encoder + head      | 0.000       | 0%      | ✗      |
| 4. BC CNN end-to-end             | 0.000       | 0%      | ✗      |
| **5. eb-JEPA MPC action-cond.**  | **0.75**    | **50%** | **✅** |

```
FINAL RESULTS — 20/20 episodes
  Mean reward    : 0.75      (up to 3 logs/episode)
  Success rate   : 50.0%     (10/20 episodes chop ≥1 tree)
  Phase 4 Gate   : ✅ PASSED  (threshold 30%)
```

Emergent behavior: **a14 (sprint+forward+attack) dominates** — exactly the lumberjack
gesture — interspersed with navigation (a13) and turns (a11/a12). Actions are
**varied and change with the scene**: the planner genuinely exploits the world model,
unlike BC agents frozen on one action.

> ⚠️ The "random baseline ~0.4" displayed by the script is an inherited estimate,
> never re-measured on this harness. The solid result is **absolute**: the agent
> genuinely chops trees in real Minecraft, 1 episode out of 2.

---

## The complete Phase 4 loop (eb_jepa version)

```
obs["pov"] [64,64,3]  →  [ResNet5 Encoder]  →  s_t [64, 8, 8]  (spatial map)
                                                     │
                                          512 action sequences (horizon=12)
                                                     │
                                  [Action-cond. WM autoregressive unroll]
                                     ŝ = s + Δ(s, action)  (residual)
                                                     │
                                       [Score vs goal latent [64,8,8]]
                                       (centroid of 12k reward>0 frames)
                                                     │
                                    best_action — repeated 4 steps (action_repeat)
                                                     │
                                          env.step(int → MineRL dict)
                                                     │
                                              obs_{t+1}  ←─ (loop)
```

---

## Lessons from Phase 4

1. **The reward dictates the architecture.** Treechop = sustained precise attack →
   a policy capable of temporal commitment was needed (action_repeat + WM).
2. **WM architecture matters as much as data.** Frozen frame→frame encoder
   (ratio 0.96) vs jointly trained action-conditioned encoder+predictor (ratio 0.929
   but *usable* latents for planning): the difference between 0% and 50%.
3. **Collapse is insidious.** A regularizer can appear active (low `reg_loss`)
   while blind to the real collapse. Always monitor `batch_var` (inter-sample variance),
   not just the regularizer loss.
4. **Honest diagnosis > blind iteration.** Three thoroughly analyzed failures led
   to the right architecture; blind iteration would not have.

---

*Previous concepts: `docs/05_planning.md` (MPC in latent space).*  
*Global architecture: `docs/01_jepa.md`.*  
*Anti-collapse: `docs/03_representation_collapse.md`.*

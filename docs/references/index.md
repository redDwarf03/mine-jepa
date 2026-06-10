# Mine-JEPA — Reference Bibliography

Curated bibliography for the mine-jepa project.  
Source of truth for _why_ each paper was chosen (or rejected) in our architecture.  
Aggregated from [awesome-jepa](https://github.com/AbdelStark/awesome-jepa) (June 2026) and our own search.

> **All arXiv IDs in this file were verified against the live arXiv abstract page (June 2026).**
> Entries that could not be verified were removed rather than guessed.

---

## 1. Directly implemented

Papers and repos that **live in our code**.

| Paper | Authors | ID / link | Used where |
|---|---|---|---|
| A Path Towards Autonomous Machine Intelligence | Yann LeCun | [openreview BZ5a1r-kVsf](https://openreview.net/forum?id=BZ5a1r-kVsf) (2022) | Original JEPA concept — `docs/01_jepa.md` |
| Self-Supervised Learning from Images with a Joint-Embedding Predictive Architecture (I-JEPA) | Assran, Duval, Misra, Bojanowski, Vincent, Rabbat, LeCun, Ballas | [arXiv:2301.08243](https://arxiv.org/abs/2301.08243) (CVPR 2023) | Encoder architecture — our backbone |
| VICReg: Variance-Invariance-Covariance Regularization for Self-Supervised Learning | Bardes, Ponce, LeCun | [arXiv:2105.04906](https://arxiv.org/abs/2105.04906) (ICLR 2022) | Anti-collapse loss — `mine_jepa/ebwm/losses.py` |
| eb_jepa — action-conditioned JEPA | Meta FAIR | [github.com/facebookresearch/eb_jepa](https://github.com/facebookresearch/eb_jepa) | **Our backbone** — vendored in `mine_jepa/eb_jepa/`; ACConvPredictor, spatial latent [D,8,8] |
| LeWorldModel: Stable End-to-End Joint-Embedding Predictive Architecture from Pixels | Maes, Le Lidec, Scieur, LeCun, Balestriero | [arXiv:2603.19312](https://arxiv.org/abs/2603.19312) (2026) · [code](https://github.com/lucas-maes/le-wm) · [site](https://le-wm.github.io/) | World model design — `mine_jepa/ebwm/`; ratio metric (val_pred/val_copy) |
| ES2025-19 (in repo: `ES2025-19.pdf`) | ESANN 2025 | local PDF | VICReg recipe for collapse prevention — `docs/03_representation_collapse.md` |

### Implementation notes

- **eb_jepa** is the backbone we chose over frozen V-JEPA 2 (see §5). Lightweight (~15 M params), action-conditioned, trains on our game data, fits 8 GB VRAM.
- **LeWorldModel** (~15 M params, single GPU, *two* loss terms only: next-embedding prediction + Gaussian regularizer) is the closest published architecture to ours. It introduced the spirit of the `ratio = val_pred / val_copy` gate we use (ratio < 1 beats copy-last; sweet spot ~0.93 for Treechop).
- **VICReg** prevents JEPA collapse (all embeddings → constant). Our `batch_var` monitor is the run-time check: < 1e-6 = collapse in progress.

---

## 2. Read — influential but not directly in code

Studied; shaped design decisions (including conscious rejections).

### Foundational theory

| Paper | Authors | ID / link | Relevance |
|---|---|---|---|
| Joint Embedding Predictive Architectures Focus on Slow Features | Sobal et al. | [arXiv:2211.10831](https://arxiv.org/abs/2211.10831) (2022) | JEPAs over-attend to slow, task-irrelevant features (textures, lighting) — exactly the trap on Minecraft's near-static background. Grounds our masking + VICReg choices. |
| LeJEPA: Provable and Scalable Self-Supervised Learning Without the Heuristics | Balestriero & LeCun | [arXiv:2511.08544](https://arxiv.org/abs/2511.08544) (2025) | Isotropic Gaussian = optimal embedding distribution; SIGReg objective. Collapse-free without stop-grad/EMA — a possible future simplification of our anti-collapse stack. |
| How JEPA Avoids Noisy Features: The Implicit Bias of Deep Linear Self-Distillation Networks | Littwin, Saremi, Advani, Thilak, Nakkiran, Huang, Susskind (Apple) | [arXiv:2407.03475](https://arxiv.org/abs/2407.03475) (2024) | Proves JEPA is implicitly biased toward *high-influence* (predictive) features, unlike MAE which chases high-variance (often noisy) ones. The theory behind why we don't reconstruct pixels on Minecraft's noisy POV. |
| Why and How Auxiliary Tasks Improve JEPA Representations | Yu et al. | [arXiv:2509.12249](https://arxiv.org/abs/2509.12249) (NeurIPS 2025) | **Directly justifies our WM v4 design.** Proves a *No Unhealthy Representation Collapse* theorem: a JEPA with an auxiliary regression head trained jointly with latent dynamics keeps non-equivalent observations distinct. Our `InventoryDynamics` head (inventory-as-state) is exactly this auxiliary-anchor pattern. |

### Video / world models

| Paper | Authors | ID / link | Relevance |
|---|---|---|---|
| Revisiting Feature Prediction for Learning Visual Representations from Video (V-JEPA) | Bardes, Garrido, Ponce, Chen, Rabbat, LeCun, Assran, Ballas | [arXiv:2404.08471](https://arxiv.org/abs/2404.08471) (ICLR 2025) | Video JEPA — masking in time. Inspired our temporal masking in `train_encoder.py`. |
| V-JEPA 2: Self-Supervised Video Models Enable Understanding, Prediction and Planning | Assran et al. (30 authors) | [arXiv:2506.09985](https://arxiv.org/abs/2506.09985) (2025) | **Rejected as primary** — frozen ViT-H, 1 M hours of natural video, OOD on Minecraft, uncloneable on consumer GPU. Comparison only. |
| Learning and Leveraging World Models in Visual Representation Learning | Garrido, Assran, Ballas, Bardes, Najman, LeCun | [arXiv:2403.00504](https://arxiv.org/abs/2403.00504) (2024) | Extends JEPA to predict effects of transformations in latent space; control over invariant vs equivariant representations — related to our joint encoder+WM training. |
| stable-worldmodel platform | Maes et al. | [github](https://github.com/galilai-group/stable-worldmodel) (2026) | Research platform from the LeWorldModel authors. Worth monitoring for WM API updates. |

### Planning / policy

| Paper | Authors | ID / link | Relevance |
|---|---|---|---|
| What Drives Success in Physical Planning with Joint-Embedding Predictive World Models? | Terver, Yang, Ponce, Bardes, LeCun | [arXiv:2512.24497](https://arxiv.org/abs/2512.24497) (2025) · [code: facebookresearch/jepa-wms](https://github.com/facebookresearch/jepa-wms) | **Most directly relevant.** Systematically studies how *architecture*, *training objective*, and *planning algorithm* affect JEPA-WM planning success — our exact setup. Their model beats DINO-WM and V-JEPA-2-AC on navigation + manipulation. Has official code + data. (Read the paper for the specific findings — we have not yet replicated them.) |
| ACT-JEPA: Novel Joint-Embedding Predictive Architecture for Efficient Policy Representation Learning | Vujinovic & Kovacevic | [arXiv:2501.14622](https://arxiv.org/abs/2501.14622) (2025) | Action-conditioned JEPA trained to jointly predict action sequences + latent observation sequences. Closest to our Phase 4/5 action-conditioned setup. |
| DINO-WM: World Models on Pre-trained Visual Features enable Zero-shot Planning | Zhou, Pan, LeCun, Pinto | [arXiv:2411.04983](https://arxiv.org/abs/2411.04983) (2024) · [site](https://dino-wm.github.io/) | World model over frozen DINOv2 patch features; plans by treating a goal *feature* as the prediction target — same goal-embedding-MPC idea as our planner. The baseline that Terver's JEPA-WM paper beats. |

---

## 3. Exploration / intrinsic motivation — the cold-start frontier

> **Why this section exists:** awesome-jepa is JEPA-scoped, so it omits the literature on the
> project's actual open wall — **cold-start chopping** (finding the first tree from a random
> spawn). That is an *exploration* problem (intrinsic motivation), not a representation problem.
> These verified references are the foundation for the curiosity / self-play direction
> sketched in `docs/08_crafting.md`.

| Paper | Authors | ID / link | Why it matters for us |
|---|---|---|---|
| Planning to Explore via Self-Supervised World Models (**Plan2Explore**) | Sekar, Rybkin, Daniilidis, Abbeel, Hafner, Pathak | [arXiv:2005.05960](https://arxiv.org/abs/2005.05960) (ICML 2020) · [code](https://github.com/ramanans1/plan2explore) | **Best fit for our stack.** Intrinsic reward = *ensemble disagreement in the world-model latent*; the agent **plans toward expected future novelty** using the WM itself. We already have a WM + MPC planner → near-direct fit. Drives exploration toward unseen states (= toward trees) with **no extrinsic reward**. |
| Curiosity-driven Exploration by Self-supervised Prediction (**ICM**) | Pathak, Agrawal, Efros, Darrell | [arXiv:1705.05363](https://arxiv.org/abs/1705.05363) (ICML 2017) | Curiosity = prediction error in a *learned feature space* (inverse-dynamics) — conceptually very close to JEPA. The canonical "WM prediction error as intrinsic reward". |
| Exploration by Random Network Distillation (**RND**) | Burda, Edwards, Storkey, Klimov | [arXiv:1810.12894](https://arxiv.org/abs/1810.12894) (2018) | Novelty = prediction error vs a fixed random net. Cheap, minimal overhead, cracked Montezuma's Revenge (hard exploration). A low-risk first intrinsic-reward to wire in. |
| Large-Scale Study of Curiosity-Driven Learning | Burda, Edwards, Pathak, Storkey, Darrell, Efros | [arXiv:1808.04355](https://arxiv.org/abs/1808.04355) (2018) | Empirical guidance on which feature space to compute curiosity in — directly informs whether to use our JEPA latent. |

---

## 4. Minecraft-specific context (June 2026)

| Paper | Authors | ID / link | Note |
|---|---|---|---|
| Solaris: Building a Multiplayer Video World Model in Minecraft | Savva, Michel, Lu, Waiwitlikhit, Meehan, Mishra, Poddar, Lu, Xie | [arXiv:2602.22208](https://arxiv.org/abs/2602.22208) (2026) | **Multi-agent Minecraft world model** (12.64 M multiplayer frames). Generative video (not JEPA), but the most recent multi-agent-Minecraft reference — relevant to our parallel/multi-agent goal. |
| Learning To Explore With Predictive World Model Via Self-Supervised Learning | Santana, Costa, Colombini | [arXiv:2502.13200](https://arxiv.org/abs/2502.13200) (2025) | Intrinsically-motivated agent that builds an internal world model, no external reward (Atari). Related exploration design point. |

---

## 5. Rejected / deferred

| Paper/Repo | Reason not used |
|---|---|
| **V-JEPA 2** ([2506.09985](https://arxiv.org/abs/2506.09985)) | 600 M-param ViT-H on natural video — OOD on Minecraft POV, uncloneable on 8 GB. Would dominate the architecture instead of being a building block. |
| **MC-JEPA** ([arXiv:2307.12698](https://arxiv.org/abs/2307.12698), Bardes, Ponce, LeCun, 2023) | Optical-flow + content specialization — irrelevant to Minecraft's mostly static background during chopping/combat. |
| Graph / 3D / Audio JEPA variants | Domain-specific. No application to our POV + inventory-state problem. |

---

## 6. Datasets used

| Dataset | Source | Used for |
|---|---|---|
| Crafter trajectories (self-collected) | `scripts/collect.py` — 33,406 transitions | Phase 0–3 encoder + WM |
| MineRL Treechop trajectories (self-collected) | `scripts/collect_minerl_multi.py` — 119,852 transitions | Phase 4 MineRL port |
| MineRLObtainIronPickaxe demos | [Zenodo 12659939](https://zenodo.org/records/12659939) — 40 demos, 84,902 frames | Phase 5 crafting WM v4 |

---

## 7. Ecosystem

- **awesome-jepa** (AbdelStark, June 2026): https://github.com/AbdelStark/awesome-jepa — curated JEPA list; this file draws from it.
- **facebookresearch/ijepa**: https://github.com/facebookresearch/ijepa — original I-JEPA (archived).
- **facebookresearch/jepa**: https://github.com/facebookresearch/jepa — V-JEPA official.
- **facebookresearch/jepa-wms**: https://github.com/facebookresearch/jepa-wms — "What Drives Success" code/data/weights.
- **lucas-maes/le-wm**: https://github.com/lucas-maes/le-wm — LeWorldModel code.
- **galilai-group/stable-worldmodel**: https://github.com/galilai-group/stable-worldmodel — research platform.
- **ramanans1/plan2explore**: https://github.com/ramanans1/plan2explore — Plan2Explore code (exploration).
- **MineRL 0.4.4**: https://github.com/minerllabs/minerl — Minecraft RL env (Phase 4–5).
- **Crafter**: https://github.com/danijar/crafter — lightweight test env (Phase 0–3).

---

## 8. Citing mine-jepa

```bibtex
@misc{mine-jepa-2026,
  author  = {redDwarf03},
  title   = {Mine-JEPA: A JEPA Agent that Plays Minecraft from Pixels},
  year    = {2026},
  url     = {https://github.com/redDwarf03/mine-jepa},
  note    = {Phases 0--5: Crafter validation -> MineRL Treechop -> Crafting with inventory world model}
}
```

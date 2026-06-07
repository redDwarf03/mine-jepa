# Computer Use Agents (CUA) — State of the Art, June 2026

> Synthesis based on: independent leaderboards (awesomeagents.ai), arXiv papers,
> official announcements from major players, and GitHub projects. Self-reported
> unverified scores are explicitly flagged.

---

## What is a CUA?

A **Computer Use Agent** is an AI system capable of controlling a computer from
screen pixels — as a human would: looking at the screen (screenshot), clicking,
typing, scrolling, filling forms, navigating between applications.

Unlike classical automation (Selenium, CSS-selector-based RPA scripts), a CUA
operates without prior knowledge of the interface structure. It "sees" the screen
and decides the next action.

Basic pipeline shared by all current CUAs:
```
screenshot → [VLM] → action (click x,y / text / key) → next screenshot → ...
```

This pipeline is **purely reactive**: the agent does not plan, does not simulate
the consequences of its actions before executing them. It reacts to each frame
as a reflex. This is the fundamental limitation of the current approach.

---

## The three CUA levels (a critical distinction)

Most comparisons mix solutions operating at very different levels. Three levels
of machine access must be distinguished:

### Level 1 — Browser-only (web only)

```
Agent → controls a single Chrome tab only
```

- **OpenAI CUA** (Operator → ChatGPT Agent): web-optimized virtual environments
- **Project Mariner** (Google, shut down May 2026): Chrome extension
- **browser-use**: Playwright/Chromium harness

**Scope:** forms, web navigation, cloud SaaS. Does not see the rest of the desktop.
High WebVoyager scores (87%) reflect this browser optimization.

**Limitation:** unusable for native apps (Photoshop, terminal, CAD, local Office).

---

### Level 2 — Real desktop (all native applications)

```
Agent → full-screen screenshot → host OS exposed
```

- **Claude Computer Use**: desktop-first, cross-OS, harness managed by the developer
- **Agent S / UI-TARS**: operate on the real desktop

**Scope:** all applications — Figma, terminal, IDE, files, legacy apps.
Most general approach and most comparable to a human at a keyboard.

**Limitation:** host OS is directly exposed. If the agent makes a mistake (file
deletion, destructive command), the damage is real and irreversible.

---

### Level 3 — Full sandboxed OS ← most powerful

```
Agent → lightweight isolated VM (full macOS or Linux) → host machine protected
```

- **Cua / trycua** (YC X25, Francesco Bonacci): uses **Apple Virtualization
  Framework** to create macOS/Linux VMs at **97% of native CPU speed** on Apple Silicon.

**What this changes:**
- The agent controls an **entire OS**: native apps, filesystem, terminal, compilers,
  graphical tools — without restriction
- The host machine is **completely isolated**: if the agent destroys the VM, it is
  recreated in seconds
- Reproducibility: each task starts from a known state (snapshot)
- Compatibility: any CUA model (Claude, GPT, UI-TARS) can run on top of it

This is the equivalent of **Docker for agents**: execution infrastructure, not a model.
A Level 2 agent + Cua = Level 3.

**Why this is far more powerful than browser-only:** the agent can open Xcode,
compile code, move files, launch processes, interact with any graphical interface
— like a human with a full Mac, but in a resettable sandbox.

---

**Visual summary:**

| Level | Scope | Safety | Examples |
|-------|-------|--------|---------|
| 1 — Browser-only | Web only | Low risk | OpenAI CUA, browser-use |
| 2 — Real desktop | All apps | Host OS exposed | Claude CU, Agent S |
| 3 — Sandboxed OS | Full isolated OS | Host protected | Cua (trycua) |

---

## 1. Key players

### Anthropic — Claude Computer Use

**Launch:** October 2024, Claude 3.5 Sonnet, open beta for developers.

**Model evolution:**

| Model | Date | OSWorld score (independent) |
|-------|------|---------------------------|
| Claude 3.5 Sonnet | Oct. 2024 | ~22% |
| Claude Sonnet 4.5 | 2025 | 61.4% |
| Claude Opus 4.5 | 2025 | 66.3% |
| **Claude Opus 4.6** | **Early 2026** | **72.7%** ← surpasses human |
| Claude Sonnet 4.6 | Early 2026 | 72.5% |

The human baseline on OSWorld is **72.4%**. Claude Opus 4.6 slightly surpasses it
according to the independent leaderboard awesomeagents.ai (updated April 2026).

**Architecture:** Desktop-first, cross-OS (Linux, Windows, macOS, containers). The
caller manages the harness (screen capture, action dispatch), Claude decides what to do.
Pay-per-use API, globally available.

**Strengths:** Complex desktop workflows, multi-application, filesystem, native
applications, approval loops via the tool-use API.

**Known weaknesses:** Scrolling, dragging, zooming remain difficult. Inherent latency
from screenshot round-trip. Estimated cost ~$0.28/task (765 image tokens +
600 text tokens + 1000 output tokens + ~7 actions).

---

### OpenAI — CUA / ChatGPT Agent

**Timeline:**
- **Jan. 23, 2025**: launch of Operator (research preview, ChatGPT Pro, US only),
  powered by the CUA model (GPT-4o + RL on GUI)
- **March 2025**: extended to Plus and Team tiers
- **Jul. 17, 2025**: ChatGPT Agent — merger of Operator + Deep Research into ChatGPT
- **Aug. 31, 2025**: Operator standalone shut down, absorbed into ChatGPT Agent
- **Q4 2025**: CUA model made available to developers via Agents SDK
- **Late 2025**: GPT-4o replaced by an o3-based version
- **May 2026**: ChatGPT Agent active on all tiers (Plus, Pro, Business, Enterprise)

**Scores:**
- CUA original (GPT-4o): **38.1% OSWorld**, **87% WebVoyager** (independent)
- GPT-5.4: **75.0% OSWorld-Verified** — ⚠️ self-reported by OpenAI, unverified

**Architecture:** Browser-focused, cloud-controlled virtual environments. Highly
optimized for web, less documented for native desktop outside the browser.

**Important note on comparisons:** OpenAI CUA operates in virtual environments
optimized for web; Claude operates in real desktop environments with all their
complexity. Scores are not directly comparable.

---

### Google — Project Mariner → Gemini Agent

**Timeline:**
- **Dec. 2024**: launch of Project Mariner (DeepMind), Chrome extension,
  up to 10 simultaneous web tasks
- **May 4, 2026**: **official shutdown of standalone Project Mariner**
- **June 2026**: capabilities absorbed into Gemini Agent and Chrome "auto-browse" mode

**Score (Project Mariner, before shutdown):** **83.5% WebVoyager** — best known
performance on this browser benchmark.

**Current architecture (Gemini):** DOM awareness + accessibility tree + vision, not
pixel-only parsing. Reduced latency on forms and SaaS navigation.
Google does not publish comparative metrics post-integration.

---

### Microsoft — Copilot Studio Computer-Using Agents

**Timeline:**
- **Sept. 2025**: preview in Copilot Studio
- **May 13, 2026**: **general availability (GA)**
- **June 2026 (Build 2026)**: Satya Nadella declares Microsoft's "agentic era";
  extension to Windows endpoints, SQL Server, SharePoint, Dynamics 365

**Models in production:** Claude Sonnet 4.5 and OpenAI CUA (both offered).

**Enterprise controls:** Azure Key Vault for credentials, Microsoft Purview
audit logging, human-in-the-loop via Outlook.

**Positioning:** Next-generation RPA — adaptive when layouts change,
without fragile CSS selectors.

---

## 2. Comparative scores (June 2026)

| Model/Agent | OSWorld (indep.) | OSWorld-Verified | WebVoyager | Status |
|---|---|---|---|---|
| **Human baseline** | **72.4%** | **72.4%** | — | Reference |
| Claude Opus 4.6 | **72.7%** | — | — | ✅ verified indep. |
| Claude Sonnet 4.6 | 72.5% | — | — | ✅ verified indep. |
| GPT-5.4 | — | **75.0%** | — | ⚠️ self-reported |
| Agent S3 (Simular) | ~66-72.6% | — | — | ✅ peer-reviewed paper |
| Qwen3 VL 235B | 66.7% | — | — | ✅ verified indep. |
| UI-TARS-2 | 47.5% | — | — | ✅ paper |
| OpenAI CUA (GPT-4o) | 38.1% | — | 87% | ✅ verified indep. |
| Project Mariner | — | — | 83.5% | ✅ verified, shut down |

**CUB benchmark** (106 real multi-industry workflows, very hard):
best agent = Writer's Action Agent at **10.4%** only — reflecting the true
difficulty of production tasks, not academic benchmarks.

---

## 3. Academic research — key papers

### Active benchmarks

| Benchmark | Focus | Difficulty |
|-----------|-------|-----------|
| **OSWorld** | 369 cross-app tasks on real OS | Main reference |
| **OSWorld-Verified** | Manually verified subset | Increased reliability |
| **ScreenSpot-Pro** | High-resolution GUI grounding | MAI-UI 32B: 67.9% (best) |
| **WindowsAgentArena** | 154 Windows tasks | Agent S3: 50.2% |
| **WebVoyager** | Web navigation | OpenAI CUA: 87% |
| **CUB** | 106 real industrial workflows | Best: 10.4% |
| **HippoCamp** | Personalized user profiles | New |
| **WorldGUI** | Arbitrary starting point | ICLR 2026 |

### Notable papers 2025-2026

**Architecture:**
- `arXiv:2501.16150` — *Survey on Agents for Computer Use*: complete taxonomy of
  approaches (reactive, model-based, hierarchical), learning paradigms
- `arXiv:2504.00906` — *Agent S2*: compositional architecture LLM planning +
  VLM grounding (UI-TARS-1.5-7B). Agent S3: 72.6% with Best-of-N
- `arXiv:2509.02544` — *UI-TARS-2*: Multi-Turn RL, "All In One" (GUI, games, code)

**Security (explosion of research):**
- `arXiv:2603.14707` — *Visual Confused Deputy*: attacks exploiting divergences
  between visual perception and actual system state
- `arXiv:2602.08235` — *Benign Inputs, Severe Harms*: unintentional dangerous
  behaviors (SSH misconfiguration, unwanted code execution)
- `arXiv:2510.12200` — *HackWorld*: evaluation of CUA offensive capabilities on
  web vulnerabilities
- `arXiv:2601.09923` — *CaMeLs CUA Security*: system-level security framework

**Data & training:**
- `arXiv:2602.08153` — *ANCHOR*: branch-point data generation for GUI agents
  (accepted ICLR 2026)

---

## 4. Open-source ecosystem

### browser-use ⭐⭐⭐
- Repo: `github.com/browser-use/browser-use`
- Lightweight, self-healing browser harness, makes websites accessible to agents
- BU 2.0 (Jan. 2026): +12% precision vs v1.0; WebUI: DeepSeek-r1 compatible
- Commercial offering: Browser Use Box (Claude Code + Browser Harness), anti-detect,
  CAPTCHA solving, proxies in 195+ countries
- Compatible with OpenAI, Anthropic, any standard LLM

### UI-TARS (ByteDance) ⭐⭐⭐⭐
- Repo: `github.com/bytedance/ui-tars` — **33,573 stars** (May 2026),
  the largest open-source GUI agent project on GitHub
- Specialized VLM trained on massive GUI data via data flywheel
- Evolution: 24.6% → 42.5% → 47.5% OSWorld (Jan. 2025 → Apr. → Sept. 2025)
- UI-TARS-1.5-7B available on HuggingFace
- Agent TARS CLI v0.3.0: streaming + AIO Agent Sandbox

### Agent S / S2 / S3 (Simular AI) ⭐⭐⭐
- Repo: `github.com/simular-ai/Agent-S` — 11,800 stars, Apache 2.0 license
- Best open-source on OSWorld excluding proprietary models
- Compositional architecture: LLM generation + UI-TARS-1.5-7B for grounding
- Cross-platform: Linux, macOS, Windows, Android

### Cua / trycua (YC X25) ⭐⭐⭐
- Repo: `github.com/trycua/cua`
- Site: `cua.ai` — Y Combinator Spring 2025 batch, founder: Francesco Bonacci (ex-Microsoft/Xbox)
- **Level 3 infrastructure**: macOS/Linux VMs via Apple Virtualization Framework,
  97% native CPU speed on Apple Silicon
- Three layers: **Lume** (high-perf VM) + **CUI** (perception + actions) +
  **CUA** (agent framework, compatible with Claude, GPT, Ollama, LangGraph, AutoGen)
- The agent controls a fully isolated OS: native apps, filesystem, terminal,
  compilers, graphical interfaces
- Compatible with any existing CUA model — this is the infrastructure, not the brain

### BrowserOS (Coasty AI)
- Repo: `github.com/browseros-ai/BrowserOS`
- Open-source agentic browser (AGPL-3.0), alternative to ChatGPT Atlas / Perplexity Comet

### Paper reference
- `github.com/OSU-NLP-Group/GUI-Agents-Paper-List` — complete list of GUI agent papers

---

## 5. Real-world use cases (deployed in production)

| Sector | Player | Results |
|--------|--------|---------|
| Finance | JPMorgan | 450+ AI use cases in production, presentations in 30s, $18B tech budget |
| Supply chain | General Mills | 5,000+ deliveries evaluated/day, $20M saved since 2024 |
| Customer service | Klarna | 2/3 of chats handled by AI, 11min → 2min, ~$60M saved in 2025 |
| Enterprise general | — | Gartner: 40% of enterprise apps with task-specific agents by 2026 (vs <5% in 2025) |
| Healthcare | — | HIMSS March 2026: **90% security failure rate** — very risky sector |

Most deployed CUA use cases: web forms, data entry, SaaS navigation, legacy RPA
automation, onboarding, reporting.

---

## 6. Current limitations

### Reliability
- **76% of 847 production AI agent deployments failed in 2026** (Coasty AI).
  Main cause: lack of observability, not the models themselves.
- Failure cascades in multi-agent systems
- Very low completion rate on real complex tasks (CUB: ~10%)
- Documented incident: agent in infinite retry loop for 11 hours without detection →
  "catastrophic" bill

### Security
- **Visual prompt injection**: the screen can contain malicious text manipulating
  the agent ("visual confused deputy")
- **Unintentional behaviors** on benign inputs (SSH, code execution)
- **Shadow deployment**: 29% of employees deploy unvalidated agents
  into enterprise systems without audit
- **Sensitive data**: screenshots sent to external servers

### Cost and latency
- ~$0.28 per SOTA task (7 actions, including screenshots)
- Per-action latency: round-trip screenshot → inference → action → screenshot
- Partial remedies: prompt caching, background mode, event-driven webhooks

### GUI Grounding
- Even the best models plateau **below 70% on ScreenSpot-Pro** (high-res professional)
- Scrolling, dragging, zooming: persistent difficulties across all models
- High sensitivity to unusual resolutions and pixel densities

### Generalization
- Overfitting to known benchmarks; degradation on new interfaces
- Long multi-step planning: coherence difficult to maintain beyond ~20 actions
- Transfer across OS and applications remains an open problem

---

## 7. Trends and directions (2026 and beyond)

**1. Specialized models > generalist models**
VLMs trained specifically for GUI (UI-TARS, MAI-UI, OS-Atlas) systematically outperform
generalist LLMs on grounding. Compositional architecture (LLM planning + small 7B VLM
grounding) is establishing itself as the dominant pattern.

**2. Multi-turn Reinforcement Learning**
RL on complete GUI trajectories is replacing imitation learning alone. UI-TARS-2 and
Agent S3 are the most advanced examples. Trend: agents that improve by doing, not just by imitating.

**3. Absorption into consumer products**
Project Mariner → Gemini, Operator → ChatGPT Agent, GA Copilot Studio: all major
players are absorbing computer use into their main products. **2026 is the year of
general production deployment.**

**4. DOM + vision hybrid (for the web)**
Combining accessibility tree + screenshot reduces latency and errors. Google did it
with Gemini. For desktop, pixel-only remains dominant but insufficient alone.

**5. Safety as an active sub-discipline**
At least 5 arXiv papers in 2025-2026 on CUA security. Visual prompt injection,
unintentional behaviors, and shadow agents are becoming full research topics.

**6. Observability as a prerequisite**
Pixel-level session replay, action-level logging, per-task cost tracking are becoming
production requirements. Emerging market for agent-specific tooling.

**7. Toward long and parallel agents**
Dynamic Workflows (Anthropic Enterprise), background mode (OpenAI): agents are moving
from "one request" to "multi-day autonomous task with parallel sub-agents".

---

---

## Perspective — JEPA as an alternative to reactive CUAs

> This section analyzes how the JEPA architecture (developed in Mine-JEPA)
> positions itself relative to current CUAs, and where it could bring a breakthrough.

### The fundamental problem of current CUAs: zero world model

All existing CUAs — from Level 1 to Level 3 — share the same architecture:

```
screenshot_t → [VLM] → action_t → screenshot_{t+1} → [VLM] → action_{t+1} → ...
```

The agent is **blind to the future**. It does not know what will happen if it clicks
that button before doing it. It cannot plan a sequence of 10 actions without
executing them one by one, hoping each one leads in the right direction.

Direct consequences:
- High failure rate on long tasks (CUB: ~10% completion)
- Inefficient error recovery: the agent does not "understand" why it failed
- Multi-step planning: impossible without executing (and therefore potentially breaking)
- Cost: each action = one full API call with screenshot

### The JEPA approach: a world model in latent space

Mine-JEPA builds exactly what CUAs are missing:

```
screenshot_t → [JEPA Encoder] → s_t (128D latent)
                                       │
                                s_t + action_t
                                       │
                               [World Model] → ŝ_{t+1} (predicted)
                                       │
                           512 simulated sequences (MPC, horizon=12)
                                       │
                              [Scorer vs s_goal]
                                       │
                                  best_action  ← without executing anything
```

**What this changes:**

| Capability | Reactive CUA (state of the art) | Mine-JEPA |
|------------|--------------------------------|-----------|
| Plan before acting | ✗ | ✅ MPC over 12 steps |
| Simulate consequences | ✗ | ✅ Latent World Model |
| Planning cost | 1 API call/action | Local matrix computation |
| Error recovery | Retry blindly | Re-plan from current state |
| Long sequences | Rapid degradation | Stable (fixed horizon, re-plan) |
| Goal-directed | Vague text prompt | Precise latent centroid |

### What Mine-JEPA results validate (Phases 1-4)

- **Collapse-free encoder**: `batch_var ≈ 1.22` on real Minecraft frames —
  visual representations are rich and stable
- **World Model > baseline**: ratio < 1.0 on human demos — the model genuinely
  predicts the consequences of actions, not just "copy the state"
- **Functional MPC planner**: +7.5% achievements vs random on Crafter (Phase 3)
- **Architecture generalization**: the same pipeline runs on Crafter (simplified game)
  and on real Minecraft (MineRL) without modifying a single line of architecture

### Possible positioning vs CUAs

Mine-JEPA is not a turnkey Level 3 CUA — it is a **missing building block**:
the planning module that CUAs do not have.

Two possible positioning angles:

**Option A — Planning module for existing CUAs**
```
Cua (trycua) OS sandbox  +  Claude Computer Use (perception + grounding)
        +
    Mine-JEPA World Model  (multi-step planning in latent space)
```
The JEPA encoder trains on screenshots from the current session.
The MPC planner chooses the action sequence before executing it in the VM.
Result: a Level 3 CUA that plans — nonexistent today.

**Option B — Specialized autonomous agent (vertical)**
Since Mine-JEPA is trained on a specific task (Treechop = tree),
apply the same pipeline to a repetitive business workflow (e.g.: fill 200 identical
forms, extract data from 500 similar PDFs) — where the world model can truly learn
the interface dynamics and plan effectively.

### Honest limitations

- **Training data**: the World Model requires demos of the target task
  (like the 453k Zenodo frames for Treechop). Not plug-and-play on an unknown interface.
- **Generalization**: strong on the learned task, degradation on new interfaces
  (same limitation as UI-TARS but for different reasons).
- **Competition**: major labs have massively superior resources to train generalist VLMs.
  JEPA's advantage is in planning, not raw perception.
- **Training latency**: unlike Claude Computer Use (zero fine-tuning),
  Mine-JEPA requires a training phase on task data.

### Fundamental learning difference: SFT vs self-supervised

**How current CUAs learn (SFT — Supervised Fine-Tuning):**

UI-TARS, Claude Computer Use, OpenAI CUA are all trained on massive datasets
of GUI interactions **annotated by humans**:

```
Screenshot → [human annotates] → "the correct action was: click at (x=847, y=312)"
                                        ↓
                             dataset of millions of (screenshot, correct_action) pairs
                                        ↓
                              supervised fine-tuning of the VLM
```

Consequences:
- **Data production cost**: large-scale human annotation (ByteDance built an entire
  "data flywheel" for UI-TARS)
- **Label dependency**: without "correct action" annotation, impossible to learn
- **Limited generalization**: the model learns to imitate, not to understand

---

**How Mine-JEPA learns (self-supervised on raw trajectories):**

The JEPA encoder needs no annotation. It learns solely from consecutive frame
pairs — what we store in `.npz`:

```
(frame_t, frame_{t+1})  →  [JEPA] → "predicts the representation of frame_{t+1}
                                       from frame_t without seeing the pixels"
```

The world model learns from `(frame_t, action_t, frame_{t+1})` triplets —
the action does not need to be "correct", just recorded. A human demo playing
normally is sufficient.

```
JEPA data = raw trajectories (.npz)
  frames  : [N, 64, 64, 3]   ← raw pixels
  actions : [N]               ← integer (0-16), just what was done
  rewards : [N]               ← success signal, no annotation required
  dones   : [N]               ← episode end
```

Consequences:
- **Zero human annotation**: any gameplay video is sufficient to train the encoder
  (the 453k Zenodo frames were raw demos, not annotated)
- **Scalable**: more videos = better encoder, without annotation cost
- **Applicable to any interface**: film a human using an app for 1 hour →
  complete training dataset

| | SFT (current CUAs) | Self-supervised (JEPA) |
|---|---|---|
| Data required | Screenshots + "correct action" annotation | Raw videos/trajectories |
| Annotation cost | High (expert humans) | Zero |
| "Correct action" label | Required | Not required |
| Scalability | Limited by annotation cost | Unlimited (any video) |
| Data source | Proprietary datasets built on purpose | Existing demos, screencasts |

---

### Hardware difference: cloud API vs local inference

**CUA with LLM (Claude Opus 4.6, GPT-5.4, UI-TARS 72B):**

```
screenshot  →  [encode into tokens]  →  API call (network)  →  [cloud GPU 80GB+]
               ~765 image tokens          ~200ms latency         VLM inference
                    ↓
             action returned  →  execute  →  new screenshot  →  (loop)
```

Each action = a network round-trip + inference on a massive GPU cluster.

| Resource | Value |
|----------|-------|
| GPU required on agent side | None (but internet required) |
| GPU on provider side | A100/H100 80GB (not accessible) |
| Cost per action | ~$0.04 (image + text tokens) |
| Cost per task (7 actions) | ~$0.28 |
| Latency per action | 200ms–2s (network + inference) |
| Data sent | Full screenshot → external servers |
| Offline operation | Impossible |

---

**CUA with Mine-JEPA (15M encoder + 140K params world model):**

```
screenshot  →  [local JEPA encoder]  →  latent s_t (128D)
                    ~1ms GPU/CPU           ↓
                               [local World Model]  →  512 × 12 simulated states
                                    ~5ms GPU/CPU        ↓
                                               [Scorer]  →  best_action
                                                    ↓
                                             execute
```

The full planning pass (512 candidates × 12 steps) runs **locally, without network**,
in a few milliseconds on a consumer GPU.

| Resource | Value |
|----------|-------|
| Training GPU | RTX 3060/4060 8GB sufficient (RTX 5060 Ti used) |
| Inference GPU | CPU sufficient (15M param encoder) |
| Cost per action | ~$0 (local compute after training) |
| Cost per task | Electricity only |
| Latency per action | <10ms (local) |
| Data sent | None — everything stays local |
| Offline operation | Full |

---

**Implications:**

The JEPA approach unlocks use cases impossible with LLM-based CUAs:
- **Healthcare / medical**: screenshots never leave the machine (GDPR compliance)
- **Defense / industry**: network-cut or air-gapped, agent still functional
- **Embedded**: robot, drone, industrial terminal — no cloud accessible
- **Volume**: 10,000 actions/day without proportional API bill
- **Critical latency**: <10ms vs ~500ms to decide the next action

---

### The window of opportunity

Current CUAs are all converging on the same reactive architecture (screenshot → VLM →
action). World-model-based planning is **absent from all production products as of June
2026** — including the most advanced (Claude Opus 4.6, GPT-5.4, Agent S3).

This is Mine-JEPA's original angle: not a better grounding VLM, but
**the planning layer that all CUAs are missing**.

---

## Summary in one sentence

> In June 2026, Claude Opus 4.6 reaches human performance on the reference benchmark
> OSWorld (72.7% vs 72.4%), but completion rates on real industrial tasks remain
> around 10% — the technology is promising and entering production, but reliability
> on complex workflows remains the main challenge.

---

## Sources

- [Computer Use Leaderboard — awesomeagents.ai](https://awesomeagents.ai/leaderboards/computer-use-leaderboard/)
- [Anthropic vs OpenAI CUA — WorkOS](https://workos.com/blog/anthropics-computer-use-versus-openais-computer-using-agent-cua)
- [Computer Use Agents 2026 — Digital Applied](https://www.digitalapplied.com/blog/computer-use-agents-2026-claude-openai-gemini-matrix)
- [OpenAI Operator Timeline — Presenc AI](https://presenc.ai/research/openai-operator-update-tracker-2026)
- [Project Mariner Shutdown — Android Headlines](https://www.androidheadlines.com/2026/05/google-shuts-down-project-mariner-ai-agent.html)
- [Microsoft Copilot Studio CUA GA — Microsoft Tech Community](https://techcommunity.microsoft.com/blog/copilot-studio-blog/computer-using-agents-in-microsoft-copilot-studio-are-now-generally-available/4519427)
- [AI Agent Monitoring Blind Spots — Coasty AI](https://coasty.ai/blog/ai-agent-monitoring-observability-blind-spots-2026-20260403)
- [CUA Benchmarks Guide — O-Mega AI](https://o-mega.ai/articles/the-2025-2026-guide-to-ai-computer-use-benchmarks-and-top-ai-agents)
- [arXiv:2501.16150 — CUA Survey](https://arxiv.org/pdf/2501.16150)
- [arXiv:2504.00906 — Agent S2](https://arxiv.org/pdf/2504.00906)
- [arXiv:2509.02544 — UI-TARS-2](https://arxiv.org/html/2509.02544v1)
- [arXiv:2603.14707 — Visual Confused Deputy](https://arxiv.org/pdf/2603.14707)
- [arXiv:2602.08235 — Benign Inputs Severe Harms](https://arxiv.org/pdf/2602.08235)
- [GitHub — browser-use](https://github.com/browser-use/browser-use)
- [GitHub — UI-TARS](https://github.com/bytedance/ui-tars)
- [GitHub — Agent-S](https://github.com/simular-ai/Agent-S)
- [GitHub — GUI Agents Paper List](https://github.com/OSU-NLP-Group/GUI-Agents-Paper-List)
- [Gartner Enterprise Agents 2026 Prediction](https://www.gartner.com/en/newsroom/press-releases/2025-08-26-gartner-predicts-40-percent-of-enterprise-apps-will-feature-task-specific-ai-agents-by-2026-up-from-less-than-5-percent-in-2025)

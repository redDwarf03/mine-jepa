# Mine-JEPA — Un agent JEPA qui joue à Minecraft depuis les pixels

> **Document auto-suffisant.** Tout le contexte nécessaire est ici. On peut vider/compacter
> le contexte de conversation : ce fichier est la source de vérité unique.

---

## 1. Contexte & objectif (le « pourquoi »)

**Qui** : développeur qui découvre JEPA. Ne connaît pas encore le sujet → **le projet est
aussi un parcours d'apprentissage**.

**Double objectif (validé avec l'utilisateur)** :
1. **Apprendre JEPA en profondeur** en le construisant.
2. **Sortir un projet visible** sur la scène IA : démo clonable + vidéo partageable.
   Stratégie = **intégration spectaculaire** (s'appuyer sur des briques open-source
   existantes) plutôt que recherche from-scratch.

**Pourquoi ce projet n'est pas inutile (état de l'art, juin 2026)** :
- **Créneau libre côté packaging** : la *capacité* JEPA-depuis-pixels existe déjà en
  recherche (LeWorldModel, mars 2026 ; Sub-JEPA, mai 2026), mais **personne n'a sorti de
  démo grand public, clonable et spectaculaire** « JEPA joue à un jeu ». Le green field est
  dans l'**application + le packaging**, pas dans l'architecture.
- **Collision de marques novatrice** : « JEPA + Minecraft » surfe sur deux vagues (les
  world-models de LeCun + la lignée IA-Minecraft VPT/Voyager/Dreamer). Jamais publié.
- **Démo-friendly** : un agent qui *joue* est l'une des rares sorties JEPA réellement
  **visibles** (JEPA produit des embeddings latents invisibles par défaut — il FAUT
  l'attacher à quelque chose qui agit à l'écran).

**Réserves honnêtes intégrées** :
- On ne vise PAS « battre Meta » ni un papier de recherche. On *applique + package*.
- Objectif réaliste = **reconnaissance dans la niche IA** + portfolio fort + apprentissage réel.
- Contrainte non négociable : **ça doit tourner sur GPU grand public et se cloner-lancer
  facilement**, sinon pas de diffusion.

---

## 2. C'est quoi JEPA ? (socle pédagogique — à transformer en `docs/01_jepa.md`)

JEPA = **Joint-Embedding Predictive Architecture** (Yann LeCun, 2022). Idée centrale :
- Un **context-encoder** encode ce qu'on voit (ex : 3 dernières frames) → vecteur latent `s_x`.
- Un **target-encoder** (copie EMA, gradient bloqué) encode ce qu'on veut prédire (frames
  suivantes) → `s_y`.
- Un **predictor** prédit `ŝ_y` à partir de `s_x` (+ éventuellement une **action**).
- **Loss = distance dans l'espace latent** entre `ŝ_y` et `s_y` (PAS de reconstruction pixel).

**Pourquoi c'est malin** : un modèle génératif s'épuise à prédire chaque pixel (texture de la
terre, mouton en fond). JEPA prédit seulement la **structure abstraite** (« si je frappe ce
bloc, il casse ») et **ignore les détails inutiles**. Plus efficace, plus robuste.

**Le piège n°1 = le collapse** : si encoder + predictor apprennent à tout mapper sur une
constante, la loss tombe à 0 mais le modèle n'a rien appris (variance des embeddings → 0).
**Parades** (cf. papier `ES2025-19.pdf` déjà dans le repo, *JEPA for RL*, ESANN 2025) :
- target-encoder en **EMA** (θ̄ ← 0.99·θ̄ + 0.01·θ) et gradient bloqué côté target ;
- **régularisation de variance/covariance (VICReg)** : forcer la variance des embeddings > seuil ;
- (en RL) laisser des gradients de la tâche traverser l'encoder.

**World model action-conditionné** : on injecte l'action `a_t` dans le predictor → il prédit
le **prochain état latent** `ŝ_{t+1}`. En enchaînant, on **imagine le futur** en latent. On
peut alors **planifier** : simuler plusieurs séquences d'actions en latent, garder celle qui
rapproche du but. C'est exactement ce que fait V-JEPA 2-AC pour les robots.

---

## 3. Briques réutilisées (NE PAS réinventer)

| Brique | Rôle | Source |
|---|---|---|
| `facebookresearch/eb_jepa` | Exemples officiels JEPA **avec action-conditioned video + planning** — point de départ le plus direct | github.com/facebookresearch/eb_jepa |
| `facebookresearch/vjepa2` (torch.hub) | Encodeur V-JEPA 2 pré-entraîné + predictor AC (`vjepa2_ac_vit_giant`) — mode « pro »/comparaison | github.com/facebookresearch/vjepa2 |
| **LeWorldModel (LeWM)** | JEPA stable end-to-end **depuis pixels, ~15M params**, contrôle 2D/3D → idéal GPU grand public. **Vérifier dispo du code en Phase 0** | arXiv 2603.19312 |
| `ES2025-19.pdf` (dans le repo) | Recette JEPA→RL + anti-collapse VICReg | ESANN 2025 |
| **Crafter** | Clone Minecraft 2D léger, `pip install`, tourne partout → **banc d'essai de dé-risquage** | github.com/danijar/crafter |
| **MineRL** | Vrai Minecraft, espace d'action VPT (clavier/souris) → **la démo spectaculaire finale** | minerllabs/minerl |

**Décision d'architecture** : backbone primaire = **JEPA léger style LeWM (~15M) entraîné sur
le jeu** (clonable + pédagogique + prouvé par LeWM). Mode secondaire/stretch = brancher
**V-JEPA 2 gelé** pour comparer. Raison : « clonable sur GPU grand public » + « tu apprends en
le construisant » l'emportent sur la puissance brute de V-JEPA giant (lourd + OOD sur Minecraft).

**Décision d'environnement** : **Crafter d'abord** (pipeline JEPA validée vite, tourne
partout), **MineRL ensuite** (le visuel Minecraft = la marque qui fait le buzz).

---

## 4. Plan d'exécution par phases (chaque phase = un livrable visible + un livrable pédago)

> Piloté par des **gates** : on ne passe à la phase suivante que si le critère est atteint.
> Chaque phase produit (a) un artefact **visible** (pour la démo) et (b) un doc **pédago**
> (pour ton apprentissage ET la doc virale du projet).

### Phase 0 — Fondations & décor
- Scaffold repo : `mine_jepa/` (code), `docs/` (pédago), `scripts/`, `configs/`, `assets/`.
  Env Python (uv ou conda), PyTorch, timm, einops. CI minimal.
- Installer **Crafter**, capturer frames + actions, lancer un agent aléatoire → **1re vidéo**.
- Vérifier dispo du code **LeWM** ; cloner `eb_jepa` et le faire tourner sur un exemple.
- 📚 **Pédago** : `docs/01_jepa.md` (section 2 ci-dessus, vulgarisée) + `docs/02_setup.md`.
- 🎬 **Visible** : GIF d'un agent random dans Crafter + schéma archi.
- ✅ **GATE** : env tourne, pipeline `(frames, actions)` capturée, eb_jepa exécuté.

### Phase 1 — Représentation JEPA (encoder sans collapse)
- Implémenter/adapter un **encoder JEPA** (style LeWM ou eb_jepa) entraîné en self-supervised
  sur les frames du jeu. EMA target + **VICReg** anti-collapse.
- **Linear-probe** : entraîner un classifieur linéaire sur les embeddings gelés pour prédire
  un état du jeu (inventaire, objets proches) → prouve que l'embedding capture du sens.
- 📚 **Pédago** : `docs/03_representation_collapse.md` (collapse, EMA, VICReg, courbes de variance).
- 🎬 **Visible** : projection PCA/t-SNE du latent **colorée par état du jeu** → « le modèle a
  appris la structure sans aucune étiquette ». (Excellent visuel narratif.)
- ✅ **GATE** : linear-probe > baseline aléatoire ; variance des embeddings saine (pas de collapse).

### Phase 2 — World model action-conditionné (le cœur)
- Entraîner le **predictor** : `s_t` + `a_t` → `ŝ_{t+1}` en latent. Action projetée + ajoutée
  au hidden (recette ESANN). Valider erreur de prédiction latente **1-pas ET multi-pas** vs
  baseline « copie de l'état ».
- 📚 **Pédago** : `docs/04_world_model.md` (action-conditioning, rollout latent, pourquoi
  prédire des latents > prédire des pixels).
- 🎬 **Visible — LE hook spectaculaire** : « **l'IA imagine le futur de Minecraft dans sa
  tête** ». Dérouler le world-model en latent sur K pas et visualiser via **retrieval du plus
  proche voisin de frames réelles** (ou un mini-décodeur entraîné *uniquement* pour la viz).
- ✅ **GATE** : erreur latente multi-pas nettement < baseline copie ; pas de collapse.

### Phase 3 — Agent qui joue (planning latent)
- **Planning MPC/CEM en latent** vers un **but-image** (capture cible) : échantillonner des
  séquences d'actions, dérouler le world-model, scorer par distance au but, exécuter la 1re
  action, replanifier (horizon glissant). Réutiliser la logique `eb_jepa` planning.
- Tâches courtes vérifiables : aller à un objet visible, ramasser du bois, descendre de N cases.
- (Stretch) politique apprise **dans l'imagination** (style Dreamer) pour tâches à récompense.
- 📚 **Pédago** : `docs/05_planning.md` (CEM/MPC, but-image, planifier en latent).
- 🎬 **Visible — L'ASSET VIRAL** : vidéo de l'agent qui **joue depuis les pixels**.
- ✅ **GATE** : ≥ 1 tâche réussie de façon fiable sur N épisodes.

### Phase 4 — Port vers le vrai Minecraft
- Porter la pipeline de Crafter → **MineRL** (visuel Minecraft réel = la marque). Réentraîner
  predictor/encoder sur frames MineRL.
- Polish démo : split-screen « **JEPA imagine vs réalité** » + « JEPA joue à Minecraft, il a
  appris son propre modèle du monde ».
- 📚 **Pédago** : `docs/06_minecraft_port.md` (MineRL, espace d'action VPT, pièges d'install).
- ✅ **GATE** : tourne sur GPU grand public, reproductible (seed + configs).

### Phase 5 — Packaging viral
- **README** avec GIFs/vidéo en haut, pitch en 2 lignes, **install one-command** (Docker +
  notebook Colab pour les sans-GPU), poids sur Hugging Face.
- **Storytelling** : fil X/blog « j'ai fait jouer une IA à Minecraft avec l'archi de LeCun
  (JEPA), depuis les pixels, sans génération d'image ». Les `docs/0X_*.md` pédago **deviennent**
  le contenu « how it works » (ton apprentissage = ton marketing).
- (Bonus narratif) micro-comparaison vs un LLM/VLM jouant la même tâche → angle
  « JEPA plus rapide/moins cher par action ».
- ✅ **GATE** : un inconnu clone et obtient une démo en < 15 min (ou via Colab sans rien installer).

---

## 5. Risques (honnêtes) & mitigations

- **R1 — Collapse** (l'écueil n°1 JEPA). → EMA target + VICReg ; monitorer la variance dès Phase 1.
- **R2 — OOD perception** (V-JEPA = vidéo naturelle ; jeu = synthétique). → On entraîne un JEPA
  *sur le jeu* (LeWM-style), pas V-JEPA gelé en primaire ; linear-probe Phase 1 = gate.
- **R3 — Débit temps réel** (encoder + CEM). → modèle léger ~15M, frames downsamplées, rollouts
  courts, cache d'encodage. Crafter d'abord (léger).
- **R4 — Install MineRL** (JDK8, miroirs Zenodo). → Crafter valide tout avant ; MineRL en Phase 4.
- **R5 — Démo « marche pas » = pas de buzz.** → Gates stricts : on ne package (Phase 5) que si
  l'agent réussit vraiment (Phase 3). Pas de hype sur du vide.
- **R6 — Code LeWM indisponible.** → Fallback : eb_jepa (action-conditioned + planning officiels)
  comme base ; vérifié en Phase 0.

---

## 6. Vérification (comment on saura que ça marche)

- Phase 0 : `scripts/collect.py` produit un dataset `(frames, actions)` + GIF random agent.
- Phase 1 : `scripts/probe.py` → accuracy linear-probe > seuil ; log variance (anti-collapse).
- Phase 2 : `scripts/eval_wm.py` → courbe erreur latente 1/k-pas vs baseline copie + viz imagination.
- Phase 3 : `scripts/play.py` → taux de succès tâches sur N épisodes + vidéos.
- Phase 4 : idem sur MineRL, sur GPU grand public.
- Phase 5 : test « clone-and-run » par un tiers / Colab.

---

## 7. Première itération concrète (au démarrage)

**Phase 0** : scaffold du repo + install Crafter + `scripts/collect.py` (frames+actions+GIF) +
`docs/01_jepa.md` (pédago) + vérifier dispo code LeWM & faire tourner un exemple eb_jepa.
C'est le socle qui valide l'outillage avant tout entraînement.

# C'est quoi JEPA ?

> Ce doc explique l'architecture au cœur de Mine-JEPA. Pas de prérequis — si tu sais ce
> qu'est un réseau de neurones, tu peux lire ça.

---

## Le problème que JEPA résout

Imagine que tu veux apprendre à un modèle de comprendre la dynamique d'un jeu vidéo
(Minecraft, Crafter…) sans aucun label. La solution classique ? L'**auto-encodeur** :
on compresse l'image, on la reconstruit, et si la reconstruction est bonne, le modèle
a "compris" quelque chose.

**Problème** : un auto-encodeur valorise *chaque pixel* également. Il va se battre pour
reconstruire parfaitement la texture de la terre, la couleur du ciel, le mouton en
arrière-plan — des détails que l'agent n'a pas besoin de comprendre pour agir.

Un humain ne pense pas en pixels quand il joue. Il pense : *"Si je frappe ce bloc de
bois, il casse et tombe"*. C'est une représentation **abstraite**, pas pixellique.

JEPA (Joint-Embedding Predictive Architecture) est l'architecture proposée par
**Yann LeCun (Meta, 2022)** pour apprendre exactement ces représentations abstraites.

---

## L'idée en 3 composants

```
Frames passées ──→ [ Context Encoder ] ──→ s_x (état latent)
                                               │
                                         [ Predictor ] + action a_t ──→ ŝ_{t+1}
                                                                              │
Frames futures ──→ [ Target Encoder  ] ──→ s_y (cible latente)              │
                                               │                              │
                                         Loss = ‖ŝ_{t+1} - s_y‖²  ←─────────┘
```

### 1. Le Context Encoder (x-encoder)
Encode ce que l'agent *voit maintenant* (les 1–3 dernières frames) → vecteur latent `s_x`.
Dans Mine-JEPA : un **ResNet5** (~40K params) qui prend une frame 64×64 RGB.

### 2. Le Target Encoder (y-encoder)
Encode ce qui *va se passer* (frames suivantes) → vecteur latent `s_y`.
**Clé** : ce réseau est une **copie EMA** (Exponential Moving Average) du context encoder.
Ses poids ne sont jamais mis à jour par backprop directement — ils suivent doucement
les poids du context encoder :

```
θ̄_{t+1} ← 0.99 · θ̄_t + 0.01 · θ_t
```

Pourquoi EMA ? Pour éviter le collapse (voir plus bas).

### 3. Le Predictor
Un petit réseau (MLP ou Conv léger) qui prédit `ŝ_{t+1}` à partir de `s_x` et de
l'action `a_t`. C'est le **world model** : il prédit comment l'état du monde change
quand l'agent fait une action.

**La loss est toujours dans l'espace latent** :
```
L_JEPA = ‖ŝ_{t+1} - s_y‖²
```

Jamais de reconstruction pixel-par-pixel. C'est ça la différence fondamentale avec
un modèle génératif.

---

## Le piège n°1 : le Collapse

JEPA a un gros défaut : il peut "tricher". Si l'encodeur apprend à tout mapper vers
le même vecteur constant (ex: `[0, 0, 0, …, 0]`), alors `ŝ_{t+1} ≈ s_y` toujours,
la loss tombe à 0, et le modèle n'a rien appris.

**Indicateur** : la variance des embeddings tombe en dessous de `1e-6`.

**Deux parades**, issues de VICReg (Bardes & LeCun, 2021) et du papier ESANN 2025
(*JEPA for RL*) :

1. **EMA du target encoder** : si les poids de l'encodeur changent brutalement,
   les targets changent plus lentement → force la prédiction à rester non-triviale.

2. **Régularisation de variance (VICReg)** : on ajoute une loss qui pénalise
   les embeddings dont la variance est trop faible :
   ```
   L_reg = -min(1, (1/D) Σ_i Var(s_x)_i)
   ```
   On clamp à 1 pour que ce soit une perte bornée.

La loss totale d'entraînement de Mine-JEPA :
```
L = L_JEPA + λ_reg · L_reg + (gradients RL si on entraîne un agent)
```

---

## Le World Model action-conditionné

Dans Mine-JEPA, le predictor reçoit **l'action de l'agent** en plus de l'état latent :

```
ŝ_{t+1} = Predictor(s_t, a_t)
```

Pour des actions discrètes (Crafter a 17 actions), on utilise un **embedding discret** :
```python
a_encoded = Embedding(n_actions=17, d_model=32)(action)
```

Ça permet de **dérouler le world model sur plusieurs pas** sans jamais toucher
l'environnement réel :
```
s_1 = Predictor(s_0, a_0)
s_2 = Predictor(s_1, a_1)
...
s_k = Predictor(s_{k-1}, a_{k-1})
```
C'est l'**imagination dans l'espace latent**.

---

## Comment l'agent planifie

Avec un world model qui prédit l'état latent futur, on peut planifier par **MPC** 
(Model Predictive Control) :

1. On définit un **but** : l'embedding encodé d'une frame cible (ex: "être à côté
   d'un arbre").
2. On échantillonne des séquences d'actions candidates aléatoirement.
3. On déroulé chaque séquence dans le world model en latent.
4. On garde la séquence dont l'état final est **le plus proche de l'embedding-but**.
5. On exécute seulement la 1ère action, on ré-observe, on replanifie.

Cet algorithme s'appelle **CEM (Cross-Entropy Method)**. Il est déjà implémenté dans
`mine_jepa/eb_jepa/planning.py` (`CEMPlanner`).

---

## Pourquoi c'est mieux qu'un LLM pour ce cas d'usage

| | LLM / VLM (Computer Use) | JEPA (Mine-JEPA) |
|---|---|---|
| Raisonnement haut niveau | ✅ Fort | ❌ Absent |
| Contrôle réactif | ❌ Trop lent (1–10s/action) | ✅ Rapide (<100ms/action) |
| Comprend la dynamique visuelle | ⚠️ Approx. (via description) | ✅ Direct (depuis les pixels) |
| Taille | Milliards de params | ~15M params |
| GPU nécessaire | Serveur ou API | RTX 3080+ |
| "Imagine" le futur | ❌ Non (génère du texte) | ✅ Oui (rollout latent) |

JEPA ne remplace pas le LLM — il complète. Le LLM dit **quoi** faire (haut niveau),
JEPA fait **comment** le faire (bas niveau réactif).

---

## Résumé en une phrase

> JEPA apprend une représentation abstraite du monde en prédisant l'état **latent** futur
> (pas les pixels), avec un target encoder EMA pour éviter le collapse, et un predictor
> conditionné par l'action pour simuler les conséquences de chaque mouvement.

---

*Concepts à lire ensuite : `docs/03_representation_collapse.md` (le collapse en détail),
`docs/04_world_model.md` (le predictor action-conditionné).*

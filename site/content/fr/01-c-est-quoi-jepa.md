---
title: "Qu'est-ce que JEPA, et pourquoi apprendre à un programme à jouer à Minecraft avec ça ?"
slug: "01-c-est-quoi-jepa"
lang: "fr"
order: 1
prerequisites: []
source_docs: ["docs/01_jepa.md", "docs/references/index.md", "CLAUDE.md#What this project is (1 line)"]
---

::: beginner

## Le projet, en une phrase

Mine-JEPA, c'est une tentative d'apprendre à un programme à jouer à Minecraft simplement en
regardant des images à l'écran — pas de règles écrites à l'avance, pas de solution toute faite,
pas de "si tu vois un arbre, appuie sur ce bouton". Juste des images brutes et une manette. Ce
chapitre parle de l'idée qui rend ça possible : une architecture appelée **JEPA**.

## Pourquoi ne pas simplement prédire le pixel suivant ?

L'idée la plus évidente serait celle-ci : montrer au programme des milliers d'images de
Minecraft, et lui apprendre à deviner à quoi ressemblera l'image suivante, pixel par pixel. S'il
devient bon à ça, il doit forcément comprendre le jeu, non ?

Il y a un problème. Imagine que tu doives prédire, pixel par pixel, une vidéo de quelqu'un qui
marche dans une forêt. Il faudrait deviner la couleur exacte de chaque feuille, la texture précise
du chemin de terre, la nuance exacte du ciel. Tout ça, c'est surtout du bruit visuel — ça ne
change rien à *la décision à prendre ensuite*. Un modèle obligé de s'obséder sur chaque pixel
passe le plus clair de son effort sur le mauvais problème, un peu comme un élève à qui on
demanderait d'apprendre un manuel par cœur, mot pour mot, au lieu de comprendre ce qu'il raconte.

Réfléchis à la façon dont *toi* tu joues réellement à un jeu. Tu ne penses pas "le pixel en
position (340, 220) est marron". Tu penses "il y a un arbre devant moi, si je le frappe, il va se
casser et me donner du bois". C'est une information beaucoup plus petite, et beaucoup plus utile,
que l'image complète.

## L'idée centrale : compresser d'abord, prédire ensuite

JEPA veut dire **Joint-Embedding Predictive Architecture** (« architecture prédictive à
plongements joints »). Elle a été proposée par Yann LeCun (un chercheur en IA bien connu chez
Meta) en 2022, dans le cadre d'une vision plus large de la façon dont des machines pourraient
apprendre à comprendre le monde. L'idée tient en un mouvement clé : au lieu de prédire le futur en
*pixels*, on le prédit dans un **résumé compressé** de l'image — ce qu'on appelle un
**embedding** (ou « plongement », ou « représentation latente »). Vois un embedding comme une
courte liste de nombres qui capture "ce qui compte" dans une scène, un peu comme un résumé d'une
phrase capture l'intrigue d'un livre sans en répéter chaque mot.

Voici la forme que ça prend :

1. Un **encodeur** (l'« encoder ») regarde l'image actuelle et la compresse en un vecteur compact
   — "voici ce que je comprends actuellement de la situation".
2. Un **prédicteur** (le « predictor ») prend ce vecteur, ainsi que l'action que l'agent est sur le
   point de faire (avancer, frapper avec l'outil, etc.), et prédit à quoi ressemblera le *prochain*
   vecteur compact.
3. Un second encodeur regarde l'image suivante *réelle*, et produit le vrai vecteur compact
   correspondant.
4. Le modèle est entraîné pour que sa prédiction se rapproche le plus possible de ce vrai vecteur.

Remarque importante : à aucun moment dans cette boucle le modèle n'essaie de redessiner l'image.
Il compare "le résumé compressé de ma supposition" au "résumé compressé de ce qui s'est vraiment
passé". C'est toute l'astuce.

## Une image concrète pour s'en souvenir

Imagine que tu joues aux échecs par SMS avec un ami, et qu'au lieu de décrire chaque détail du
plateau, vous vous mettez d'accord pour dire simplement des choses comme "cavalier prend pion,
échec". Vous ne perdez pas de mots à décrire le grain du bois des pièces. Vous ne gardez que
l'information qui change ce qui va se passer ensuite. JEPA essaie exactement ça : faire inventer à
un réseau de neurones sa propre version de ce langage abrégé — automatiquement, juste en
regardant des images — puis utiliser cet abrégé pour prédire "que se passe-t-il si je fais ceci".

## Ce que ça apporte au projet

Une fois qu'un modèle sait prédire "à quoi ressemblera mon résumé compact du monde si je prends
cette action", il peut commencer à *imaginer* — essayer une action dans sa tête, vérifier si le
résultat imaginé se rapproche de ce qu'il veut, et seulement ensuite appuyer réellement sur le
bouton. C'est le germe de la planification, et c'est pour ça que Mine-JEPA est construit autour de
JEPA plutôt que, par exemple, autour d'un modèle qui essaierait de générer des images complètes
du futur.

## Pourquoi ne pas utiliser un énorme modèle d'IA déjà prêt à l'emploi ?

On pourrait se demander : les très gros modèles d'IA (ceux derrière les chatbots ou les
générateurs d'images) ne comprennent-ils pas déjà la vidéo ? En quelque sorte — mais les plus
gros sont énormes (des centaines de millions à des milliards de paramètres), conçus pour décrire
ou générer de la vidéo, pas pour réagir en temps réel, et n'ont jamais été entraînés spécifiquement
sur Minecraft. Ce projet utilise volontairement un modèle JEPA **petit** — assez petit pour
s'entraîner sur une seule carte graphique grand public — construit et entraîné *directement sur
le jeu qu'il doit comprendre*. Il ne t'écrira pas un poème sur Minecraft, mais il peut réagir à
une image en une fraction de seconde, ce qui est exactement ce qu'exige le fait de jouer à un jeu
en temps réel.

:::

::: expert

## Énoncé du problème

Le backbone de Mine-JEPA est un JEPA léger (~15M paramètres) entraîné de bout en bout sur des
données pixel Crafter/MineRL, choisi explicitement plutôt qu'un grand modèle de fondation vidéo
figé (« frozen ») — voir la justification du rejet plus bas. L'architecture suit la proposition
JEPA de Yann LeCun (*A Path Towards Autonomous Machine Intelligence*, openreview BZ5a1r-kVsf,
2022) et hérite sa lignée d'encodeur d'I-JEPA (Assran et al., arXiv:2301.08243, CVPR 2023).

## Pourquoi pas une prédiction générative en espace pixel

Un modèle génératif (autoencodeur, diffusion, modèle pixel autorégressif) est entraîné pour
minimiser une perte de reconstruction ou de vraisemblance sur *l'ensemble* de l'observation —
chaque pixel a le même poids dans l'objectif. Sur une vue POV Minecraft/Crafter, cela signifie
que la perte est dominée par du signal à forte entropie et sans intérêt pour la tâche (texture du
feuillage, gradient du ciel, bruit d'éclairage) plutôt que par la structure de basse dimension
réellement pertinente pour la tâche (posture de l'agent, identité des objets proches, état
d'inventaire). C'est exactement le mode de défaillance générique contre lequel JEPA est conçu :
les features utiles pour le contrôle sont généralement à *faible variance et forte influence*
dans le signal pixel, pas à forte variance — voir Littwin et al. (arXiv:2407.03475) pour
l'argument théorique selon lequel le biais implicite de JEPA favorise précisément ces features
prédictives à forte influence plutôt que les features bruitées à forte variance qu'un objectif de
reconstruction (par ex. MAE) poursuit.

## L'architecture

Trois composants, tous opérant sur un latent par image `s ∈ R^D` (D=128 dans l'encodeur Crafter de
la Phase 1 de Mine-JEPA) :

```
x_t  ──→ [Context Encoder f_θ]  ──→ s_x
                                       │
                              [Predictor g] + a_t  ──→ ŝ_{t+1}
                                                             │
x_{t+1} ──→ [Target Encoder f_θ̄]  ──→ s_y                  │
                                       │                     │
                            L = ‖ŝ_{t+1} - s_y‖²  ←──────────┘
```

- **Context encoder** `f_θ` : ResNet5 (~40K paramètres) qui prend une image RGB 64×64 en entrée
  (`docs/01_jepa.md`).
- **Target encoder** `f_θ̄` : architecturalement identique, mais ses poids sont une EMA
  (**Exponential Moving Average**, moyenne mobile exponentielle) de ceux de `f_θ`
  (`θ̄_{t+1} ← 0.99·θ̄_t + 0.01·θ_t`), avec les gradients bloqués (`@torch.no_grad()` dans l'étape
  de mise à jour). C'est le mécanisme qui empêche les deux encodeurs de co-s'effondrer vers une
  constante triviale — voir le Chapitre 02 pour le traitement complet de l'anti-collapse.
- **Predictor** : un petit MLP (ou convolution légère) qui prend `s_x` et un embedding d'action
  discrète (`Embedding(n_actions, 32)`, sur l'espace à 17 actions de Crafter), et produit
  `ŝ_{t+1}`.

La perte est exclusivement un L2 en espace latent : `L_JEPA = ‖ŝ_{t+1} - s_y‖²`. Il n'y a aucun
terme de reconstruction pixel dans l'objectif — c'est la différence structurelle qui définit JEPA
face aux modèles du monde génératifs/autoencodeurs, pas un simple détail d'entraînement.

## Conditionnement par l'action et rollout latent

Comme le predictor est conditionné par `a_t`, il encode la dynamique de transition plutôt que des
statistiques marginales sur l'état suivant : `ŝ_{t+1} = g(s_t, a_t)`. Cela permet de dérouler
("unroll") entièrement en espace latent sans toucher au moteur de rendu ni à l'environnement réel :

```
s_1 = g(s_0, a_0);  s_2 = g(s_1, a_1); ...; s_k = g(s_{k-1}, a_{k-1})
```

Cette « imagination latente » est le mécanisme exploité par le planificateur (chapitre à venir, sur
le monde model et la planification) via MPC/CEM : échantillonner des séquences d'actions
candidates, les dérouler en espace latent, les évaluer contre un embedding-objectif, exécuter la
première action de la meilleure séquence, replanifier.

## Choix d'architecture et alternative rejetée

Le projet a explicitement rejeté V-JEPA 2 figé (« frozen », Assran et al., arXiv:2506.09985, 30
auteurs, 2025) comme backbone principal : un ViT-H de 600M paramètres entraîné sur ~1M heures de
vidéo naturelle est hors distribution (« OOD ») sur la vue POV stylisée de Minecraft, et n'est ni
clonable ni fine-tunable de bout en bout sur un GPU grand public à 8 Go de VRAM. Il reste
disponible uniquement comme comparaison secondaire via `torch.hub`, jamais comme substrat de
planification. Le design de backbone choisi — petit, entraîné directement sur le domaine cible,
conditionné par l'action — suit de très près LeWorldModel (Maes, Le Lidec, Scieur, LeCun,
Balestriero, arXiv:2603.19312, 2026) : ~15M paramètres, un seul GPU, et l'objectif à deux termes
(prédiction du prochain embedding + un régularisateur de variance/covariance) que la perte de
Mine-JEPA reprend dans son propre principe (voir Chapitre 02).

## Pourquoi ça plutôt qu'une politique LLM/VLM pour cette tâche

JEPA et un modèle de langage/vision-langage résolvent des problèmes différents et ne sont pas des
substituts en concurrence ici : un agent piloté par LLM ("computer use") raisonne bien sur des
instructions de haut niveau mais, à ~1–10 s par décision, est bien trop lent pour du contrôle
réactif, et sa "compréhension" de la dynamique de la scène passe par une description textuelle
plutôt qu'une prédiction directement conditionnée par les pixels. Le backbone JEPA de Mine-JEPA
tourne en moins de 100 ms par action et prédit la dynamique visuelle directement à partir des
pixels, au prix de n'avoir aucun raisonnement de haut niveau propre. Le cadrage du projet : un LLM
dirait *quoi* faire (haut niveau), JEPA fait *comment* le faire — ce projet construit et valide
uniquement ce second volet.

## Références (vérifiées, tirées de docs/references/index.md)

- LeCun, *A Path Towards Autonomous Machine Intelligence*, openreview BZ5a1r-kVsf (2022) — la
  proposition originale de JEPA.
- Assran et al., I-JEPA, arXiv:2301.08243 (CVPR 2023) — lignée de l'architecture d'encodeur.
- Maes, Le Lidec, Scieur, LeCun, Balestriero, LeWorldModel, arXiv:2603.19312 (2026) —
  l'architecture publiée la plus proche ; source du gate `ratio = val_pred/val_copy` utilisé à
  partir du Chapitre 03.
- Assran et al., V-JEPA 2, arXiv:2506.09985 (2025) — rejeté comme backbone principal, comparaison
  uniquement.
- Littwin et al., arXiv:2407.03475 (2024) — fondement théorique de pourquoi JEPA favorise les
  features prédictives plutôt que les features bruitées à forte variance.

:::

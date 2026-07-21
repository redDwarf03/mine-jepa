---
title: "Essayer 512 avenirs dans sa tête avant d'appuyer sur un bouton"
slug: "04-planifier-en-imagination"
lang: "fr"
order: 4
prerequisites: ["01-c-est-quoi-jepa", "02-le-piege-du-collapse", "03-le-modele-du-monde"]
source_docs: ["docs/05_planning.md", "CLAUDE.md#Phase 3 — gates validated"]
---

::: beginner

## Il manque encore une pièce

Récapitulons où on en est. Le Chapitre 1 a donné au modèle un encodeur qui sait résumer une
image en une courte liste de nombres (un **embedding**) sans tricher (Chapitre 2). Le Chapitre 3
lui a donné un **world model** (modèle du monde) : une fonction qui sait imaginer « si je fais
cette action, à quoi ressemblera l'embedding suivant ? », et qui bat clairement la solution
paresseuse consistant à recopier l'état actuel.

Mais résumer des images et imaginer leur suite, ce n'est toujours pas *jouer*. Il manque une
dernière pièce : **comment choisir quelle touche appuyer, maintenant, à cet instant précis ?**
C'est le sujet de ce chapitre — la Phase 3 du projet, testée sur Crafter (le petit jeu
d'entraînement avant le vrai Minecraft).

## D'abord, il faut savoir où on veut aller

Avant de pouvoir choisir une action, il faut définir un **objectif** — et cet objectif, lui
aussi, est un embedding. Le projet construit ce qu'il appelle le **goal embedding** (l'embedding
objectif) de façon très simple : il prend toutes les images du jeu où le personnage a un bon
niveau de nourriture (la faim est un bon indicateur de survie), les passe dans l'encodeur, et
fait la moyenne de tous ces vecteurs. Ce point moyen — le **centroïde** — devient « à quoi
ressemble un bon état ». L'agent n'a jamais reçu l'étiquette « ça, c'est un bon état » pendant
son entraînement — cet objectif est construit *après coup*, à partir de données déjà collectées.

## L'idée : essayer plein d'avenirs imaginaires, choisir le meilleur

Voici la partie amusante. Imagine un livre « dont tu es le héros », où à chaque page tu peux
choisir entre plusieurs actions, et chaque choix mène à une suite différente de l'histoire.
Plutôt que de choisir une action au hasard puis de voir ce qui se passe, imagine que tu puisses,
en une fraction de seconde, **feuilleter 512 histoires imaginaires différentes** — chacune une
suite de 12 choix d'affilée — sans jamais tourner une seule vraie page du livre. Tu regardes
laquelle de ces 512 fins imaginaires ressemble le plus à ce que tu veux (l'objectif), et *alors
seulement* tu fais réellement le premier choix de la meilleure histoire imaginée. Puis tu répètes
tout le processus depuis ta nouvelle situation réelle.

C'est exactement l'algorithme qu'utilise Mine-JEPA, appelé **MPC par tir aléatoire** (« random-
shooting Model Predictive Control ») :

1. Encoder l'état actuel en embedding.
2. Tirer au hasard 512 séquences différentes de 12 actions chacune.
3. Pour chaque séquence, dérouler le world model pas à pas — 12 fois — pour imaginer où elle mène.
4. Comparer chacune des 512 destinations imaginées à l'objectif ; garder la séquence dont la
   destination imaginée s'en rapproche le plus.
5. N'exécuter réellement que la *première* action de cette meilleure séquence.
6. Recommencer tout le processus depuis le nouvel état réel.

## Pourquoi recommencer à chaque étape plutôt que suivre le plan entier ?

Bonne question, et la réponse est honnête : le world model se trompe de plus en plus au fil des
étapes imaginées — les petites erreurs s'accumulent. Si l'agent suivait aveuglément un plan de 12
actions imaginé une seule fois, il finirait par dériver loin de la réalité. En re-planifiant à
chaque étape à partir de ce qui s'est *vraiment* passé, l'agent corrige continuellement sa
trajectoire. C'est ce qu'on appelle un **horizon glissant** (« receding horizon ») : on ne
regarde loin devant que pour décider quoi faire *maintenant*.

## Pourquoi 512 histoires suffisent (et pas des milliards)

Avec 17 actions possibles et 12 étapes, le nombre total de séquences possibles est astronomique —
environ 600 milliards. On n'en essaie que 512. Ça marche parce que beaucoup d'actions ont un
effet à court terme très similaire (avancer vers la gauche ou vers la droite ne mène pas à des
mondes complètement différents après une seule étape), donc 512 tirages aléatoires couvrent déjà
bien les directions qui comptent. Et comme tout ce calcul se fait en embeddings — de petits
vecteurs de nombres — plutôt qu'en vraies images, l'ordinateur peut imaginer les 512 × 12 étapes
en quelques millisecondes.

## Ce qui s'est vraiment passé

Le projet a mesuré ce planificateur deux fois, à des moments différents, avec des chiffres qui se
ressemblent sans être identiques (ce qui arrive quand on refait une mesure sur un nouveau lot
d'épisodes plutôt que d'essayer de faire coller artificiellement les deux résultats).

Une évaluation sur 50 épisodes a donné, pour l'agent JEPA-MPC contre un agent qui joue au hasard :
récompense moyenne ~2,1 contre ~1,5, ~3,0 contre ~2,4 « achievements » (objectifs du jeu
accomplis) par épisode, et un taux de succès (au moins un achievement) proche de 100% contre 98%
pour l'agent aléatoire.

Le gate officiel de la Phase 3, rapporté dans le journal du projet, donne : **100% de taux de
succès**, **2,56 achievements par épisode contre 2,38** pour l'agent aléatoire (+7,5%), et une
récompense **+14%**. Le premier épisode de l'agent obtient 3 achievements différents : se
réveiller, ramasser du bois, et poser une table — ce qui demande de trouver un arbre, de
l'approcher, de le frapper, puis de poser un objet. Rien de tout ça n'était codé à la main.

## Pourquoi ça marche — et ce que ça ne résout pas

L'intuition : le world model a appris que « si je fais X, l'embedding bouge dans telle direction ».
Quand l'objectif est « un état avec beaucoup de nourriture », le planificateur enchaîne
naturellement des actions qui rapprochent l'embedding de cet objectif — trouver une plante, s'en
approcher, la manger — sans qu'on lui ait jamais dit comment faire ça étape par étape.

Ce n'est pas parfait pour autant. Le world model se trompe sur de longs horizons, et l'objectif
n'est qu'un point moyen (le centroïde) : il dit *à quoi ressemble* un bon état, pas *comment y
arriver*. Deux états très différents visuellement peuvent parfois être « proches » dans l'espace
des embeddings sans que ça veuille vraiment dire la même chose — un flou qu'on retrouvera plus
loin dans l'histoire du projet.

Mais même imparfait, ce world model guide mieux qu'un joueur qui appuie au hasard. Et la
prochaine étape logique — celle du chapitre suivant — est de rebrancher exactement ce même
pipeline (encodeur, world model, planificateur) sur le vrai Minecraft.

:::

::: expert

## Le problème et sa formalisation

À l'issue des Chapitres 1-3, on dispose de `f_θ : x → s ∈ R^D` (encodeur, figé depuis la Phase 1)
et `g : (s_t, a_t) → ŝ_{t+1}` (world model, Phase 2). Il manque une politique. Mine-JEPA choisit
de **ne pas apprendre de politique paramétrique** (pas de policy gradient, pas de fonction de
valeur) — la planification se fait directement par recherche dans l'espace latent, à chaque pas
de temps, en réutilisant les modules déjà entraînés sans gradient additionnel.

## Construction du goal embedding

```python
good_frames = frames[food >= 7]          # ~16 000 frames sur 32 000
goal = encoder(good_frames).mean(dim=0)  # [D] — centroïde
```

Le goal est un centroïde post-hoc dans l'espace latent, construit à partir d'un sous-ensemble du
dataset de collecte filtré sur un proxy de survie (food ≥ 7), sans aucune étiquette de tâche
fournie pendant l'entraînement de l'encodeur ou du world model.

## Random-shooting MPC

```
Pour chaque pas de temps :
  1. Encoder l'état courant  →  s_t
  2. Tirer N=512 séquences d'actions aléatoires de longueur H=12
  3. Pour chaque séquence : dérouler le world model sur H pas → ŝ_{t+H}
  4. Scorer : score_i = -MSE(ŝ_{t+H,i}, s_goal)
  5. Exécuter la première action de la séquence au meilleur score
  6. Répéter (horizon glissant)
```

```python
class LatentMPCPlanner:
    @torch.no_grad()
    def plan(self, s_current, s_goal):
        s = s_current.expand(self.n_candidates, -1).clone()          # [N, D]
        actions = torch.randint(0, self.n_actions,
                                 (self.n_candidates, self.horizon))    # [N, H]
        for h in range(self.horizon):
            s = self.predictor(s, actions[:, h])                      # [N, D]
        scores = -(s - s_goal).pow(2).mean(dim=1)                     # [N]
        return actions[scores.argmax(), 0].item()
```

L'intégralité du planificateur tient en une dizaine de lignes — un corollaire direct du fait que
tout le calcul lourd (compréhension de scène, dynamique) a déjà été poussé dans l'encodeur et le
predictor lors des phases précédentes ; le planificateur lui-même n'est qu'une recherche.

## Justification du budget de calcul

Espace de séquences : `17^12 ≈ 6×10^11`. Le budget de candidats (N=512) n'en couvre qu'une
fraction infime, mais suffit parce que de nombreuses actions ont des effets à court terme
similaires (redondance directionnelle de l'espace d'action de Crafter) — l'échantillonnage
i.i.d. couvre les grandes directions utiles sans avoir besoin d'une recherche exhaustive. Le
rollout batché de 512×12 pas s'exécute en < 5 ms sur GPU, car chaque pas n'est qu'un forward pass
du predictor (~140K paramètres) sur un batch de 512 — tout se passe en espace latent, sans jamais
retoucher le moteur de rendu ni l'environnement réel.

## Horizon glissant

Re-planifier à chaque pas à partir de l'état *réellement* observé, plutôt que d'exécuter le plan
de 12 pas en aveugle, corrige l'erreur composée accumulée par le world model sur des rollouts
longs (cf. Chapitre 03, section sur l'accumulation d'erreur k-step). C'est un choix structurel :
la robustesse vient de la fréquence de re-planification, pas de la précision du world model seul.

## Résultats mesurés — deux évaluations distinctes

`docs/05_planning.md` rapporte une évaluation sur 50 épisodes Crafter :

| Métrique | Agent JEPA-MPC | Baseline aléatoire |
|----------|---------------|-----------------|
| Récompense moyenne | ~2,1 | ~1,5 |
| Achievements/épisode | ~3,0 | ~2,4 |
| Taux de succès (≥1 achievement) | ~100% | ~98% |
| FPS | ~150 | — |

`CLAUDE.md` (le gate officiel de la Phase 3) rapporte des chiffres distincts sur ce qui semble
être un lot d'épisodes différent : **100% de taux de succès**, **2,56 achievements/épisode contre
2,38** pour la baseline aléatoire (+7,5%), et **récompense +14%**. Les deux mesures viennent de
la même Phase 3 et pointent dans la même direction (amélioration nette sur les trois métriques,
succès quasi-total), mais ne coïncident pas chiffre pour chiffre — cohérent avec le fait qu'il
s'agit de deux runs d'évaluation distincts plutôt que d'une même mesure rapportée deux fois. Les
deux sont rapportées ici telles quelles plutôt que forcées à s'accorder. Le premier épisode
enchaîne 3 achievements (`wake_up`, `collect_wood`, `place_table`) — une séquence qui suppose de
localiser un arbre, s'en approcher, le frapper, puis poser un objet, sans logique de tâche
codée à la main.

## Pourquoi ça marche

Le predictor conditionné par l'action a appris la fonction de transition `ŝ_{t+1} = g(s_t, a_t)`.
Quand l'objectif est un centroïde de « bons » états, le score `-MSE(ŝ_{t+H}, s_goal)` favorise
naturellement les séquences d'actions qui font converger la trajectoire latente vers cette région
— sans qu'aucune récompense de tâche explicite n'ait jamais été injectée dans l'entraînement de
l'encodeur ou du predictor. Le comportement orienté-but émerge entièrement de la combinaison
(world model + recherche), pas d'un objectif d'apprentissage par renforcement.

## Limites identifiées et pistes du projet

**Limite principale** : le goal embedding est un centroïde — il encode *à quoi ressemble* le but,
pas *comment l'atteindre*. Deux états visuellement distincts peuvent être proches dans l'espace
latent sans être équivalents fonctionnellement (ambiguïté géométrique de l'espace latent) ; ceci
préfigure un problème plus large — la géométrie latente sur laquelle repose la planification n'est
pas garantie par la seule qualité de prédiction — qui refera surface dans une phase ultérieure du
projet, sur un jeu de données différent.

**Extension future notée dans le plan de la Phase 3** : le CEM (Cross-Entropy Method) — affiner
itérativement la distribution d'échantillonnage des actions sur plusieurs itérations, plutôt
qu'un tir unique de 512 séquences i.i.d. — déjà implémenté pour actions continues dans
`mine_jepa/eb_jepa/planning.py` au moment de la Phase 3, mais pas encore branché sur le
planificateur discret de Crafter. Une version discrète de cette idée reviendra dans une phase
ultérieure du projet.

## Le pipeline complet à ce stade

```
Frames 64×64  →  [Encodeur Phase 1]  →  s_t  [D=128]
                                            │
                                      s_t + a_t
                                            │
                                  [World Model Phase 2]  →  ŝ_{t+1}
                                            │
                              512 séquences imaginées
                                            │
                                [Score vs s_goal]
                                            │
                                       best_action
                                            │
                                Crafter.step(action)
                                            │
                                  obs_{t+1}  ←─ (boucle)
```

Tout se passe en espace latent, à l'exception des deux extrémités : l'entrée pixel et l'action
finale.

## Références (vérifiées, tirées de docs/references/index.md)

- Maes, Le Lidec, Scieur, LeCun, Balestriero, LeWorldModel, arXiv:2603.19312 (2026) — la
  convention `ratio = val_pred/val_copy` du Chapitre 03, socle sur lequel repose la fiabilité du
  rollout latent exploité ici par le planificateur.
- Meta FAIR, eb_jepa (github.com/facebookresearch/eb_jepa) — la logique de planification
  (`mine_jepa/eb_jepa/planning.py`) réutilisée pour l'extension CEM mentionnée en fin de chapitre.

:::

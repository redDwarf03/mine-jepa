---
title: "Le raccourci que le modèle essaie toujours de trouver (et comment on l'en empêche)"
slug: "02-le-piege-du-collapse"
lang: "fr"
order: 2
prerequisites: ["01-c-est-quoi-jepa"]
source_docs: ["docs/03_representation_collapse.md", "CLAUDE.md#Risk #1: COLLAPSE"]
---

::: beginner

## Un modèle qui « gagne » sans rien apprendre

Dans le Chapitre 1, on a posé le jeu d'entraînement de JEPA : regarder une image, la compresser en
une courte liste de nombres (un **embedding**), prédire à quoi ressemblera l'embedding de l'image
*suivante*, et être noté sur la précision de cette prédiction. Plus l'erreur est basse, mieux
c'est censé être.

Sauf qu'il existe une façon d'obtenir une note parfaite à ce jeu sans rien apprendre du tout sur
Minecraft.

Imagine un élève qui remarque que son correcteur ne vérifie jamais si une réponse est *juste*, mais
seulement si elle *correspond exactement à ce qu'il avait écrit la fois précédente*. Cet élève
n'a alors qu'à écrire le même mot — disons « banane » — à chaque question, à chaque contrôle, pour
toujours. Si « banane » est jugé être une « prédiction » acceptable de lui-même, cet élève obtient
un score parfait à tous les coups, sans avoir rien compris à aucune des matières testées.

C'est exactement le piège dans lequel JEPA peut tomber. On appelle ça le **collapse**
(effondrement) : l'encodeur apprend à écraser *toutes* les images — quoi qu'il se passe réellement
dans le jeu — vers exactement le même vecteur de sortie, disons `[0, 0, 0, ..., 0]`. Si chaque
image donne le même vecteur, alors prédire « le vecteur de l'image suivante » devient trivial :
c'est encore ce même vecteur constant. L'erreur entre la prédiction et la cible tombe à zéro. La
courbe d'entraînement a l'air magnifique. Et le modèle n'a strictement rien appris sur Minecraft
— il ne sait pas distinguer un arbre d'un zombie ou d'un ciel dégagé, parce qu'il n'a jamais
regardé ce qui différencie ces images entre elles.

C'est un problème sérieux parce qu'un modèle « collapsé » est *activement trompeur* si on ne
surveille que la courbe de perte (« loss »). Une perte proche de zéro ressemble à un succès. La
seule façon de détecter le piège, c'est de vérifier autre chose : est-ce que les sorties du
modèle sont réellement *différentes* pour des entrées réellement différentes ?

## Comment on le détecte

La parade consiste à mesurer en permanence à quel point les embeddings du modèle sont *dispersés*
sur un lot (« batch ») d'images différentes — une quantité que le projet appelle `batch_var`
(variance du batch). Si des images qui se ressemblent peu dans le jeu (être debout dans un désert
vs. être debout dans une forêt) produisent aussi des embeddings très différents, `batch_var` reste
raisonnablement élevé. Si le modèle a basculé dans le raccourci « je réponds toujours banane »,
`batch_var` s'écroule vers zéro — chaque image est projetée vers (presque) le même point, il n'y a
plus rien à disperser.

## Deux garde-fous, pas seulement une surveillance

Se contenter de surveiller le chiffre ne suffit pas : on veut aussi rendre le collapse difficile à
atteindre en premier lieu. Mine-JEPA combine deux contre-mesures :

**1. Une cible d'évaluation « à la traîne » (EMA).** Plutôt que d'avoir un encodeur qui se note
lui-même contre une copie de lui-même mise à jour exactement à la même vitesse (ce qui rend très
facile pour les deux copies de glisser ensemble vers la même réponse paresseuse), l'encodeur
« cible » — celui qui produit le corrigé — n'avance qu'à petits pas, via une moyenne mobile de
poids appelée **EMA** (Exponential Moving Average, moyenne mobile exponentielle). C'est comme
séparer un élève du corrigé par un décalage dans le temps : le corrigé se met à jour un peu après
l'élève, ce qui empêche l'élève de copier le même raccourci dans les deux à la fois.

**2. Une pénalité explicite « disperse-toi » (VICReg).** En plus de l'EMA, la recette
d'entraînement ajoute une pénalité directe (issue d'une technique appelée VICReg) qui punit le
modèle chaque fois que ses embeddings pour des images différentes commencent à se regrouper trop
près les uns des autres. C'est une règle qui dit, en somme : « tu n'as pas le droit de donner la
même réponse à tout, même si ça te ferait bien noter à court terme. »

## Ce qui s'est vraiment passé lors du premier entraînement de ce projet

Ce n'est pas un risque théorique dont l'équipe s'inquiétait dans l'abstrait — c'est quelque chose
qui a été mesuré directement pendant l'entraînement de la Phase 1 (30 epochs, sur une RTX 5060 Ti,
sur 32 676 transitions de jeu Crafter). Au moment de la vérification, `batch_var` valait **1,13**
— largement au-dessus du seuil d'alerte documenté (`batch_var < 1e-4`) — et la perte de validation
finale était de **0,080**. En d'autres mots : la perte a baissé *et* les embeddings sont restés
dispersés. Cette combinaison, c'est ce à quoi ressemble « le modèle apprend vraiment quelque chose,
il ne triche pas », dans les chiffres.

L'équipe n'a pas fait confiance aux chiffres seuls, non plus : un test indépendant a suivi (un
« linear probe » — sonde linéaire : un classifieur très simple peut-il lire la santé de l'agent
directement sur les embeddings figés, sans rien y ajouter ?). Résultat : **90,8 %**, contre une
base de référence à **86,9 %** — soit environ **3,9 points de pourcentage** de mieux. C'est une
preuve indépendante que les embeddings contiennent vraiment une information exploitable sur l'état
du jeu, et pas seulement une variance qui a l'air saine.

:::

::: expert

## Collapse : mécanisme, et pourquoi les architectures à embedding joint y sont particulièrement exposées

Les méthodes auto-supervisées basées sur la reconstruction (autoencodeurs, prédiction pixel/token
masqué à la BERT/MAE) sont structurellement protégées du collapse représentationnel : on ne peut
pas reconstruire une image à partir d'un code constant, donc la perte elle-même interdit la
solution triviale. JEPA n'a aucune protection de ce genre par construction — le context encoder et
le predictor sont optimisés conjointement en espace latent, sans aucune ancre vers les pixels bruts
dans la perte, donc la paire est libre de co-adapter n'importe quelle solution qui minimise
`‖ŝ_{t+1} - s_y‖²`, y compris le minimum global à `s_x = s_y = ŝ_{t+1} = const`. Les méthodes
contrastives (SimCLR) évitent ça via des paires négatives explicites (un terme répulsif qui
force les entrées différentes à s'écarter), ce que JEPA omet délibérément — le compromis accepté
par ce projet : pas de négatifs, pas besoin de gros batchs, mais un risque de collapse plus élevé
qu'il faut gérer architecturalement.

## Signal surveillé

`batch_var = embeddings.var(dim=0).mean()` — variance moyenne par dimension sur un batch
d'entraînement. Ce projet documente deux seuils, à ne pas confondre :

- `docs/03_representation_collapse.md` fixe le **seuil d'alerte opérationnel** à
  `batch_var < 1e-4` — c'est le seuil que le gate de la Phase 1 utilise réellement (« > 1e-4 »
  requis pour passer, mesuré à 1,178 au moment de la sonde, per `CLAUDE.md`).
- La section « Risk #1 : COLLAPSE » de `CLAUDE.md` (la règle d'architecture générale du projet)
  fixe une alarme plus extrême, « `batch_var < 1e-6` : collapse en cours », comme signal de
  collapse déjà largement engagé plutôt que comme seuil de passage du gate.

Ce chapitre traite `1e-4` comme le seuil opérationnel du gate Phase 1, et `1e-6` comme le plancher
d'alarme au-delà duquel le collapse n'est plus une hypothèse mais un fait. Ce contrôle est fait à
chaque epoch comme un gate permanent, pas comme une vérification ponctuelle.

## Contre-mesure 1 — Target encoder EMA

```
θ̄_{t+1} ← 0.99 · θ̄_t + 0.01 · θ_t
```

`θ` (context encoder) reçoit les gradients normalement ; `θ̄` (target encoder) n'est mis à jour que
via cette EMA, avec `@torch.no_grad()` imposé à l'étape de mise à jour — aucun chemin de gradient
n'existe de la perte vers `θ̄` directement. Cela découple la vitesse de changement de la cible de
prédiction de la vitesse de changement des entrées du predictor, ce qui supprime le chemin de
collapse le plus facile : si les deux encodeurs bougeaient en lockstep sous gradient, la paire
pourrait co-glisser vers une constante avec perte nulle et aucun signal de gradient pour s'en
échapper. Avec une cible qui dérive lentement, le predictor ne peut pas « s'endormir » sur une
solution triviale fixe puisque la cible elle-même continue de bouger — une forme
d'auto-distillation par momentum, structurellement identique à l'astuce du target network dans
DINO/BYOL, utilisée ici dans le même but anti-collapse.

## Contre-mesure 2 — VICReg (Bardes, Ponce, LeCun, arXiv:2105.04906, ICLR 2022)

Deux termes de régularisation explicites ajoutés à l'objectif, en s'appuyant sur la recette
documentée localement dans `ES2025-19.pdf` (ESANN 2025) :

**Terme de variance** (anti-collapse direct) :
```
L_std = mean( max(0, 1 - std(s_x, dim=0)) )
```
Nul quand chaque dimension de l'embedding a un std ≥ 1 ; augmente quand la variance chute
(collapse en cours), fournissant un signal de gradient qui s'oppose activement au collapse plutôt
que de simplement le détecter après coup.

**Terme de covariance** (anti-redondance) :
```
L_cov = mean( off_diagonal( cov(s_x)^2 ) )
```
Pénalise la corrélation entre dimensions de l'embedding — sans lui, un modèle pourrait satisfaire
le terme de variance tout en ayant chaque dimension qui encode le même signal unidimensionnel, ce
qui est fonctionnellement proche du collapse même avec un `batch_var` nominalement élevé.

## L'objectif total de la Phase 1 de Mine-JEPA

```
L = L_JEPA + λ_std · L_std + λ_cov · L_cov
    λ_std = 1.0, λ_cov = 0.04   (configs/train_encoder.yaml)
```

`λ_std` est fixé un ordre de grandeur au-dessus de `λ_cov` parce que le collapse en variance est le
risque existentiel ; la décorrélation n'est qu'un raffinement secondaire.

## Dynamique d'entraînement mesurée (run réel, Crafter, 32 676 transitions, RTX 5060 Ti)

| Epoch | total | jepa | std_loss | cov_loss | batch_var | val_loss |
|------:|------:|-----:|---------:|---------:|----------:|---------:|
| 1 | 0.190 | 0.134 | 0.040 | 0.434 | 1.057 | 0.250 |
| 2 | 0.119 | 0.101 | 0.001 | 0.405 | 1.124 | 0.191 |
| 3 | 0.106 | 0.091 | 0.001 | 0.347 | 1.128 | 0.122 |
| 4 | 0.094 | 0.081 | 0.001 | 0.303 | 1.133 | 0.114 |
| 5 | 0.084 | 0.073 | 0.001 | 0.271 | 1.150 | 0.098 |

Lecture : `batch_var` *monte* (1,057→1,150) au fil de l'entraînement plutôt que de décroître vers
zéro — l'inverse de la signature du collapse. `std_loss` sature près de son plancher (~0,001) dès
l'epoch 2, ce qui indique que la contrainte de variance est satisfaite tôt et à faible coût,
laissant le terme de prédiction JEPA (qui continue de baisser, 0,134→0,073) comme objectif
contraignant. `cov_loss` baisse de façon monotone (0,434→0,271), cohérent avec une décorrélation
progressive entre dimensions.

Le résultat du gate Phase 1 rapporté dans `CLAUDE.md`, après le run complet de 30 epochs :
**val_loss=0,080, batch_var=1,13** — nettement au-delà du seuil d'alerte de 1e-4. `CLAUDE.md`
note aussi une mesure distincte, `batch_var` = 1,178 « au moment de la sonde » (probe), un chiffre
légèrement différent du 1,13 final — les deux tracent le même run mais à des instants de mesure
différents, ce qui est cohérent avec le fait que `batch_var` continue de fluctuer légèrement
pendant l'entraînement plutôt que de converger vers une valeur unique figée.

Corroboration indépendante via `scripts/probe.py` : une sonde linéaire entraînée sur les
embeddings figés prédit la santé de l'agent à **90,8 %**, contre une base à **86,9 %** — soit
**+3,9 points de pourcentage** (90,8 − 86,9 ; `CLAUDE.md` arrondit cet écart à « +3,8 % », un
léger écart d'arrondi par rapport au calcul direct des deux pourcentages qu'il rapporte
lui-même — les deux valeurs mesurées, 90,8 % et 86,9 %, sont elles bien vérifiées). C'est une
preuve que la variance conservée est un signal *pertinent pour la tâche*, pas juste du bruit qui
a une variance non nulle par hasard.

## La signature de défaillance contre laquelle on se protège

Pour contraste (non exécuté comme une expérience d'ablation documentée, mais présenté comme le
motif attendu en l'absence d'EMA/VICReg) : `batch_var` décroissant de ~1,05 vers `1e-9` au fil des
epochs d'entraînement, tandis que la perte JEPA chute simultanément vers zéro — le piège de
diagnostic étant que la seule courbe de perte a alors l'air d'un succès. C'est pourquoi
`batch_var` est suivi comme un diagnostic permanent et obligatoire (selon les instructions de la
section Risk #1 de `CLAUDE.md`), et non comme une vérification de débogage occasionnelle.

## Références (vérifiées, tirées de docs/references/index.md)

- Bardes, Ponce, LeCun, VICReg, arXiv:2105.04906 (ICLR 2022) — la régularisation
  variance/covariance utilisée directement dans `mine_jepa/ebwm/losses.py`.
- ES2025-19 (ESANN 2025, PDF local) — la recette anti-collapse adaptée dans
  `docs/03_representation_collapse.md`.
- Sobal et al., arXiv:2211.10831 (2022) — la tendance des JEPA à trop s'attacher à des features
  lentes et non pertinentes pour la tâche ; contexte utile pour comprendre pourquoi la variance
  seule ne garantit pas des représentations utiles (motive le terme de covariance et des choix de
  masquage ultérieurs, non résolus par VICReg seul).

:::

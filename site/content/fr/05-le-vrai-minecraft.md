---
title: "Le grand saut vers le vrai Minecraft : quatre échecs, puis un agent qui coupe des arbres"
slug: "05-le-vrai-minecraft"
lang: "fr"
order: 5
prerequisites: ["01-c-est-quoi-jepa", "02-le-piege-du-collapse", "03-le-modele-du-monde", "04-planifier-en-imagination"]
source_docs: ["docs/06_minecraft_port.md", "CLAUDE.md#Phase 4 gates"]
---

::: beginner

## Crafter, c'était les roues stabilisatrices

Jusqu'ici, tout ce que le projet a construit — l'encodeur (Chapitre 1), les garde-fous contre le
collapse (Chapitre 2), le world model (Chapitre 3), le planificateur (Chapitre 4) — a été testé
sur **Crafter**, un petit jeu léger qui ressemble à Minecraft en dessin simplifié. C'était le bon
choix pour déboguer vite. Mais le vrai objectif du projet, celui qui donne son nom au projet,
c'est le **vrai** Minecraft — le jeu en 3D avec ses vraies textures, celui que tout le monde
imagine quand on dit « une IA joue à Minecraft ».

Ce chapitre raconte ce qui s'est passé quand le projet a fait ce saut. Et il faut être honnête :
**ça n'a pas marché du premier coup. Ni du deuxième. Ni du troisième. Ni du quatrième.**
La cinquième tentative a marché — et comprendre *pourquoi* les quatre premières ont échoué est
au moins aussi instructif que la réussite finale.

## La bonne nouvelle d'abord : rien à reconstruire

Le point clé de ce chapitre : **l'architecture ne change pas**. L'encodeur, le world model, le
planificateur — ce sont, en principe, exactement les mêmes briques que sur Crafter. Seul le jeu
change. Si l'idée de JEPA (comprimer d'abord, prédire ensuite, dans un résumé plutôt qu'en
pixels) est solide, elle devrait fonctionner sur n'importe quel jeu vidéo, pas seulement sur
Crafter. C'est exactement ce que ce chapitre met à l'épreuve.

## Le tuyau technique qui relie Python au vrai Minecraft

Le vrai Minecraft n'est pas écrit en Python. Le projet utilise **MineRL**, une bibliothèque qui
pilote Minecraft via un mod nommé **Malmo** (développé à l'origine par Microsoft). Le chemin
technique ressemble à ça : le code Python envoie des ordres à un serveur Java qui fait tourner
une vraie instance de Minecraft, et récupère en retour une image 64×64 pixels — la même taille que
les images de Crafter, pour que rien d'autre n'ait besoin de changer.

Ce pont Python ↔ Java est fragile. Le projet a rencontré un bug particulièrement retors, surnommé
**MALMOBUSY** : après un premier épisode de jeu, dès qu'on essayait de lancer le suivant, tout se
bloquait pendant trois minutes avant de planter. La raison, en résumé : quand un épisode se
termine, Minecraft met un petit instant à revenir dans un état « prêt pour la suite », mais
Python, impatient, envoie déjà l'ordre suivant. Minecraft répond « occupé », referme la
connexion... et Python continue d'attendre une réponse sur une ligne qui n'existe plus.
Solution retenue, pas élégante mais fiable : **relancer Minecraft entièrement à chaque épisode**
plutôt que d'essayer de réutiliser la même instance. Chaque partie de Minecraft démarre en
30 à 60 secondes ; collecter 20 épisodes prend donc environ une demi-heure — lent, mais robuste.

## Premier essai : l'agent tourne en rond, récompense zéro

Une fois la connexion technique stabilisée, le premier vrai test a donné un résultat sans appel :
sur 20 épisodes de jeu (« couper un arbre »), l'agent n'a obtenu **aucune récompense, aucun
achievement**. Il ne plante pas, il joue — mais il ne fait jamais rien d'utile.

Deux raisons, toutes les deux liées au même problème de fond :

**1. L'objectif n'avait aucun signal.** L'objectif (le centroïde du Chapitre 4) avait été
construit à partir des images d'un agent qui se baladait au hasard — et un agent au hasard ne
coupe jamais d'arbre. Résultat : l'objectif ne pointait vers rien de particulier, comme demander
son chemin à quelqu'un qui n'est jamais allé là où on veut aller.

**2. Le world model était trop faible.** Sur des images filmées par un agent qui erre sans but,
Minecraft change très peu d'une image à l'autre — donc le world model apprenait surtout que
« rien ne change jamais », ce qui rend la planification aveugle : imaginer 12 pas dans le futur
ne mène presque jamais nulle part de différent.

## La solution : apprendre à partir de vraies parties humaines

Le projet a récupéré des enregistrements de vraies parties jouées par des humains — des joueurs
qui, eux, savent couper des arbres. Les serveurs officiels qui hébergeaient ces enregistrements
n'existaient plus (404, le site a fermé), mais la communauté en avait fait une copie de sauvegarde
sur Zenodo (une archive scientifique publique) : 210 parties enregistrées, avec vidéo et actions.

En ré-entraînant l'encodeur et le world model sur ces 453 496 images issues de vraies parties
(dont 12 056 montrant un moment où un joueur venait de couper du bois), le projet obtient un
objectif *avec du signal réel* — et pourtant, ça ne suffit toujours pas.

## Quatre tentatives, quatre échecs — et une leçon qui se répète

**Le détail crucial** : dans ce jeu, casser un tronc d'arbre demande de **tenir le bouton
« frapper » fixe, visé sur le même tronc, pendant environ vingt instants consécutifs**. Bouger en
même temps change la cible visée à chaque instant — la coupe ne se termine jamais. Dans les
vraies parties humaines, 76% des moments où le joueur vient d'obtenir du bois montrent l'action
« frapper, sans bouger » — pas « avancer en frappant ». N'importe quelle méthode incapable de
*tenir* une action précise dans le temps est condamnée d'avance.

- **Tentatives 1 et 2** — le même planificateur qu'au Chapitre 4, rebranché sur Minecraft :
  échec, récompense zéro. Le world model n'était toujours pas assez bon pour distinguer des futurs
  différents sur des images presque statiques.
- **Tentative 3** — apprendre directement, image par image, quelle touche appuyer (« imitation »
  d'un joueur humain, sans world model ni planification) : échec. L'agent se figeait sur une seule
  action répétée en boucle. Deux raisons : dès qu'il dévie une seule fois du comportement humain,
  il se retrouve dans une situation jamais vue à l'entraînement et dérive ; et l'encodeur du
  Chapitre 1 avait appris à résumer des *scènes*, pas à repérer « où est le tronc pour viser
  dessus ».
- **Tentative 4** — un réseau de neurones pur, pixels vers action, sans passer par les embeddings
  JEPA du tout : échec aussi, pour une raison différente mais liée. Une politique sans aucune
  mémoire du passé récent ne peut pas exprimer « je suis en train de casser ce bloc, je continue »
  — chaque image est traitée isolément.

## Ce qui a finalement marché

La cinquième tentative reprend l'architecture action-conditionnée de Meta (`eb_jepa`) avec cinq
changements en même temps, aucun suffisant seul :

1. Garder une **carte spatiale** d'embeddings plutôt qu'un simple vecteur — pour préserver « où,
   dans l'image, se trouve le tronc », une information écrasée par un vecteur plat.
2. Entraîner l'encodeur et le predictor **ensemble**, conditionnés par l'action, plutôt que de
   figer l'encodeur d'abord — les embeddings se structurent directement autour des *conséquences*
   des actions.
3. Faire prédire au predictor seulement le **changement** entre les deux images plutôt que l'image
   suivante entière — « ne rien faire » devient alors littéralement « prédire zéro changement »,
   une solution de repli automatiquement raisonnable.
4. Garder les garde-fous anti-collapse du Chapitre 2 — et il a fallu les corriger en cours de
   route (voir plus bas).
5. **Répéter chaque action décidée pendant 4 instants de jeu** plutôt qu'un seul — c'est ce qui
   permet enfin de tenir un coup soutenu.

## Un collapse a bien failli tout gâcher, ici aussi

Au premier essai de cette nouvelle architecture, le signal anti-collapse (le `batch_var` du
Chapitre 2) s'est effondré à zéro dès la troisième epoch d'entraînement — un vrai collapse. La
cause : le garde-fou vérifiait la variance *entre les pixels d'une même carte*, qui reste presque
toujours non-nulle, au lieu de vérifier la variance *entre différentes images du lot*, la seule
qui compte vraiment. Le garde-fou surveillait la mauvaise chose — corrigé, `batch_var` est resté
stable autour de 1,2 sur 20 epochs entières.

## Le résultat : l'agent coupe vraiment des arbres

Avec ces cinq ingrédients, l'agent obtenu chope réellement du bois en vrai Minecraft — pas
100% du temps, mais un vrai succès mesuré et honnête : sur 20 épisodes avec la version publiée,
25% des épisodes obtiennent au moins une bûche, avec une récompense moyenne de 0,30 (un épisode a
même coupé deux bûches). C'est un résultat modeste dans l'absolu, mais c'est la toute première
fois que le pipeline fonctionne sur du vrai Minecraft — après quatre échecs propres et bien
compris.

## L'honnêteté qui a suivi : ce chiffre bouge, et pas à cause de la chance qu'on croit

Une fois ce résultat obtenu, le projet a essayé de comprendre *pourquoi* — et de le reproduire.
La première explication qui semblait évidente (« un embedding plus gros casse la couverture du
plan ») s'est révélée **fausse** : en refaisant l'expérience avec un embedding petit mais la même
« recette » d'entraînement plus poussée (plus d'epochs, séquences plus longues), l'agent a échoué
aussi. Ce n'est donc pas la taille du modèle qui compte.

Ce qui compte réellement, c'est **la recette d'entraînement** — mesurée par le fameux ratio du
Chapitre 3 (erreur du predictor / erreur de la solution paresseuse). La recette d'origine
converge vers un ratio d'environ **0,93**, et c'est la seule qui produit un agent qui joue
correctement. Entraîner *plus longtemps* (plus d'epochs, séquences plus longues) fait baisser ce
ratio à environ 0,88 — ce qui semble « mieux » selon la métrique du Chapitre 3 — mais **casse
l'agent**, quelle que soit la taille du modèle. Un world model sur-entraîné apprend à copier la
*pose statique* qui accompagne le succès (rester immobile en frappant) au lieu du *geste* qui
mène au succès (s'approcher puis frapper) — l'agent finit par se figer en frappant dans le vide.

Et il y a une dernière couche d'honnêteté, encore plus inconfortable : **même avec exactement la
même recette et le même ratio (0,93), deux entraînements différents ont donné 50% de succès une
fois, et 25% une autre fois**. L'entraînement n'était pas figé avec une graine aléatoire fixe
(un « seed » — un nombre qui fixe tout le hasard interne, pour qu'on puisse rejouer exactement
la même séquence d'événements) : chaque entraînement tire un léger hasard différent, et cette
différence suffit à changer la « forme » de l'espace latent d'une façon qui n'apparaît pas dans le
ratio, mais qui change beaucoup le succès final. La checkpoint officiellement publiée obtient 25%
— honnête, pas le meilleur chiffre jamais observé, mais celui qui est réellement disponible et
reproductible tel quel.

:::

::: expert

## Objectif de la Phase 4 et invariance architecturale

Ce chapitre porte le pipeline Phase 1-3 (encodeur, world model conditionné par l'action, MPC
random-shooting) de Crafter vers **MineRL**, sans changer la conception architecturale — seul le
domaine d'entrée change (rendu 3D réel Minecraft 64×64 RGB vs pixel-art Crafter). L'objectif
explicite est de tester si l'hypothèse JEPA (features prédictives et à faible dimension plutôt que
reconstruction pixel exhaustive) tient sur un domaine visuellement plus riche et moins stylisé.

## Le pont technique MineRL/Malmo

```
Python ──► Malmo (JVM, Java 8) ──► Minecraft Forge ──► rendu 64×64
```

Contraintes d'installation notables : JDK 8 strict (incompatible JVM 11+), `gradlew.bat` requiert
`shell=True` sous Python 3.12, dépôt MixinGradle JitPack indisponible (remplacé par
`org.spongepowered:mixingradle:0.6-SNAPSHOT`), compilation Forge ~15-30 min (~500 Mo).
L'espace d'action MineRL est un **dict d'actions continues** (`forward`, `attack`, `jump`,
`camera: [pitch, yaw]`, …), discrétisé en 17 classes via une table fixe
(`configs/minerl_actions.yaml`) — analogue à l'espace d'action à 17 actions déjà utilisé sur
Crafter, ce qui permet de réutiliser le predictor conditionné par l'action sans en changer la
signature.

## Le bug MALMOBUSY

Symptôme : `TimeoutError: Mission didn't start after 180 seconds` au second `env.reset()`. Cause
racine : MineRL 0.4.4 communique via socket TCP ; à la fin d'un épisode, Python envoie
immédiatement le `MissionInit` suivant, mais la JVM répond `MALMOBUSY` (pas encore revenue à
DORMANT) puis **ferme le socket côté serveur**. Python retente sur le même socket désormais
orphelin et bloque jusqu'au timeout :

```
Python                     Minecraft (JVM)
  │── <MissionInit> ────────────►│ (RUNNING→DORMANT en cours)
  │◄─────────────── MALMOBUSY ──│
  │── <MissionInit> (retry) ───►│  ← socket déjà fermé côté Java
  │  (bloqué sur recv, 180s)     │
  TimeoutError ✗
```

Tentatives de correction ayant échoué : augmenter `SOCKTIME` (240s→1200s, timeout encore atteint
après ~20 min) ; patcher la reconnexion socket dans `_multiagent.py` (Minecraft ignore la nouvelle
connexion). **Contournement retenu** : un processus Python neuf par épisode
(`scripts/collect_minerl_multi.py --shards 15`, `scripts/play_minerl_multi.py --episodes N`) —
le premier épisode d'un processus frais réussit toujours puisqu'il n'implique aucun `reset()`.
Coût : ~30-60s de démarrage Minecraft par épisode.

## Diagnostic du premier échec (agent aléatoire → demos)

```
scripts/play_minerl_multi.py --episodes 20 → 19/20 complétés, reward moyen 0.000
```

Deux causes partagées : (1) le goal embedding, construit à partir de frames collectées par une
politique aléatoire qui ne coupe jamais d'arbre, ne pointe vers aucune direction utile ; (2) le
world model, évalué via `ratio = val_pred/val_copy = 0,983` sur ces mêmes données aléatoires — un
agent quasi-statique produit des transitions où « rien ne change » est déjà presque optimal, donc
le predictor n'apprend aucune dynamique causale action→conséquence, seulement une quasi-identité.

## Les démonstrations humaines (Zenodo)

Les serveurs S3 officiels de MineRL sont morts (`404`) ; sauvegarde communautaire sur Zenodo
(`zenodo.org/records/12659939`, `MineRLTreechop-v0.zip`, 1,5 Go, 210 démonstrations). Format par
démo : `recording.mp4` (vidéo brute), `rendered.npz` (récompenses + actions discrètes, **sans les
frames**), `metadata.json`. `scripts/prepare_demos.py` extrait les frames du MP4 via
`cv2.VideoCapture`, les redimensionne à 64×64, discrétise les actions, aligne MP4↔NPZ (décalage
possible de 1-2 frames). Résultat :

```
Total frames    : 453 496
Frames reward>0 : 12 056 (2,7%)
Demos chargées  : 210
```

Ré-entraînement (`train_encoder_demos`, `train_wm_demos`) sur ce corpus expert.

## Le mécanisme de récompense — la contrainte qui dicte l'architecture

Casser un tronc dans Treechop demande de **maintenir `attack` fixe, visé sur le même bloc, sur
~20 ticks consécutifs**. Preuve empirique, sur les 12 056 frames à récompense>0 des démos
humaines :

```
a6  (attack seul)      : 76,2%
a0  (noop)              : 8,8%
a1  (forward)           : 5,1%
a7  (forward+attack)    : 4,7%
```

Toute politique incapable de produire une action **soutenue et précise dans le temps** est
structurellement condamnée — ce constat motive directement l'ingrédient `action_repeat=4` de
l'architecture retenue.

## Les quatre approches qui échouent — analyse causale

**Approches 1-2 — MPC + world model 1-step (flat vector).** Ratio plafonné à 0,959 sur données
quasi-statiques : « ne rien changer » est déjà quasi-optimal, donc après 12 pas de rollout les 512
candidats convergent vers des latents quasi-identiques → l'argmax devient un choix arbitraire.
Un predictor markovien à 1 pas ne peut de plus représenter « attaquer le même bloc 20 fois » —
la dépendance temporelle dépasse l'horizon d'un seul pas conditionné.

**Approche 3 — Behavioral Cloning sur encodeur figé + tête de classification.** `val_acc` ≈ 64%
en offline, mais en jeu l'agent se fige sur une seule action (a0 ou a7 à ~100%). Deux causes
imbriquées : *covariate shift* (dès la première déviation, l'agent atteint des états jamais vus
en démo → prédictions aberrantes → dérive non corrigée) ; et l'encodeur JEPA, entraîné frame→frame
sans conditionnement par l'action, encode des *scènes* plutôt que des indices actionnables
(« où viser »). Tentative corrective (repondération de la classe a6, 58% des données) : effet
contre-productif — elle pénalise justement l'action qui produit la récompense.

**Approche 4 — CNN end-to-end pixels→action.** `val_acc` ≈ 49%, toujours figé. Cause distincte
mais apparentée : une politique sans mémoire ne peut exprimer l'engagement temporel
(« je suis en train de casser ce bloc, je continue ») — chaque frame est traitée indépendamment.

## L'architecture qui débloque : eb-JEPA action-conditionné

Cinq différences simultanées par rapport aux approches précédentes, chacune insuffisante seule :

| # | Ingrédient | Pourquoi |
|---|------------|----------|
| 1 | Latents **spatiaux** `[64,8,8]` (vs vecteur plat 128) | préserve « où est le tronc dans l'image » |
| 2 | Encodeur + predictor entraînés **conjointement**, conditionnés par l'action | latent structuré autour des *conséquences* de l'action |
| 3 | Predictor **résiduel** (prédit `s_{t+1}-s_t`) | « ne rien faire » = copie → ratio ≤ 1 garanti par construction |
| 4 | VICReg **corrigé** (`spatial_as_samples=False`) | mesure la variance *entre échantillons du batch*, pas entre pixels d'une carte |
| 5 | `action_repeat=4` | replanifie tous les 4 pas, répète l'action → produit l'attaque soutenue |

### Le piège du collapse, à nouveau

Premier entraînement eb_jepa : `batch_var` 0,0018 → 0,0000 à l'epoch 3 (collapse total). Cause :
le régularisateur était configuré avec `spatial_as_samples=True`, mesurant la variance *entre
pixels d'une même carte spatiale* (toujours non-nulle par construction), au lieu de la variance
*entre entrées du batch* (celle qui s'effondrait réellement) — un régularisateur **actif mais
aveugle au collapse qui comptait**. Correction : `spatial_as_samples=False` + `std_coeff` 1→10,
`cov_coeff` 0,04→1. Après correction : `batch_var` stable ~1,2 sur 20 epochs.

```
Avant correction : batch_var 0,0018 → 0,0000 (epoch 3)   ⚠️ COLLAPSE
Après correction  : batch_var ~1,2 stable sur 20 epochs   ✅
```

## Résultat du gate 4

```bash
scripts/train_eb_jepa.py   →  checkpoints/ebwm.pt  (ratio 0,929, batch_var ~1,2)
scripts/play_minerl_multi.py --script scripts/play_ebwm.py
```

| Approche | Reward moyen | Succès | Statut |
|----------|-------------|--------|--------|
| 1-2. MPC + WM 1-step (ratio ≈0,96) | 0,000 | 0% | ✗ |
| 3. BC encodeur figé + tête | 0,000 | 0% | ✗ |
| 4. BC CNN end-to-end | 0,000 | 0% | ✗ |
| 5. eb-JEPA MPC action-conditionné | 0,30–0,75 | 25–50% | ✅ |

Résultat final publié (20/20 épisodes, checkpoint publiée, ratio 0,927) : **reward moyen 0,30,
taux de succès 25,0% (5/20)**, un épisode ayant coupé 2 bûches. Les actions exécutées sont
**variées et changent avec la scène** (mélange a14/a13/a1/a6), à l'opposé des politiques BC figées
sur une seule action — signe que le planificateur exploite réellement le world model plutôt que
de mémoriser un geste unique.

> **Mise en garde honnête sur le chiffre.** Le taux de succès varie **25-50% entre runs
> d'entraînement** à ratio de prédiction quasi-identique (~0,93). Le meilleur run observé atteint
> 50% (10/20) ; le checkpoint publié obtient 25% (5/20). L'entraînement n'est **pas seedé** —
> chaque run produit une géométrie latente différente, et le succès de planification en aval n'est
> que **faiblement couplé** à la métrique de prédiction reproductible (voir l'ablation ci-dessous).
> La baseline « aléatoire ~0,4 » imprimée par le script est une estimation héritée, jamais
> re-mesurée sur ce harness — traiter le résultat absolu (l'agent coupe des arbres, jusqu'à
> 2 bûches/épisode) comme l'affirmation solide, pas la comparaison à la baseline.

## Ablation : ce qui détermine réellement la performance

Quatre runs d'entraînement sur le même corpus de 453K frames de démos :

| Run | embed_dim | recette | Params | Ratio | Succès |
|-----|-----------|---------|--------|-------|--------|
| Original (perdu) | 64 | T=8, 20 ep | 664K | 0,929 | **50%** |
| WM v2 | **128** | T=12, 25 ep | 2,47M | 0,890 | 5% |
| v1-retrain | 64 | T=12, 25 ep | 664K | 0,882 | ~0% |
| v1-restored | 64 | **T=8, 20 ep** | 664K | 0,927 | **25%** |

**Première hypothèse (fausse) : « le plus grand latent casse la couverture du MPC ».** Quand
WM v2 (embed_dim=128) régresse à 5%, l'explication naturelle est que doubler le latent
`[128,8,8]` rend l'espace trop grand pour les 512 candidats de tir aléatoire. **v1-retrain la
réfute** : revenir uniquement sur l'architecture (embed_dim=64) en gardant la recette v2 (T=12,
25 epochs) échoue toujours (~0%). Latent petit, toujours cassé — la taille n'était pas la cause.

**Ce qui compte réellement : la recette d'entraînement, via le ratio de prédiction.** La seule
configuration produisant un agent fonctionnel est la recette d'origine (séquences T=8, 20 epochs),
qui converge vers un ratio **~0,93**. Les deux variantes sur-entraînées (T=12, 25 epochs → ratio
~0,88), à *n'importe quel* embed_dim, produisent un agent cassé. Entraîner le world model *plus
fort* (plus d'epochs, séquences plus longues → ratio plus bas) fait apprendre au planificateur la
**pose statique** des frames de succès (a6 = attack-seul, 76% des frames reward>0) au lieu du
**geste** qui produit la récompense — l'agent reste immobile en frappant dans le vide. Il existe
un **point idéal** autour du ratio 0,93, pas une règle « plus bas = mieux ».

**Et même à ce point idéal, la variance run-à-run reste élevée.** Le tirage original atteint 50% ;
le tirage restauré (même recette, ratio quasi-identique 0,927) atteint 25%. L'entraînement n'est
pas seedé, donc chaque run produit une géométrie latente distincte, et le succès de planification
en aval est seulement **faiblement couplé** à la métrique de prédiction reproductible. Le 50%
était un tirage favorable, pas une garantie de la recette.

**Constat honnête** : un world model qui prédit *mieux* à l'entraînement (ratio plus bas) peut
produire un *pire* agent, et deux runs à recette et ratio identiques peuvent différer d'un facteur
2 en succès. La qualité de prédiction est nécessaire mais loin d'être suffisante — la *géométrie*
latente dont dépend la planification n'est pas capturée par la seule perte de prédiction.

## Leçons de la Phase 4

1. **La récompense dicte l'architecture.** Treechop = attaque soutenue et précise → il fallait
   une politique capable d'engagement temporel (`action_repeat` + world model).
2. **L'architecture du world model compte autant que les données.** Encodeur figé frame→frame
   (ratio 0,96) vs encodeur+predictor conjoints conditionnés par l'action (ratio 0,929 mais
   latents *exploitables* pour la planification) : la différence entre 0% et 50%.
3. **Le collapse est sournois.** Un régularisateur peut sembler actif (`reg_loss` bas) tout en
   étant aveugle au collapse qui compte réellement. Toujours surveiller `batch_var`
   (variance inter-échantillons), pas seulement la perte du régularisateur.
4. **Un diagnostic honnête vaut mieux qu'une itération à l'aveugle.** Trois échecs analysés en
   profondeur ont mené à la bonne architecture ; une itération aveugle n'y serait pas arrivée.
5. **Meilleure prédiction ≠ meilleur agent — et la recette, pas la taille, est le levier.**
   Sur-entraîner le world model (plus d'epochs/données → ratio 0,88) casse l'agent aux deux
   embed_dim testés ; seule la recette d'origine (ratio ~0,93) fonctionne. Il y a un point idéal
   de ratio, pas une règle « plus bas = mieux ».
6. **Le succès de planification est faiblement couplé à la métrique de prédiction, avec une forte
   variance run-à-run.** Même recette, même ratio 0,927 → 50% sur un tirage, 25% sur un autre.
   L'entraînement n'est pas seedé ; la géométrie latente dont dépend la planification n'est pas
   fixée par la perte de prédiction. Rapporter des plages, pas le chiffre le plus favorable — et
   seeder l'entraînement avant de revendiquer la reproductibilité.

## Références (vérifiées, tirées de docs/references/index.md)

- Meta FAIR, eb_jepa (github.com/facebookresearch/eb_jepa) — le backbone action-conditionné
  vendored dans `mine_jepa/eb_jepa/`, socle de l'approche 5.
- Bardes, Ponce, LeCun, VICReg, arXiv:2105.04906 (ICLR 2022) — le régularisateur dont la
  mauvaise configuration (`spatial_as_samples=True`) a causé le collapse de ce chapitre.
- Maes, Le Lidec, Scieur, LeCun, Balestriero, LeWorldModel, arXiv:2603.19312 (2026) — origine de
  la convention `ratio = val_pred/val_copy` utilisée pour caractériser le point idéal ~0,93.

:::

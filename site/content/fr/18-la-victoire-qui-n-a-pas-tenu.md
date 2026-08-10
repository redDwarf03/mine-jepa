---
title: "La première victoire de la campagne n'a pas survécu à un échantillon plus grand — et c'est elle-même qui s'en est aperçue"
slug: "18-la-victoire-qui-n-a-pas-tenu"
lang: "fr"
order: 18
prerequisites: ["01-c-est-quoi-jepa", "02-le-piege-du-collapse", "03-le-modele-du-monde", "04-planifier-en-imagination", "05-le-vrai-minecraft", "06-apprendre-a-fabriquer", "07-la-curiosite-en-panne", "08-le-mur-est-comportemental", "09-les-prochaines-pistes", "10-le-negatif-le-plus-net", "11-la-boussole-a-l-envers", "12-la-memoire-des-lieux-visites", "13-le-sauvetage-aveugle", "14-un-geant-du-web-a-l-epreuve", "15-cinquieme-confirmation-fausse-alerte", "16-predire-l-avenir-pas-l-image", "17-le-raccourci-est-dans-l-oeil"]
source_docs: ["docs/10_coldstart_engineering.md#Cold-start attempt #18", "CLAUDE.md#Phase 5+"]
---

::: beginner

## Là où on en était

Le Chapitre 17 s'est terminé sur un chiffre lourd : **six** façons complètement différentes de
mesurer « y a-t-il un arbre proche ? » — deux petits modules entraînés, un géant du web jamais
touché par ce projet, un réentraînement direct, un calcul de couleur fait main, et même une
simple formule statistique sans aucun apprentissage — étaient toutes tombées dans le même
piège : elles se laissaient distraire par la luminosité de la scène plutôt que de vraiment
juger la présence d'un arbre. La décision de la suite (réentraîner le cœur du modèle, ou
accepter cette limite et continuer avec ce qui marche déjà) restait posée à l'utilisateur,
non tranchée.

Avant de trancher, une relecture des dernières publications scientifiques sur des sujets
proches a fait remonter deux idées neuves, bon marché à tester avant tout engagement lourd.
Ce chapitre raconte ce qui s'est passé quand elles l'ont été — et son événement le plus
important n'est pas un résultat, mais une **correction que l'équipe s'est infligée à elle-même,
dans la même session de travail**, avant que quiconque n'ait le temps de crier victoire trop
vite.

## Idée n°1 : et si on regardait la distance, pas la couleur ?

Toutes les tentatives précédentes essayaient de deviner « il y a un arbre proche » à partir de
la couleur et de la texture de l'image — exactement le genre d'indice que la luminosité peut
polluer. Une publication scientifique récente proposait autre chose : ajouter à un modèle JEPA
une notion de **profondeur** — à quelle distance se trouve chaque partie de l'image, un peu
comme un radar qui mesure les distances plutôt qu'un œil qui regarde les couleurs — et cette
publication montrait que ça aidait un modèle à mieux généraliser sur des scènes inconnues.

Le test est construit exactement sur le modèle du Chapitre 14 : prendre un modèle de vision
tout fait, jamais entraîné sur Minecraft, capable d'estimer à quelle distance se trouve chaque
zone d'une image à partir d'une seule photo. Aucun réglage n'est ajusté pour Minecraft — c'est
un outil extérieur, utilisé tel quel, exactement pour éviter qu'un apprentissage propre au
projet ne réinvente le même raccourci de luminosité.

Sur le tout petit échantillon d'images déjà utilisé par chaque chapitre précédent (4 images
avec un arbre proche, 6 sans arbre), ce test a réussi les **deux** conditions que six tentatives
précédentes n'avaient jamais réussies ensemble : il distinguait bien les scènes avec arbre des
scènes sans arbre, ET il ne se laissait presque pas distraire par la luminosité — de très loin
le meilleur résultat sur ce deuxième point depuis le début de la campagne. Sur le moment, ça
ressemblait au tout premier « oui » de cette longue enquête.

## Mais l'équipe ne s'est pas arrêtée là — et a bien fait

Un chiffre a immédiatement mis la puce à l'oreille : sur la première condition (bien distinguer
arbre/pas d'arbre), le résultat ne dépassait le seuil de réussite que d'un tout petit cheveu —
le genre de marge qui peut disparaître si on regarde plus d'exemples. Plutôt que de publier ce
résultat comme une victoire, la même équipe, dans la même session de travail, a immédiatement
élargi l'échantillon d'images : au lieu de se contenter des 10 images habituelles, elle a
examiné et classé à la main **toutes** les images restantes disponibles pour ce test — pas une
sélection triée sur le volet, la population entière — pour arriver à 27 images au total (en
écartant honnêtement 4 images jugées trop ambiguës pour être classées).

**Sur cet échantillon plus grand, le résultat s'est effondré.** La capacité à distinguer
arbre/pas-d'arbre est repassée sous le seuil de réussite. Le sens restait correct — les images
avec arbre continuaient à scorer un peu plus haut en moyenne — mais l'écart était devenu trop
faible pour être une vraie découverte : c'était le genre d'écart qu'un petit échantillon produit
parfois par pur hasard, pas une propriété fiable du signal.

C'est le cœur de ce chapitre : **la toute première victoire apparente de cette campagne longue
de dix-huit tentatives n'a pas résisté à un examen plus large — et c'est la même équipe, le même
jour, qui l'a détecté et corrigé**, plutôt que de laisser le premier résultat flatteur devenir
l'histoire officielle. C'est exactement la même honnêteté qui, depuis le tout premier chapitre
de ce site, a fait dire « 0/20 », « pas significatif » ou « ça ne marche pas » chaque fois que
c'était la vérité — appliquée ici, pour la première fois, à un résultat du projet lui-même
plutôt qu'à celui d'un concurrent extérieur.

Une chose importante à ne pas confondre, cependant : **deux affirmations différentes**, et une
seule d'entre elles a survécu. « Ce signal ne se laisse pas distraire par la luminosité » —
vrai, confirmé, et c'est même le meilleur résultat de toute la campagne sur ce point précis.
« Ce signal détecte vraiment un arbre proche » — faux, en tout cas pas encore prouvé, dès qu'on
regarde assez d'exemples. Ne pas être trompé par la luminosité ne suffit pas à être un bon
détecteur d'arbre.

## Idée n°2 : et si le vrai problème n'était pas visuel du tout ?

Une deuxième publication scientifique, sur un sujet différent, a inspiré une question qui n'a
rien à voir avec les couleurs ou la lumière : est-ce que l'agent a appris à **bouger** de façon
suffisamment différente dans les deux jeux d'entraînement pour que ça pose problème tout seul ?

Le test compte, sans rien entraîner ni faire tourner de GPU, quelles actions apparaissent dans
les parties d'experts utilisées pour chacune des deux tâches. Résultat frappant : dans les
parties d'experts de la tâche « couper un arbre » (Treechop), l'action la plus fréquente et de
loin est **frapper** (58,5 % du temps) — logique, l'expert passe son temps à bûcheronner. Dans
les parties d'experts de la tâche de fabrication (Obtain), les actions sont beaucoup plus
partagées entre « ne rien faire », « avancer » et « frapper », avec beaucoup moins de frappe. Un
calcul statistique qui mesure à quel point deux répartitions d'actions sont différentes donne un
écart **104 fois plus grand** que ce qu'on obtiendrait par pur hasard en comparant une moitié
d'une partie d'experts à l'autre moitié de la même partie.

Ce n'est prouvé la cause de rien pour l'instant — c'est un fait nouveau et honnêtement présenté
comme une piste, pas une certitude. Mais c'est la toute première fois, en dix-huit tentatives,
qu'un test fait remonter un écart réel et important entre les deux jeux d'entraînement qui n'a
**rien à voir avec la couleur ou la lumière**. Ça ouvre une porte que personne n'avait encore
ouverte : peut-être que le modèle ne s'est simplement jamais assez entraîné à bouger comme le
fait un agent en exploration, parce que ses parties d'experts lui montraient surtout comment
bûcheronner.

## Un petit test en direct : rien de cassé de façon spectaculaire, mais un signal à surveiller

Une petite expérience en direct (6 parties) a essayé de faire naviguer l'agent en utilisant
cette estimation de distance plutôt que la boussole habituelle, dès que l'agent semble perdu.
Le mécanisme ne s'est déclenché que 3 fois sur les 6 parties — trop peu pour vraiment juger s'il
se comporte bien — et n'a montré aucun blocage grave sur une seule direction, contrairement à
plusieurs tentatives ratées passées. Aucune coupe de bois, sans surprise, ce n'était pas la
question posée.

En revanche, un signal préoccupant est apparu et a été signalé honnêtement plutôt que caché :
dans 2 parties sur 6, l'agent est mort **pendant que** le réflexe anti-noyade (réparé et confirmé
au Chapitre 13) essayait activement de le sortir de l'eau. Ce réflexe avait pourtant survécu à
6 parties sur 6 sans aucune mort lors de sa dernière vérification. Rien ne prouve encore que
c'est cette nouvelle méthode de navigation par distance qui cause le problème — ça pourrait être
un hasard sur un aussi petit nombre de parties — mais l'explication la plus plausible est
intéressante : les modèles qui estiment la distance à partir d'une seule image se trompent
souvent sur l'eau, une surface qui réfléchit la lumière de façon trompeuse. Ce point mérite une
vérification dédiée avant de faire confiance à la solution anti-noyade avec ce nouveau
mécanisme de navigation.

## Ce que ce chapitre change, et ce qu'il ne change pas

- Le diagnostic du Chapitre 17 (le défaut de luminosité est profondément ancré dans la façon
  dont le modèle de base compresse une image, pas dans une méthode d'apprentissage précise)
  **tient toujours** — le test « profondeur » n'a pas réparé le problème central, seulement
  montré qu'un signal peut échapper à ce piège précis sans pour autant devenir un bon détecteur
  d'arbre.
- **Une vraie nouveauté apparaît** : un écart de comportement, pas de perception, entre les
  deux jeux d'entraînement — jamais mesuré avant, et qui n'a rien à voir avec la couleur ou la
  lumière.
- **Le moment le plus important de ce chapitre reste la correction elle-même** : un résultat qui
  semblait être la première vraie victoire de dix-huit tentatives s'est révélé être un mirage dû
  à un trop petit échantillon — et l'équipe l'a découvert et corrigé le jour même, sans laisser
  la version flatteuse s'installer. C'est la preuve concrète que la règle « vérifier avant de
  croire », appliquée depuis le premier chapitre de ce site, fonctionne aussi quand elle s'applique
  à son propre travail.
- La décision de fond (réentraîner le modèle de base, ou consolider autour de ce qui marche déjà)
  reste, comme au Chapitre 17, une question ouverte pour l'utilisateur — pas tranchée par ce
  chapitre.

:::

::: expert

## Contexte

Le Chapitre 17 (attempt #17) a clos deux attaques directes contre la notation goal-centroid de
`ebwm.pt` (repli OOD par distance de Mahalanobis, vérification de l'hypothèse « manque de
données sombres ») sur un statu quo : 6 confirmations indépendantes du même confound
luminosité/composition de scène, décision retrain-vs-consolidate laissée à l'utilisateur. Ce
chapitre couvre l'attempt #18 de `docs/10_coldstart_engineering.md`/`CLAUDE.md#Phase 5+` : une
passe de recherche bibliographique dédiée (2026-07-27, couvrant 2026-07-13 à 2026-07-27) a fait
remonter 5 nouveaux papers JEPA (ajoutés à `docs/references/index.md`), dont deux ont rouvert des
sous-questions bon marché avant tout engagement de réentraînement. L'événement notable de cette
tentative n'est pas un résultat mais une **correction émise dans la même session**.

## Diagnostic 1 — généralisation de la pseudo-profondeur : un premier GO apparent qui n'a pas
survécu à un échantillon plus large

Motivé par Khan, « Depth-Regularized JEPA World Models Learn More Transferable Representations
from Real Outdoor Robot Data » ([arXiv:2607.16314](https://arxiv.org/abs/2607.16314), 2026) : un
modèle du monde JEPA de 18M paramètres + SIGReg sur vidéo robotique réelle, avec un terme
auxiliaire de supervision par profondeur, gagne -33% d'erreur sur une sonde d'odométrie visuelle
et une meilleure séparation du score de surprise en distribution ET hors distribution (benchmark
TartanGround) sous décalage de domaine réel, sans coût d'inférence supplémentaire — la première
instance publiée de la conclusion de l'attempt #15 lui-même : le confound de luminosité a besoin
« d'une modalité différente », pas d'une nouvelle feature photométrique.

`scripts/diagnose_depth_gate.py` fait tourner MiDaS_small (`torch.hub`, `intel-isl/MiDaS`,
tout fait, aucun entraînement Minecraft-spécifique — même logique de « modèle extérieur » que le
test CLIP de l'attempt #14 Phase 1) sur le jeu de 251 frames standard de la campagne, en notant
chaque frame par la moyenne de ses 10% de pixels les plus proches selon MiDaS (proxy d'objet le
plus proche).

**Première passe, le petit échantillon habituel de la campagne (tree_close n=4, no_tree n=6) :**

| Gate | Seuil | Résultat |
|---|---|---|
| A — séparation | ≥ 1,3x | **PASS — 1,304x** |
| B — indépendance à la luminosité | \|r\| < 0,3 | **PASS — r = 0,0451** (le meilleur de toute la campagne, de loin ; fourchette précédente 0,117-0,947) |

Lu au premier degré, c'était le premier mécanisme sur 7 tests indépendants (#7, #11, #14
Phase1/Phase2, #15, #17 Prong A, et celui-ci) à réussir les deux gates établis — signalé sur le
moment comme « une marge fine sur un petit échantillon », pas déclaré comme une victoire, parce
que cette marge semblait fragile à l'inspection (Gate A dépassait le seuil de 1,3x de seulement
0,004).

**Suivi le même jour : l'échantillon annoté à la main a été étendu de 10 à 27 frames** (21
nouveaux candidats inspectés visuellement — la population *entière* restante éligible pour ce
gate dans `data/minerl_coverage/episodes.npz` et `assets/spawn_thumbs/`, pas une sous-sélection
triée sur le volet ; 4 écartées comme authentiquement ambiguës, un taux d'exclusion de 19%,
rapporté plutôt que caché).

| Gate | n=10 (original) | n=27 (étendu) |
|---|---|---|
| A — séparation | 1,304x (PASS) | **1,086x (FAIL)** |
| B — indépendance à la luminosité | r=0,0451 (PASS) | r=0,0451 (PASS, inchangé) |

> **LEÇON : le premier passage à 1,304x était un artefact de petit échantillon, pas une vraie
> séparation robuste.** Les frames avec arbre proche continuent à scorer plus haut en moyenne que
> les frames sans arbre (644,3 contre 593,5) — la *direction* reste correcte — mais la marge s'est
> effondrée bien en dessous du seuil de 1,3x une fois l'échantillon presque triplé. Le résultat
> d'indépendance à la luminosité du Gate B est réel et non affecté : la profondeur n'est
> authentiquement pas un raccourci de luminosité, le meilleur résultat de tout mécanisme testé
> par cette campagne. Mais l'indépendance à un confound n'est pas la même chose qu'être un
> détecteur d'arbre qui fonctionne.

**VERDICT CORRIGÉ : MIXED, pas GO.** Le diagnostic établi à l'attempt #17 — aucun mécanisme n'a
encore séparé proprement les scènes proches-d'arbre des scènes ouvertes tout en restant
indépendant de la luminosité, à une taille d'échantillon fiable — **tient toujours**. Ce qui a
réellement changé : l'indépendance à la luminosité de la profondeur est confirmée et
reproductible (un signal non photométrique qui n'est pas lui-même un raccourci de luminosité,
même s'il n'est pas encore, seul, un détecteur qui fonctionne). Corrigé dans la session même où
il a été trouvé, pas laissé debout comme un faux premier GO — la discipline d'honnêteté de la
campagne appliquée à elle-même, pas seulement à chaque nouveau mécanisme testé.

## Diagnostic 2 — recouvrement de couverture d'actions Treechop/Obtain : un facteur réellement
nouveau, non photométrique, qui tient toujours

Motivé par Zhang, Guan, Zhang, Zhang, Li, « On the Identifiability of Controlled World Models »
([arXiv:2607.22430](https://arxiv.org/abs/2607.22430), 2026) : un JEPA action-conditionné ne
retrouve un état/dynamique fiable que si la distribution d'actions d'entraînement a une
couverture adéquate. `scripts/diagnose_action_coverage.py` mesure ceci directement — pas de
GPU, pures statistiques sur tableaux d'actions, seedé, auto-calibré contre un null Treechop-vs-
Treechop en split-half plutôt qu'un seuil inventé.

- **Fraction hors-vocabulaire** : seulement **2,33%** des actions Obtain poolées utilisent un
  indice hors du vocabulaire de 17 actions entraîné de `ebwm.pt` — bien plus bas que l'estimation
  naïve de départ « 5/22≈22,7% » (les démos d'experts orientées fabrication invoquent rarement le
  craft par rapport au mouvement ; le jeu de couverture en politique aléatoire seul est à 22,6%
  hors-vocabulaire).
- **Divergence de Jensen-Shannon sur les indices partagés** : Treechop vs. Obtain poolé =
  **0,1453**, contre un null Treechop-vs-Treechop-split-half de **0,0014** — un ratio de **104x**,
  non explicable par le bruit d'échantillonnage. Les démos Treechop sont 58,5% attack / 14,7%
  forward / 12,0% noop (« marcher vers un arbre, tenir l'attaque ») ; Obtain est comparativement
  plus riche en noop/forward et pauvre en attack (33%/31%/25%).
- **Résultat bonus, plus spécifique que la question posée** : les données d'entraînement propres
  de Treechop n'exercent jamais que 8 des 17 indices d'action entraînés de `ebwm.pt` — strafe,
  jump, et les deux directions d'inclinaison caméra ne sont jamais échantillonnés à
  l'entraînement, un écart de couverture interne à Treechop, indépendant du domaine Obtain.

> **LEÇON, tenue à la discipline « hypothèse vs. confirmée » de la campagne** : ceci établit un
> écart distributionnel réel, large, non photométrique — le premier diagnostic sur 18 tentatives
> à faire remonter un facteur candidat en dehors de la famille luminosité/composition de scène —
> mais ne prouve PAS à lui seul que ce mécanisme cause l'inversion de score de l'attempt #10.
> L'affirmation du papier concerne l'identifiabilité état-action-état-suivant ; ce diagnostic n'a
> mesuré que l'histogramme marginal d'usage des actions. Un facteur contributif plausible, pas
> une cause confirmée.

Reformule « réentraîner l'objectif central » d'une idée vague et coûteuse en deux candidats
concrets et bornés : élargir la couverture d'actions propre de Treechop, et/ou repondérer
l'entraînement vers les actions qu'Obtain exerce réellement. Non affecté par la correction du
Diagnostic 1.

## Test de sanité en direct — `scan.macro: "depth"` (N=6) : pas de coupe, mécanisme à peine
exercé, un signal de régression signalé sans être enterré

Dispatché contre le résultat ORIGINAL (depuis corrigé) du Diagnostic 1, avant que l'échantillon
plus large ne revienne. Recadré correctement une fois la correction arrivée : lu comme « ce cap
piloté par la profondeur se comporte-t-il sainement », pas comme validant une réparation.
`mine_jepa/ebwm/depth.py` (nouveau module — chargement MiDaS, notation de profondeur par colonne,
calcul de delta de cap) alimente une nouvelle variante de macro de scan
(`configs/play_craft_commit4_depth.yaml`, construite sur la base déjà validée commit_length=4 +
évitement de danger). Par construction, ne touche jamais à la notation en espace latent de
`CraftPlannerV4`/`SwitchingCraftPlanner` — MiDaS a besoin de pixels réels, les rollouts candidats
du planificateur sont des latents imaginés sans pixels à décoder, donc la profondeur ne peut
informer qu'un cap de navigation sur la frame réelle courante, pas un score de rollout.

- **0/6 logs, 0/6 planches, récompense moyenne 0,000** (sous la ligne de base ~0,4 en politique
  aléatoire de MineRL) — attendu, pas la question posée par ce batch.
- **La macro de scan ne s'est déclenchée que 3 fois sur les 6 épisodes** — `goal_score_std`
  descendait rarement assez bas pour l'invoquer. La question de sanité n'est répondue que
  faiblement par ce batch, indépendamment de la réserve de petit N qui s'applique déjà partout
  dans cette campagne.
- Sur les 3 déclenchements : aucun blocage sévère (contrairement au CEM de l'attempt #6 ou au
  priming de pool d'actions de l'attempt #8, tous deux >80% de concentration sur une seule
  action) ; un a convergé en 2 pas ; un a tenu un cap constant sur la colonne la plus à droite
  sur 4 des 6 pas avec un détour ; **un a fait un revirement complet de la colonne la plus à
  droite (delta +26,2°) vers la plus à gauche (delta -26,2°) en un seul pas de 16 ticks** — pas
  le bug classique de ping-pong-à-chaque-replan de la campagne (premier round de fuite dirigée
  de l'attempt #13), mais un revirement réel, inexpliqué, sur un échantillon trop petit (2
  points) pour être caractérisé davantage.
- **Signal de régression, signalé plutôt qu'enterré** : 2/6 épisodes se sont terminés par
  `died_during_escape=True` (mort pendant que le réflexe anti-noyade tentait activement de
  s'échapper de l'eau) — exactement le mode d'échec que le dernier round de l'attempt #13
  (élargissement de `align_deg` + ancre sèche débouncée) croyait RÉPARÉ à 6/6 épisodes survécus,
  0 mort, même N=6. Ce batch réutilise cette configuration de danger identique, en ajoutant
  seulement la nouvelle macro de scan par profondeur en parallèle. Pas établi comme causal à ce
  N (pourrait être du bruit de batch à batch qui recoïncide par hasard), mais plausible : les
  modèles de profondeur monoculaire sont connus pour se comporter de façon imprévisible sur des
  surfaces réfléchissantes/transparentes comme l'eau, donc un cap piloté par la profondeur
  pourrait plausiblement diriger vers l'eau ou s'y attarder d'une façon que les macros
  `"turn"`/`"frontier"` précédentes ne faisaient pas. **Avant de faire confiance à la réparation
  anti-danger de l'attempt #13 comme robuste à travers les choix de macro de scan, ceci mérite
  une vérification dédiée — pas affirmé comme régression confirmée, mais pas non plus écarté.**

GIF : `assets/agent_play_craft_commit4_depth.gif`. Log complet :
`logs/coldstart_attempt18_depth_sanity_n6.log`.

## Diagnostic d'ensemble après l'attempt #18

La conclusion « le confound encodeur/notation est structurel et non réparable sans réentraîner »
de l'attempt #17 **tient toujours sur la question de la séparation** — aucun mécanisme n'a encore
séparé proprement les scènes proches-d'arbre des scènes ouvertes tout en restant indépendant de
la luminosité, à une taille d'échantillon fiable. Ce qui a réellement changé : l'indépendance à
la luminosité de la profondeur (Gate B, r=0,045, inchangé sur les deux échantillons) est réelle
et reproductible — un signal non photométrique qui n'est pas lui-même un raccourci de
luminosité, même s'il n'est pas encore, seul, un détecteur d'arbre qui fonctionne — et l'écart de
couverture d'actions du Diagnostic 2 est un facteur séparé, toujours debout, authentiquement
nouveau et non photométrique. Aucun des deux n'est une réparation en direct prouvée. Le
Diagnostic 2 reformule « réentraîner l'objectif central » en deux candidats concrets et bornés
(repondération de la couverture d'actions ; SIGReg à la place de VICReg, voir
[arXiv:2607.13612](https://arxiv.org/abs/2607.13612)) plutôt qu'une idée vague et coûteuse. Le
signal de régression du test de sanité en direct est une question ouverte séparée sur
l'interaction entre mécanismes (choix de macro de scan vs. évitement de danger), sans rapport
avec le score central. **La décision sur la suite (réentraîner l'objectif central de `ebwm.pt`
vs. consolider autour des mécanismes de couverture/exécution qui fonctionnent déjà) appartient
toujours à l'utilisateur — cette tentative enregistre des résultats, pas un engagement vers une
prochaine étape.**

## Références

- Khan, « Depth-Regularized JEPA World Models Learn More Transferable Representations from Real
  Outdoor Robot Data », [arXiv:2607.16314](https://arxiv.org/abs/2607.16314) (2026) — fondement
  du Diagnostic 1 (MiDaS_small, séparation par profondeur, indépendance à la luminosité).
- Zhang, Guan, Zhang, Zhang, Li, « On the Identifiability of Controlled World Models »,
  [arXiv:2607.22430](https://arxiv.org/abs/2607.22430) (2026) — fondement du Diagnostic 2
  (recouvrement de couverture d'actions Treechop/Obtain).
- Arnez, Gomez-Villa, « The SIGReg Objective as Variational Free Energy: A Theoretical
  Active-Inference Account of JEPA World Models », [arXiv:2607.13612](https://arxiv.org/abs/2607.13612)
  (2026) — mentionnée dans le diagnostic d'ensemble comme second candidat concret si le
  réentraînement de l'objectif central est un jour engagé ; non testée dans ce chapitre.

Les trois références sont vérifiées dans `docs/references/index.md`.

:::

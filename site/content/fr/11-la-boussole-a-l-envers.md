---
title: "La campagne fait une pause : la boussole ne s'est pas éteinte, elle pointe à l'envers"
slug: "11-la-boussole-a-l-envers"
lang: "fr"
order: 11
prerequisites: ["01-c-est-quoi-jepa", "02-le-piege-du-collapse", "03-le-modele-du-monde", "04-planifier-en-imagination", "05-le-vrai-minecraft", "06-apprendre-a-fabriquer", "07-la-curiosite-en-panne", "08-le-mur-est-comportemental", "09-les-prochaines-pistes", "10-le-negatif-le-plus-net"]
source_docs: ["docs/10_coldstart_engineering.md", "CLAUDE.md#Phase 5+"]
---

::: beginner

## Là où on en était

Le Chapitre 10 s'est terminé sur un nouveau suspect, pas encore confirmé : et si le problème
n'était pas la façon dont l'agent propose des gestes (testée et retestée pendant tout le
Chapitre 8), mais la façon dont le monde imaginé lui-même **juge** ces gestes une fois placé
dans une situation qu'il connaît mal ? Ce chapitre raconte le test qui a tranché cette
question — et referme, pour l'instant, toute une campagne d'enquête menée sur plusieurs
chapitres. Le résultat est plus précis, et un peu plus inquiétant, que ce qui était attendu.

## Le test : regarder la boussole elle-même, sans faire jouer l'agent

Toute cette enquête, depuis le Chapitre 6, s'appuie sur une seule idée : le planificateur
compare chaque histoire qu'il imagine à un point de repère — le **centroïde** (le Chapitre 4
explique cette idée : la moyenne de plein d'images qui représentent le but, par exemple
« un arbre coupé »). Plus l'histoire imaginée ressemble à ce point de repère, meilleure elle
est jugée. Cette comparaison, c'est la boussole du projet.

Jusqu'ici, personne n'avait jamais vérifié directement, sans faire jouer l'agent, si cette
boussole donnait de bonnes indications une fois sortie de son terrain d'entraînement. Ce
chapitre fait exactement ça : prendre des images fixes, certaines venant des parties
d'expert sur lesquelles le modèle a appris (Chapitre 5), d'autres venant de vrais points de
départ aléatoires du jeu de fabrication (Chapitre 6) — et demander à la boussole de noter
chacune, sans qu'aucun personnage ne bouge. Rien n'est entraîné dans ce test, rien n'est
modifié dans le modèle : c'est une prise de mesure, pas une réparation.

## Premier résultat, trompeur si on s'arrête là

En regardant seulement les moyennes globales, rien ne saute aux yeux : les scores sur les
points de départ aléatoires ne sont pas plus « plats » que sur les parties d'experts — si on
compare juste des moyennes brutes, le point de départ aléatoire aurait même l'air, à première
vue, un peu *plus* discriminant. Ça aurait pu clore l'enquête sur un verdict décevant :
« la boussole va bien, ce n'est pas elle ».

## Le vrai résultat : ce n'est pas éteint, c'est inversé

Mais en comparant, image par image, des scènes où un arbre est clairement visible tout près
face à des scènes où il n'y en a aucun, un schéma net apparaît — et il est très différent de
ce que tout le monde supposait depuis le Chapitre 8.

Sur les parties d'experts (le terrain d'entraînement de la boussole) : une image où la
canopée d'un arbre remplit tout l'écran obtient un score nettement plus haut (environ 6 fois
plus haut) qu'une image de prairie ouverte sans arbre. C'est exactement ce qui était attendu
— la boussole fonctionne là où elle a appris.

Sur de vrais points de départ du jeu de fabrication : une clairière avec des arbres tout
proches, ou une jungle dense juste devant l'agent, obtient un score **plus bas** qu'une
prairie ouverte sans le moindre arbre, ou même qu'une plage vide. Même chose sur d'autres
images prises à de vrais redémarrages du jeu : un tronc d'arbre qui remplit tout le cadre
obtient le score le plus bas de tout son groupe de comparaison, pendant qu'une prairie vide
obtient l'un des plus hauts.

Ce n'est donc pas que la boussole s'éteint et n'indique plus rien (ce qui était l'hypothèse
depuis le Chapitre 6) — **elle indique quelque chose de très clair, mais dans le mauvais
sens.** Rapprocher l'agent d'un arbre, dans cette situation précise, fait *baisser* son score
au lieu de le faire monter.

## Pourquoi c'est plus grave qu'un signal plat

Un signal plat (« je ne sais pas », comme la curiosité en panne du Chapitre 7) est
honnête : il ne trompe personne, il dit juste « aucune idée ». Un signal qui pointe dans le
mauvais sens est pire : il donne au planificateur une fausse confiance, et le pousse
activement à s'éloigner de ce qu'il cherche, sans jamais laisser deviner que quelque chose
ne va pas. C'est le même genre de piège que le Chapitre 10 avait déjà repéré pour une petite
règle de distance entraînée séparément (confondue par la luminosité de la scène) — sauf que
cette fois, c'est le mécanisme de base de tout le projet, celui utilisé depuis le tout début
de l'enquête, qui est en cause.

## Ce que ça referme, et ce que ça n'referme pas

Ce résultat répond enfin à la question laissée ouverte à la fin du Chapitre 10 : le problème
vient-il de la génération des gestes candidats, ou du jugement porté sur eux par le monde
imaginé ? La réponse, maintenant confirmée par une mesure directe et pas seulement déduite par
élimination : **c'est le jugement.** Le mur n'est pas « l'agent ne sait pas quoi faire », c'est
« la boussole indique le mauvais chemin dès qu'elle sort de son terrain d'entraînement ».

Après sept tentatives d'affiner ou de remplacer la façon de proposer des gestes (Chapitre 8),
puis ce test direct sur le jugement lui-même, la campagne d'enquête sur ce problème précis
**fait une pause ici** — pas un abandon, une pause. Deux constats solides en ressortent :

1. **La génération de gestes n'est pas le vrai goulot d'étranglement.** Trois méthodes très
   différentes pour proposer de meilleurs gestes candidats ont toutes échoué à faire bouger le
   résultat, y compris sur des points de départ confirmés jouables où un arbre était bien
   visible (Chapitre 9-10).
2. **La boussole du monde imaginé pointe activement à l'envers** une fois sortie du terrain
   sur lequel elle a été entraînée.

## Le menu pour la suite (rien n'est encore lancé)

Quatre pistes existent maintenant pour reprendre ce travail, classées de la moins chère et
la plus ciblée à la plus coûteuse et incertaine — aucune n'a encore été lancée, c'est un
menu, pas un plan d'action :

1. **Réparer la boussole précisément là où elle se trompe** (la moins chère). Ce test a
   pointé exactement quoi est cassé (le sens, pas l'intensité du signal) et sur quelles
   images (celles du jeu de fabrication, pas celles des parties d'experts). On peut donc
   collecter de vrais exemples « proche » et « loin » directement sur ce jeu précis, et
   entraîner une petite correction dessus — sans nécessairement toucher aux poids
   principaux du modèle.
2. **Une mémoire des endroits déjà visités.** Au lieu de comparer chaque image au même
   point de repère fixe, l'agent pourrait se souvenir des zones qu'il a déjà explorées
   pendant l'épisode et viser les zones inconnues en priorité — mais seulement si ce choix
   se fait en comptant les endroits visités, pas en réutilisant la même boussole cassée pour
   juger « à quel point je suis proche d'une zone inconnue » (sinon le même problème
   réapparaît sous un autre nom).
3. **Un second cerveau, plus lent, pour la recherche.** Un modèle séparé qui planifierait
   sur un temps plus long (« trouve une forêt ») avant de laisser la main au modèle rapide
   déjà utilisé pour couper l'arbre une fois proche. L'idée la plus ambitieuse des quatre,
   mais aussi la plus coûteuse : elle demanderait d'entraîner un nouveau modèle, et il
   faudrait veiller à ce qu'il apprenne bien sur des points de départ réalistes, pas
   seulement sur les mêmes parties d'experts qui ont produit le problème actuel.
4. **Copier des vraies parties humaines de recherche** — reléguée en dernier, pour une
   raison simple : ce test vient justement de montrer que le problème n'est pas le manque
   de bonnes propositions de gestes, mais leur mauvais jugement. Copier plus de comportements
   humains ne répare pas un jugement à l'envers, à moins de la combiner avec l'une des trois
   pistes précédentes.

## Et maintenant

Comme pour chaque chapitre précédent de ce projet, ce résultat est rapporté tel quel : ni
maquillé en victoire, ni présenté comme un échec définitif. C'est une pause de travail après
une enquête longue et honnête, avec un diagnostic net et un menu clair pour la reprendre.

:::

::: expert

## Contexte

Le Chapitre 10 (attempt #9) s'est terminé sur une hypothèse posée par élimination, pas
confirmée directement : après que trois mécanismes de génération de candidats
mécaniquement différents (macros écrites à la main + manœuvre bushwhack, CEM réel, actor BC)
aient tous échoué à faire bouger le résultat — y compris sur des spawns confirmés viables avec
arbre visible (`spawn_diag`) — le seul composant jamais testé isolément restait la notation
goal-centroid native de `ebwm.pt` elle-même, le mécanisme sur lequel toute tentative depuis
l'attempt #1 a été construite sans jamais le vérifier directement. Ce chapitre couvre
l'attempt #10 de `CLAUDE.md`/`docs/10_coldstart_engineering.md` : un diagnostic purement
offline qui teste cette notation directement, puis la clôture (provisoire) de la campagne
qui en découle.

## Méthode (attempt #10, PC, 2026-07-21, aucun MineRL/Java, aucun entraînement)

`scripts/diagnose_score_generalization.py` + `configs/diagnose_score_generalization.yaml`
réutilisent tel quels `DiscreteLatentPlanner._sample_actions()`/`_score()` — le code exact
déjà utilisé en direct par le scan et le `spawn_diag` — appliqués hors-ligne sur 251 images
fixes : 160 frames Treechop (`data/minerl_goal/episodes.npz`, la donnée d'entraînement de
`ebwm.pt` elle-même, 40 épisodes × 4 offsets internes pour varier la distance à l'arbre), 11
vraies frames de spawn cold-start `MineRLObtainIronPickaxeDense` (`assets/spawn_thumbs/` de
l'attempt #9), et 80 frames issues des épisodes de couverture de l'attempt #3
(`data/minerl_coverage/episodes.npz`, découpage par blocs de 400 pas pour contourner le bug
connu `dones`-tout-`False` du merge de shards, correctif de l'attempt #7 réutilisé tel quel).
Mêmes hyperparamètres que le planificateur chop deux-cerveaux en direct (horizon=12,
n_candidates=512, sticky_prob=0,5), seed 0. `ebwm.pt` chargé figé,
`requires_grad_(False)` vérifié sur tous les paramètres — aucun checkpoint modifié, aucun
entraînement.

## Résultat agrégat brut — un quasi-lavage, et à lui seul aurait INFIRMÉ l'hypothèse

| Groupe | n | moyenne | médiane | std | min | max | p10 | p90 |
|---|---|---|---|---|---|---|---|---|
| treechop | 160 | 0,00742 | 0,00459 | 0,00716 | 0,00022 | 0,03484 | 0,00126 | 0,01996 |
| obtain_spawn | 11 | 0,01085 | 0,00977 | 0,00565 | 0,00165 | 0,01900 | 0,00572 | 0,01794 |
| obtain_coverage | 80 | 0,00833 | 0,00610 | 0,00700 | 0,00055 | 0,04225 | 0,00185 | 0,01625 |

Médiane et p90 d'Obtain sont comparables, sinon légèrement *supérieurs*, à ceux de Treechop —
aucune histoire simple de type « le score s'aplatit sur Obtain » ne survit aux chiffres bruts
seuls. Lu isolément, ce tableau aurait été un argument contre l'hypothèse d'un problème sur
Obtain.

## Résultat pairé, image par image — une inversion nette, pas un aplatissement

| Source | Arbre clairement visible/proche | `goal_score_std` | Sans arbre / ouvert / distant | `goal_score_std` |
|---|---|---|---|---|
| Treechop (offset 0,5, distribution native) | canopée remplit le cadre (ep007) | **0,0274** | prairie+cabane, arbres distants (ep015) | 0,0027 |
| | tunnel de canopée (ep012) | **0,0171** | prairie ouverte, ligne d'arbres distante (ep016) | 0,0037 |
| | | | prairie, aucun arbre (ep033) | 0,0017 |
| | | | prairie ouverte, ligne d'arbres distante (ep037) | 0,0064 |
| Vrai spawn Obtain (attempt #9) | clairière forestière, arbres proches | 0,0060 | prairie ouverte | **0,0190** |
| | jungle dense, arbres proches | 0,0057 | prairie ouverte | **0,0179** |
| | | | plage, aucun arbre | 0,0130 |
| | | | grotte sombre, aucun arbre | 0,0069 |
| Couverture Obtain (vrais redémarrages) | tronc remplit le cadre | 0,0030 | prairie ouverte | **0,0176** |
| | canopée de jungle dense | 0,0098 | plaine ouverte | **0,0146** |

Note méthodologique : les frames Treechop à offset=0,0 (« spawn ») montrent en réalité surtout
du ciel ou des vues sous-marines à orientation de caméra aléatoire — un résultat incident en
soi — donc la comparaison Treechop utilise les frames offset=0,5, prises en plein milieu d'une
démonstration de coupe réelle.

Sur Treechop, les frames canopée-proche scorent environ **6× plus haut** que les frames
distantes/sans arbre (0,017-0,027 contre 0,002-0,007) — reproduction, à partir d'un
échantillon offline totalement indépendant, du calibrage en direct original de ce même
projet (bande « canopée remplit le cadre » 0,02-0,056 contre bande « perdu » 0,0002-0,002,
Chapitre 8). Sur les deux échantillons Obtain, rassemblés indépendamment, la direction
**s'inverse** : les frames les plus proches d'un arbre/canopée scorent au bas ou en dessous du
bas de la fourchette du groupe (0,003-0,010), pendant que des frames ouvertes sans arbre
atteignent le haut de la fourchette (0,013-0,019) — égalant ou dépassant la bande « arbre
visible » de Treechop, sans montrer le moindre arbre.

## Verdict : hypothèse confirmée, sous une forme plus précise que prévu

> **Leçon : ce n'est pas un effondrement de magnitude (le mode d'échec de RND, Chapitre 7) —
> c'est une confusion directionnelle dans la notation goal-centroid native, brute, non
> entraînée, de `ebwm.pt` elle-même.** Sur la distribution visuelle de spawn libre de
> `MineRLObtainIronPickaxeDense`, la distance goal-centroid discrimine mesurablement quelque
> chose — l'écart agrégat n'est pas plus plat que sur Treechop — simplement pas la proximité à
> un arbre, et dans chaque paire d'images vérifiée ici, elle pointe dans le MAUVAIS sens :
> un arbre plus proche score comme moins prometteur qu'une scène ouverte et sans arbre. C'est
> le même schéma « un signal confiant-mais-faux est pire qu'un signal honnêtement plat » déjà
> diagnostiqué au Chapitre 10 pour une métrique de distance entraînée *séparément* (là, une
> confusion de luminosité) — montré ici pour la première fois sur le mécanisme même que
> toute tentative depuis l'attempt #1 a construit et jamais testé isolément. Ceci referme la
> note de l'attempt #9 (« signalé comme hypothèse poussée par élimination, pas encore comme
> fait établi ») par une réponse directe : oui, et le mécanisme est une confusion
> directionnelle, pas un effondrement.

Aucun checkpoint modifié (`ebwm.pt` chargé en lecture seule pendant tout le diagnostic, comme
à chaque tentative précédente). CSV complet par frame et boxplot comparant les trois groupes :
`assets/diagnostics/score_generalization.csv`, `assets/diagnostics/score_generalization.png`.
Un diagnostic, pas une réparation — aucun changement de planificateur ou de notation n'a
découlé de ce test, par construction du protocole.

## La campagne fait une pause : synthèse des deux constats convergents

La campagne (attempts #4 à #10) a convergé sur deux constats indépendants et confirmés :

**(a) la qualité de la génération d'actions n'est pas le goulot d'étranglement** — trois
correctifs mécaniquement différents (macros écrites à la main, CEM réel, un acteur BC
entraîné) ont tous échoué à faire bouger le résultat, y compris sur des spawns
démontrablement viables avec arbre visible (attempt #9) ;

**(b) la notation goal-centroid native de `ebwm.pt`**, le mécanisme sur lequel toute
tentative a été construite, **s'inverse activement** sur la distribution de spawn de
`MineRLObtainIronPickaxeDense` — un arbre plus proche score plus bas qu'une vue
ouverte/sans arbre, l'opposé de son comportement sur Treechop (attempt #10).

Le mur n'est pas « l'agent ne sait pas quoi décider » — c'est « la boussole pointe à
l'envers hors de sa distribution d'entraînement ».

## Quatre pistes candidates, classées par coût/risque — aucune encore lancée

1. **Correction de score ciblée sur le domaine Obtain (nouvelle, la moins chère, la plus
   directement ciblée).** L'attempt #10 identifie exactement ce qui est cassé (le sens, pas
   la magnitude) et sur quelle distribution (Obtain, pas Treechop) — un petit correctif
   entraîné (adaptateur ou tête de distance) avec une vraie supervision proche/loin collectée
   DEPUIS Obtain lui-même (pas Treechop+couverture, ce qu'utilisait la réparation ratée de
   l'attempt #7) est maintenant une expérience précisément cadrée plutôt qu'un tir dans le
   noir. La moins chère des quatre ; ne nécessite pas de toucher aux poids principaux de
   `ebwm.pt` si implémentée comme une petite tête adaptatrice, sous la discipline anti-collapse
   standard du projet.
2. **Mémoire topologique / frontière épisodique.** Construire une carte des états visités
   pendant l'épisode et viser des sous-buts de frontière plutôt qu'un unique centroïde fixe —
   mais seulement si la sélection de frontière est pilotée par la visite d'états/couverture
   (façon Go-Explore), PAS par la distance latente à un but fixe. Si elle réutilise la même
   métrique de distance centroïde cassée pour juger « à quel point suis-je proche d'un point
   de frontière », elle hérite du constat (b) et échoue de la même façon. Ne nécessite pas de
   réentraîner `ebwm.pt`. Deuxième moins chère, conditionnée à bien faire ce choix de
   conception.
3. **H-JEPA — modèle du monde hiérarchique.** Un second modèle du monde, plus lent, qui
   planifierait « trouver une forêt » sur un horizon long, avant de rendre la main au modèle
   rapide existant pour « couper l'arbre » une fois proche. Conceptuellement la réponse la
   plus directe à un problème authentiquement long-horizon et à but rare, mais doit être
   entraîné délibérément sur une distribution de spawn de type Obtain, sinon il risque
   d'hériter du même défaut de calibrage Treechop-seul à un étage supérieur. Le coût/risque le
   plus élevé des quatre (un nouveau modèle à entraîner, et « qu'est-ce qui compte comme
   sous-but » est lui-même un problème de conception non trivial).
4. **Fine-tuning BC sur des images de recherche humaine.** Déprioritisée — l'attempt #9 a
   déjà montré que de meilleures/plus diverses propositions de candidats n'aident pas quand
   l'évaluateur les note à l'envers ; cette option améliore les propositions, pas
   l'évaluation, donc elle n'attaque pas le constat (b) du tout, à moins d'être combinée à
   l'une des pistes précédentes.

Aucune de ces quatre pistes n'est lancée — c'est un menu pour une reprise future du travail,
pas un plan engagé. La campagne s'arrête ici avec un diagnostic net, pas un abandon : après
sept tentatives sur la génération d'actions (attempts #4-#9) et un test direct sur
l'évaluation elle-même (attempt #10), les deux moitiés du mécanisme de planification ont
chacune été isolées et mesurées séparément — une discipline d'honnêteté inchangée depuis le
premier chapitre de ce site.

## Références (déjà vérifiées, tirées de `docs/references/index.md`, aucune nouvelle citation dans ce chapitre)

Ce chapitre ne s'appuie sur aucune nouvelle référence bibliographique : l'attempt #10 est un
diagnostic de mesure directe, pas l'application d'une méthode publiée — il réutilise le code
de planification déjà motivé par les références citées aux Chapitres 8 et 10
(Terver et al. arXiv:2512.24497, Destrade et al. arXiv:2601.00844, Burda et al.
arXiv:1810.12894).

:::

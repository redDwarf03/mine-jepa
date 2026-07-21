---
title: "Après les pistes A et C : la politique apprise devient la priorité"
slug: "09-les-prochaines-pistes"
lang: "fr"
order: 9
prerequisites: ["01-c-est-quoi-jepa", "02-le-piege-du-collapse", "03-le-modele-du-monde", "04-planifier-en-imagination", "05-le-vrai-minecraft", "06-apprendre-a-fabriquer", "07-la-curiosite-en-panne", "08-le-mur-est-comportemental"]
source_docs: ["CLAUDE.md#Phase 5+"]
---

::: beginner

## Attention : ce chapitre a changé depuis sa première version

Quand ce chapitre a été écrit pour la première fois, les pistes A et C décrites plus bas n'étaient
encore que des idées, pas des résultats. Ce n'est plus le cas : elles ont depuis été testées
ensemble (le Chapitre 8 en raconte l'histoire complète, avec les vrais chiffres). Ce chapitre est
donc mis à jour pour distinguer clairement **ce qui a été fait** (pistes A et C, résultat négatif
mais instructif) de **ce qui reste un plan, pas encore testé** (la piste B, promue en priorité, et
deux idées complémentaires ajoutées après ce dernier résultat). Si tu reviens sur ce chapitre plus
tard et que la section « pas encore testé » ci-dessous mentionne toujours des idées sans chiffres,
c'est qu'elles n'ont toujours pas été essayées.

## Récapitulatif rapide : les pistes A et C, testées ensemble (voir Chapitre 8 pour les détails)

Les deux idées les moins coûteuses de ce plan — mettre de bons gestes tout faits dans la liste des
essais du planificateur (piste A) et remplacer le réflexe « tourner sur place » par une manœuvre de
croisière qui avance en sprintant (piste C) — ont été testées ensemble, en plus de la correction
déjà en place depuis le Chapitre 8. Résultat sur 8 épisodes : toujours zéro bûche coupée. Mais les
deux mécanismes ont bien fonctionné : le bon geste tout fait a effectivement été choisi par le
planificateur dans plusieurs épisodes, et la manœuvre de croisière s'est elle aussi déclenchée au
moins une fois. Le vrai enseignement n'est donc pas le zéro en lui-même, mais un comportement
inattendu : dans plusieurs épisodes, l'agent s'est mis à répéter le même geste presque tout le
temps (jusqu'à 100% du temps) — un verrouillage qui rappelle un problème déjà vu avec une méthode
de planification plus raffinée testée au Chapitre 8, sans que ce soit encore confirmé comme
exactement le même mécanisme.

Ce résultat affine le diagnostic : quand le planificateur n'a aucun indice fiable pour comparer ses
options (parce qu'aucun arbre n'est en vue), lui donner du bruit pur le fait s'agiter sans but ;
lui donner un choix concentré de bons gestes tout faits le fait, au contraire, se figer aveuglément
sur l'un d'eux — parce que rien ne vient jamais le faire changer d'avis. Dans les deux cas, le
problème reste le même : le planificateur n'a jamais *appris*, à partir de vraies parties, ce qu'un
joueur fait réellement quand il ne voit rien d'intéressant.

## Ce qui reste à tester : la piste B, promue en priorité, et deux idées complémentaires

### Piste B : apprendre les bons gestes plutôt que les écrire à la main

Avec les pistes A et C testées et instructives mais insuffisantes, la piste qui restait jusqu'ici
en troisième position devient la priorité : entraîner une petite fonction qui apprend, à partir des
parties d'experts déjà utilisées ailleurs dans le projet, quelles actions un joueur choisit
typiquement dans une situation donnée. Cette fonction ne remplace pas le planificateur — elle sert
seulement à *proposer* de meilleurs candidats parmi lesquels le monde imaginé (Chapitre 3) continue
de choisir et corriger à chaque tour, exactement le même principe que des méthodes de jeu très
reconnues (les mêmes idées que celles qui ont battu des champions humains aux échecs et au jeu de
Go) : une intuition apprise propose des coups, une recherche explicite les vérifie.

Un piège identifié à l'avance, avant même de lancer cette expérience : les parties d'experts
utilisées pour l'entraînement montrent presque toujours un joueur déjà proche d'un arbre — elles ne
contiennent presque aucun exemple de « chercher méthodiquement quand on ne voit rien ». Pour éviter
que cette fonction n'apprenne qu'à « toujours attaquer l'arbre visible » sans jamais apprendre à
chercher — la même faiblesse, au fond, que les pistes A et C côté recherche —, le plan prévoit d'y
mélanger les épisodes de couverture aléatoire déjà collectés au Chapitre 7 (ceux qui montrent, eux,
de vraies situations « perdu, en train de chercher »).

**Cette piste vient toujours avec le même rappel important que dans la version précédente de ce
chapitre** : le Chapitre 5 avait déjà testé une approche « copier un joueur humain » qui avait
échoué (récompense zéro), mais cette version-là utilisait la copie comme décision *finale*, sans
aucun moyen de se corriger en cas de dérive. Ici, la fonction apprise ne fait que suggérer — le
planificateur garde le dernier mot à chaque tour.

### Deux idées complémentaires, elles aussi pas encore testées

- **Réparer la règle de distance entraînée avec de la variété d'éclairage.** Le Chapitre 8 a
  montré que la règle de distance entraînée (une des tentatives précédentes) réagissait à la
  luminosité de la scène (jour/nuit/grotte) plutôt qu'à la vraie distance à l'arbre — parce qu'elle
  n'avait jamais vu de vraies scènes de nuit ou de grotte pendant son entraînement. Le plan :
  ajouter de la variation artificielle de luminosité et de contraste aux images d'entraînement
  (sans avoir besoin de collecter de nouvelles données), puis refaire exactement le même test
  hors-ligne qu'au Chapitre 8 pour voir si la règle sépare mieux « loin » de « juste sombre ».
  Cette réparation serait utile en particulier si la piste B a besoin d'un signal de distance
  fiable pour départager ses propres propositions.
- **Un diagnostic sur le point de départ.** Plusieurs épisodes de cette enquête (Chapitres 7 et 8)
  se sont terminés dans un endroit sans aucun arbre à portée — un ravin rocheux, une zone
  souterraine. Aucune méthode ne peut réussir depuis un tel point de départ, quelle que soit sa
  qualité. Le plan : simplement enregistrer, au début de chaque épisode, le type d'endroit où
  l'agent apparaît, pour pouvoir distinguer, dans les futurs lots de résultats, « l'algorithme a
  échoué » de « le point de départ rendait le succès impossible dès le début ». Ce n'est pas une
  amélioration de l'agent, c'est une amélioration de la façon de mesurer — mais les échecs répétés
  sur des points de départ sans arbre, déjà vus deux fois, montrent que cette mesure manque depuis
  le début.

## L'ordre prévu

1. Entraîner et tester la piste B (priorité 1).
2. Réparer la règle de distance avec la variation de luminosité — un candidat pour donner à la
   piste B un signal fiable pour choisir entre ses propres propositions.
3. Ajouter le diagnostic de point de départ, pour que les prochains chiffres distinguent enfin
   échec d'algorithme et spawn impossible.
4. Évaluer la piste B et la règle de distance réparée ensemble, une fois que les deux existent.

Comme pour chaque tentative précédente de ce projet, le résultat — qu'il soit positif, négatif ou
inconclusif — sera rapporté avec les mêmes standards d'honnêteté que les chapitres précédents : les
vrais chiffres, jamais un chiffre arrangé pour paraître mieux qu'il n'est.

:::

::: expert

## Contexte : d'un diagnostic à cinq attaques, à une nouvelle priorité

Le Chapitre 8 se termine désormais sur cinq attaques indépendantes convergentes : quatre visant la
qualité du signal/score (RND en ligne, scan re-câblé, CEM réel, métrique de distance entraînée) et
une cinquième (attempt #8, récapitulée ci-dessous) attaquant directement la *génération* de
candidats via les Propositions A (priming du pool) et C (manœuvre bushwhack), combinées à
`commit_length=4`. Ce chapitre distingue explicitement ce qui a été **exécuté** (A et C, NO-GO mais
un finding qualitatif net) de ce qui reste **un plan non exécuté** (Proposition B, promue priorité
1, plus deux affinements ajoutés après l'attempt #8).

## Récapitulatif : Propositions A + C (attempt #8) — voir Chapitre 8 pour le détail complet

`planner.action_pool_priming` (~30 macros avant+attaque, ~30 rotation caméra, ~30 marche arrière
injectées dans le pool de 512) + `scan.macro: bushwhack` (sprint-saut avant borné remplaçant le
tourner-en-place, déclenché par `goal_score_std` plat sur le chop planner), combinés à
`commit_length=4`. **N=8, seed 0 : 0/8 logs, 0/8 planches, reward 0** — non significatif contre le
taux de base pooled `commit_length=4` seul (3/31 ≈ 9,7%, ≈0,8 succès attendus sur N=8).

Les deux mécanismes ont **vérifiablement déclenché** : `a7` (macro avant+attaque primé) 21-49% de
part dans 3/8 épisodes ; `a13` (macro bushwhack) 28% avec 8 déclenchements de scan dans 1/8
épisode. **Finding qui dépasse le 0/8** : 3/8 épisodes montrent `a14` (geste préexistant
avancer+attaquer) à 83-100% de part — verrouillage comportemental quasi total, qui **rappelle**
(sans confirmation quantitative encore établie contre les distributions propres de
`commit_length=4` seul — signalé, pas affirmé) la régression de concentration du CEM réel de
l'attempt #6 (66,3% moyen contre 35,8%), obtenue par un mécanisme différent (menu figé/macro de
couverture vs raffinement itératif) mais convergeant sur la même signature : un score plat privé de
gradient réel se fait *verrouiller* par tout mécanisme qui concentre le pool de candidats, au lieu
de rester varié.

## Proposition B (priorité 1, promue) — a priori de politique latente

Entraîner une tête actor par clonage comportemental sur `ebwm.pt` figé, à partir des démos
Treechop, pour *proposer* des candidats MPC au lieu d'un bruit uniforme/collant ou d'un menu figé
(A) — le MPC continue d'évaluer et de re-planifier à chaque pas, donc pas un repeat de l'échec BC
pur du Chapitre 5 (Phase 4, approches 3-4), où le BC était la politique finale sans correction.

**Affinement ajouté après l'attempt #8** : les démos Treechop garantissent la proximité d'un
arbre — elles contiennent presque aucune trajectoire de recherche authentique. Un actor entraîné
uniquement dessus risquerait d'apprendre « toujours attaquer l'arbre visible » sans jamais
apprendre à chercher, reproduisant la même faiblesse structurelle que A et C côté recherche.
Mitigation prévue : mélanger les épisodes de couverture aléatoire de l'attempt #3 (`docs/10`) aux
démos Treechop pendant l'entraînement de l'actor, pour que la distribution imitée contienne au
moins un peu de comportement de recherche authentique.

## Affinement 1 — réparer la métrique de distance entraînée (attempt #7) avec de l'augmentation photométrique

Le gate offline de l'attempt #7 séparait bien proche/lointain (ratio 7,9×) mais le signal vivant en
jeu suivait la luminosité de scène (jour/nuit/grotte, corrélation Pearson -0,565 avec
`goal_score_std`) plutôt que la distance réelle à l'objectif, parce qu'aucune des deux sources
d'entraînement (démos Treechop, épisodes de couverture) ne contenait de vraies scènes nocturnes ou
souterraines. Plan concret : ajouter du `ColorJitter` agressif (luminosité/contraste/gamma) à la
boucle d'entraînement de `train_value_projector.py`, puis rejouer exactement le même gate offline
censuré/hinge — aucune nouvelle collecte de données nécessaire. Une politique apprise (B) a
toujours besoin d'un score non plat pour départager ses propres propositions ; cette réparation est
la candidate directe pour ce rôle.

## Affinement 2 — diagnostic de viabilité du spawn

L'épisode 7 de l'attempt #8 s'est terminé prématurément (1856/3000 pas) sans mort enregistrée et
sans jamais trouver d'arbre — un spawn sans arbre à portée ne peut structurellement pas être
résolu, quelle que soit la qualité de l'algorithme. Les attempts #5 et #8 montrent tous deux des
spawns manifestement invivables diluant chaque taux de succès mesuré jusqu'ici. Plan : logger le
type de spawn (souterrain/océanique vs proche-forêt) au début de chaque épisode dans
`play_craft.py`/`play_minerl_multi.py`, pour que le dénominateur d'un futur lot distingue « échec de
l'algorithme » de « succès impossible par construction ». Correctif de mesure, pas de capacité.

## Ordre d'exécution prévu

1. Proposition B (priorité 1).
2. Réparation photométrique de la métrique de distance (attempt #7) — candidat de score non plat
   pour B.
3. Diagnostic de viabilité du spawn — correctif de mesure, indépendant des deux précédents.
4. Évaluer B et la métrique réparée ensemble une fois les deux disponibles.

Aucune de ces trois pistes n'a de statut privilégié avant exécution et mesure réelle — même
discipline d'honnêteté que chaque attempt précédent (#1-8).

:::

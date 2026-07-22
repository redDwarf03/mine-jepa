---
title: "Après les pistes A et C : la politique apprise a été promue, puis testée (suite au Chapitre 10)"
slug: "09-les-prochaines-pistes"
lang: "fr"
order: 9
prerequisites: ["01-c-est-quoi-jepa", "02-le-piege-du-collapse", "03-le-modele-du-monde", "04-planifier-en-imagination", "05-le-vrai-minecraft", "06-apprendre-a-fabriquer", "07-la-curiosite-en-panne", "08-le-mur-est-comportemental"]
source_docs: ["CLAUDE.md#Phase 5+"]
---

::: beginner

## Attention : ce chapitre a changé deux fois depuis sa première version

Quand ce chapitre a été écrit pour la première fois, les pistes A et C décrites plus bas n'étaient
encore que des idées, pas des résultats. Ce n'est plus le cas depuis longtemps : elles ont été
testées ensemble (le Chapitre 8 en raconte l'histoire complète, avec les vrais chiffres). À ce
moment-là, ce chapitre avait été mis à jour une première fois pour promouvoir la piste B (apprendre
les bons gestes plutôt que les écrire à la main) au rang de priorité, avec deux idées
complémentaires encore non testées.

**Deuxième mise à jour, celle-ci** : la piste B a, elle aussi, été construite et testée pour de
vrai — et les deux idées complémentaires ont, elles aussi, été menées à leur terme. **Le
Chapitre 10 raconte cette histoire en détail** ; ce chapitre-ci récapitule maintenant l'état réel de
chaque piste, plutôt que de continuer à les présenter comme des plans en attente.

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

## Où en est chaque piste maintenant (le détail complet est au Chapitre 10)

### Piste B : apprendre les bons gestes plutôt que les écrire à la main — **testée : ÉCHEC, mais un échec qui élimine deux explications**

L'idée, promue en priorité après les pistes A et C : entraîner une petite fonction qui apprend, à
partir des parties d'experts déjà utilisées ailleurs dans le projet (plus les épisodes de
couverture aléatoire du Chapitre 7, pour lui montrer aussi de vraies situations « perdu, en train
de chercher »), quelles actions un joueur choisit typiquement dans une situation donnée. Cette
fonction ne remplace pas le planificateur — elle propose seulement de meilleurs candidats parmi
lesquels le monde imaginé (Chapitre 3) continue de choisir et de corriger à chaque tour, comme des
méthodes de jeu très reconnues (les mêmes idées que celles qui ont battu des champions humains aux
échecs et au jeu de Go) : une intuition apprise propose des coups, une recherche explicite les
vérifie.

Cette piste a maintenant été construite et testée pour de vrai. Résultat sur 8 épisodes : **toujours
zéro bûche coupée.** Mais deux choses importantes ont pu être vérifiées et éliminées grâce à ce
test : l'agent n'a **pas** répété un seul geste en boucle (contrairement au Chapitre 8), et les 8
points de départ n'étaient **pas** des endroits sans arbre — un nouvel outil de mesure (voir
ci-dessous) l'a confirmé. C'est le résultat négatif le plus net de toute l'enquête : une proposition
de gestes vraiment variée et bien entraînée, testée sur des points de départ confirmés jouables, et
toujours zéro. **Le Chapitre 10 raconte cette histoire en détail**, avec un nouveau suspect (pas
encore confirmé) pour la suite de l'enquête.

**Ce même rappel reste valable** : le Chapitre 5 avait déjà testé une approche « copier un joueur
humain » qui avait échoué (récompense zéro), mais cette version-là utilisait la copie comme décision
*finale*, sans aucun moyen de se corriger en cas de dérive. Ici, la fonction apprise ne fait que
suggérer — le planificateur garde le dernier mot à chaque tour ; ce n'était donc pas un simple
« retour en arrière » vers l'échec du Chapitre 5, et le Chapitre 10 explique pourquoi le résultat est
malgré tout resté négatif.

### Deux idées complémentaires — **toutes deux menées à leur terme**

- **Réparer la règle de distance entraînée avec de la variété d'éclairage — testée : ÉCHEC.** Le
  Chapitre 8 avait montré que la règle de distance entraînée réagissait à la luminosité de la scène
  (jour/nuit/grotte) plutôt qu'à la vraie distance à l'arbre. La réparation prévue (ajouter de la
  variation artificielle de luminosité et de contraste à l'entraînement) a bien été essayée — mais
  le problème qu'elle visait à corriger **s'est aggravé** au lieu de s'améliorer sur une mesure plus
  propre. Le Chapitre 10 en donne le détail et l'explication probable.
- **Un diagnostic sur le point de départ — construit, et déjà utile.** L'outil qui enregistre, au
  début de chaque épisode, si un point de départ jouable est réellement présent a bien été
  construit. Il a servi directement dans le test de la piste B (ci-dessus) pour confirmer que les 8
  échecs de ce lot n'étaient pas dus à des points de départ impossibles à gagner — la première fois
  que ce projet peut affirmer ça avec une mesure, plutôt qu'une impression.

## Et maintenant

Le Chapitre 10 raconte l'histoire complète de la piste B testée, ce qu'elle élimine, et la nouvelle
hypothèse — pas encore confirmée — qui en ressort pour continuer l'enquête. Comme pour chaque
tentative précédente de ce projet, le résultat a été rapporté avec les mêmes standards d'honnêteté :
les vrais chiffres, jamais un chiffre arrangé pour paraître mieux qu'il n'est.

:::

::: expert

## Contexte : d'un diagnostic à cinq attaques, à une nouvelle priorité

Le Chapitre 8 se termine désormais sur cinq attaques indépendantes convergentes : quatre visant la
qualité du signal/score (RND en ligne, scan re-câblé, CEM réel, métrique de distance entraînée) et
une cinquième (attempt #8, récapitulée ci-dessous) attaquant directement la *génération* de
candidats via les Propositions A (priming du pool) et C (manœuvre bushwhack), combinées à
`commit_length=4`. Ce chapitre distinguait initialement ce qui avait été **exécuté** (A et C, NO-GO
mais un finding qualitatif net) de ce qui restait **un plan non exécuté** (Proposition B, promue
priorité 1, plus deux affinements ajoutés après l'attempt #8). **Mise à jour** : les trois — Proposition
B, réparation photométrique, diagnostic de spawn — ont depuis été exécutées (attempt #9,
`CLAUDE.md#Phase 5+`). Ce chapitre récapitule l'état réel de chacune ; **le Chapitre 10 en donne le
détail complet**, y compris le nouveau diagnostic qui en ressort.

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

## Proposition B — a priori de politique latente — **testée (attempt #9) : NO-GO, mais le négatif le plus net de la campagne**

Le plan était d'entraîner une tête actor par clonage comportemental sur `ebwm.pt` figé, à partir des
démos Treechop mélangées aux épisodes de couverture de l'attempt #3 (pour éviter que l'actor
n'apprenne qu'à « toujours attaquer l'arbre visible », la même faiblesse structurelle que A et C
côté recherche), pour *proposer* des candidats MPC au lieu d'un bruit uniforme/collant ou d'un menu
figé (A). Ce plan a été exécuté tel quel : `mine_jepa/ebwm/actor.py::BCActor`, gate anti-collapse
obligatoire (une ablation Treechop-seul a été correctement refusée : `top_action_frac` 0,964 contre
0,863 pour la version retenue, entraînée avec la couverture), câblage bit-for-bit vérifié.

**N=8, seed 0, `configs/play_craft_commit4_actor.yaml` : 0/8 logs, reward 0** (Fisher p≈0,21 contre
le taux de base pooled 3/31). Mais ce lot **élimine deux explications concrètes** : aucun
verrouillage comportemental (concentration d'action 16-54%, très loin du 83-100% de l'attempt #8),
et aucun spawn invivable (`spawn_diag` confirme `max_chop_std` 0,017-0,047 sur les 8 épisodes,
au-dessus du seuil calibré de 0,005). **Le détail complet, y compris le nouveau diagnostic qui en
ressort (l'évaluation du monde imaginé pourrait être le vrai goulot, pas la génération de
candidats), est au Chapitre 10.**

## Affinement 1 — réparer la métrique de distance entraînée (attempt #7) avec de l'augmentation photométrique — **testée : NO-GO**

Le gate offline de l'attempt #7 séparait bien proche/lointain (ratio 7,9×) mais le signal vivant en
jeu suivait la luminosité de scène (jour/nuit/grotte, corrélation Pearson -0,565 avec
`goal_score_std`) plutôt que la distance réelle à l'objectif. La réparation prévue (`ColorJitter`
agressif dans `train_value_projector.py`, puis le même gate offline censuré/hinge) a été
implémentée et exécutée : le gate offline tient toujours (séparation 8,7× contre 7,9×), mais la
confusion réelle avec la luminosité **s'aggrave** sur une mesure isolée plus propre
(`r=0,117 → r=0,498`). **NO-GO** — la confusion est vraisemblablement ancrée dans l'espace latent
figé de `ebwm.pt` lui-même, pas introduite par le projecteur ; le checkpoint réparé n'a donc pas été
déployé dans l'évaluation de la Proposition B ci-dessus, qui procède sur la seule notation
goal-centroid. Détail complet au Chapitre 10.

## Affinement 2 — diagnostic de viabilité du spawn — **construit et déjà utilisé**

L'épisode 7 de l'attempt #8 s'était terminé prématurément (1856/3000 pas) sans jamais trouver
d'arbre — un spawn sans arbre à portée ne peut structurellement pas être résolu. Le diagnostic prévu
(`spawn_diag` dans `scripts/play_craft.py`, vignette + `max_chop_std` contre un seuil calibré de
0,005) a été construit et **déjà exploité dans l'évaluation de la Proposition B ci-dessus**, où il a
confirmé la viabilité des 8 spawns du lot — la première fois que ce projet dispose d'une mesure,
plutôt qu'une impression, pour distinguer échec d'algorithme et spawn impossible.

## Et maintenant

Les trois pistes de ce chapitre ont toutes été exécutées et mesurées — même discipline d'honnêteté
que chaque attempt précédent (#1-8). Le Chapitre 10 en donne le récit complet et la nouvelle
hypothèse, non encore confirmée, qui en ressort pour la suite de l'enquête.

:::

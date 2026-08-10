---
title: "Même un détecteur qui ne peut rien apprendre retombe sur le même raccourci : le problème est dans l'œil, pas dans l'apprentissage"
slug: "17-le-raccourci-est-dans-l-oeil"
lang: "fr"
order: 17
prerequisites: ["01-c-est-quoi-jepa", "02-le-piege-du-collapse", "03-le-modele-du-monde", "04-planifier-en-imagination", "05-le-vrai-minecraft", "06-apprendre-a-fabriquer", "07-la-curiosite-en-panne", "08-le-mur-est-comportemental", "09-les-prochaines-pistes", "10-le-negatif-le-plus-net", "11-la-boussole-a-l-envers", "12-la-memoire-des-lieux-visites", "13-le-sauvetage-aveugle", "14-un-geant-du-web-a-l-epreuve", "15-cinquieme-confirmation-fausse-alerte", "16-predire-l-avenir-pas-l-image"]
source_docs: ["docs/10_coldstart_engineering.md#Cold-start attempt #17", "CLAUDE.md#Phase 5+"]
---

::: beginner

## Là où on en était

Depuis le Chapitre 11, un fait dérangeant traîne au centre de toute cette campagne, jamais
réparé : la boussole du planificateur — celle qui compare une histoire imaginée à un souvenir
de succès — pointe **à l'envers** une fois sortie de son terrain d'entraînement. Chaque
tentative depuis (Chapitres 12 à 16) a construit quelque chose *autour* de ce problème —
une mémoire des lieux visités, un réflexe anti-noyade, une prédiction d'exploration — sans
jamais s'attaquer directement à la boussole elle-même. Ce chapitre raconte les deux premières
tentatives qui visent directement le cœur du problème. Aucune des deux ne fonctionne. Mais
ensemble, elles apprennent quelque chose d'important sur *où* se cache réellement ce défaut.

## Première idée : ne pas réparer la boussole, apprendre à ne pas lui faire confiance

Au lieu de corriger le jugement biaisé de la boussole, cette première idée essaie de le
contourner autrement : construire un détecteur séparé, dont le seul travail est de repérer
« cette image ressemble à quelque chose que le modèle n'a jamais bien vu à l'entraînement » —
et si c'est le cas, ignorer la boussole et laisser la main à la mémoire des lieux visités
(Chapitre 12), qui elle a déjà fait ses preuves.

La particularité de ce détecteur, c'est qu'il ne s'entraîne pas du tout, au sens où
l'apprentissage automatique l'entend d'habitude. Pas de réseau de neurones, pas de
descente de gradient (la méthode habituelle par laquelle un modèle ajuste peu à peu ses
réglages internes pour améliorer un score). Il se contente de mesurer, une bonne fois pour
toutes, à quoi ressemble la forme statistique typique — la moyenne et la dispersion — des
images d'entraînement dans l'espace compressé (l'**embedding**, la représentation compacte
que fabrique le modèle à partir d'une image) que le modèle utilise déjà. Ensuite, pour
n'importe quelle nouvelle image, il calcule simplement à quelle distance elle se trouve de
cette forme typique. Plus loin = plus suspect. C'est une formule mathématique fixe, pas
quelque chose qui « apprend » au sens où un raccourci trompeur pourrait s'y glisser en
douce.

Ce détecteur a été soumis à trois tests, sur les mêmes images déjà utilisées pour prouver
au Chapitre 11 que la boussole était inversée :

1. **Sait-il distinguer un terrain connu d'un terrain inconnu ?** Presque, mais raté de
   justesse — la différence entre les deux catégories n'était pas assez nette.
2. **Est-ce qu'il repère spécifiquement les images où la boussole s'est trompée**, et pas
   juste « n'importe quelle image un peu différente » ? Raté plus clairement — le détecteur
   réagissait à « c'est un décor différent », pas à « c'est ici que le jugement est faux ».
3. **Est-ce qu'il se laisse distraire par un détail sans rapport, comme la simple luminosité
   de l'image ?** Raté nettement, et c'est le résultat le plus important des trois : le
   détecteur suivait la luminosité presque autant que les précédentes tentatives ratées des
   Chapitres 10, 14 et 15.

## Pourquoi ce troisième échec compte plus que les cinq précédents

Voilà le point le plus important de ce chapitre. Cinq fois avant celle-ci (Chapitres 10, 11,
14 en comptant ses deux moitiés, et 15), un système entraîné s'est fait piéger par la
luminosité de la scène au lieu de vraiment juger la présence d'un arbre. On aurait pu penser
que le problème venait de la façon dont ces systèmes *apprenaient* — un raccourci facile que
l'entraînement finissait toujours par trouver, comme une pente de facilité. Mais ce nouveau
détecteur **n'apprend rien du tout**. C'est une formule fixe, sans réglages ajustables, sans
possibilité de « tricher » en trouvant un raccourci pendant un entraînement — parce qu'il n'y
a pas d'entraînement.

Et pourtant, il tombe exactement dans le même piège.

Cela change complètement l'explication la plus probable. Le problème n'est vraisemblablement
pas « nos méthodes d'entraînement trouvent toujours le même mauvais raccourci ». Le problème
est plus profond : la confusion entre « c'est un arbre proche » et « c'est sombre » semble
être **déjà présente dans la façon même dont le modèle de base compresse une image en
représentation compacte** — avant même qu'un quelconque apprentissage supplémentaire
n'intervienne. N'importe quel calcul construit par-dessus cette représentation, aussi
prudent soit-il, hérite du même défaut, parce que le défaut est dans le matériau brut, pas
dans la façon de le travailler.

## Deuxième idée, plus modeste : le problème vient-il d'un manque de photos sombres ?

La deuxième piste de ce chapitre revient sur une vieille hypothèse jamais vérifiée
directement, datant du tout début de cette enquête (le raccourci de luminosité corrigé — sans
succès — au Chapitre 10) : et si le modèle confondait obscurité et absence d'arbre simplement
parce qu'il n'avait presque jamais vu de scènes sombres pendant son tout premier
entraînement ?

La vérification est simple, sans rien entraîner : compter, dans les données d'entraînement
d'origine, la proportion d'images sombres ou sous l'eau. Résultat : à peine 1 % — l'hypothèse
d'un manque de diversité était donc bien fondée, pour ce modèle d'origine.

Mais le Chapitre 14 avait déjà réentraîné une version du modèle sur un mélange de données
beaucoup plus large, incluant beaucoup de scènes issues du vrai jeu de fabrication — et
cette vérification montre que ces données-là contenaient déjà 16 à 22 % d'images sombres ou
sous l'eau, même en comptant large. L'image bizarre repérée au Chapitre 14 (celle dont le
score a empiré après le réentraînement) n'était donc pas un cas extrême jamais rencontré : elle
ressemble à beaucoup d'autres images déjà présentes dans les données d'entraînement.
**Conclusion : pour ce cas précis, manquer de photos sombres n'est plus une explication
plausible.** Si quelqu'un reprend un jour la réparation du modèle de base, la piste la plus
prometteuse n'est probablement pas « plus de données », mais quelque chose dans *la façon
dont l'entraînement compare des scènes différentes entre elles* — un point que personne n'a
encore testé.

## Ce que ça change pour la suite

Ces deux résultats négatifs, mis ensemble, ferment une question et en éclaircissent une
autre :

- **Sixième confirmation indépendante du même piège de luminosité** — après un petit module
  entraîné, ce même module réentraîné, une variation de lumière artificielle, un modèle
  géant tout fait, un calcul de couleur fait main, et maintenant une simple formule
  statistique sans aucun apprentissage. Six façons complètement différentes de s'y prendre,
  un seul et même mur.
- **La piste « pas assez de données sombres » est fermée** pour le cas précis qui l'avait
  motivée — pas parce que plus de données ne servirait jamais à rien en général, mais parce
  que, dans ce cas précis, il y en avait déjà assez.
- Le projet se retrouve donc devant un choix net, pas encore tranché : soit réentraîner le
  cœur même du modèle avec un objectif d'entraînement différent — un chantier lourd,
  jamais tenté jusqu'ici — soit accepter ce défaut comme une limite connue du projet et
  continuer à construire sur ce qui fonctionne déjà (exécuter les plans plus longtemps, la
  mémoire des lieux visités, le réflexe anti-noyade). Ce n'est pas encore décidé, et ce
  chapitre ne tranche pas à la place de qui de droit.

Comme pour chaque chapitre de ce site : deux vraies tentatives, deux échecs honnêtes, et un
résultat qui, même négatif, apprend quelque chose de solide sur la nature du problème.

:::

::: expert

## Contexte

Le Chapitre 16 (attempt #16, CVP) a clos sans toucher au problème central identifié dès le
Chapitre 11 (attempt #10) : la notation goal-centroid native de `ebwm.pt`, toujours utilisée
en direct par le planificateur de coupe deux-cerveaux dès que la recherche trouve quelque
chose, s'inverse sur la distribution de spawn d'Obtain. Chaque tentative des attempts #11 à
#16 a contourné ce fait plutôt que de le corriger. Ce chapitre couvre l'attempt #17 de
`docs/10_coldstart_engineering.md`/`CLAUDE.md#Phase 5+` : deux attaques directes et bon
marché sur ce mécanisme central, avant tout engagement plus coûteux.

## Prong A — détecteur OOD comme repli, plutôt qu'une réparation du score

**Idée, orthogonale à « réparer le score »** : si le latent figé de `ebwm.pt` peut être montré
comme mesurablement hors distribution sur une frame Obtain, un dispatch ultérieur pourrait se
replier sur la recherche par couverture `FrontierTracker` (attempt #12), déjà fonctionnelle,
plutôt que de faire confiance à une boussole confirmée inversée là (attempt #10). Sans
gradient, sans fonction de perte pour une tête aval — un contraste volontaire avec chaque
attempt à tête entraînée (#7, #11, #14 Phase 2) déjà tombé dans le piège de luminosité.

`scripts/diagnose_ood_gate.py` (`configs/diagnose_ood_gate.yaml`) ajuste une seule gaussienne
(moyenne, covariance) sur les latents `ebwm.pt` poolés de 4 000 frames Treechop aléatoires —
Lee, Lee, Lee & Shin, « A Simple Unified Framework for Detecting Out-of-Distribution Samples
and Adversarial Attacks », arXiv:1807.03888 (NeurIPS 2018), statistiques closed-form, aucune
boucle d'entraînement — évaluée à la feature `vpool` exacte que `CraftPlannerV4`/
`SwitchingCraftPlanner` calculent déjà à chaque replan (`mine_jepa/ebwm/planner.py`), puis
marque les frames de test par leur distance de Mahalanobis à cet ajustement. Trois gates sur
le même jeu de 251 frames que chaque attempt précédent de la campagne (160 Treechop, 11 vraies
thumbnails de spawn Obtain, 80 frames de couverture Obtain).

| Gate | Seuil | Résultat |
|---|---|---|
| A — séparation (distance de Mahalanobis moyenne Obtain vs. Treechop) | ≥ 1,3x | **ÉCHOUÉ — 1,294x** (raté de justesse ; reverifié directement depuis le CSV brut : moyenne obtain 9,905 vs. treechop 7,657, n=91/160) |
| B — spécificité (élevé spécifiquement sur les frames à sens confirmé faux de l'attempt #10, pas uniformément sur tout Obtain) | ≥ 1,2x | **ÉCHOUÉ — 1,105x** |
| C — contrôle négatif (corrélation avec la luminosité brute de l'image) | \|r\| < 0,3 | **ÉCHOUÉ — r = 0,56** |

Le Gate A raté de justesse signifie que le détecteur distingue à peine « ceci est Obtain » de
« ceci est Treechop ». Le Gate B, échoué plus nettement, signifie que même la faible
séparation qu'il capture n'est pas concentrée sur les frames où le score est confirmé faux —
il marquerait « ceci est Obtain », un signal nettement moins utile pour un dispatch de repli
que « ce score-ci n'est pas fiable ici ». Le Gate C est le résultat le plus tranchant des
trois :

> **LEÇON : 6e confirmation indépendante de la confusion luminosité/composition de scène, et
> la plus structurellement décisive à ce jour.** r=0,56 tombe carrément dans la fourchette de
> chaque attempt à tête entraînée (0,117-0,947, attempts #7/#11/#14/#15) — mais ce détecteur
> **n'a ni gradient, ni fonction de perte, ni aucun moyen d'« apprendre » un raccourci** : c'est
> un ajustement gaussien closed-form et un calcul de distance. Le fait qu'il atterrisse quand
> même dans la même fourchette de confusion montre que le raccourci n'est pas quelque chose que
> des têtes aval apprennent à exploiter — il est cuit dans la géométrie brute de l'espace
> latent figé de `ebwm.pt` lui-même, hérité par toute statistique construite dessus sans
> réentraîner l'objectif propre de l'encodeur.

**VERDICT : NO-GO sur les trois gates.** Non câblé dans `mine_jepa/ebwm/planner.py` ni
`scripts/play_craft.py` — aucun batch en direct dépensé sur un mécanisme qui a échoué ses
propres gates offline. `ebwm.pt` chargé figé et vérifié `requires_grad_(False)` tout du long ;
aucun checkpoint touché. Artefacts conservés en diagnostics uniquement :
`assets/diagnostics/ood_gate.csv`, `assets/diagnostics/ood_mahalanobis_stats.npz`.

## Prong B — l'anomalie de l'attempt #14 Phase 2 est-elle un manque de diversité des données ?

L'hypothèse originale de l'attempt #7 — jamais testée directement jusqu'ici — était que la
confusion de luminosité de `ebwm.pt` pourrait provenir d'un manque de diversité d'éclairage
dans ses données d'entraînement (frames sombres/sous-marines/grottes sous-représentées). Avant
de collecter quoi que ce soit de nouveau, une vérification en lecture seule : quelle part des
données réellement utilisées correspond déjà à cette description ?

En utilisant le détecteur calibré sous-l'eau/grotte de `mine_jepa/ebwm/hazard.py` (l'heuristique
de ratio de canaux invariante à la luminosité, validée à l'attempt #13 — préférée à la
luminosité brute, un mauvais discriminant ici puisque Treechop est en réalité plus sombre en
moyenne à cause de l'ombre de la canopée) :

- Données d'entraînement Treechop **originales** de `ebwm.pt` : seulement **1,0 %** de frames
  marquées sous-l'eau/grotte — l'écart signalé par l'attempt #7 était réel, pour le modèle
  d'origine.
- Données de domaine Obtain réellement utilisées pour le fine-tune de l'attempt #14 Phase 2
  (`data/minerl_craft` + `data/minerl_coverage`, sur-échantillonnées ~4x) : **16-22 %** de
  telles frames, même après sur-échantillonnage.

La frame anormale spécifique de l'attempt #14 Phase 2 (la frame sombre grotte/sous-l'eau dont
le score a *empiré*, 0,0130 → 0,025-0,031, après le fine-tune) a été identifiée provisoirement
par correspondance visuelle et numérique — avec un écart non réconcilié signalé honnêtement
plutôt que maquillé — et se situe bien dans la fourchette des exemples d'entraînement déjà
présents, pas comme un cas extrême jamais rencontré.

> **LEÇON : l'écart qui motivait le Prong B est déjà fermé pour les données réellement
> utilisées à l'attempt #14 Phase 2.** Collecter de nouvelles données n'est pas bien étayé
> comme prochaine étape pour cette anomalie précise. Si la piste du réentraînement de
> l'encodeur est reprise, une correction de pondération ou d'objectif d'entraînement — rien
> dans la perte VICReg + prédiction actuelle ne récompense explicitement un **ordre de
> distance relatif correct entre biomes**, seulement la précision de prédiction locale — est
> la prochaine question la mieux motivée, pas plus de données.

## Diagnostic d'ensemble, sur son terrain le plus solide à ce jour

Six approches indépendantes et mécaniquement diverses convergent maintenant sur la même
confusion luminosité/composition de scène : deux têtes entraînées sur latents figés (#7, #11),
un modèle tout fait de 400M images jamais touché par ce projet (#14 Phase 1, CLIP), un
fine-tune direct de l'encodeur lui-même (#14 Phase 2), une caractéristique invariante à la
luminosité conçue à la main (#15), et maintenant une statistique closed-form non entraînée
(#17 Prong A). Combiné à la fermeture par le Prong B de la théorie « juste besoin de plus de
données » pour le cas précis qui l'avait soulevée, le défaut apparaît **structurel** à la
représentation figée de `ebwm.pt` et/ou à son objectif d'entraînement — pas réparable par
quoi que ce soit construit par-dessus le checkpoint existant sans réentraîner son objectif de
base, un chantier nettement plus coûteux que tout ce qui a été tenté aux attempts #7-#17.

**Pas encore décidé si ça vaut la peine d'être poursuivi, ou s'il faut consolider autour des
mécanismes qui fonctionnent déjà (`commit_length`, couverture par frontière, évitement de
danger) et accepter le score central comme une limitation connue et permanente — question
posée à l'utilisateur, pas tranchée par ce chapitre.**

## Références

- Lee, Lee, Lee & Shin, « A Simple Unified Framework for Detecting Out-of-Distribution Samples
  and Adversarial Attacks », [arXiv:1807.03888](https://arxiv.org/abs/1807.03888) (NeurIPS
  2018) — fondement du Prong A (ajustement gaussien + distance de Mahalanobis sur le latent
  poolé de `ebwm.pt`), vérifiée dans `docs/references/index.md`.

Le Prong B ne s'appuie sur aucune nouvelle référence : il réutilise tel quel le détecteur
sous-l'eau/grotte de `mine_jepa/ebwm/hazard.py`, déjà motivé et calibré à l'attempt #13
(Chapitre 13).

:::

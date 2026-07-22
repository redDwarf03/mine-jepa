---
title: "Le modèle le plus proche de H-JEPA jusqu'ici prédit l'avenir, pas l'image — et perd quand même contre la simple moyenne"
slug: "16-predire-l-avenir-pas-l-image"
lang: "fr"
order: 16
prerequisites: ["01-c-est-quoi-jepa", "02-le-piege-du-collapse", "03-le-modele-du-monde", "04-planifier-en-imagination", "05-le-vrai-minecraft", "06-apprendre-a-fabriquer", "07-la-curiosite-en-panne", "08-le-mur-est-comportemental", "09-les-prochaines-pistes", "10-le-negatif-le-plus-net", "11-la-boussole-a-l-envers", "12-la-memoire-des-lieux-visites", "13-le-sauvetage-aveugle", "14-un-geant-du-web-a-l-epreuve", "15-cinquieme-confirmation-fausse-alerte"]
source_docs: ["CLAUDE.md#Phase 5+"]
---

::: beginner

## Là où on en était

Le Chapitre 15 a fermé, cette fois pour de bon, toute une famille de tentatives : aucun calcul basé
sur une seule image — qu'il soit appris, tout fait, ou fabriqué à la main pour résister aux
changements de lumière — ne peut séparer proprement « c'est une forêt » de « c'est sombre », parce
que dans ce jeu, les forêts sont vraiment plus sombres que les prairies. Cinq tentatives
différentes, cinq confirmations du même mur. Restaient sur la table, pour reprendre l'enquête sur
le point de départ à froid : la mémoire des lieux visités (Chapitre 12), qui a des résultats réels
mais modestes et en perte de vitesse, et l'idée la plus lourde et la plus ambitieuse du menu — un
second cerveau séparé, pensé pour la recherche à long terme. Ce chapitre raconte la première vraie
tentative dans cette direction : pas encore le grand second cerveau complet, mais un premier essai,
moins coûteux, conçu spécifiquement pour éviter le piège du Chapitre 15 dès le départ.

## Une idée différente : prédire la découverte, pas l'image

Jusqu'ici, chaque tentative de ce genre demandait à un petit modèle de regarder une image et de
juger : « est-ce que ça ressemble à une scène prometteuse ? ». C'est précisément ce type de
question qui s'est toujours retrouvé piégé par la luminosité. Cette fois, l'idée change de nature :
au lieu de juger une image, un petit modèle apprend à prédire, pour chaque direction possible où
l'agent pourrait aller, **combien de nouvelles cases de la grille explorée seraient probablement
découvertes** — une sorte de pari sur l'utilité d'explorer par là, pas un jugement esthétique sur ce
qui est affiché à l'écran.

Pour faire ce pari, ce petit modèle ne regarde **jamais** la couleur ni la texture d'une image. Il
se base uniquement sur deux types d'indices : un calcul classique de mouvement entre deux images
consécutives (est-ce que la caméra bouge beaucoup ou peu dans telle direction ?), et l'historique
des zones déjà visitées, hérité de la mémoire construite au Chapitre 12. C'est la tentative la plus
proche, à ce jour, de la véritable idée derrière **JEPA** — le nom même de ce projet : au lieu de
prédire une image future pixel par pixel, on prédit une petite quantité utile sur l'avenir (ici,
« combien de nouveau terrain je vais découvrir »), à partir d'indices compacts plutôt que de la
couleur brute des pixels. C'est exactement le genre de prédiction que ce projet a toujours cherché
à faire, appliqué ici à une nouvelle question.

## Un vrai bug trouvé en chemin, pas juste un manque de données

Avant même de pouvoir entraîner quoi que ce soit, il fallait collecter des exemples réels de
« dans telle direction, voici combien de nouveau terrain a effectivement été découvert ». Un
premier lot de collecte a révélé un vrai bug, resté invisible jusque-là : quand plusieurs
directions sont à égalité (ce qui arrive presque tout le temps au début d'une exploration, quand
aucune case voisine n'a encore été visitée), le mécanisme choisissait systématiquement, sans le
vouloir, la même direction par défaut — 54 fois sur 57 déclenchements dans ce premier lot. Ce
n'était donc pas un vrai choix exploratoire à chaque fois, juste un réflexe caché qui revenait
toujours au même endroit. Corrigé en ajoutant une option de tirage au sort pour départager les
égalités (l'ancien comportement reste disponible et inchangé si on ne l'active pas), puis
recollecté : cette fois, les 12 directions possibles sont bien représentées dans les données.

## Deux bons signes, avant même d'entraîner quoi que ce soit

Deux vérifications de sécurité ont été faites sur ces données fraîchement recollectées, avant toute
tentative d'entraînement :

1. **Est-ce qu'il y a une vraie différence entre les directions ?** Amélioré nettement après la
   correction du bug, mais basé sur peu d'exemples par direction (entre 1 et 7) — encourageant,
   pas encore une confirmation solide.
2. **Est-ce que la luminosité de la scène domine encore la cible qu'on essaie de prédire ?** Ce
   test a été fait deux fois, sur deux lots de collecte indépendants, et les deux fois, la réponse
   est claire : **non**, la luminosité n'a presque aucun lien avec la quantité de terrain
   nouvellement découvert. C'est le résultat le plus solidement reproductible de toute cette longue
   enquête sur l'absence de piège lié à la luminosité — enfin une piste qui ne tombe pas dans le
   même trou que les cinq précédentes.

## Le vrai test : est-ce que ce petit modèle peut prédire un essai précis ?

Avec ces deux bons signes, un petit modèle a été réellement entraîné — un tout petit réseau de
neurones, à peine 1 900 réglages internes. Mais ce projet a une règle stricte, appliquée à chaque
étape : ne jamais juger un modèle sur ses propres données d'entraînement. La bonne façon de vérifier
honnêtement, c'est de diviser les données en plusieurs tas, d'entraîner sur certains et de tester
sur ceux qui restent, plusieurs fois de suite avec des tas différents à chaque fois, pour ne pas se
faire avoir par un découpage chanceux ou malchanceux — c'est ce qu'on appelle la validation croisée.

Comparé à cette méthode rigoureuse contre le repère le plus simple possible — deviner tout le
temps la moyenne de toutes les valeurs déjà vues, sans même regarder la direction en question — le
petit modèle appris **fait pire**, pas mieux. Un essai systématique de huit variantes différentes
(réseaux plus petits, réglages plus prudents contre le sur-apprentissage) n'a jamais réussi à
battre cette moyenne simple, ne serait-ce qu'une seule fois. Et pour être vraiment sûr que ce
n'était pas juste un problème de réglage d'un réseau de neurones trop compliqué pour la tâche, une
version encore plus simple a été testée — un modèle linéaire classique, sans réseau de neurones du
tout, avec un frein réglable contre le sur-apprentissage. Résultat identique : plus on serre ce
frein, plus le modèle se rapproche de deviner une valeur presque constante — et il ne dépasse
jamais la moyenne simple, même dans ce cas le plus prudent possible.

## Pourquoi c'est un échec d'un genre différent des précédents

C'est important de bien distinguer ce résultat des cinq échecs du Chapitre 15. Là-bas, le problème
était qu'un modèle **apprenait quelque chose de trompeur** — un raccourci qui donnait l'illusion de
fonctionner tout en mesurant en réalité autre chose (la luminosité). Ici, c'est différent : les deux
vérifications de sécurité montrent un vrai signal agrégé, honnête, et pas trompé par la luminosité.
Le problème est ailleurs : **deviner précisément le résultat d'un seul essai particulier, à partir
de seulement quatre indices grossiers sur la scène, est une tâche beaucoup plus difficile que
repérer une tendance générale sur l'ensemble des essais** — et avec seulement une centaine
d'exemples au total, ce n'est tout simplement pas assez de données pour qu'un modèle, aussi simple
soit-il, apprenne à le faire de façon fiable. Ce n'est pas une preuve que l'idée de départ est
mauvaise. C'est un constat honnête que la tâche demande vraisemblablement beaucoup plus de données
(sans doute plusieurs centaines d'exemples, pas un meilleur réglage) avant de pouvoir dire si elle
est apprenable du tout avec ces indices.

Suivant la règle d'honnêteté de ce projet, ce petit modèle n'a **pas** été branché dans le jeu réel :
aucune partie n'a été dépensée à tester un modèle dont la vérification croisée dit clairement qu'il
ne fonctionne pas encore.

## Où en est le projet, après 16 vraies tentatives

À ce stade de l'enquête sur le point de départ à froid, il est utile de faire un point d'ensemble,
honnête, sans en rajouter dans un sens ou dans l'autre :

- **La piste « réparer le jugement visuel » est maintenant fermée**, avec cinq confirmations
  indépendantes du même piège de luminosité — un petit module appris, ce même module réentraîné sur
  d'autres données, une variation artificielle de lumière pendant l'entraînement, un modèle géant
  tout fait, et un calcul de couleur fait à la main. Aucune de ces cinq façons de s'y prendre n'a
  fonctionné, pour la même raison de fond.
- **La piste « recherche et couverture » est celle qui a produit les seuls vrais résultats
  positifs de toute la campagne** — exécuter plus longtemps un bon plan (Chapitre 8), la mémoire des
  lieux visités (Chapitre 12) — mais avec des gains qui s'essoufflent : le sauvetage anti-noyade
  tient bien à grande échelle (Chapitre 15) sans pour autant faire remonter le taux de coupe, et ce
  chapitre montre qu'aller plus loin dans cette direction (prédire l'exploration plutôt que la
  compter après coup) se heurte maintenant à un problème de quantité de données, pas d'idée.
- **Un mécanisme, nommé à plusieurs reprises depuis le Chapitre 11 mais jamais réparé directement,
  reste le fil le plus important encore ouvert** : la boussole même du planificateur de coupe — celle
  qui compare une histoire imaginée à un souvenir de succès — a été confirmée **inversée** dès le
  Chapitre 11, et chaque tentative depuis (recherche, sauvetage, prédiction de couverture) a
  contourné ce problème plutôt que de s'y attaquer de front. Avec la piste visuelle maintenant
  fermée et la piste de couverture montrant des rendements décroissants, ce mécanisme jamais
  réparé devient le levier le plus significatif qui reste sur la table.

Comme pour chaque chapitre de ce site depuis le premier jour : ce compte-rendu ne maquille rien.
Un signal réel a été trouvé (la luminosité ne domine pas la cible de ce nouveau modèle), un vrai
bug a été trouvé et corrigé en chemin, et le résultat final reste malgré tout un échec honnête à ce
stade — pas une victoire déguisée, pas un abandon non plus.

:::

::: expert

## Contexte

Le Chapitre 15 a fermé la piste candidate 1 du menu du Chapitre 11 (correction de score
photométrique) avec une cinquième confirmation indépendante du raccourci de luminosité, sous une
contrainte nouvelle et plus forte que les précédentes : **aucune caractéristique photométrique
mono-frame ne peut, structurellement, séparer luminosité et composition de scène dans ce domaine.**
Ce chapitre couvre l'attempt #16 de `CLAUDE.md#Phase 5+` (aucune entrée `docs/10` correspondante à
ce jour) : le premier mécanisme de la campagne construit explicitement sous la contrainte
« pas de notation photométrique mono-frame », un premier pas non-photométrique et non-visuel vers
la piste candidate 3 (H-JEPA) sans en payer le coût complet.

## Conception : le Coverage-Value Predictor (CVP)

Proposition Explorer, revue et affinée en externe : un petit MLP prédisant `Δunique_cells` (le
gain de couverture attendu) par cap candidat, à partir de caractéristiques **non-photométriques
uniquement** — un proxy classique de flux optique par différence de frames par quadrant, plus
l'histogramme de visitation locale déjà maintenu par `FrontierTracker` (Chapitre 12). C'est un
prédicteur de forme authentiquement JEPA (entrée+action → état futur), mais avec la **cible
substituée** : de la reconstruction de pixels vers une quantité géométrique compacte. Il alimente
la macro de scan frontière déjà validée plutôt que de remplacer sa passation de main au
planificateur de coupe.

## Instrumentation, collecte, et un bug réel trouvé en chemin

`scan.frontier.log_transitions` (config-gated, défaut désactivé) ajouté à `scripts/play_craft.py` ;
deux lots collectés.

**Premier lot (N=12, 57 lignes)** a révélé un bug réel, jusque-là inaperçu :
`FrontierTracker.frontier_heading_deg()` départage les égalités vers le plus petit index de cap, et
comme les cellules d'une grille encore peu explorée sont presque toujours à égalité (0 visite
chacune), 54/57 déclenchements ont « choisi » le cap 0,0° par construction, pas par préférence
réelle. Le Gate 1 (étendue dynamique à travers les caps) était incertifiable sur ces données.

**Correction** : option `tie_break="random"` config-gated (seedée), défaut `"first"` = ancien
comportement vérifié inchangé. **Recollecte (N=14, 44 lignes)** : les 12 caps possibles sont
maintenant représentés (1-7 lignes chacun).

## Gates offline sur les données recollectées

- **Gate 2 (la luminosité ne domine pas la cible) : PASSÉ sur LES DEUX lots indépendamment**
  (r ≈ 0,10, signes opposés) — le résultat non-confondu le plus reproductible de toute l'histoire de
  la campagne.
- **Gate 1 (étendue dynamique)** : nettement amélioré après correction du bug, mais reposant sur de
  petits échantillons par cap (1-7 lignes) — évalué comme « encourageant, pas une confirmation
  solide ».

## Le modèle réellement entraîné — NO-GO, vérifié en profondeur, pas juste mal réglé

Les deux CSV combinés (~101 lignes), un petit MLP (~1,9K paramètres) entraîné avec validation
croisée à 5 plis obligatoire contre un repère trivial « toujours prédire la moyenne ».

**Configuration par défaut** : MAE du modèle 1,590 contre 1,169 pour le repère (pire).

**Balayage d'hyperparamètres à 8 variantes** (réseaux plus petits, régularisation plus forte) : ne
bat jamais le repère, meilleur ratio 1,06 (encore pire).

**Vérification par régression linéaire (Ridge) partant de zéro**, pour exclure un artefact de
sur-apprentissage propre au MLP : à mesure que la force de régularisation augmente, l'erreur du
modèle ne fait que se rapprocher du repère à mesure qu'il est forcé vers une prédiction quasi
constante — elle ne le dépasse jamais.

> **Diagnostic : prédire le résultat d'un essai bruité et unique à partir de 4 caractéristiques
> grossières de niveau scène est une tâche bien plus difficile que les statistiques agrégées
> vérifiées par les Gates 1-2, et n'est pas apprenable à N≈100 avec ce jeu de caractéristiques —
> ce n'est pas une preuve que le signal agrégé est illusoire, seulement que la prédiction par
> ligne a besoin de bien plus de données (probablement plusieurs centaines de lignes, pas d'un
> meilleur réglage) pour être apprenable, si elle l'est du tout avec ces caractéristiques.**

Conformément à la discipline d'honnêteté du dispatch, le modèle n'a **pas** été câblé dans
`play_craft.py`, aucun `scan.macro: "learned_frontier"` n'a été ajouté, et aucun épisode en direct
n'a été dépensé à tester un modèle dont le gate de validation croisée dit qu'il ne fonctionne pas.
Aucun checkpoint écrit (`checkpoints/coverage_predictor.pt` n'existe pas). `ebwm.pt` et
`craft_wm_v4.pt` intacts.

## Pourquoi ce négatif est d'une nature différente de celui des Chapitres 11/12/14/15

Les échecs précédents de la famille « raccourci de luminosité » sont des cas où un modèle
**apprend quelque chose de réel mais trompeur** — un raccourci qui produit un bon score de gate
tout en mesurant en réalité une variable confondante (luminosité). Ici, les deux gates offline
(Gate 2 deux fois, Gate 1 après correction du bug) indiquent un signal agrégé réel et non confondu
— le problème n'est pas la validité du signal, c'est la **difficulté intrinsèque de la tâche de
prédiction par essai individuel** combinée à une **taille d'échantillon insuffisante** (~100
lignes). C'est un échec de puissance statistique et de granularité de la tâche, pas un échec de
principe de conception comme les cinq précédents.

## Où ça laisse la campagne — statut après 16 tentatives numérotées

- **Piste #1 (correction encodeur/notation) fermée, confirmée 5 fois** : attempts #7, #11, #14
  (phases 1 CLIP + 2 fine-tune direct), et #15 (chrominance par ratio) ont chacun buté
  indépendamment sur une confusion de luminosité/composition de domaine. Aucune caractéristique
  photométrique mono-frame — apprise, prête à l'emploi, ou conçue à la main pour l'invariance — ne
  la répare.
- **Piste #2 (couverture/exécution) détient les seuls vrais résultats positifs de la campagne** :
  `commit_length=4` seul (9,7% cumulé), la recherche par frontière de l'attempt #12 (1/20, puis
  confirmée à N=20 avec le correctif anti-noyade de l'attempt #13 superposé : noyade 60%→15%,
  épisodes à chance équitable 40%→60%, mais taux de coupe resté à 0/20 — rendements décroissants de
  la couverture seule, exactement la condition qui justifiait d'essayer la piste #3). L'attempt #16
  (CVP) prolonge cette ligne sous la contrainte « pas de notation photométrique » et trouve un vrai
  signal agrégé (Gate 2, deux fois) mais aucun modèle apprenable par essai à cette taille
  d'échantillon.
- **Piste #3 (H-JEPA proprement dit) non construite** — l'attempt #16 était la première sonde bon
  marché et non-photométrique que le diagnostic établi appelait ; elle n'a pas produit de mécanisme
  déployable, mais elle n'a pas non plus échoué pour une raison photométrique, donc la porte n'est
  pas fermée de la même façon que la piste #1. Version la moins coûteuse pour une reprise :
  collecter substantiellement plus de lignes de transition (plusieurs centaines) avant de
  réentraîner, selon la propre recommandation du dispatch CVP.
- **Le mécanisme nommé mais jamais réparé directement** : l'attempt #10 (Chapitre 11) a confirmé
  que la notation goal-centroid native de `ebwm.pt` — utilisée en direct par le planificateur de
  coupe deux-cerveaux dès que la recherche trouve quelque chose — s'inverse sur la distribution de
  spawn d'Obtain. Chaque tentative des attempts #11 à #16 a contourné ce problème (mécanismes de
  recherche, évitement de danger, prédiction de couverture) plutôt que de le corriger directement.
  Avec la piste #1 fermée et les pistes #2/#3 montrant toutes deux des rendements décroissants sans
  y toucher, ceci est désormais le mécanisme non examiné le plus déterminant de la campagne — pas
  encore décidé s'il faut, ou comment, l'attaquer directement.

## Références

Ce chapitre ne s'appuie sur aucune référence bibliographique nouvelle vérifiée dans
`docs/references/index.md`. Le design du CVP est décrit dans `CLAUDE.md` comme une proposition
Explorer affinée en interne, dans l'esprit général d'un prédicteur JEPA à cible substituée (prédire
une quantité géométrique plutôt que des pixels) — un principe déjà motivé pour ce projet par
l'architecture JEPA elle-même (Chapitre 1, LeCun, concept JEPA original) et par le choix de
prédiction en espace latent déjà fait pour `mine_jepa/ebwm/` (Assran et al., I-JEPA,
arXiv:2301.08243 ; Maes et al., LeWorldModel, arXiv:2603.19312), sans qu'aucune de ces références
ne décrive spécifiquement la prédiction de couverture d'exploration — ce composant précis n'a donc
pas de référence externe propre à citer.

:::

---
title: "Cinquième confirmation pour le raccourci de luminosité, une fausse alerte qui n'en était pas une, et une énigme à 144 qui reste sans réponse"
slug: "15-cinquieme-confirmation-fausse-alerte"
lang: "fr"
order: 15
prerequisites: ["01-c-est-quoi-jepa", "02-le-piege-du-collapse", "03-le-modele-du-monde", "04-planifier-en-imagination", "05-le-vrai-minecraft", "06-apprendre-a-fabriquer", "07-la-curiosite-en-panne", "08-le-mur-est-comportemental", "09-les-prochaines-pistes", "10-le-negatif-le-plus-net", "11-la-boussole-a-l-envers", "12-la-memoire-des-lieux-visites", "13-le-sauvetage-aveugle", "14-un-geant-du-web-a-l-epreuve"]
source_docs: ["CLAUDE.md#Phase 5+"]
---

::: beginner

## Là où on en était

Le Chapitre 14 s'est terminé sur une décision : la piste la plus lourde du menu du Chapitre 11
(construire un second modèle du monde, plus lent, pour « trouver une forêt » — une idée surnommée
**H-JEPA**) était désormais justifiée par de vraies preuves, pas seulement par un argument
plausible, parce que même le réentraînement le plus direct et le plus soigné du modèle existant
avait échoué à corriger proprement le raccourci de luminosité. Avant de se lancer dans ce chantier
coûteux, ce chapitre raconte trois choses qui se sont passées juste avant et juste après cette
décision : une relecture qui a évité de construire un outil inutile, un dernier test bon marché qui
a fermé la porte pour de bon, et deux découvertes séparées faites en repassant à plus grande échelle
un mécanisme du Chapitre 13.

## Une relecture avant de construire quoi que ce soit

Une idée, déjà évoquée sans être testée, consistait à construire à la main un petit outil de vision qui
repérerait le feuillage d'un arbre par sa teinte particulière (les verts et les bruns typiques d'un
tronc et de son feuillage) plutôt que d'utiliser la boussole cassée du projet. Avant de passer du
temps à le construire, quelqu'un a relu calmement tout ce que les chapitres précédents avaient déjà
appris. Le raisonnement : CLIP, au Chapitre 14, est un modèle géant entraîné spécifiquement pour
résister aux changements de lumière sur des centaines de millions de photos — et il a quand même
buté sur le même raccourci. Un outil fait maison, bien plus simple, avait donc de très fortes
chances de ne faire que répéter la même leçon une cinquième fois, à un coût réel de travail, sans
apporter d'information nouvelle. Recommandation : ne pas le construire, et investir plutôt dans les
deux seuls mécanismes du projet qui ont déjà produit de vrais résultats sans passer par un jugement
visuel direct — la mémoire des lieux visités (Chapitre 12) et l'exécution plus longue d'un bon plan
(Chapitre 8).

## Un dernier test bon marché, quand même

Une idée plus étroite et bien moins coûteuse a tout de même été testée directement, parce qu'elle
réutilisait un outil déjà construit et déjà validé : le petit détecteur de noyade du Chapitre 13
fonctionne en comparant des **rapports** de couleur (le bleu contre le rouge et le vert) plutôt que
des valeurs brutes — c'est précisément ce qui le rend capable de repérer une noyade aussi bien en
plein jour que de nuit. Est-ce que ce même tour de calcul, appliqué non plus à l'écran entier mais à
chaque petit morceau de l'image pris séparément, pourrait repérer un feuillage d'arbre de la même
façon, indépendamment de la luminosité de la scène ?

Le test a repris exactement les mêmes 251 images déjà utilisées à chaque diagnostic précédent
(Chapitre 11 et 14), avec les mêmes étiquettes posées à la main (« arbre proche » ou « pas
d'arbre »).

## Le résultat : à moitié bon, et pire que jamais sur l'autre moitié

La première moitié du test réussit : ce calcul par petits morceaux sépare bien les images avec
arbre proche des images sans arbre — un vrai résultat directionnel correct, dans la bonne fourchette
attendue.

Mais la deuxième moitié — vérifier que ce score n'est pas juste une façon détournée de mesurer la
luminosité — échoue presque aussi mal que le pire résultat vu jusqu'ici, celui de CLIP au Chapitre
14. Sur le petit jeu d'images étiquetées à la main, la corrélation avec la luminosité est
quasiment aussi forte, dans l'autre sens. Et surtout, cette fois, le problème n'est pas limité au
petit jeu de test : il apparaît largement, sur les 251 images, aussi bien sur les scènes du jeu de
coupe d'arbres d'origine que sur celles du jeu de fabrication.

## L'explication la plus nette de toute l'enquête

Le tour du rapport de couleur marche pour l'eau parce que la teinte de l'eau recouvre **tout
l'écran** de la même façon — c'est exactement le genre de décalage global que diviser des couleurs
entre elles permet d'annuler. Mais le problème ici n'est pas un décalage global : c'est que, dans ce
jeu comme dans la réalité, **les forêts denses sont, par nature, des scènes plus sombres, et les
prairies ouvertes des scènes plus claires**. Ce n'est pas un artefact d'un calcul particulier, c'est
une caractéristique du monde lui-même que le jeu imite. Aucun calcul de couleur, aussi malin
soit-il — appris, tout fait, ou fabriqué à la main pour résister aux changements de lumière — ne
peut démêler « c'est sombre » de « c'est une forêt » quand les deux choses sont, dans les données
disponibles, presque la même chose.

Ce résultat ferme, cette fois pour de bon, toute la piste « peut-être qu'un calcul de couleur plus
malin réglerait le problème ». Cinq façons différentes de s'y attaquer — un petit module appris,
ce même module réentraîné sur d'autres exemples, une variation artificielle de la luminosité
pendant l'entraînement, un modèle géant tout fait, et maintenant ce calcul par petits morceaux —
ont toutes buté sur le même mur. La correction de la boussole (piste n°1 du menu du Chapitre 11)
reste fermée, et cette fois avec une raison plus solide qu'avant : ce n'est pas qu'aucune tentative
n'a encore trouvé le bon réglage, c'est que ce genre de correction n'a structurellement aucune
chance de fonctionner sur ce problème précis.

## Séparément : le sauvetage anti-noyade repassé à grande échelle

Le Chapitre 13 avait laissé le geste de sauvetage anti-noyade avec un verdict encourageant, mais
testé sur seulement 6 parties. Un lot bien plus grand — 20 parties, combinant la mémoire des lieux
visités du Chapitre 12 et le sauvetage anti-noyade corrigé du Chapitre 13 — a maintenant été
exécuté, avec un objectif précis : est-ce que ce sauvetage tient toujours à cette échelle, et,
question restée ouverte jusqu'ici, est-ce que réduire les noyades permet enfin de couper du bois ?

**La noyade est réellement corrigée à grande échelle** : 3 parties sur 20 se terminent par une
noyade (15%), contre 12 sur 20 (60%) dans le tout premier lot du Chapitre 12. Les parties qui vont
jusqu'au bout sans être coupées court passent de 8 sur 20 (40%) à 12 sur 20 (60%). Le sauvetage
tient donc, pas seulement sur les 6 parties où il avait été validé, mais à une échelle bien plus
grande.

**Mais couper du bois reste à zéro** : 0 bûche sur 20, 0 planche sur 20 — alors même que davantage
de parties ont maintenant une vraie chance équitable de chercher un arbre. Ce n'est pas un recul
significatif par rapport au chapitre précédent (1 réussite sur 20) — la différence entre 0 et 1
sur 20 essais ne dit rien de fiable à cette taille d'échantillon — mais ça confirme, une fois de
plus, le constat déjà posé : survivre plus longtemps et savoir chercher/s'approcher efficacement
sont deux problèmes séparés. Réparer l'un n'a pas automatiquement réparé l'autre.

## Une leçon de méthode : une fausse alerte n'est pas un vrai arrêt

Le compte-rendu qui accompagnait ce lot de 20 parties affirmait, à l'origine, que le test avait été
interrompu par une « panne d'infrastructure grave » après seulement 4 épisodes. Une vérification
indépendante a montré que c'était **faux** : le programme qui pilote ces parties lance un processus
Minecraft séparé pour chaque épisode, un par un. Un incident technique passager sur un seul épisode
n'arrête donc jamais le programme qui orchestre l'ensemble — il passe simplement à l'épisode
suivant. Les journaux bruts confirment que les 20 épisodes se sont bien déroulés du début à la fin,
sans aucune intervention. La leçon retenue : une erreur qui touche un seul épisode dans cet outil
n'est pas la même chose qu'une panne qui arrête tout le lot — il faut vérifier que le programme
d'ensemble a réellement continué avant de déclarer un arrêt complet.

## L'énigme du reward=144

Un détail curieux figurait déjà dans les journaux de ce même lot de tests, sans avoir encore été
creusé : un épisode avait affiché, une seule fois, une récompense de 144 — un chiffre bien plus haut que tout ce qui a
jamais été vu ailleurs dans cette campagne (une réussite normale rapporte une récompense de 9). Le
programme de jeu a reçu un nouvel outil d'observation, activable au choix, qui affiche désormais le
maximum atteint pour **chaque objet** de l'inventaire au cours d'un épisode, pas seulement le bois
et les planches suivis jusqu'ici. Un nouveau lot de 12 parties a été lancé avec cet outil activé,
sur la même configuration : récompense de 0,000 sur les 12 épisodes, et le seul objet jamais
apparu dans un inventaire, sur l'ensemble du lot, était de la **terre ordinaire** (entre 1 et 30
unités par épisode, ramassée sans le vouloir en marchant ou en attaquant) — un objet qui ne
rapporte strictement aucune récompense dans ce jeu. L'épisode d'origine qui avait affiché 144 avait
déjà pris fin avant que cet outil n'existe, donc son état exact au moment précis reste
irrécupérable. Ce chiffre ne s'est jamais reproduit sur ces 12 nouveaux essais et reste, pour
l'instant, un événement isolé et non expliqué — parqué comme une curiosité documentée, sans effet
sur les conclusions de la campagne, plutôt que poursuivi sans un échantillon bien plus grand.

## Et maintenant

Ce chapitre referme une longue ligne d'enquête (les corrections de score basées sur la couleur ou
la luminosité) tout en apportant, séparément, une bonne nouvelle solide à grande échelle (le
sauvetage anti-noyade) et une énigme non résolue qui ne change rien au diagnostic principal. Comme
toujours dans ce projet : les bons résultats et les résultats décevants sont rapportés avec la
même précision, et rien n'est habillé pour paraître mieux qu'il ne l'est.

:::

::: expert

## Contexte

Le Chapitre 14 a conclu que la condition posée pour engager la piste candidate 3 du menu du
Chapitre 11 (H-JEPA hiérarchique) était remplie par des preuves empiriques, pas seulement par un
argument plausible : même le fine-tuning direct de `ebwm.pt` avec augmentation photométrique
n'avait produit qu'un résultat mixte. Ce chapitre couvre l'attempt #15 (`CLAUDE.md#Phase 5+`,
aucune entrée correspondante dans `docs/10_coldstart_engineering.md` à ce jour — écart de
documentation signalé explicitement dans `CLAUDE.md` lui-même) : une réévaluation de la proposition
H-JEPA, un test offline étroit qui en découle, et un lot de confirmation N=20 combinant les
mécanismes des Chapitres 12-13.

## Réévaluation de la proposition H-JEPA, sans code

Une proposition Explorer pour H-JEPA littéral avait été soumise. Avant tout développement, une
réévaluation à froid a noté que CLIP (Chapitre 14) — un modèle de 400M images conçu spécifiquement
pour résister à la variation photométrique — avait déjà échoué au même double gate qu'affronterait
une heuristique de teinte/contour construite à la main. En conséquence : construire cette
heuristique était jugé très probablement destiné à ne produire qu'une 5ᵉ confirmation, à un coût
d'ingénierie réel, sans information nouvelle — **recommandation de ne pas la construire**.
Recommandation complémentaire : les deux seuls mécanismes non basés sur un jugement visuel qui
fonctionnent dans la campagne (`FrontierTracker`, `commit_length`) sont le meilleur investissement
suivant, plutôt que de greffer davantage de biais de contenu visuel dessus.

## Test offline étroit : ratios de chrominance par tuile spatiale

Une idée plus ciblée et moins coûteuse issue de cette réévaluation a été testée directement :
`mine_jepa/ebwm/hazard.py` utilise des **ratios de canaux invariants à la luminosité** (pas des
valeurs brutes) — un choix qui fonctionne pour l'eau parce que la teinte sous-marine est un
décalage global et uniforme sur toute la frame. Ce même tour fonctionne-t-il pour le feuillage,
calculé **par tuile spatiale** plutôt que sur la frame entière ?
`scripts/diagnose_chroma_tile_generalization.py`, sur le même jeu de 251 frames et le même
étiquetage manuel que chaque diagnostic précédent (attempts #10, #14).

**Résultat : MIXTE, mais le gate de luminosité échoue presque aussi mal que le pire cas de CLIP.**

- Gate de direction : **PASSÉ** (ratio de séparation 1,482, ≥ le seuil de 1,3).
- Gate d'indépendance à la luminosité : **ÉCHOUÉ**. r = -0,925 sur le jeu étiqueté à la main
  (contre -0,947 pour CLIP — quasiment à égalité pour le pire de la campagne, signe opposé) ;
  r = -0,585 sur l'ensemble des 251 frames (treechop -0,748, obtain_spawn -0,600,
  obtain_coverage -0,671) — un effet large, pas limité au petit jeu étiqueté.

## Interprétation, la plus nette de la campagne

> **Leçon : la normalisation par ratio élimine exactement l'échelle de luminosité GLOBALE, comme
> conçu (pourquoi elle marche pour l'eau) — mais elle ne peut pas éliminer une confusion
> COMPOSITIONNELLE où les étiquettes de vérité-terrain elles-mêmes corrèlent le type de scène
> avec la luminosité (forêts sombres contre champs ouverts clairs est la composition de scène
> réelle de ce domaine, pas un artefact d'un mécanisme de notation particulier). Ceci signifie
> que la confusion de luminosité n'est réparable par AUCUNE caractéristique photométrique
> mono-frame — apprise, prête à l'emploi, ou conçue à la main pour être invariante — sans
> structure supplémentaire (multi-frame, spatiale/géométrique, ou une modalité différente).**

Ceci ferme définitivement la piste « peut-être qu'un calcul de caractéristique plus malin répare
ça » ; la piste candidate 1 du menu du Chapitre 11 reste fermée, pour une raison plus solide
qu'avant.

## Lot de confirmation N=20 : frontier + hazard combinés, taux de coupe mesuré pour la première fois sur cette combinaison

`configs/play_craft_commit4_hazard.yaml` (recherche par frontière du Chapitre 12 + sauvetage
anti-noyade corrigé de l'attempt #13, Chapitre 13) exécuté à N=20.

**Note de processus, corrigée.** Le compte-rendu du dispatch Tester affirmait une « panne
d'infrastructure grave » ayant arrêté le lot à l'épisode 4 — **faux**, vérifié indépendamment :
`play_minerl_multi.py` lance un processus Java/Malmo séparé par épisode, donc une erreur transitoire
de machine à états Malmo sur un seul épisode ne tue pas l'orchestrateur, qui passe simplement à
l'épisode suivant. Le lot a exécuté ses 20 épisodes de bout en bout (« FINAL RESULTS — 20/20
episodes succeeded ») sans aucune intervention. Leçon : une erreur par épisode dans ce harnais
n'équivaut pas à un échec de lot — vérifier le processus orchestrateur lui-même avant de déclarer
un arrêt dur.

**Noyade : 3/20 (15%)**, confirmé via de vrais messages Malmo `MineRLAgent0 drowned` — en baisse
depuis le taux de référence de l'attempt #12 original (12/20, 60%). Le correctif de l'attempt #13
tient à N=20, pas seulement au N=6 où il avait été confirmé. Autres terminaisons précoces (causes
non liées — chute, mob, etc., hors périmètre de ce correctif) : 5/20 (25%). Épisodes pleine
longueur (« fair-shot ») : 12/20 (60%), en hausse depuis ~8/20 (40%) dans le lot original de
l'attempt #12.

**Coupe/fabrication : 0/20 bûches, 0/20 planches** — malgré davantage d'épisodes bénéficiant
d'une chance équitable, aucune coupe sur ce lot (contre 1/20 pour l'attempt #12). Pas une
régression significative à ce N (un test de Fisher ne distinguerait pas 0/20 de 1/20) — la
variance habituelle à petit N de cette campagne. Confirme à nouveau le diagnostic établi : réduire
la confusion de noyade augmente les épisodes à chance équitable mais ne se convertit pas
automatiquement en coupe — survie et efficacité de recherche/approche restent des problèmes
séparés.

## L'anomalie reward=144.000 — investiguée, non reproduite, non résolue

`play_craft.py` a reçu un diagnostic optionnel `logging.full_inventory` (défaut désactivé,
bit-pour-bit inchangé si non activé) traçant/affichant la valeur maximale atteinte pour **chaque**
clé d'inventaire par épisode, pas seulement bûche/planches. Un nouveau lot N=12 avec ce diagnostic
activé (même configuration) a montré : reward=0,000 sur les 12 épisodes, et le SEUL objet
d'inventaire jamais non nul sur tout le lot était `dirt` (1-30 par épisode, ramassé
incidemment en marchant/attaquant) — `dirt` n'est PAS dans la table de récompense
(`RewardForPossessingItem` ne couvre que log/planks/stick/crafting_table/wooden_pickaxe/
cobblestone/furnace/stone_pickaxe/iron_ore/iron_ingot/iron_pickaxe), donc rapporte zéro récompense
et constitue une fausse piste pour le mystère d'origine. Le processus de l'épisode d'origine avait
déjà pris fin avant que ce diagnostic n'existe, son état exact reste donc irrécupérable — le
mécanisme qui a produit 144 ne s'est pas reproduit sur 12 nouvelles tentatives et reste un
événement isolé, non caractérisé. N'affecte aucune conclusion de campagne (le taux de coupe est ce
qui compte, et ceci lui est orthogonal) — parqué comme curiosité documentée, non poursuivi en
l'absence d'un échantillon beaucoup plus grand.

## Où ça laisse la campagne

`ebwm.pt` et `craft_wm_v4.pt` restent intacts sur l'ensemble de ce chapitre : le test de
chrominance par tuile est un diagnostic offline sans paramètre appris ; le lot de confirmation
N=20 et le diagnostic `full_inventory` réutilisent des mécanismes déjà entraînés/câblés sans
modifier aucun checkpoint principal.

## Références

Ce chapitre ne s'appuie sur aucune référence bibliographique nouvelle : le test de chrominance par
tuile réutilise l'heuristique de couleur déjà construite et calibrée pour l'attempt #13
(Chapitre 13), sans méthode publiée sous-jacente ; le lot de confirmation N=20 et le diagnostic
`reward=144` sont des exécutions/instrumentations empiriques du projet, pas l'application d'une
référence externe.

:::

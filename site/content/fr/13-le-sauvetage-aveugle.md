---
title: "L'alarme à noyade fonctionne parfaitement ; le geste de sauvetage, lui, ne sait pas où est la terre ferme"
slug: "13-le-sauvetage-aveugle"
lang: "fr"
order: 13
prerequisites: ["01-c-est-quoi-jepa", "02-le-piege-du-collapse", "03-le-modele-du-monde", "04-planifier-en-imagination", "05-le-vrai-minecraft", "06-apprendre-a-fabriquer", "07-la-curiosite-en-panne", "08-le-mur-est-comportemental", "09-les-prochaines-pistes", "10-le-negatif-le-plus-net", "11-la-boussole-a-l-envers", "12-la-memoire-des-lieux-visites"]
source_docs: ["CLAUDE.md#Phase 5+", "docs/10_coldstart_engineering.md"]
---

::: beginner

## Là où on en était

Le Chapitre 12 s'est terminé sur un vrai point positif : la mémoire des lieux déjà visités a
produit un deuxième succès réel (1 bûche coupée sur 20 essais), avec un comportement d'agent sain,
sans aucun signe de blocage sur un seul geste. Mais ce mécanisme avait lui-même une limite
signalée dès sa conception : quand il pousse l'agent à explorer une direction peu visitée, il ne
sait absolument rien des dangers qui pourraient se trouver sur son chemin.

En relisant, épisode par épisode, les journaux bruts de ce même lot de 20 essais — pas seulement
le chiffre final, mais ce que le jeu lui-même racontait pendant chaque partie — un fait s'est
révélé : sur les vingt épisodes, **douze** se sont terminés par un message du jeu confirmant que
l'agent s'était **noyé**. Pas une supposition, un vrai message du serveur Minecraft
(« MineRLAgent0 drowned »), retrouvé directement dans les journaux techniques de chaque partie.
Ce chapitre raconte la tentative construite directement en réponse à cette découverte, et ce
qu'elle apprend — un résultat qui, une fois de plus, n'est pas une victoire, mais qui referme la
question avec une précision inhabituelle.

## Le problème : aucun capteur de vie n'existe dans ce jeu précis

Avant de construire quoi que ce soit, il fallait vérifier une chose simple : le jeu envoie-t-il à
l'agent une information du genre « ta barre de vie », « ton niveau d'air sous l'eau » ? La réponse,
vérifiée directement dans le code de l'environnement de jeu utilisé ici
(`MineRLObtainIronPickaxeDense-v0`) : **non, rien de tout ça n'existe dans ce que le jeu transmet
au programme Python.** Seules deux choses arrivent côté agent : l'image de la caméra, et le
contenu de l'inventaire. Pas de vie, pas de souffle, pas d'air. Il faut donc deviner « je suis en
train de me noyer » uniquement à partir de ce que l'écran montre.

## L'idée : l'eau teinte l'écran d'une façon reconnaissable

Dans Minecraft, être sous l'eau donne à tout l'écran une teinte bleutée particulière : le rouge et
le vert de l'image deviennent presque égaux entre eux, pendant que le bleu grimpe nettement
au-dessus des deux. C'est un effet de brouillard coloré qui recouvre toute la vue, peu importe ce
qu'il y a devant l'agent. Un petit outil a donc été construit (`mine_jepa/ebwm/hazard.py`) qui lit,
image par image, la couleur moyenne de l'écran et compare le niveau de bleu à celui du rouge et du
vert — sans aucun apprentissage, juste un calcul de couleur.

## Premier calibrage, raté à moitié : la nuit change tout

La première version comparait des **différences brutes** de couleur (« le bleu dépasse le rouge de
tant de points »), calée sur une vraie noyade observée en plein jour, confirmée par le message du
jeu à l'instant exact où elle s'est produite. Cette version fonctionnait bien pour cette noyade-là
— mais elle a complètement **raté une deuxième vraie noyade**, survenue de nuit. La raison est
simple une fois qu'on la voit : dans une scène sombre, le bleu monte proportionnellement tout
autant qu'en plein jour, mais sa valeur brute reste minuscule (tout est sombre), donc un seuil basé
sur des différences absolues ne se déclenche jamais.

La correction : comparer des **rapports** de couleur plutôt que des différences absolues — un
calcul qui reste vrai que la scène soit très claire ou très sombre, parce qu'il compare les
couleurs entre elles plutôt qu'à une valeur fixe.

## Vérification sérieuse, deux fois

Cette nouvelle version a été repassée sur environ 5 900 vraies images, prises sur trois parties
entières qui se sont bien terminées (jour, crépuscule, forêt, ciel — des scènes très variées) plus
les deux vraies noyades déjà mentionnées. Résultat : **aucune fausse alerte** sur aucune des
images de parties normales, la noyade de jour est repérée à **100%** de ses images, et la noyade
de nuit à **environ 81%**. Les 19% manqués sont des images d'un noir presque total, où les trois
couleurs s'effondrent toutes vers zéro en même temps — une vraie limite d'un outil basé sur la
couleur des pixels dans l'obscurité complète, pas un simple réglage de seuil mal ajusté.

## Le geste de secours câblé

Quand le détecteur s'allume, il prend le contrôle : il alterne un saut (pour refaire surface et
respirer) avec un pas en arrière fixe, pendant un temps limité (jusqu'à 60 instants de jeu), avant
de rendre la main au fonctionnement normal.

## Le test en vrai jeu, 5 parties

- **3 parties sur 5** : rien à signaler, le détecteur ne s'est jamais déclenché.
- **1 partie sur 5** : l'agent meurt tôt, mais le détecteur ne s'est **jamais** déclenché — cette
  mort précise n'était donc pas une noyade. Une chute, un monstre, de la lave : le monde de
  Minecraft peut simplement être dangereux sur un point de départ aléatoire, et cet outil n'a
  jamais eu la prétention de couvrir ce genre de mort.
- **1 partie sur 5, la plus intéressante** : le détecteur s'est allumé **sans interruption pendant
  plus de 260 instants de jeu d'affilée** (plus de 4 secondes réelles) — le geste de secours
  (saut + pas en arrière) s'est bien déclenché à chaque instant, exactement comme prévu. **Et
  l'agent est mort à la fin de cette séquence quand même.**

## Le verdict : l'alarme marche, le sauvetage est aveugle

Le détecteur, en lui-même, fonctionne : il est précis, bien calibré, et il marche aussi bien de
jour que de nuit. Le vrai problème est plus loin dans la chaîne : le geste qui répond à l'alarme
ne sait absolument pas **dans quelle direction se trouve la terre ferme**. Alterner un saut et un
pas en arrière fixe n'a aucune idée de si ce pas en arrière mène vers le rivage ou plus profond
dans l'eau, ou juste le long d'une berge sans jamais s'en approcher. Si la direction tombe mal,
l'agent peut rester piégé indéfiniment — et une alarme qui sonne juste, sans jamais réussir à
sauver, ne sert à rien en pratique.

C'est exactement la même forme de leçon que ce projet avait déjà croisée une fois, pour un
mécanisme complètement différent (le réflexe « je suis perdu » du Chapitre 8) : **un détecteur
bien calibré n'est pas, à lui seul, une solution, si le geste qui l'écoute ne peut pas résoudre la
vraie situation.**

## Et maintenant

Ce résultat n'est pas déployé tel quel : c'est un « non » honnête, pas un « presque oui » maquillé.
Une piste de suite est explorée séparément, sans résultat connu au moment d'écrire ces lignes :
diriger le geste de secours vers le dernier endroit où l'agent était connu comme étant hors de
l'eau, en réutilisant le même petit outil de repérage de position déjà construit pour la mémoire
des lieux visités (Chapitre 12) — pas de nouvel apprentissage, juste du comptage et de la
géométrie, comme pour cette mémoire elle-même.

:::

::: expert

## Contexte

Le Chapitre 12 a laissé le mécanisme de frontière topologique (attempt #12) comme le point positif
de la campagne, avec une limite explicitement non traitée dès sa conception : la sélection de cap
ne comporte aucune notion de collision ou de danger. Ce chapitre couvre un diagnostic gratuit puis
l'attempt #13, tous deux issus d'une relecture des journaux du lot N=20 de l'attempt #12.

## Diagnostic gratuit : la noyade comme cause dominante de terminaison précoce

Corrélation, épisode par épisode, entre le journal maître du batch et les journaux clients Malmo
(`logs/mc_*.log`, un par sous-processus `play_minerl_multi.py`), par horodatage de fichier.
**12 des ~20 épisodes** contiennent un message serveur explicite `MineRLAgent0 drowned`,
directement précédant les dernières lignes de l'épisode (mort réelle de fin d'épisode, pas un tick
de dégât transitoire survécu) — vérifié à nouveau directement sur les journaux bruts, pas
seulement repris d'un rapport antérieur. Les épisodes qui vont jusqu'au plafond de 3000 pas ne
contiennent aucun message de noyade — une coupure nette, bimodale, pas une tendance floue.

**Conséquence pour la lecture du chiffre de tête de l'attempt #12 (1/20, 5%)** : sur le
sous-ensemble d'épisodes qui survivent assez longtemps pour chercher dans des conditions
équitables (pas coupés court par une noyade), le taux de succès apparent est plus proche de 1 sur
7-8 que de 1 sur 20. Les deux lectures sont honnêtes ; le 1/20 brut reste le chiffre réellement
déployé, mais attribuer tout l'écart à un déficit de recherche/approche serait faux — une bonne
partie vient d'un problème de danger au spawn, explicitement hors périmètre de la conception de
`FrontierTracker` (aucune conscience de collision/danger dans la sélection de cap).

## Attempt #13 — détecteur de noyade par pixels + geste d'échappement : NO-GO, mais diagnostic net

**Cause du choix pixel plutôt que capteur d'état.** Vérifié contre le code source de l'environnement
lui-même : `MineRLObtainIronPickaxeDense-v0` ne transmet aucune observation de vie, de souffle ou
d'air côté Python — seulement l'image caméra et l'inventaire. Toute détection doit donc passer par
l'image.

**Implémentation** (`mine_jepa/ebwm/hazard.py`) : sous l'eau, Minecraft teinte tout l'écran d'un
brouillard bleuté achromatique (rouge ≈ vert, bleu élevé). Deux statistiques de couleur moyenne sur
la frame :

```
ratio  = mean(B) / max(mean(R), mean(G))
rel_rg = |mean(R) - mean(G)| / max(mean(R), mean(G))
```

**Calibrage v1 (rejeté) — différences absolues.** Calé sur une noyade réelle observée en plein
jour, confirmée par le message de mort du jeu exactement au pas 644 d'un épisode. Fonctionnait sur
cette noyade, **ratait complètement** une seconde noyade réelle survenue de nuit : dans une scène
sombre, l'élévation du bleu est proportionnellement aussi forte mais négligeable en valeur brute de
pixel — un seuil absolu ne se déclenche jamais.

**Calibrage v2 (retenu) — ratios**, invariants à la luminosité globale de la scène par
construction, remplaçant les différences absolues.

**Validation** sur ~5 900 frames réelles poolées depuis trois épisodes complets survécus (jour,
crépuscule, forêt, ciel) plus les deux vraies noyades : **zéro faux positif** sur toute frame
survivante ; **100%** des frames de la noyade diurne correctement détectées ; **≈81%** de la
noyade nocturne. Les 19% manqués correspondent à des frames de noir quasi total où les trois
canaux de couleur s'effondrent vers zéro simultanément et les ratios deviennent trop bruités pour
être lus — une vraie limite d'une heuristique de couleur pixel au fond de l'échelle de luminosité,
pas un problème de réglage de seuil supplémentaire.

**Câblage** : au déclenchement, le détecteur remplace la sortie du planificateur ou de la macro de
recherche en cours par une action d'échappement — alternance saut (pour refaire surface) / pas en
arrière fixe — pendant jusqu'à 60 instants de jeu par déclenchement, puis rend la main au contrôle
normal.

**Test en direct, 5 épisodes réels :**

| Épisode | Déclenchement du détecteur | Issue |
|---|---|---|
| 3 épisodes | jamais déclenché | rien à signaler |
| 1 épisode | jamais déclenché | mort précoce — cause non-noyade (chute, mob hostile, lave — hors périmètre du mécanisme par construction) |
| 1 épisode | déclenché en continu **>260 instants de jeu** (>4 secondes réelles), échappement exécuté à chaque instant comme prévu | **mort à la fin de la séquence malgré tout** |

**Verdict.** Le détecteur lui-même est fonctionnellement correct — précis, bien calibré,
invariant à la luminosité. L'échec est en aval : l'action d'échappement (saut + pas en arrière
fixe) n'a aucune information directionnelle sur où se trouve la terre ferme. Si le pas en arrière
s'oriente vers de l'eau plus profonde, ou longe une berge sans s'en rapprocher, l'agent peut rester
piégé indéfiniment sans que l'alarme, correctement déclenchée, ne se convertisse jamais en
sauvetage réel.

> **Leçon : même forme que l'attempt #5 (Chapitre 8), sur un mécanisme entièrement différent.**
> Un détecteur « quelque chose ne va pas » correctement câblé et calibré n'est pas, à lui seul, un
> correctif si l'action qui le consomme ne peut pas résoudre la situation réelle. Là, c'était le
> réflexe de recherche face à un score plat ; ici, c'est un échappement sans direction face à un
> danger réel et correctement détecté. Le point commun : détecter n'est pas agir efficacement, et
> aucun de ces deux mécanismes ne peut se corriger lui-même une fois câblé sur une action de
> réponse aveugle.

**Statut livré : NO-GO, non déployé tel quel.** Piste de suite explorée séparément, résultat
inconnu au moment de la rédaction : orienter l'échappement vers la dernière position connue hors de
l'eau, en réutilisant le même outil léger de suivi de position par calcul mort déjà construit pour
`FrontierTracker` (attempt #12) — aucun apprentissage, seulement du comptage et de la géométrie,
cohérent avec le choix de conception déjà fait pour ce même mécanisme.

## Où ça laisse la campagne

Le diagnostic de noyade et l'attempt #13 ne changent pas le verdict du Chapitre 11 sur le mur
principal (recherche/approche pour trouver le premier arbre) — ils isolent une source de mortalité
distincte et partiellement responsable de la faiblesse du chiffre de tête de l'attempt #12, sans
la corriger complètement. `ebwm.pt` et `craft_wm_v4.pt` restent intacts : l'attempt #13 n'introduit
aucun paramètre appris, uniquement une heuristique de couleur pixel et un réflexe d'échappement
câblé à la main.

## Références

Ce chapitre ne s'appuie sur aucune référence bibliographique nouvelle : le détecteur de noyade de
l'attempt #13 est une heuristique de couleur pixel construite et calibrée directement sur les
données de ce projet, pas l'application d'une méthode publiée — conformément à la règle du projet
de ne citer que des identifiants arXiv déjà vérifiés dans `docs/references/index.md`, aucun n'est
invoqué ici faute de pertinence directe.

:::

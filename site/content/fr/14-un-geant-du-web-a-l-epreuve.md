---
title: "Un géant du web à l'épreuve : CLIP repère bien la forêt, mais lui aussi confond ça avec la luminosité"
slug: "14-un-geant-du-web-a-l-epreuve"
lang: "fr"
order: 14
prerequisites: ["01-c-est-quoi-jepa", "02-le-piege-du-collapse", "03-le-modele-du-monde", "04-planifier-en-imagination", "05-le-vrai-minecraft", "06-apprendre-a-fabriquer", "07-la-curiosite-en-panne", "08-le-mur-est-comportemental", "09-les-prochaines-pistes", "10-le-negatif-le-plus-net", "11-la-boussole-a-l-envers", "12-la-memoire-des-lieux-visites", "13-le-sauvetage-aveugle"]
source_docs: ["CLAUDE.md#Phase 5+", "docs/10_coldstart_engineering.md"]
---

::: beginner

## Là où on en était

Le Chapitre 11 avait posé le diagnostic le plus important de toute cette longue enquête sur le
point de départ à froid : la boussole du projet (le score qui compare chaque histoire imaginée par
le modèle du monde à un souvenir « d'arbre coupé », voir Chapitre 4) ne s'éteint pas simplement une
fois sortie de son terrain d'entraînement — elle **pointe à l'envers**. Un arbre tout proche reçoit
un score plus bas qu'une prairie vide. Le Chapitre 12 a montré, en creusant encore, qu'une partie de
ce problème vient très probablement d'un raccourci caché dans le tout premier modèle de vision du
projet lui-même (Chapitre 1-2) : au lieu de vraiment comprendre « il y a un arbre ici », le modèle
semble surtout repérer si l'image est claire ou sombre — un raccourci confirmé trois fois de suite,
sous trois formes différentes.

Avant de se lancer dans la piste la plus lourde du menu laissé par le Chapitre 11 (construire un
second cerveau, un modèle séparé et plus lent, rien que pour « trouver une forêt »), une personne
extérieure au projet, consultée par le responsable, a proposé une question plus simple et beaucoup
moins coûteuse à tester d'abord : **est-ce qu'un très gros modèle d'IA déjà tout fait, jamais
entraîné spécifiquement sur Minecraft, sait déjà repérer une forêt correctement ?** Si oui, pas
besoin de construire quoi que ce soit de nouveau — on pourrait simplement le réutiliser tel quel. Ce
chapitre raconte ce test, et ce qu'il révèle — un résultat à moitié encourageant, à moitié inquiétant,
et honnêtement pas encore complètement compris.

## L'idée : emprunter les yeux d'un géant plutôt que d'en construire un nouveau

Le modèle proposé s'appelle **CLIP**. Il n'a jamais rien vu de ce projet ni de Minecraft : il a été
entraîné, par une autre équipe, sur des centaines de millions de photos et de légendes prises sur
internet — le genre de choses qu'on trouve en cherchant des images sur le web. Ce que CLIP sait
faire, une fois entraîné : comparer une image quelconque à une phrase quelconque, et dire à quel
point elles « vont bien ensemble », sans avoir besoin d'être réentraîné pour chaque nouvelle tâche
(on appelle ça une comparaison « zero-shot » — littéralement « sans aucun essai d'entraînement
supplémentaire »).

Le test était simple : reprendre exactement les mêmes vraies images du jeu qui avaient servi à
découvrir le problème de boussole inversée au Chapitre 11, et demander à CLIP de comparer chacune
à deux phrases : « une forêt dense avec beaucoup d'arbres » contre « un champ ouvert et herbeux sans
arbre ». Deux conditions devaient être remplies pour que le test soit un vrai succès :

1. **CLIP doit donner raison au bon sens** : une image avec un arbre proche doit recevoir un score
   plus favorable à « forêt » qu'une image sans arbre. (C'est exactement l'inverse de ce que faisait
   la boussole cassée du projet au Chapitre 11.)
2. **Ce score ne doit pas être, en réalité, juste une façon détournée de mesurer la luminosité de la
   scène** — sinon ce serait le même vieux raccourci déjà repéré trois fois (Chapitre 11), simplement
   caché derrière un modèle beaucoup plus gros et beaucoup plus impressionnant.

## Le résultat : la moitié du test réussit clairement, l'autre moitié échoue largement

**La première condition est réussie, et nettement** : CLIP donne bien un meilleur score « forêt »
aux images qui montrent réellement des arbres proches qu'à celles qui n'en montrent aucun. Sur ce
point précis, CLIP fait mieux que la boussole cassée du projet — il ne s'inverse pas.

**La deuxième condition échoue, et largement.** Le score de CLIP est très fortement lié à la
luminosité globale de l'image — presque comme si les deux mesuraient quasiment la même chose. Et ce
n'est pas seulement vrai sur les images difficiles du jeu de fabrication (là où la boussole du projet
s'inverse) : c'est vrai **même sur les images faciles du jeu de coupe d'arbres original**, celui où
la boussole maison du projet fonctionne déjà correctement depuis le Chapitre 6.

## Ce que ça veut dire, honnêtement — et ce qui reste un vrai mystère

Il faut être prudent ici, parce que c'est une question ouverte, pas une certitude établie.

Ce résultat **affaiblit, sans la démolir complètement**, une idée qui semblait raisonnable jusque-là :
que le petit modèle du projet confond luminosité et forêt simplement parce qu'il n'a pas vu assez de
scènes variées (jour, nuit, différentes météos) pendant son entraînement. Si un modèle géant,
entraîné sur des centaines de millions de photos bien plus variées que tout ce que ce projet pourra
jamais collecter, fait la **même** confusion — et même un peu pire — alors le manque de diversité
n'explique peut-être pas tout.

Il y a même une explication possible qui ne serait pas un « bug » du tout : une vraie forêt dense,
dans la vraie vie comme dans un jeu qui l'imite, **est réellement plus sombre** qu'un champ ouvert en
plein soleil, à cause de l'ombre des feuillages. Repérer ça pourrait être un signal utile et sensé,
pas une erreur de raisonnement.

Mais une observation précise empêche de s'arrêter à cette explication simple : parmi les images
testées, une scène de **grotte sombre, sans le moindre arbre**, a été classée par CLIP dans le même
groupe que les scènes ouvertes et claires — « pas de forêt » — au lieu d'être confondue avec une
forêt sombre, comme une histoire de « la noirceur = la forêt » l'aurait prédit. Il se passe donc
autre chose que la simple luminosité, mais quoi exactement reste, à ce jour, une vraie question sans
réponse.

## Phase 2 : réentraîner directement le modèle du monde — un résultat mitigé, pas un résultat propre

La décision prise à la suite du test CLIP n'était pas d'exiger que le futur correctif devienne
complètement indépendant de la luminosité (au risque de retirer un signal peut-être légitime), mais
de vérifier directement si le vrai problème d'origine — la boussole qui pointe à l'envers sur de
vrais points de départ aléatoires — disparaît, peu importe par quel mécanisme. Ce travail est
maintenant terminé, et voici ce qu'il a donné.

Le projet a repris le modèle du monde existant (pas depuis zéro, un simple ajustement des poids déjà
entraînés) et l'a réentraîné sur un mélange : les images garanties-forêt d'origine, plus de vraies
démonstrations de spawn libre, plus des épisodes d'exploration au hasard. Nouveauté par rapport à
tous les essais précédents : cette fois, une **augmentation photométrique** (les couleurs, la
luminosité et le contraste de chaque courte séquence sont modifiés au hasard, mais de façon cohérente
sur toute la séquence plutôt qu'image par image, pour forcer le modèle à ne plus s'appuyer aveuglément
sur la luminosité) a été appliquée directement à l'entraînement du modèle du monde lui-même — pas à
un petit module ajouté par-dessus, comme dans les tentatives précédentes. C'est la première fois de
toute cette enquête que ce geste-là est fait directement sur le modèle principal.

Les vérifications de sécurité habituelles (pas d'effondrement de la représentation — voir Chapitre 2
— et la qualité de prédiction qui ne bouge presque pas, ce qui était voulu : l'idée était un ajustement
léger, pas un nouvel entraînement complet) sont passées sans accroc sur les 5 étapes d'entraînement.

**Le vrai test consistait à refaire, sur chacune des 5 versions ajustées, exactement le même
diagnostic qui avait découvert le problème de boussole inversée.** Le résultat est réellement partagé,
pas juste « ça a presque marché » :

- **En écartant une seule image précise** — une scène sombre, comme une grotte ou un passage sous
  l'eau, sans le moindre arbre — le correctif a l'air propre : sur les 5 versions ajustées, les scènes
  avec un arbre proche obtiennent maintenant un score plusieurs fois plus élevé que les scènes ouvertes
  sans arbre. C'est un vrai renversement par rapport au sens inversé d'origine.
- **Mais en remettant cette seule image dans le calcul, le résultat repart dans le mauvais sens sur
  chacune des 5 versions**, parce que le score de cette image précise **est devenu pire** après
  l'ajustement, pas meilleur. C'est une anomalie nouvelle, liée à la faible luminosité, qui apparaît à
  un endroit différent d'avant — mais qui appartient clairement à la même famille de problème que le
  raccourci lié à la luminosité déjà repéré plus tôt (Chapitre 12, et la première moitié de ce
  chapitre avec CLIP).

Aucune des 5 versions ajustées n'a été promue pour remplacer le modèle de référence, et aucun nouveau
test en jeu réel n'a été fait : la règle du projet est de ne dépenser un test en jeu que sur un
candidat qui a clairement réussi son test hors-jeu d'abord — et celui-ci n'a pas clairement réussi.

**Pourquoi c'est important, dit avec précision** : c'est la quatrième fois, avec quatre approches
vraiment différentes, qu'une anomalie liée à la luminosité apparaît — un petit module ajouté, entraîné
sur les caractéristiques déjà figées du modèle ; ce même module, ré-entraîné spécifiquement sur des
données de spawn libre ; un modèle géant tout fait, jamais entraîné pour ce projet (CLIP, plus haut
dans ce chapitre) ; et maintenant, un réentraînement direct du modèle du monde lui-même, avec une
vraie augmentation photométrique — l'attaque la plus directe tentée jusqu'ici sur ce problème précis.
Ça affaiblit sérieusement l'idée que « le modèle n'a simplement pas encore vu assez de lumières
différentes » explique tout — même la tentative la plus directe et la plus soignée pour corriger
exactement ça a quand même produit une nouvelle anomalie, pas un correctif propre.

## Et maintenant

La condition que le projet s'était lui-même fixée pour se lancer dans la piste la plus lourde du menu
laissé au Chapitre 11 — un second modèle du monde, plus lent, dédié à « trouver une forêt » avant de
rendre la main au modèle rapide existant pour couper l'arbre, appelé **H-JEPA** — était : « seulement
si le correctif direct et moins coûteux échoue ». C'est maintenant chose faite, avec de vraies
preuves à l'appui plutôt qu'un simple argument plausible. Le projet s'oriente donc vers cette piste
plus structurellement différente comme prochaine direction, plutôt que de continuer à chercher un
correctif direct sur le modèle existant.

:::

::: expert

## Contexte

Le Chapitre 11 a établi que la notation goal-centroid native de `ebwm.pt` s'inverse hors
distribution Treechop (arbre proche → score plus bas qu'une scène ouverte). Le Chapitre 12 a
confirmé, une troisième fois indépendante, qu'un raccourci de luminosité vit très probablement dans
l'encodeur visuel figé lui-même (attempt #11 : corrélation score/luminosité 0,643, et corrélation
`is_tree_close`/luminosité de -0,917 sur le propre jeu d'étiquetage manuel du gate, démontrant que
le gate de direction à 87,5% mesurait en réalité le même raccourci). Ce chapitre couvre la phase 1
de l'attempt #14 : un diagnostic purement offline, sans entraînement Minecraft-spécifique, testant
si un modèle de vision-langage pré-entraîné générique et totalement hors-domaine résout déjà le
problème de direction — avant d'engager le coût de la piste candidate 3 du Chapitre 11 (H-JEPA
hiérarchique).

## Méthode

Un expert externe consulté par le porteur du projet a proposé de tester **CLIP** (Radford et al.,
OpenAI) en zero-shot, avant toute autre intervention — un modèle jamais touché ni affiné pour ce
projet, entraîné sur des centaines de millions de paires image-texte du web. Protocole : similarité
zero-shot CLIP entre chaque frame et deux descriptions textuelles, « a dense forest with many trees »
contre « an open grassy field with no trees », appliquée sur le **même jeu de frames réelles** qui
avait servi à découvrir l'inversion à l'attempt #10 (Chapitre 11) — ni nouvelles données, ni
ré-échantillonnage, pour une comparaison directement appariée avec le diagnostic précédent.

Deux conditions de passage étaient exigées, pas une seule :

**(a)** CLIP doit noter correctement les frames arbre-proche au-dessus des frames sans arbre —
le test de direction que la notation native de `ebwm.pt` échoue (attempt #10).

**(b)** Le score de CLIP ne doit pas être une simple fonction de la luminosité globale de la
scène — sinon ce serait le même raccourci que celui confirmé trois fois à l'attempt #11, redécouvert
derrière un modèle plus gros plutôt que résolu.

## Résultat

**(a) validée clairement** : une séparation réelle et correctement orientée, contrairement à la
notation native de `ebwm.pt` sur la même distribution.

**(b) échouée, largement.** Le score CLIP corrèle fortement avec la luminosité de scène — une
relation proche d'une quasi-colinéarité entre les deux variables. Point notable : cette corrélation
tient **aussi sur l'environnement Treechop d'origine**, celui où la notation native de `ebwm.pt`
fonctionne déjà correctement (Chapitre 6, Chapitre 8) — pas seulement sur la distribution difficile
de spawn libre où le problème avait été découvert.

## Lecture prudente — hypothèse, pas fait établi

Ce résultat **affaiblit, sans la réfuter**, l'hypothèse portée depuis l'attempt #9/#11 selon
laquelle le raccourci de luminosité serait dû à un manque de diversité d'éclairage dans les données
d'entraînement Minecraft-spécifiques du projet (Treechop, quasi exclusivement diurne). Un modèle
entraîné sur un corpus web de plusieurs ordres de grandeur plus divers en éclairage que tout corpus
collectable dans ce projet reproduit — et même dépasse en intensité — le même raccourci. Si la
diversité de données suffisait à éliminer ce raccourci, on ne s'attendrait pas à le retrouver aussi
fort chez CLIP.

Une lecture alternative, non exclue : « une forêt dense est physiquement plus sombre qu'un champ
ouvert » pourrait être un signal réel et légitime à capter, pas une erreur de raisonnement — la
luminosité et la présence de forêt sont authentiquement corrélées dans le monde (et dans son
imitation par le jeu).

Mais cette lecture alternative ne suffit pas à tout expliquer : une frame spécifique de **grotte
sombre, sans arbre**, a été groupée par CLIP avec les scènes ouvertes et claires (« pas de forêt »),
et non avec un profil « forêt sombre » — ce qu'une histoire de pure luminosité prédirait pourtant.
Quelque chose d'autre que la luminosité brute intervient donc dans le score de CLIP, sans qu'on
puisse dire précisément quoi à ce stade. **Ceci est explicitement laissé comme question ouverte, pas
comme fait établi** — cohérent avec la discipline d'honnêteté du projet sur les résultats
non tranchés.

## Phase 2 : fine-tuning direct de `ebwm.pt` avec augmentation photométrique — résultat mitigé

Plutôt que de poursuivre la piste CLIP zero-shot elle-même, ou d'exiger d'un futur correctif qu'il
devienne explicitement invariant à la luminosité (au risque de retirer un signal potentiellement
légitime, comme discuté ci-dessus), la décision prise à l'issue de la phase 1 était de procéder
directement à un fine-tuning du modèle du monde du projet sur un mélange de données garanties-forêt
(Treechop) et de données de spawn libre réelles (démonstrations expertes Obtain + épisodes
d'exploration aléatoire), **puis de re-vérifier directement si le problème d'inversion original
(attempt #10, Chapitre 11) disparaît — quel que soit le mécanisme qui médiatise ce changement** —
plutôt que d'imposer une contrainte d'indépendance à la luminosité comme critère de succès. Cette
phase est maintenant conclue.

**Méthode** : reprise (warm-start) de `ebwm.pt` — même architecture, pas un réentraînement depuis
zéro — sur le mélange Treechop + spawn libre expert + exploration aléatoire décrit ci-dessus, avec
**augmentation photométrique** (jitter de luminosité/contraste/saturation, randomisé mais appliqué de
façon cohérente sur toute une séquence courte, pas frame par frame) injectée directement dans
l'entraînement du modèle du monde lui-même — pas dans un module additionnel comme dans les tentatives
précédentes (le repair ColorJitter de l'attempt #7, puis l'attempt #11). C'est la première fois dans toute la
campagne que cette augmentation est appliquée au modèle principal plutôt qu'à un composant greffé.

**Gates de sécurité** : passées proprement aux 5 epochs d'entraînement — pas de collapse de
représentation (voir Chapitre 2), qualité de prédiction quasi inchangée (attendu : l'objectif était
un ajustement léger, pas un réentraînement complet).

**Le vrai test** : re-exécution du diagnostic exact de l'attempt #10 sur chacun des 5 snapshots
fine-tunés. Résultat authentiquement mixte, pas un win propre :

- En excluant une frame précise — une scène sombre de type grotte/sous-marine, sans arbre — le
  correctif paraît propre : sur les 5 snapshots, les scènes arbre-proche notent maintenant
  correctement plusieurs fois plus haut que les scènes ouvertes/sans arbre — un vrai renversement du
  sens par rapport à l'inversion d'origine.
- En incluant cette même frame, le résultat repart dans le mauvais sens sur chacun des 5 snapshots,
  parce que le score de cette frame précise **s'est dégradé** après le fine-tuning, pas amélioré — une
  anomalie nouvelle, liée à la faible luminosité, apparaissant à un endroit différent de
  l'attempt #11, mais reconnaissable comme appartenant à la même famille de raccourci lié à la
  luminosité (Chapitre 12 / attempt #11, et la phase 1 CLIP de ce même chapitre).

Aucun snapshot fine-tuné n'a été promu au rang de checkpoint de référence ; aucun test en jeu réel
(live) n'a été effectué, conformément à la règle du projet de ne réserver un test live qu'à un
candidat ayant clairement passé son gate offline d'abord — ce qui n'est pas le cas ici.

**Pourquoi c'est significatif** : c'est la quatrième fois, avec quatre approches mécaniquement
différentes, qu'une anomalie liée à la luminosité apparaît — un petit module additionnel entraîné sur
des features figées (attempt #7) ; ce même module ré-entraîné spécifiquement sur des données Obtain
(attempt #11) ; un modèle vision-langage géant, hors-domaine, jamais touché (CLIP, phase 1 de ce
chapitre) ; et maintenant un réentraînement direct du modèle du monde lui-même avec une vraie
augmentation photométrique — l'attaque la plus directe tentée jusqu'ici sur ce problème précis. Ceci
affaiblit sensiblement l'hypothèse « le modèle n'a simplement pas vu assez de diversité d'éclairage » :
même la tentative la plus directe et la plus soignée pour corriger exactement ce manque de diversité
a produit une nouvelle anomalie plutôt qu'un correctif propre.

## Décision pour la suite

La condition que le projet s'était fixée pour engager la piste candidate 3 du menu du Chapitre 11 —
**H-JEPA**, un second modèle du monde hiérarchique, plus lent, planifiant « trouver une forêt » sur un
horizon long avant de rendre la main au modèle rapide existant pour le geste de coupe — était
explicitement « seulement si le correctif direct et moins coûteux échoue ». Cette condition est
désormais remplie par des preuves empiriques (la phase 2 ci-dessus étant la tentative de correctif
direct la plus poussée du projet à ce jour), et non plus seulement par un argument plausible. Le
projet s'oriente donc vers H-JEPA comme prochaine direction, plutôt que de continuer à itérer sur des
correctifs directs de `ebwm.pt` ou de ses modules additionnels.

`ebwm.pt` (le checkpoint de référence) n'est modifié ni par le diagnostic CLIP (modèle tiers, jamais
chargé pour la planification) ni par le fine-tuning de la phase 2 : les 5 snapshots produits sont
conservés séparément versionnés, selon la convention déjà suivie pour chaque variante de ce projet
(`craft_wm_v4_coverage.pt`, `value_projector_obtain.pt`, etc.) — aucun remplacement silencieux du
checkpoint de référence.

## Références

CLIP (Radford, Kim, Hallacy, Ramesh, Goh, Agarwal, Sastry, Askell, Mishkin, Clark, Krueger, Sutskever,
*Learning Transferable Visual Models From Natural Language Supervision*, 2021) est utilisé ici en
zero-shot, hors-domaine, comme diagnostic externe — ce projet n'a **pas** d'identifiant arXiv vérifié
pour CLIP dans `docs/references/index.md` à ce jour, et n'en invente aucun ici, conformément à la
règle du projet de ne citer que des références déjà vérifiées dans ce fichier. Ce chapitre s'appuie
par ailleurs sur le diagnostic de l'attempt #10 (Chapitre 11) et le raccourci de luminosité confirmé
trois fois à l'attempt #11 (Chapitre 12), déjà documentés sans nouvelle citation bibliographique.

:::

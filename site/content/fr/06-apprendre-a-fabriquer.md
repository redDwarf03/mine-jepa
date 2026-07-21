---
title: "Apprendre à fabriquer : la règle est comprise, le premier arbre reste hors de portée"
slug: "06-apprendre-a-fabriquer"
lang: "fr"
order: 6
prerequisites: ["01-c-est-quoi-jepa", "02-le-piege-du-collapse", "03-le-modele-du-monde", "04-planifier-en-imagination", "05-le-vrai-minecraft"]
source_docs: ["docs/08_crafting.md", "CLAUDE.md#Phase 5 gates"]
---

::: beginner

## Le prochain objectif : fabriquer un outil

Le Chapitre 5 s'est arrêté sur une vraie victoire : l'agent coupe du bois en vrai Minecraft,
environ une fois sur quatre. La suite logique, c'est de lui apprendre à faire quelque chose
*avec* ce bois — le transformer en planches, puis en outil. Le rêve de départ était « une IA qui
fabrique une épée en bois ». Petit contretemps amusant : dans la version de Minecraft utilisée
par ce projet (MineRL 0.4.4), **l'épée en bois n'existe tout simplement pas** comme action de
fabrication — seule la branche technologique qui mène à la pioche est câblée dans le jeu. Le
nouvel objectif devient donc : couper une bûche, puis la transformer en planches, en bâton, poser
une table d'établi, et fabriquer une pioche en bois. La chaîne complète de fabrication.

Pour ça, le projet change d'environnement : au lieu de Treechop (« coupe un arbre, rien
d'autre »), il passe à `MineRLObtainIronPickaxeDense`, une version de Minecraft qui donne accès à
l'inventaire du joueur (combien de bûches, de planches, de bâtons il possède) et qui récompense
chaque objet obtenu (une bûche vaut 1 point, une planche 2, etc.).

## Premier essai : deviner l'inventaire depuis l'image → ça ne peut pas marcher

La première idée semblait naturelle : garder l'encodeur qui résume l'image (Chapitre 1), et lui
coller une petite extension qui essaie de *deviner* l'inventaire à partir de cet embedding (ce
résumé en nombres de l'image).

Ça ne pouvait pas marcher, et la raison est presque évidente une fois qu'on la voit : **l'écran
ne montre jamais le nombre de planches que tu possèdes.** Quand tu fabriques des planches dans
Minecraft, l'image à l'écran ne change presque pas — le compteur « planches : 36 » est une donnée
à part, jamais dessinée dans la vue à la première personne. Résultat : cette extension n'apprend
que des vagues corrélations de décor (« scène de forêt → peu de planches », « près d'une table →
plus de planches »), jamais la vraie règle. Et comme l'image ne change presque pas pendant qu'on
fabrique, le world model se contente de « copier » l'embedding précédent — sa prédiction ne
change quasiment rien. En jeu, cet agent ne fait rien d'utile. Un échec net, mais qui apprend
quelque chose d'important.

## L'idée clé de ce chapitre

> **Fabriquer un objet, ce n'est pas un problème d'image. C'est un problème d'état discret —
> le compteur d'objets qu'on possède.**

Puisqu'on ne peut pas deviner l'inventaire depuis l'image, il faut que l'inventaire devienne une
**entrée** du world model — une donnée qu'on lui fournit directement, au lieu d'essayer de la lui
faire retrouver depuis les pixels. C'est exactement pour ça que Minecraft, dans cette version de
l'environnement, donne l'inventaire comme observation séparée : le jeu sait bien que ce n'est pas
visible à l'écran.

## Deuxième essai : l'inventaire comme mémoire du modèle → ça marche

La nouvelle version du world model (appelée WM v4 dans le projet) sépare deux choses :

- une partie **visuelle** — l'eb-JEPA du Chapitre 5, qui comprend « y a-t-il un arbre devant
  moi ? suis-je près d'une table ? » ;
- une partie **inventaire** — une petite fonction ajoutée au modèle qui prend l'inventaire
  actuel, l'action choisie, et ce que voit la partie visuelle, et qui prédit le *nouvel*
  inventaire.

Concrètement : `nouvel_inventaire = ancien_inventaire + changement(ancien_inventaire, action,
ce_que_je_vois)`. En entraînant cette fonction sur les parties d'humains, le modèle a appris,
tout seul, une règle simple mais très concrète : **fabriquer avec une bûche produit quatre
planches** — exactement la vraie recette de Minecraft, apprise sans jamais être écrite dans le
code, juste observée dans les données.

## Le piège des démonstrations humaines : personne ne rate jamais un craft

Un modèle qui sait « fabriquer → +4 planches » n'est pas suffisant. Une fois mis en jeu, l'agent
s'est mis à **appuyer sur « fabriquer » en boucle, même sans aucune bûche en poche** — ce qui,
bien sûr, ne produit rien.

La raison est amusante et instructive : **aucun joueur humain n'essaie de fabriquer quelque chose
sans en avoir les ingrédients.** Les enregistrements de parties humaines utilisées pour
l'entraînement ne contiennent donc *aucun* exemple de craft raté. Le modèle a appris « fabriquer
→ +4 planches » de façon absolue, sans jamais voir qu'il fallait une bûche au préalable. C'est un
piège classique de l'apprentissage à partir de démonstrations d'experts : **des experts ne
montrent jamais leurs échecs**, donc le modèle n'apprend jamais les conditions qui doivent être
réunies avant d'agir.

La solution retenue ici, sans attendre une boucle complète d'exploration autonome (le sujet des
prochains chapitres) : fabriquer artificiellement des **exemples négatifs**. On dit au modèle,
explicitement : « si tu fabriques sur un inventaire vide, le résultat est zéro ». Il a fallu
doser cet ajout avec soin — la première tentative, trop appuyée, a écrasé le signal positif (le
modèle s'est mis à prédire quasiment zéro planche *tout le temps*, même sur les vrais crafts
réussis). Le bon équilibre : donner beaucoup plus de poids aux rares moments de craft réel dans
les données (144 sur 85 000 instants, largement noyés sinon) et une pénalité plus modérée pour le
craft sur inventaire vide. Résultat final : le modèle sait *à la fois* « craft + bûche → +4
planches » *et* « craft + inventaire vide → rien ». L'agent arrête de fabriquer dans le vide.

## Un planificateur qui change d'objectif selon ce qu'il a en poche

Le planificateur (celui du Chapitre 4, qui imagine plusieurs futurs et choisit le meilleur) reçoit
maintenant deux objectifs possibles, et choisit selon l'inventaire :

- **pas de bûche** → objectif « couper du bois » (la même astuce qu'au Chapitre 5) ;
- **au moins une bûche** → objectif « maximiser le gain d'inventaire » (planches, bâtons...).

## La preuve que la fabrication marche, en vrai Minecraft

Pour vérifier que la fabrication marche *vraiment*, indépendamment du problème « trouver le
premier arbre » (qui reste dur, on va y venir), le projet lance l'agent dans une version de test
de l'environnement qui démarre directement avec du bois en poche (5 bûches, 3 planches). Sur 6
épisodes, **100% de réussite** : l'agent fabrique à chaque fois entre 16 et 20 planches
supplémentaires, avec une récompense de 10 points. C'est un agent qui planifie et exécute
lui-même toute la chaîne de fabrication — on lui donne juste le bois de départ.

Petite remarque amusante et cohérente avec tout ce chapitre : **on ne voit rien à l'écran pendant
que l'agent fabrique.** La preuve de la réussite, ce n'est pas une image impressionnante — c'est
le compteur d'inventaire et la récompense qui montent. Exactement la raison pour laquelle
l'inventaire a dû devenir une mémoire du modèle plutôt qu'une chose à deviner depuis l'image.

## Le mur qui reste : trouver le premier arbre, seul

Voici l'honnêteté qui clôt ce chapitre. Une fois lâché dans le vrai jeu, en mode survie, sans
bois de départ, l'agent se comporte de façon sensée — il passe tout son temps en mode « couper du
bois », avance de façon dirigée plutôt qu'au hasard — mais sur 5 épisodes, il n'a coupé **aucune
bûche**.

Pourquoi c'est plus dur qu'au Chapitre 5 : dans Treechop (Chapitre 5), le joueur apparaît toujours
au milieu d'une forêt dense, avec des arbres garantis dans son champ de vision. Ici, le joueur
apparaît **n'importe où** dans un monde de survie généré au hasard — les arbres peuvent être
loin, cachés derrière une colline, ou totalement absents du champ de vision de départ. L'agent
doit d'abord **chercher** un arbre avant de pouvoir le couper, une capacité que rien, jusqu'ici,
ne lui a jamais appris.

**Le bilan honnête de ce chapitre** : la partie « comprendre la règle de fabrication » est
résolue — le world model a vraiment appris la recette, et l'agent fabrique parfaitement une fois
qu'il a du bois. Le vrai problème ouvert, c'est de trouver ce premier arbre depuis un point de
départ aléatoire. C'est le sujet des chapitres suivants.

:::

::: expert

## Objectif de la Phase 5 et choix de l'environnement

`MineRLObtainIronPickaxeDense-v0` remplace Treechop comme banc de test. `wooden_sword` n'a pas de
handler de craft dans MineRL 0.4.4 (`CraftNearbyAction` ne couvre que la branche pioche) ;
l'objectif devient donc la chaîne équivalente `log → planks → stick → crafting_table → wooden
pickaxe`. L'environnement apporte trois éléments absents de Treechop : l'inventaire dans
l'observation, une récompense dense par objet (log=1, planks=2, stick=4, …) et une action
`craft` discrète (pas de menu GUI). Démonstrations : Zenodo `MineRLObtainIronPickaxe-v0.zip`
(2,8 Go), 40 demos préparées via `scripts/prepare_demos_obtain.py` → 84 902 frames, **144 pas de
craft-planks**, 37/40 démos atteignant une pioche en bois, espace d'action à **22 classes**
(17 mouvement + 5 craft, `configs/minerl_actions_obtain.yaml`).

## Tentative 1 — WM v3 : inventaire comme tête de prédiction → échec structurel

```
frame → [encodeur visuel] → latent → [tête inventaire] → inventaire prédit
```

Défaut fondamental : la vue à la première personne (64×64) ne contient jamais le compteur
d'inventaire — "planks: 36" n'est jamais rendu à l'écran. Conséquences mesurées :

- la tête n'apprend que des corrélations de scène (stade de partie ↔ inventaire probable), jamais
  le mécanisme causal ;
- la scène étant quasi statique pendant un craft, le predictor **copie** (ratio ≈ 0,98, la même
  métrique `val_pred/val_copy` définie au Chapitre 3) ;
- au moment de planifier, l'action `craft` ne change pas le latent visuel prédit → la tête
  d'inventaire lit le *même* inventaire prédit → gain de planches prédit = 0 → **planificateur
  aveugle au craft.**

## L'insight structurant

> **La fabrication est un problème d'état discret d'inventaire, pas un problème de pixels.**

L'inventaire doit être une **variable d'état du world model** (une entrée), pas une quantité
prédite depuis la frame — cohérent avec le fait que MineRL l'expose comme observation séparée
plutôt que de la rendre à l'écran.

## Tentative 2 — WM v4 : inventaire comme variable d'état → la règle est apprise

```
Perception (pixels)              État discret (inventaire)
─────────────────                ──────────────────────────
eb-JEPA visuel                   InventoryDynamics (MLP)
"arbre devant ? table proche ?"   inv_{t+1} = inv_t + g(inv_t, action, latent_visuel)
```

L'inventaire devient une **entrée** ; la dynamique `g` (petit MLP) est conditionnée par le latent
visuel, donc apprend à la fois le chop (attack + visuel-arbre → log+1) et le craft (craft + log →
planks+4). Résultat mesuré, `dPlanks@craft` (Δplanks prédit sur les vrais pas de craft-planks) :

```
epoch 1: +1,24    epoch 4: +4,01    epoch 20: +3,81
```

`dPlanks@craft ≈ +4` est exactement la recette Minecraft (1 log → 4 planks), apprise purement
depuis des démonstrations — pas codée en dur. Ce résultat est directement dans l'esprit de Yu et
al. (arXiv:2509.12249, *Why and How Auxiliary Tasks Improve JEPA Representations*, NeurIPS 2025) :
une tête auxiliaire (`InventoryDynamics`) entraînée conjointement avec la dynamique latente
maintient des observations non-équivalentes bien distinctes — leur théorème de *No Unhealthy
Representation Collapse* est exactement le mécanisme derrière la conception de WM v4.

## Le piège de la précondition (le trou des démos expertes)

En jeu, l'agent v4 **fabrique en continu sur un inventaire vide** (`a17 = 30%` des pas),
n'obtenant rien. Cause : aucune démo humaine ne montre un craft raté (`craft` sur inventaire vide)
— le modèle apprend « craft → +4 » **sans condition**, `dPlanks@craft = +4` paraissant parfait
précisément parce que mesuré uniquement sur des pas de craft qui possédaient toujours une bûche.
C'est l'argument le plus direct en faveur de la curiosité/self-play (chapitres suivants) : un
agent qui crafte sur inventaire vide et observe l'absence d'effet **apprend** la précondition par
sa propre erreur de prédiction.

### La correction : négatifs synthétiques + pondération équilibrée

- **Négatif synthétique** : imposer aux pas de craft `g(inventaire vide, craft, visuel) ≈ 0`.
- **Équilibrage** : les transitions de craft sont rares (144/85k). Un poids de précondition naïf
  (5,0) a **écrasé** le signal positif — le modèle a pris le raccourci « toujours prédire ~0
  planche » (`dPlanks` s'est effondré de +4 à +0,4). Correction : **sur-pondérer ×30** les rares
  transitions positives de craft, poids de précondition modéré (2,0).

**Résultat équilibré** : `dPlanks@craft ≈ +3,8` **et** `precond ≈ 0,0001`. Le modèle sait
désormais *à la fois* « craft + log → +4 planks » *et* « craft + vide → rien ». En jeu, l'agent
arrête de fabriquer inutilement.

## Le planificateur : basculer d'objectif selon l'état d'inventaire

`SwitchingCraftPlanner`, un seul MPC (Chapitre 4), deux objectifs :

```
pas de log   → CHOP  : rapprocher le latent visuel du centroïde "log obtenu"
                       (l'astuce Treechop du Chapitre 5)
log présent  → CRAFT : maximiser le gain d'inventaire prédit (Δlog, Δplanks) via g
```

Combine deux briques déjà validées séparément — le chop (centroïde de but) et le craft (WM v4).

## Démo live du craft — fabrication réussie en vrai Minecraft

Pour isoler la preuve du bouclage craft *sans* la difficulté du cold-start chopping, l'agent est
lancé sur `MineRLObtainTest-v0` (env de debug, log=5 planks=3 au spawn, monde plat). Résultat
sur 6/6 épisodes : **100% de réussite, +16 à +20 planches par épisode (5 logs × 4 planks),
récompense 10.** La fabrication est planifiée et exécutée par l'agent — seul le bois de départ
est offert.

> Rappel important : **le craft est invisible dans la vue à la première personne** — l'écran ne
> change presque pas. La preuve est l'inventaire/la récompense (+20 planches, reward 10), pas un
> GIF. C'est exactement la raison pour laquelle l'inventaire a dû devenir une variable d'état du
> world model plutôt qu'une cible visuelle.

## Le mur qui reste : le cold-start chopping en survie

Avec le planificateur à bascule, le comportement est sensé (mode chop dominant, actions `a1`/`a13`
majoritaires, pas de vagabondage aléatoire) mais sur 5 épisodes : **0 bûche coupée.**

Raisons identifiées :

- **Treechop spawn en forêt dense** (arbres garantis dans le champ de vision) → l'agent Treechop
  coupe 25-50% (Chapitre 5). **`ObtainIronPickaxeDense` spawn dans un biome de survie aléatoire**
  — arbres potentiellement loin, derrière une colline, ou absents de la vue initiale. L'agent
  doit d'abord *trouver* un arbre.
- Le predictor visuel copie (ratio ≈ 0,98) sur des frames quasi statiques → le planificateur ne
  peut pas « imaginer » vivement se tourner vers un arbre → l'objectif chop est un signal de
  pilotage faible.
- Les épisodes se terminent souvent tôt (~750-1500 pas) sur des dangers de survie.

## Bilan honnête

| Composant | Statut |
|-----------|--------|
| WM apprend la règle de craft (1 log → 4 planks) | ✅ `dPlanks@craft = +3,8` |
| WM apprend la précondition (pas de log → pas de craft) | ✅ `precond ≈ 0` |
| World model inventaire-comme-état (v4) | ✅ `checkpoints/craft_wm_v4.pt` |
| Planificateur à bascule (chop ↔ craft) | ✅ bascule correcte en jeu réel |
| Craft **en direct, bois fourni** | ✅ 100% sur 6 ép., +16-20 planches/ép. |
| Craft de bout en bout depuis un **cold start** | ❌ bloqué par le cold-start chopping en survie |

**La fabrication est résolue au niveau du world model. Obtenir la première bûche dans un monde
de survie aléatoire est le problème ouvert** — de la même famille que le 25-50% de Treechop, en
plus dur ici.

## Leçons

1. **Fabriquer ≠ pixels.** L'inventaire n'est pas dans la frame ; il doit être une variable d'état
   du world model (v3 → v4 rend cette leçon concrète).
2. **Un world model peut apprendre une règle symbolique de jeu** depuis des démonstrations —
   `dPlanks = +4` est la recette Minecraft, apprise, pas codée.
3. **Les démos expertes enseignent des actions, pas des préconditions.** Sans exemple de craft
   raté, le modèle croit que fabriquer marche toujours. Les négatifs (synthétiques, ou via
   curiosité/self-play) sont requis.
4. **Les signaux rares mais critiques doivent être sur-pondérés** — et l'équilibre compte : 144
   pas de craft noyés dans 85k étaient invisibles jusqu'au poids ×30 ; une précondition trop
   forte a ensuite écrasé ce même signal.
5. **Connaître son verrou.** La partie conceptuellement dure (le craft) est résolue ; le vrai mur
   (le cold-start chopping) est nommé honnêtement plutôt que noyé sous un titre de « milestone
   complet ».

## Références (vérifiées, tirées de docs/references/index.md)

- Yu et al., *Why and How Auxiliary Tasks Improve JEPA Representations*, arXiv:2509.12249
  (NeurIPS 2025) — justifie directement le design de `InventoryDynamics` comme tête auxiliaire
  ancrée sur la dynamique latente.
- Maes, Le Lidec, Scieur, LeCun, Balestriero, LeWorldModel, arXiv:2603.19312 (2026) — la
  convention `ratio = val_pred/val_copy` réutilisée pour diagnostiquer l'échec de WM v3.

:::

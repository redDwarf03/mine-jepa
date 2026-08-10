---
title: "Le premier vrai réentraînement du cœur du modèle : deux leviers, deux échecs bien compris, une pause choisie"
slug: "19-deux-leviers-deux-echecs-compris"
lang: "fr"
order: 19
prerequisites: ["01-c-est-quoi-jepa", "02-le-piege-du-collapse", "03-le-modele-du-monde", "04-planifier-en-imagination", "05-le-vrai-minecraft", "06-apprendre-a-fabriquer", "07-la-curiosite-en-panne", "08-le-mur-est-comportemental", "09-les-prochaines-pistes", "10-le-negatif-le-plus-net", "11-la-boussole-a-l-envers", "12-la-memoire-des-lieux-visites", "13-le-sauvetage-aveugle", "14-un-geant-du-web-a-l-epreuve", "15-cinquieme-confirmation-fausse-alerte", "16-predire-l-avenir-pas-l-image", "17-le-raccourci-est-dans-l-oeil", "18-la-victoire-qui-n-a-pas-tenu"]
source_docs: ["CLAUDE.md#Phase 5+ — Cold-start attempt #19"]
---

::: beginner

## Là où on en était

Le Chapitre 18 s'est terminé sur une vraie décision, prise le 28 juillet 2026 par l'utilisateur
du projet : après **dix-huit tentatives** pour réparer, de l'extérieur, la façon dont le modèle
principal (`ebwm.pt`) juge « y a-t-il un arbre proche ? », toutes tombées sur le même piège de
luminosité, il était temps d'essayer autre chose — **toucher pour la première fois au cœur même
de ce modèle**, plutôt que de continuer à empiler des béquilles autour de lui sans jamais
rouvrir le capot. Deux idées précises et chiffrées étaient sur la table, trouvées au chapitre
précédent : élargir le vocabulaire de gestes que le modèle a appris à reconnaître, et changer
l'ingrédient anti-effondrement qui l'empêche de « tricher » en apprenant à tout confondre.

Ce chapitre raconte ce qui s'est passé quand ces deux idées ont été essayées pour de vrai. Les
deux ont échoué — mais **chacune pour une raison précise qu'on a comprise**, pas dans le flou. Et
la décision qui suit n'est pas un abandon : c'est une pause choisie.

## Levier 1 : apprendre au modèle plus de gestes

Souvenez-vous du Chapitre 18 : un test avait montré que dans les parties où l'expert coupe des
arbres, le modèle n'a presque jamais vu certains gestes — sauter, se déplacer sur le côté,
regarder vers le haut ou vers le bas. Sur dix-sept gestes possibles, seuls huit apparaissaient
vraiment dans les données d'entraînement d'origine.

Le correctif était concret : relire les parties enregistrées et **récupérer** ces gestes qui
étaient là depuis le début, mais que le programme qui prépare les données ne savait pas encore
lire correctement. Une fois corrigé, presque tous les gestes apparaissent (quinze sur dix-sept
au lieu de huit). Le modèle a ensuite été réentraîné, en partant de ses poids actuels — pas
depuis zéro — avec un taux d'apprentissage très prudent (l'équivalent d'ajuster à petits pas,
pas de tout rebattre), pendant cinq passages complets sur les données.

**Résultat : ça n'a pas marché.** Le test qui mesure si le modèle distingue bien « arbre proche »
de « pas d'arbre » a échoué avant ET après ce réentraînement, sans amélioration progressive au
fil des cinq passages. Le vocabulaire de gestes s'est bien élargi, mais la façon dont le modèle
juge une scène ne s'est pas améliorée pour autant.

### Pourquoi ? Une enquête, pas une supposition

Face à cet échec, l'équipe s'est posé la bonne question avant de passer à autre chose : *pourquoi*
ça n'a pas marché ? Une première explication simple est venue à l'esprit — peut-être qu'en
ajoutant l'étiquette « sauter », le programme avait accidentellement effacé l'étiquette
« frapper » sur les mêmes images (un peu comme si, en cochant une nouvelle case sur un
formulaire, on décochait une case déjà remplie par erreur). **Cette explication a été vérifiée
deux fois, avec des comptages exacts** — et elle est fausse : le nombre d'images étiquetées
« frappe » est resté rigoureusement identique, image pour image, avant et après.

Ce qui a vraiment changé : environ 5 images sur 100 ont changé d'étiquette, et l'écrasante
majorité de ce changement, ce sont des images où l'expert avançait ET sautait en même temps (une
« bunny-hop », une technique de déplacement bien réelle dans Minecraft) — un vrai geste qu'on a
enfin appris à voir, pas une erreur.

L'explication la plus solide (mais **pas encore prouvée**, l'équipe est honnête là-dessus) :
ces gestes rares représentaient environ 1 % de l'attention d'entraînement du modèle avant la
correction, et sont soudainement passés à environ 4 % après — jusqu'à 9 fois plus sur certaines
combinaisons de gestes. C'est un peu comme si un élève qui avait quasiment jamais pratiqué le
piano recevait d'un coup neuf fois plus d'heures de cours que d'habitude sur cet instrument :
même si ses autres matières ne changent pas, le choc de ce nouvel apprentissage déséquilibre ses
habitudes générales. Une suite plus prudente (introduire ces gestes plus progressivement) a été
envisagée mais pas essayée — l'utilisateur a préféré passer directement au deuxième levier.

## Levier 2 : changer l'ingrédient anti-effondrement

Le deuxième levier touchait à quelque chose de plus profond : l'ingrédient qui empêche le modèle
de « tricher ». Rappel du Chapitre 2 : un modèle JEPA peut apprendre à représenter *toutes* les
images de la même façon (un effondrement, ou « collapse ») parce que ça minimise artificiellement
son erreur sans rien apprendre d'utile. Ce projet utilise depuis le début un ingrédient appelé
VICReg pour empêcher ça. Deux publications scientifiques récentes affirment qu'un ingrédient plus
récent, appelé **SIGReg**, serait plus fiable en théorie.

Avant même de coder quoi que ce soit, un examen du code existant a révélé une surprise : la
version de VICReg réellement utilisée dans ce projet n'était déjà, depuis le début, qu'une
**moitié** de la recette complète — un seul des deux mécanismes que la théorie prévoit. Ça a
simplifié le remplacement par SIGReg : pas besoin de reconstruire une architecture entière,
juste d'échanger un ingrédient contre un autre au même endroit.

Le nouvel ingrédient a été testé avec la recette **la plus prudente de toute la campagne** :
taux d'apprentissage encore plus bas que le Levier 1, seulement trois passages maximum sur les
données, et surtout — un **nouveau garde-fou construit spécialement pour ce test**, capable de
détecter un type d'effondrement que l'ancien outil de surveillance ne peut pas voir.

### Un effondrement d'un genre différent, détecté avant qu'il ne fasse trop de dégâts

Voici l'explication de ce nouveau danger, avec une image simple. Le vieil outil de surveillance
du projet (`batch_var`, utilisé depuis le Chapitre 2) mesure si les représentations du modèle
sont devenues toutes *identiques* — un effondrement « en hauteur », comme si toute une classe
d'élèves donnait exactement la même réponse à chaque question. Mais il existe un **deuxième
genre d'effondrement**, plus sournois : les représentations restent bien différentes les unes
des autres dans l'ensemble (donc `batch_var` ne voit rien d'anormal), mais tout ce qui les rend
différentes se concentre sur une poignée de détails, alors que le modèle avait auparavant plus
de quatre mille façons différentes de varier. C'est comme si toute la classe continuait à donner
des réponses variées, mais que ces réponses ne portaient plus que sur 4 ou 5 sujets au lieu de
plusieurs milliers — une richesse illusoire.

**C'est exactement ce qui s'est passé, dès le tout premier passage sur les données**, et le
nouveau garde-fou l'a détecté et a arrêté l'entraînement avant de continuer inutilement : le
nombre effectif de « directions utiles » dans les représentations du modèle s'est effondré de
26,7 à 4,5 — une chute de 83 % — pendant que le vieil outil de surveillance affichait un chiffre
parfaitement sain, aussi bon que n'importe quel bon entraînement précédent. Sans ce nouveau
garde-fou, personne ne s'en serait aperçu à temps.

Sur cet unique instantané du modèle sauvé avant le naufrage complet, le test central (« distingue
bien arbre proche de pas d'arbre ») a donné un résultat **encore pire** que le Levier 1 — et le
test sur la tâche d'origine du modèle (couper des arbres dans le jeu simple) s'est quasiment
effondré aussi. Ce nouvel ingrédient, tel qu'essayé ici, a cassé le modèle plus largement qu'il
ne l'a réparé.

Important : cet échec-là n'est **pas** compté comme une septième confirmation du fameux piège de
luminosité des chapitres précédents. C'est un problème d'une autre nature — un effondrement des
représentations, pas une confusion entre couleur et distance. Les deux problèmes se ressemblent
dans leurs symptômes (« le modèle rate le test ») mais pas dans leur cause.

## La décision : une pause, pas un abandon

Face à deux leviers, deux échecs, chacun désormais bien compris (pas juste « ça n'a pas marché »
mais « voici pourquoi »), l'utilisateur a choisi de **mettre la campagne en pause** plutôt que
d'enchaîner tout de suite sur un troisième levier. C'est une décision importante à ne pas mal
lire : ça ne veut **pas** dire que réentraîner le cœur du modèle est impossible. Ça veut dire que
ces deux implémentations précises, les moins coûteuses disponibles pour chaque idée, ont chacune
échoué pour une raison désormais identifiée — pas par manque d'essai, mais par un vrai problème
technique repéré et expliqué.

Ce qui reste debout et fonctionne, comme référence positive du projet : la règle qui empêche
l'agent d'abandonner son plan trop vite, la recherche qui pousse l'agent à explorer le terrain
plutôt que de tourner en rond, et le réflexe anti-noyade. Aucun de ces trois mécanismes n'a été
touché par cette tentative — ni `ebwm.pt` lui-même, qui reste identique à avant, vérifié à
l'octet près.

:::

::: expert

## Contexte

Le Chapitre 18 (attempt #18, `CLAUDE.md#Phase 5+`) a clos la campagne sur une décision utilisateur
du 2026-07-28 : après 18 tentatives de correction *externe* de la notation goal-centroid de
`ebwm.pt` (têtes entraînées sur latents gelés, modèles hors-ligne, features faites main,
statistiques closed-form — 6 confirmations indépendantes du même confound luminosité/composition
de scène), retravailler l'objectif d'entraînement **du cœur** de `ebwm.pt` lui-même — jamais fait
en 18 tentatives, toujours frozen ou légèrement nudgé (attempt #14 Phase 2). Deux leviers
concrets, scopés par le Diagnostic 2 de l'attempt #18, étaient sur la table : (1) élargir la
couverture d'action propre de Treechop et/ou repondérer vers le mix d'actions d'Obtain
(motivé par Zhang et al., [arXiv:2607.22430](https://arxiv.org/abs/2607.22430)) ; (2) remplacer
VICReg par SIGReg (Balestriero & LeCun, [arXiv:2511.08544](https://arxiv.org/abs/2511.08544) ;
Arnez & Gomez-Villa, [arXiv:2607.13612](https://arxiv.org/abs/2607.13612)). Ce chapitre couvre
l'attempt #19 tel qu'enregistré dans `CLAUDE.md#Phase 5+`. **Non encore répercuté dans
`docs/10_coldstart_engineering.md`** au moment de l'écriture — `CLAUDE.md` est la seule source
pour cette tentative.

## Run A — élargir la couverture d'action de Treechop : NO-GO, diagnostiqué (pas juste échoué)

`scripts/prepare_demos.py::discretize_actions()` étendu pour lire
`action$jump/left/right/back` + l'inclinaison de caméra (pitch) — auparavant seuls
forward/attack/sprint/yaw étaient lus. La couverture d'indices d'action propre de Treechop passe
de 8/17 à 15/17. Fusionné avec les données Obtain exactement comme l'attempt #14 Phase 2,
fine-tuné 5 epochs à partir des poids courants de `ebwm.pt` (LR=3e-5, VICReg intact, seed=0,
snapshots `ebwm_v3_actioncoverage_epoch{1..5}.pt`, `ebwm.pt` jamais touché, md5 revérifié).

| Gate | Résultat |
|---|---|
| A — séparation (jeu étendu à main tree_close n=10 / no_tree n=17, l'échantillon de l'attempt #18) | **FAIL sur baseline (0,790x) ET les 5 epochs (0,531x-0,775x)**, non-monotone, jamais ≥1,3x |
| C — non-régression Treechop (nouveau) | sous-test de direction invalide par construction (la baseline elle-même échoue, 0,434x — pas une régression causée par le fine-tune) — retiré du verdict, seule la bande de magnitude conservée |

JSD(Treechop, Obtain) bouge à peine : 0,1453 → 0,1585 (légèrement pire) — la couverture brute
d'indices s'est améliorée mais pas la forme distributionnelle.

### Diagnostic de cause racine (sur demande de l'utilisateur, avant de décider la suite)

Revérifié indépendamment, **deux fois**, que l'hypothèse « jump masque attack dans l'ordre de
priorité if/elif » est **FAUSSE** : les comptages de frames « attack » sont identiques à l'octet
près entre l'ancien et le nouveau jeu de données (265 454 / 265 454). Ce qui a réellement changé :
4,73 % des frames reclassées, dominées par une vraie reclassification
`forward → forward+jump` (11 626 frames, un authentique bunny-hop, un relabel correct, pas une
corruption).

> **Explication la mieux étayée (pas prouvée)** : ces indices d'action longtemps inactifs
> (jump/strafe/pitch) sont passés d'environ 1,2 % à environ 3,8 % de la masse d'entraînement
> pondérée en une seule étape (~9x sur l'indice jump+forward seul) — une injection de gradient
> soudaine sur des embeddings d'action quasiment jamais entraînés, plausiblement déstabilisant
> les poids partagés du prédicteur, même si les frames des indices déjà bien entraînés n'ont, eux,
> pas changé.

Un Run A-bis (warmup / table d'embeddings d'action gelée / LR plus bas) a été scopé mais pas
tenté — l'utilisateur a choisi de passer directement au Run B.

## Run B — VICReg → SIGReg : NO-GO, plus sévèrement cassé que Run A

Le scoping a révélé que le « VICReg » actuel de `ebwm.pt` n'est en réalité qu'un
`HingeStdLoss+CovarianceLoss` sur un seul tenseur (`state`) — `sim_coeff_t`/`idm_coeff` étaient
déjà inertes à 0, aucun mécanisme paired-view/EMA-target n'existe dans ce pipeline. Implémenté
comme un `SIGRegRegularizer` d'environ 15 lignes appelant le `BCS(state, state)` déjà vendu dans
le dépôt (même tenseur deux fois — le terme d'invariance est neutre à 0 par construction, le rôle
anti-collapse vient seul du test de gaussianité marginale d'Epps-Pulley, aucun EMA nécessaire
selon l'affirmation propre de LeJEPA « collapse-free without stop-grad »).

Remplacement complet, pas additif (`std_coeff=cov_coeff=0`, `sigreg_coeff=1.0`), jeu de données
original (non-`_v2`), augmentation désactivée pour isoler la seule variable testée, LR=1e-5
(10x plus prudent que Run A), plafond de 3 epochs avec un **nouveau garde-fou de rang effectif**
(ratio de participation sur la covariance de `state`), construit spécifiquement parce que
`batch_var` ne peut pas voir un effondrement *dimensionnel* (par opposition à isotrope).

> **Le nouveau garde-fou a fait exactement le travail pour lequel il a été construit** : l'epoch 1
> seul a déclenché un arrêt anticipé — rang effectif effondré de 26,69 à 4,50 (-83 %) pendant que
> `batch_var` restait parfaitement sain (1,36, aussi haut que n'importe quel run VICReg) — un mode
> d'effondrement réel, invisible à l'ancienne métrique, capturé avant de gaspiller les epochs 2-3.

Gates offline sur cet unique instantané : Gate A pire que la baseline de Run A (0,367x contre
0,790x, plus inversé, pas moins), Gate C sévèrement échoué (le score propre de Treechop tombe à
5,7 % de la baseline — un checkpoint génériquement cassé, pas une lecture nuancée du confound).
Gate B passe nominalement (r=0,131) mais jugé de faible valeur ici — une lecture d'indépendance à
la luminosité sur une représentation effondrée à ~4,5 dimensions effectives ne mesure pas grand-
chose. `ebwm.pt` jamais touché (md5 revérifié).

Explicitement **pas** lu comme une 8ᵉ confirmation du confound — le mode d'échec ici (effondrement
dimensionnel d'une perte anti-collapse à un seul terme, sans pression de covariance) est
mécaniquement distinct du confound luminosité/composition établi par le reste de la campagne. Un
Run B-bis atténué (`CovarianceLoss` partiellement conservée aux côtés de SIGReg, additif plutôt
que remplacement complet) a été proposé comme option mais pas tenté.

## Décision

**Décision de l'utilisateur, les deux leviers ayant échoué : pause et consolidation plutôt que
scoper immédiatement un 3ᵉ levier.** Les deux fixes concrètement scopés par le Diagnostic 2 de
l'attempt #18 sont désormais épuisés tels que spécifiés à l'origine — ce n'est pas équivalent à
« réentraîner l'objectif central de `ebwm.pt` est impossible », seulement que ces deux
implémentations spécifiques, les moins coûteuses disponibles, ont échoué pour deux raisons
distinctes, désormais diagnostiquées : instabilité par injection de gradient côté données (Run A) ;
sous-contrainte de la covariance par une perte anti-collapse à un seul terme côté architecture
(Run B). Les mécanismes non photométriques qui fonctionnaient déjà plus tôt dans la campagne
(`commit_length=4`, recherche par couverture `FrontierTracker`, correctif anti-noyade) restent les
seuls résultats positifs validés et constituent la référence courante du projet. Aucun test
MineRL/Java en direct n'a été lancé pour Run A ou Run B (correctement retenu — aucun des deux n'a
passé sa porte offline). `checkpoints/ebwm.pt` intact tout au long de l'attempt #19 (md5
`ac14e65361fbddeb057963362ea1382d`, revérifié après les deux runs) ; `ebwm_v3_actioncoverage_
epoch{1..5}.pt` et `ebwm_v3_sigreg_epoch1.pt` conservés uniquement comme artefacts de comparaison,
aucun des deux promu.

## Références

- Zhang, Guan, Zhang, Zhang, Li, « On the Identifiability of Controlled World Models »,
  [arXiv:2607.22430](https://arxiv.org/abs/2607.22430) (2026) — fondement du levier Run A
  (couverture/repondération d'action).
- Balestriero, LeCun, « LeJEPA: Provable and Scalable Self-Supervised Learning Without the
  Heuristics », [arXiv:2511.08544](https://arxiv.org/abs/2511.08544) (2025) — fondement de
  SIGReg (Run B), y compris la revendication « collapse-free without stop-grad/EMA ».
- Arnez, Gomez-Villa, « The SIGReg Objective as Variational Free Energy: A Theoretical
  Active-Inference Account of JEPA World Models », [arXiv:2607.13612](https://arxiv.org/abs/2607.13612)
  (2026) — critique théorique de VICReg motivant le Run B.

Les trois références sont vérifiées dans `docs/references/index.md`.

:::

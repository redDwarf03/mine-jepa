---
title: "Ne rien faire prédisait mieux : vingt tentatives à réparer le pilote, quand le problème était le moteur"
slug: "20-ne-rien-faire-predisait-mieux"
lang: "fr"
order: 20
prerequisites: ["01-c-est-quoi-jepa", "02-le-piege-du-collapse", "03-le-modele-du-monde", "04-planifier-en-imagination", "05-le-vrai-minecraft", "06-apprendre-a-fabriquer", "07-la-curiosite-en-panne", "08-le-mur-est-comportemental", "09-les-prochaines-pistes", "10-le-negatif-le-plus-net", "11-la-boussole-a-l-envers", "12-la-memoire-des-lieux-visites", "13-le-sauvetage-aveugle", "14-un-geant-du-web-a-l-epreuve", "15-cinquieme-confirmation-fausse-alerte", "16-predire-l-avenir-pas-l-image", "17-le-raccourci-est-dans-l-oeil", "18-la-victoire-qui-n-a-pas-tenu", "19-deux-leviers-deux-echecs-compris"]
source_docs: ["docs/10_coldstart_engineering.md#Attempt #20", "CLAUDE.md#Phase 5+ — Cold-start attempt #20"]
---

::: beginner

## Là où on s'était arrêtés

Le Chapitre 19 s'est achevé sur une pause choisie. Deux tentatives de réentraîner le cœur du modèle principal avaient toutes deux échoué, chacune pour une raison bien comprise plutôt que devinée. Dix-neuf tentatives au total, et le meilleur résultat obtenu sur l'ensemble de la campagne restait sous la barre des 10 % — un succès sur dix essais, au mieux.

Ce chapitre est le dernier de la campagne. Il contient sa découverte la plus importante, et cette découverte est venue d'une direction inattendue : non pas d'une nouvelle idée sur la façon de mieux chercher, mais d'une question que personne n'avait encore pensée à poser.

## Un article scientifique sur notre propre architecture

Une relecture de routine des publications scientifiques récentes a permis de découvrir un article étudiant presque exactement la même configuration que ce projet : la même famille de modèle du monde, planifiant dans Minecraft, en boucle fermée. L'article décrivait un mode de défaillance portant un nom précis : l'**effondrement de contexte** (*context collapse*).

L'idée est troublante dès qu'on la saisit. Un modèle du monde peut être très doué pour prédire à quoi ressemblera l'instant suivant — et pourtant produire *presque la même prédiction, peu importe ce que l'agent décide de faire*. Dans cet état, toutes les mesures habituelles semblent saines. Le modèle prédit bien. Rien ne paraît cassé. Mais un planificateur construit par-dessus est aveugle, car planifier consiste entièrement à comparer « que se passe-t-il si je fais ceci ? » avec « que se passe-t-il si je fais cela ? ». Si ces deux futurs imaginés sont presque identiques, il n'y a rien à comparer, et le choix se fait au hasard du bruit.

Dix-neuf tentatives avaient été consacrées à améliorer la façon dont l'agent cherche, la façon dont il évalue ce qu'il voit, la durée pendant laquelle il s'en tient à un plan. **Aucune n'avait jamais vérifié si le modèle du monde réagissait seulement aux actions de l'agent.**

## La mesure

Le test est simple à décrire. Prenez un moment réel d'une partie enregistrée. À partir de cette seule image, demandez au modèle d'imaginer douze pas dans le futur à deux reprises : une fois en utilisant les actions réellement effectuées par le joueur, et une fois en faisant comme si le joueur n'avait absolument rien fait. Ensuite, comparez ces deux futurs imaginés avec ce qui s'est réellement passé.

Si le modèle comprend les actions, la version utilisant les vraies actions devrait être plus proche de la réalité. C'est tout l'intérêt d'un modèle du monde.

Voici le résultat, mesuré sur 400 moments dans chacun de trois environnements différents :

**Utiliser les vraies actions prédit le futur légèrement *moins bien* que de faire comme si l'agent n'avait rien fait.**

Pas à égalité. Moins bien — et de manière fiable, pas par hasard. Dans l'environnement de fabrication (*crafting*), la vraie action ne bat l'option « ne rien faire » que dans 13 % des moments testés. Le simple hasard donnerait 50 %.

## Ce qui est cassé, précisément

Il serait facile d'en conclure que le modèle ignore simplement les actions. Ce n'est pas le cas, et la nuance est capitale.

Une seconde mesure l'a vérifié directement : à partir d'une image, on demande au modèle d'imaginer l'instant suivant pour chacune des dix-sept actions possibles, puis on mesure à quel point ces dix-sept imaginaires diffèrent les uns des autres. Ils sont bel et bien différents. La mécanique interne qui représente les actions fonctionne et est bien formée. Le modèle réagit.

Mais cette réaction n'explique qu'environ 4 % de ce qui change réellement entre deux moments consécutifs du jeu — et elle pousse dans une direction qui ne correspond pas à la réalité. Le modèle a appris à réagir aux actions ; il n'a pas appris à réagir *correctement*.

Une analogie : imaginez une voiture dont le volant est bien connecté — tournez-le et la voiture change de direction — mais câblé de telle sorte que son mouvement n'a presque aucun rapport avec le tracé de la route. Le volant n'est pas cassé. Il fait tourner la voiture. Il ne vous aide simplement pas à conduire.

## Un détail qui rend l'histoire cohérente

Un chiffre n'avait pas été anticipé, et c'est la partie la plus convaincante du résultat.

Les trois environnements testés diffèrent par la quantité de mouvement qu'ils contiennent. Les enregistrements de fabrication sont principalement statiques — beaucoup d'immobilité, de menus, de petits gestes. Les enregistrements de coupe d'arbres sont les plus animés. Classés du plus statique au plus dynamique, le taux d'échec du modèle suit exactement le même ordre : plus la séquence est statique, plus l'option « ne rien faire » gagne souvent.

C'est exactement ce à quoi on s'attend si le problème est bien celui décrit. Quand très peu de choses bougent, « supposer que rien ne change » est déjà une excellente prédiction, et toute modification guidée par les actions qui est ne serait-ce que légèrement mal ajustée fait plus de mal que de bien. Personne n'avait conçu le test pour produire ce schéma ; il a émergé naturellement des données. Quand un résultat prédit une régularité qu'on ne cherchait pas, c'est généralement le signe qu'il est réel.

## La complication honnête

Il y a une tension dans cette découverte, et elle ne sera pas dissimulée.

L'agent réussit à couper des arbres 25 à 50 % du temps dans l'environnement simple de coupe d'arbres (Chapitre 5) — **alors même que ce défaut exact est présent**. Si un modèle du monde qui comprend mal les actions rendait toute planification impossible, rien n'aurait jamais dû fonctionner. Or, quelque chose a fonctionné.

Cette découverte ne peut donc pas, à elle seule, constituer l'explication complète de l'échec de l'agent lors d'un départ à froid. Tout récit s'appuyant sur elle doit aussi expliquer les succès obtenus, et ce chapitre n'en fournit pas la clé. Ce ne serait qu'une hypothèse, et ce site a passé dix-neuf chapitres à distinguer les hypothèses des mesures vérifiées.

Ce que cette découverte explique, en revanche, c'est pourquoi dix-neuf tentatives pour améliorer le *planificateur* ont si peu changé les choses. Elles affinaient toutes la façon de choisir entre des options que le modèle était incapable de différencier de manière signifiante.

Cela donne également tout son sens au seul vrai succès de la campagne. Le seul changement qui ait produit un résultat non nul (Chapitre 8) consistait à forcer l'agent à s'en tenir à son plan plus longtemps au lieu de réévaluer ses choix à chaque instant. Si l'information disponible à chaque instant est principalement du bruit, décider moins souvent et s'engager davantage est exactement la bonne réaction. Le projet l'avait découvert par essais et erreurs, sans savoir pourquoi cela aidait.

## Pourquoi la campagne s'arrête ici

Après cette mesure, la décision a été prise de clore la campagne de départ à froid plutôt que de lancer une vingtième tentative.

La raison n'est pas l'épuisement. C'est que la seule option restante relève d'un travail d'une autre nature. L'article qui a inspiré ce chapitre propose également un correctif — une méthode d'entraînement qui force le modèle à maintenir les conséquences des actions bien distinguables. La moitié du code nécessaire existe déjà dans le dépôt, désactivée depuis le premier jour. Mais l'appliquer correctement signifierait aussi changer la quantité de passé que le modèle peut observer à la fois : la version publiée regarde trente-deux moments d'historique, la nôtre un seul. Cela revient à reconstruire le modèle du monde, pas à l'ajuster.

Et il convient de préciser clairement ce que cette clôture ne prétend **pas**. Elle ne prétend pas qu'un agent JEPA est incapable d'apprendre à trouver son premier arbre. L'article à l'origine de ce chapitre montre un modèle de la même famille planifiant avec succès dans Minecraft — en récoltant de la pierre 19 fois sur 20. La capacité est réelle pour cette famille d'architectures, à une échelle supérieure à celle de ce projet. Ce qui est affirmé est beaucoup plus restreint et bien mieux étayé : **cette approche précise — réparer le planificateur autour d'un petit modèle du monde gelé — est arrivée au bout de ses possibilités, et nous savons maintenant pourquoi.**

## Ce que ce projet a réellement accompli

Il est juste de conclure sur un bilan exact plutôt que sur une impression.

L'agent a appris à voir sans étiquettes, sans s'effondrer (Chapitres 1-2). Il a appris à imaginer les conséquences de ses actions suffisamment bien pour planifier (Chapitres 3-4). Il joue au vrai Minecraft et coupe de vrais arbres (Chapitre 5). Il fabrique des objets de bout en bout dès qu'on lui donne du bois (Chapitre 6). Chacune de ces étapes a été vérifiée par rapport à un seuil chiffré avant d'être qualifiée de succès.

Et puis, vingt tentatives documentées sur un problème qui n'a pas été résolu — dont six confirmations indépendantes d'une même erreur de mesure déroutante, une victoire rétractée le jour même de sa découverte, et un diagnostic de la cause racine tout à la fin. La plupart des travaux publiés ne montrent que ce qui a fonctionné. Ce site a montré le reste, avec le même niveau de précision, parce que c'est cette partie-là qui enseigne quelque chose.

:::

::: expert

## Contexte

Le Chapitre 19 (tentative #19) s'est conclu sur une pause décidée par l'utilisateur : deux leviers de réentraînement du cœur du modèle avaient échoué, chacun avec une cause diagnostiquée. Ce chapitre couvre la tentative #20 documentée dans `docs/10_coldstart_engineering.md` et `CLAUDE.md#Phase 5+` — **la première mesure de toute la campagne cherchant à savoir si les projections d'`ebwm.pt` réagissent réellement aux actions**, constituant le résultat de clôture de la campagne.

À noter que les tentatives #7 à #19 étaient, à l'exception de la #19 elle-même, presque exclusivement des interventions sur le *score* ou sur la *recherche*. La dynamique — le fait que les futurs imaginés par le modèle du monde dépendent ou non des actions planifiées — n'avait jamais été instrumentée.

## Origine

Une veille bibliographique (10 août 2026, couvrant du 27 juillet 2026 à aujourd'hui, interrogeant arXiv *et* Google Scholar plutôt qu'arXiv seul) a fait ressortir l'article de Gan, Zeng, Cheng, Song, Tang, Wang, "ActSWM: Action-Sensitive World Models for Long-Horizon Planning in Open-World Games" ([arXiv:2607.26712](https://arxiv.org/abs/2607.26712), 2026) — **dont la ligne de base est LeWM, la famille d'architectures exacte de ce projet, évaluée sur de la planification Minecraft en boucle fermée**.

L'article nomme l'**effondrement de contexte** (*Context Collapse*) : un prédicteur latent autorégressif qui maintient une cosinus-similitude élevée avec les états futurs réels tout en produisant des futurs presque indistincts sous différentes séquences d'actions. Un `ratio` de prédiction sain avec un planificateur aveugle — le symptôme exact des Phases 4/5 de ce projet.

L'article a été vérifié en lisant directement sa source LaTeXML (équations, hyperparamètres du Tableau 3, décomptes du Tableau 8), sans passer par un résumé automatique. Cette vérification s'est avérée cruciale : elle a permis de déceler que l'article rapporte ses gains selon deux conventions différentes (points de pourcentage dans l'introduction, valeurs relatives dans les résultats), de corriger une attribution erronée du terme SigReg à LeWM au lieu de LeJEPA, et d'isoler un détail omis par les synthèses — voir la section « Le levier ouvert » ci-dessous.

## Méthode

`scripts/diagnose_context_collapse.py` + `configs/diagnose_context_collapse.yaml`. Entièrement hors-ligne : sans MineRL, sans Java, avec `ebwm.pt` chargé gelé en `requires_grad_(False)` et md5 revérifié (`ac14e65361fbddeb057963362ea1382d`, inchangé).

Adaptation de l'Éq. 10 d'ActSWM : à partir d'une image de contexte encodée, dérouler K=12 pas à deux reprises depuis le même contexte, en comparant chaque déroulement au futur réel encodé $z_{t+k}$ :

- $s_{\text{gt}, k} = \cos(\hat{z}_{\text{gt}}, z)$ — actions réelles enregistrées
- $s_{\text{zero}, k} = \cos(\hat{z}_{\text{zero}}, z)$ — contre-factuel sans action (index d'action 0)
- $\Delta_k = s_{\text{gt}, k} - s_{\text{zero}, k}$ — l'écart d'action (*action gap*)

Deux divergences délibérées par rapport à ActSWM, rapportées séparément plutôt que fondues dans leur chiffre :

1. Un **bras d'action aléatoire**. Le planificateur ne compare jamais « enregistré vs sans action » ; il compare plusieurs candidats non nuls entre eux.
2. Un **bras de dispersion aligné sur le planificateur** : l'écart-type, sur 64 séquences candidates, de la distance latente au dernier pas sur laquelle `planner.py::_score` classe les plans — le pendant hors-ligne du `goal_score_std` enregistré depuis la tentative #2.

**Treechop sert de contrôle positif interne.** Ce projet n'a pas de seuil préétabli pour $\Delta_k$ (jamais mesuré auparavant), mais l'agent planifie avec succès prouvé sur Treechop (Phase 4, 25-50 % de coupe), ce qui rend la comparaison Treechop-vs-Obtain interprétable sans barre externe.

**Un delta proche de zéro est ambigu** et la métrique d'ActSWM seule ne permet pas de lever l'ambiguïté. Une seconde mesure a donc été ajoutée : la dispersion L2 de la prédiction à 1 pas à travers les 17 choix d'actions possibles depuis la même image, divisée par le changement latent réel à 1 pas $\|z_{t+1} - z_t\|$. Cela sépare « le prédicteur ignore l'action » ($\text{share} \approx 0$) de « il réagit, mais pas de manière utile » ($\text{share} > 0$, avec $\Delta$ toujours $\approx 0$).

## Résultat

n=400 fenêtres/domaine (266 pour `obtain_coverage` — seules fenêtres survivant au filtre `max_action=17`, ce qui rend cette colonne plus bruitée et non traitée comme une preuve équivalente).

| domaine | déplacement réel 1-pas | dispersion actions | part des actions | taux victoire Δ@k=1 | Δ_zero@K | Δ_rand@K |
|---|---|---|---|---|---|---|
| treechop | 16.22 | 0.615 | 3.8% | 35.5% | −0.00028 | +0.00012 |
| obtain_craft | 4.82 | 0.520 | 10.8% | 13.0% | −0.00055 | +0.00204 |
| obtain_coverage | 11.31 | 0.703 | 6.2% | 28.2% | −0.00150 | +0.00011 |

**Pas un effondrement de contexte au sens littéral.** La voie d'action fonctionne : les 17 actions déplacent réellement la prédiction, et la table d'embeddings d'actions est saine (quasi-orthogonale, cosinus moyen par paire à -0.014).

**Mais la réponse constitue un passif net.** `delta_zero` est négatif dans tous les domaines, et de façon significative **à k=1 — le régime exact sur lequel `ebwm.pt` a été entraîné** (`train_eb_jepa.py` utilise `nsteps=1`), ce qui exclut un dérivé de déroulement multi-pas :

- treechop : −0.000444 ± 0.000178, t=−2.49, p=0.0130, l'action réelle gagne dans **35.5 %** des fenêtres
- obtain_craft : −0.000113 ± 0.000026, t=−4.37, p<0.0001, gagne dans **13.0 %**
- obtain_coverage : −0.000149 ± 0.000059, t=−2.51, p=0.0126, gagne dans **28.2 %**

L'ordre constant sur les trois domaines est **sans action > vraie action > action aléatoire**. Le modèle a appris quelque chose de réel (la vraie action bat une action aléatoire) mais pas suffisamment pour dépasser la ligne de base triviale de copie du dernier état que le déroulement sans action approxime — en cohérence avec `ratio=0.9265` (la prédiction ne bat la copie que de ~7 %).

**Contrôle de cohérence interne non planifié** : le taux de victoire est parfaitement monotone par rapport à la dynamique du domaine (déplacement réel à 1 pas 4.82 → 13.0 %, 11.31 → 28.2 %, 16.22 → 35.5 %). Plus la séquence est statique, plus la copie du dernier état est forte comme ligne de base, et plus une perturbation d'action mal ajustée coûte cher. C'est la signature attendue si la réponse à l'action est un passif net face à une ligne de base forte ; elle n'a pas été conçue pour cela et a émergé directement des données.

**Contrôle négatif** : corr(delta, luminosité image) = −0.048 / +0.031 / −0.225 — le premier mécanisme de cette campagne à être essentiellement non corrélé avec la luminosité (plage précédente : 0.117 - 0.947). Attendu par construction, puisque delta est une différence entre deux déroulements à partir de la *même* image (les facteurs d'imagerie s'annulent) — mais précieux à signaler après six échecs de mécanismes antérieurs sur ce test.

## Ce que cela établit, et ce que cela n'établit pas

**Établi** : `ebwm.pt` est, du point de vue de la planification, proche d'un prédicteur de copie du dernier état portant une perturbation dépendante de l'action qui ne suit pas les conséquences réelles. Cela se vérifie sur **Treechop, son propre domaine d'entraînement** — contrairement à l'inversion de score de la tentative #10, ce n'est donc pas un effet de décalage de domaine (*domain shift*). Il s'agit d'un second défaut indépendant sur la **dynamique**, alors que les tentatives #7 à #19 ciblaient quasi-exclusivement le **score**.

**NON établi — une tension réelle, pas une note de bas de page** : ceci ne peut pas être à soi seul la cause du mur du départ à froid, car l'agent coupe des arbres à 25-50 % sur Treechop *avec ce déficit exact présent*. Tout récit s'appuyant sur cette découverte doit aussi expliquer cela. Aucun n'est proposé ici ; ce serait une hypothèse, pas une mesure.

**NON établi** : le fait que le correctif d'ActSWM se transfére directement. Leur prédicteur utilise un contexte H=32 et leur explication causale (« un contexte long permet au prédicteur d'extrapoler l'évolution de la scène tout en ignorant l'action ») ne s'applique pas telle quelle à `ACConvPredictor` avec `context_length=1`.

**Ce que cela réencadre** : `commit_length=4` reste le seul levier ayant produit un résultat non nul (9.7 % combiné). Si l'information d'action par pas se situe au niveau du bruit face à la copie, s'engager sur un bloc d'actions plutôt que de reclasser à chaque instant sur un score dominé par le bruit est exactement la bonne compensation. La campagne l'avait découvert empiriquement à la tentative #4 sans en connaître la raison.

## Le levier ouvert — non emprunté

Le terme $L_{\text{readout}}$ d'ActSWM (Éq. 8) impose exactement la propriété mesurée comme défaillante ici : que l'action associée à chaque transition locale reste recouvrable. **La moitié de cette mécanique existe déjà dans ce dépôt, désactivée depuis le premier jour** : `mine_jepa/eb_jepa/losses.py::InverseDynamicsLoss` fait `(state_t, state_t+1) → action`, câblé dans `VC_IDM_Sim_Regularizer`, mais `build_ac_jepa` passe `idm_coeff=0.0, idm=None` (`mine_jepa/ebwm/__init__.py:146`), de sorte qu'il n'a jamais été instancié.
Par rapport à ActSWM, il manque : le gel des paramètres (leur `idm.stop_grad=true` exclut $\phi_0$ de l'optimiseur tout en rétropropageant à travers les entrées latentes), l'application aux transitions prédites par déroulement (Éq. 8b), et le terme charnière (*hinge*, Éq. 5) dans son ensemble.

## Clôture de la campagne à la tentative #20

La campagne de départ à froid est **close ici**, sur décision de l'utilisateur (10 août 2026), avec la tentative #20 comme résultat de conclusion plutôt qu'une 21e tentative. Exprimé clairement pour qu'un lecteur ultérieur ne confonde pas cela avec de l'épuisement :

- **La campagne travaillait sur la mauvaise couche.** Les tentatives #2 à #19 ont ajusté la recherche, le score et l'exécution au-dessus d'un `ebwm.pt` gelé. La tentative #20 a mesuré que le conditionnement par les actions d'`ebwm.pt` est un passif net face à la copie, de sorte qu'un planificateur MPC s'appuyant dessus classe les séquences d'actions selon des différences qui ne reflètent pas leurs conséquences. Cela explique rétrospectivement pourquoi trois correctifs de score (#7, #11, #17), deux correctifs de recherche (#5, #6) et deux réentraînements (#19 Run A/B) ont chacun échoué différemment : aucun ne traitait de la dynamique.
- **Le levier restant est une reconstruction, pas un rustine** — les termes $L_{\text{readout}}$/charnière ci-dessus, vraisemblablement accompagnés d'une longueur de contexte supérieure à 1. C'est une reconstruction du modèle du monde, pas une autre tentative dans le registre de cette campagne.
- **L'objectif annoncé du projet est déjà atteint** : Phases 0-4 validées face à de vrais critères, l'agent coupe des arbres dans le vrai Minecraft (25-50 %), la démo de fabrication en direct tourne à 100 % sur plus de 6 épisodes.

**Ce qui N'EST PAS prétendu par la clôture ici** : pas que la coupe d'arbres à partir d'un départ à froid soit impossible, ni que le levier restant échouerait. ActSWM démontre qu'un modèle de la famille LeWM planifie avec succès dans Minecraft en boucle fermée (récolte de pierre 19/20 contre 10/20 pour LeWM, à backbone, planificateur et bibliothèque d'actions identiques), donc la capacité est réelle pour cette famille d'architectures à plus grande échelle. L'affirmation plus étroite et mieux étayée : **l'approche de cette campagne — réparer le planificateur autour d'un modèle du monde gelé de 664K paramètres avec `context_length=1` — est épuisée, et la tentative #20 explique pourquoi.**

**Ligne de base de référence si les travaux reprennent un jour** : `commit_length=4` (9.7 % combiné, meilleur résultat de la campagne), recherche de couverture `FrontierTracker` (tentative #12), et correctif de noyade par évitement des dangers (tentative #13, confirmé à N=20 : noyades 60 % → 15 %, épisodes avec vraie chance 40 % → 60 %). Laissés ouverts, non résolus : le signal différé `died_during_escape` 2/6 de la tentative #18, et une possible régression du fix #13 sous la macro de balayage en profondeur.

`ebwm.pt` et `craft_wm_v4.pt` sont restés intacts tout au long de ce chapitre ; aucun checkpoint n'a été réécrit.

## Références

- Gan, Zeng, Cheng, Song, Tang, Wang, "ActSWM: Action-Sensitive World Models for Long-Horizon Planning in Open-World Games", [arXiv:2607.26712](https://arxiv.org/abs/2607.26712) (2026) — source de la définition de l'effondrement de contexte, du protocole delta Éq. 10 adapté ici, et du levier $L_{\text{readout}}$/charnière discuté ci-dessus.

Vérifié dans `docs/references/index.md`, aux côtés de huit autres articles ajoutés lors de la même passe bibliographique.

:::

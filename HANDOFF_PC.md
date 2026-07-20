# HANDOFF — clôturé (cold-start, chapitre docs/10, attempt #3)

**Cycle clos : l'expérience "coverage fine-tune" (attempt #3) est évaluée, documentée
(`docs/10_coldstart_engineering.md`, `CLAUDE.md`) et commitée. Verdict : signal amélioré,
comportement inchangé — voir détails ci-dessous. Le prochain cycle (attempt #4, RND en
ligne + tweak de longueur d'engagement du MPC) est scopé (proposal jepa-explorer) et en
cours d'implémentation — ce fichier sera réouvert/réécrit à son tour une fois ce cycle
évalué.**

## Ce qui est acquis (documenté dans docs/10)

- Sticky **0.5** + scan calibré = réglage retenu sur Treechop (40% à N=10, reward ×1.8).
- Deux cerveaux (ebwm.pt chop / craft_wm_v4 craft) : comportement transformé (profil
  bûcheron) mais toujours 0/5 logs en cold-start. Diagnostic : spawns sans arbre + rayon
  de recherche insuffisant, pas le geste ni la boussole.
- **Attempt #3 (coverage fine-tune, cette session)** : fine-tuning court de `craft_wm_v4`
  sur des frames de biomes variés (spawn aléatoire, sans label de craft) pour tester si le
  manque de données "perdu, pas d'arbre visible" explique les bandes de `goal_score_std`
  compressées. Résultat : la séparation du signal s'élargit (×3.2 → ×5.4 sur le ratio
  p90/p10) mais **0/3 logs sur les deux checkpoints (backup et fine-tuné)** — aucun
  changement comportemental. Checkpoint fine-tuné = `checkpoints/craft_wm_v4_coverage.pt`
  (ne remplace pas `craft_wm_v4.pt` ni `craft_wm_v4_backup.pt`, tous deux intacts).

## LE diagnostic à retenir

Le mur n'est ni la perception (le modèle "sait" maintenant mieux quand il est perdu) ni la
boussole (testée et éliminée) ni le geste (le mode deux-cerveaux le corrige). C'est le
**comportement de recherche/approche** lui-même qui manque : rien dans l'architecture
actuelle n'apprend à couvrir du terrain efficacement à partir d'un spawn inconnu. Améliorer
le signal "je suis perdu" ne suffit pas si rien n'agit différemment quand ce signal se
déclenche.

## Prochaine action concrète : online RND

- Objectif : une récompense de nouveauté calculée et mise à jour **pendant le jeu** (pas sur
  des démos figées comme l'expérience #1 de `docs/09`, qui avait échoué par collapse de
  l'ensemble hors-ligne). La nouveauté doit décroître avec l'expérience — c'est ce qui doit
  pousser l'agent à couvrir du terrain plutôt que refaire les mêmes gestes.
- Base de code existante à réutiliser : `mine_jepa/ebwm/curiosity.py`
  (`DisagreementEnsemble`), `DiscreteLatentPlanner(novelty_coeff)` — déjà config-gated,
  déjà branché pour la version *offline* (échouée). Le travail restant est de rendre
  l'entraînement de l'ensemble/predictor **online**, pas de repartir de zéro.
- Ne pas retoucher `ebwm.pt` / `craft_wm_v4.pt` / `craft_wm_v4_backup.pt` /
  `craft_wm_v4_coverage.pt` — tous des points de comparaison désormais utiles.

## Rappels d'exploitation

- Runs longs : fenêtre PowerShell VISIBLE + `Tee-Object` vers `logs/`. ⚠️ `Tee-Object`
  écrit en UTF-16LE — mais les scripts Python qui écrivent directement dans un fichier
  (ex. `logs/play_ep_NNN.txt`) sont en UTF-8 normal. Vérifier l'encodage réel avant de
  décoder (`file <nom>` ou `xxd` sur les premiers octets) plutôt que de supposer.
- ⚠️ **Ne jamais tuer un process sans avoir confirmé sa command line** (`Get-CimInstance
  Win32_Process -Filter "ProcessId=..."`) — un run legitime peut porter un PID qui a
  l'air suspect dans un listing brut.
- ⚠️ Les fichiers `logs/play_ep_NNN.txt` sont **réécrits à chaque run** (même noms) — copier
  ailleurs avant de lancer un second run si on veut comparer après coup.
- Marqueur de fin du wrapper multi-process : `FINAL RESULTS` (chaque épisode imprime son
  propre résumé — ne pas s'arrêter au premier `Success rate`).
- Pas de notions de durée dans les commentaires/docs (préférence user).

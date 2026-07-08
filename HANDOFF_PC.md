# HANDOFF — état de la session PC (éval cold-start, chapitre docs/10)

**Où on en est : le chapitre "attempt #2" est évalué et documenté (voir `docs/10` section
Results, déjà commité pour la partie sticky/scan). Deux pistes de suivi ont été testées
depuis ce commit — les changements sont dans l'arbre de travail, NON COMMITÉS.**

## Ce qui est acquis (commité)

- Sticky **0.5** = réglage retenu (0.7 sur-engage). Treechop : 40 % à N=10, reward ×1.8.
- Scan calibré sur ebwm.pt (`flat_threshold: 0.003`) mais **non transférable** à
  craft_wm_v4 (bandes compressées → l'agent toupille). Scan OFF dans play_craft.yaml.
- Cold-start `ObtainIronPickaxeDense` : 0 log partout avec le cerveau v4 seul.

## Testé depuis (dans l'arbre de travail, à commiter)

1. **Boussole Treechop pour le chop v4** (`goal.chop_data_path`, `scripts/play_craft.py`)
   → **0/5, éliminé** (option laissée dans le code, OFF par défaut). Documenté dans docs/10.
2. **Deux cerveaux** (`chop_model:` dans `configs/play_craft.yaml`, config-gated) :
   ebwm.pt (le bûcheron Treechop, ratio 0.927) planifie le mode chop sur les 17 actions
   mouvement communes ; craft_wm_v4 reprend au premier log. Smoke test OK.
   → **N=5 : 0 log ENCORE, MAIS le comportement est transformé** : profil bûcheron
   (a14 30-52 %, a6/a7 attaque) au lieu du a1 diffus. Log : `logs/coldstart_twobrain.log`.

## LE diagnostic à retenir (vu dans le GIF du dernier épisode)

L'Ep5 (a6=85 %) a spawné dans un **biome rocheux/ravin sans aucun arbre visible** —
l'agent broyait de la pierre. Frames vérifiées sur toute la durée : pierre, gravier,
terre, eau, zéro arbre. Plus 2 épisodes sur 5 morts prématurément (spawns dangereux).
**Le mur restant n'est plus le geste (réglé par les deux cerveaux) ni la boussole :
c'est le spawn `ObtainIronPickaxe` qui lâche l'agent dans des biomes sans arbres, et
un rayon d'exploration trop court pour en sortir.** À confirmer sur les GIFs des autres
épisodes avant de conclure définitivement (un seul épisode inspecté).

## Prochaines actions (dans l'ordre suggéré)

1. Confirmer le diagnostic : inspecter les frames des épisodes 1-4 (les GIFs des
   sous-processus s'écrasent — relancer 2-3 épisodes avec `gif_episodes` élevé si besoin).
2. **Réactiver le scan en mode deux-cerveaux** : le std du chop vient maintenant
   d'ebwm.pt → la calibration 0.003 redevient valable (c'était le point mort du scan
   sur v4). Scan + sticky + deux cerveaux = toute la chaîne enfin cohérente.
3. Si les spawns sans arbres se confirment : le problème devient "couvrir du terrain"
   → c'est exactement le cas d'usage du **RND online** (cycle pré-convenu, docs/09) —
   ou, plus simple, allonger `max_steps` pour donner un rayon de recherche réaliste.

## Rappels d'exploitation

- Runs longs : fenêtre PowerShell VISIBLE + `Tee-Object` vers `logs/` (préférence user).
  ⚠️ Tee-Object écrit en UTF-16 → `iconv -f UTF-16LE` avant tout grep.
- Marqueur de fin du wrapper multi-process : `FINAL RESULTS` (chaque épisode imprime
  son propre résumé — ne pas s'arrêter au premier `Success rate`).
- Pas de notions de durée dans les commentaires/docs (préférence user).
- `ebwm.pt` et `craft_wm_v4.pt` intacts — rien n'a été réentraîné.

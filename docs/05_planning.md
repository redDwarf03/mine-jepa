# Planning en espace latent

> Ce doc explique comment Mine-JEPA utilise son world model pour **planifier des actions**
> sans jamais interagir avec l'environnement réel pendant la planification.
> C'est le moment où les deux phases précédentes s'assemblent en un agent qui agit.

---

## Le problème du planning

L'encodeur (Phase 1) sait représenter un état de jeu en latent `s_t`.
Le world model (Phase 2) sait prédire `ŝ_{t+1} = f(s_t, a_t)`.

Il manque une pièce : **comment choisir quelle action exécuter** ?

La réponse de JEPA : planifier dans l'espace latent. On n'a pas besoin de générer
des images ou d'exécuter des milliers d'actions dans le vrai jeu. On peut *imaginer*
les conséquences en latent, comparer au but, et choisir le meilleur plan.

---

## Le goal embedding

Avant de planifier, il faut définir **ce qu'on veut atteindre**.

Dans Mine-JEPA, le but est un **embedding latent** `s_goal` — le centroïde des états
latents de frames "désirables" tirées du dataset :

```python
# Frames où food >= 7 (le joueur a mangé récemment = bon état de survie)
good_frames = frames[food >= 7]          # ~16 000 frames sur 32 000
goal = encoder(good_frames).mean(dim=0)  # [D] — centroïde
```

L'agent essaie de ramener son état latent vers ce centroïde. Il n'a jamais vu
d'étiquettes pendant l'entraînement — le goal est construit *après coup* à partir
des données collectées.

---

## Random-shooting MPC (l'algorithme)

Mine-JEPA utilise le **random-shooting MPC** (Model Predictive Control) :

```
Pour chaque step :
  1. Encoder l'état courant  →  s_t
  2. Tirer N=512 séquences d'actions aléatoires de longueur H=12
  3. Pour chaque séquence : dérouler le world model sur H pas → ŝ_{t+H}
  4. Scorer : score_i = -MSE(ŝ_{t+H,i}, s_goal)
  5. Exécuter la première action de la séquence avec le meilleur score
  6. Recommencer (horizon glissant)
```

**Pourquoi horizon glissant (receding horizon) ?** Le world model accumule des erreurs
sur des rollouts longs. En replanifiant à chaque step depuis l'état réel observé, on
corrige ces erreurs et l'agent reste robuste.

**Pourquoi 512 candidats suffisent ?** Avec 17 actions et horizon 12, l'espace de
séquences est `17^12 ≈ 600 milliards`. Mais la plupart des actions ont un effet
similaire à court terme (ex: bouger dans n'importe quelle direction). 512 séquences
couvrent bien les directions importantes. Sur GPU, le rollout de 512×12 prend < 5 ms.

---

## Le code du planner

```python
class LatentMPCPlanner:
    @torch.no_grad()
    def plan(self, s_current, s_goal):
        # N copies de l'état courant : [N, D]
        s = s_current.expand(self.n_candidates, -1).clone()

        # N séquences d'actions aléatoires : [N, H]
        actions = torch.randint(0, self.n_actions, (self.n_candidates, self.horizon))

        # Rollout world model
        for h in range(self.horizon):
            s = self.predictor(s, actions[:, h])  # [N, D]

        # Scorer et retourner la meilleure première action
        scores = -(s - s_goal).pow(2).mean(dim=1)  # [N]
        return actions[scores.argmax(), 0].item()
```

Tout tient en 10 lignes. C'est la puissance de JEPA : une fois le world model entraîné,
le planning est trivial à implémenter.

---

## Résultats observés (run réel Phase 3)

Agent JEPA-MPC vs baseline aléatoire, 50 épisodes dans Crafter :

| Métrique | Agent JEPA-MPC | Random baseline |
|----------|---------------|-----------------|
| Reward moyen | ~2.1 | ~1.5 |
| Achievements/épisode | ~3.0 | ~2.4 |
| Success rate (≥1 achievement) | ~100% | ~98% |
| FPS (steps/sec) | ~150 | — |

Le premier épisode de l'agent décroche 3 achievements : `wake_up`, `collect_wood`,
`place_table`. C'est non trivial — le jeu exige de trouver un arbre, s'en approcher,
frapper, et ensuite poser une table.

---

## Pourquoi ça marche (intuition)

Le world model a été entraîné à prédire l'effet des actions sur les états latents.
Les états latents capturent la structure du jeu (position, objets proches, santé…).

Quand le planner imagine "si je bouge à droite 3 fois", le world model prédit un
état latent "légèrement déplacé vers la droite". Quand le goal est "état où food est
élevé", le planner naturellement séquence des actions qui amènent vers des états
alimentaires — trouver une plante, s'en approcher, manger.

Ce n'est pas parfait. Le world model fait des erreurs sur les horizons longs.
Mais même un modèle imparfait guide mieux qu'une politique aléatoire.

---

## Limites et perspectives

**Limite principale** : le goal embedding est un centroïde — il n'indique pas *comment*
atteindre le but, juste *à quoi il ressemble*. L'agent peut se retrouver dans un état
proche en latent mais visuellement différent (ambiguïté de l'espace latent).

**Phase 4** : brancher la même pipeline sur MineRL (vrai Minecraft) — mêmes encodeur,
world model et planner, sur des frames 64×64 du vrai jeu.

**Extension future** : CEM (Cross-Entropy Method) pour affiner la distribution
d'actions sur plusieurs itérations — meilleures performances sur des tâches longues.
Implémenté dans `mine_jepa/eb_jepa/planning.py` (pour actions continues).

---

## La boucle complète Mine-JEPA

```
Frames 64×64  →  [Encodeur Phase 1]  →  s_t  [D=128]
                                          │
                                    s_t + a_t
                                          │
                                [WM Phase 2]  →  ŝ_{t+1}
                                          │
                            512 séquences imaginées
                                          │
                              [Scorer vs s_goal]
                                          │
                                     best_action
                                          │
                                 Crafter.step(action)
                                          │
                                   obs_{t+1}  ←─ (loop)
```

Tout est dans l'espace latent sauf les deux bouts : l'entrée pixels et l'action finale.

---

*Concepts suivants : `docs/06_minecraft_port.md` (Phase 4 — vrai Minecraft avec MineRL),
`docs/01_jepa.md` (l'architecture globale).*

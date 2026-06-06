# Le World Model action-conditionné

> Ce doc explique le deuxième composant de Mine-JEPA : le **world model**.
> Si Phase 1 t'a appris à représenter les états du jeu en latent,
> Phase 2 t'apprend à *prédire comment ces états changent* quand l'agent agit.

---

## La question centrale

À la fin de Phase 1, l'encodeur sait transformer une frame Crafter en un vecteur
latent `s_t` qui capture la structure du jeu (position, santé, objets…).

Mais l'agent ne peut pas encore planifier. Il ne sait pas répondre à la question :
> « Si je fais l'action *frapper ce bloc*, à quoi ressemblera mon état latent après ? »

Le world model répond exactement à ça.

---

## L'architecture en une ligne

```
s_t  +  a_t  →  [ Predictor ]  →  ŝ_{t+1}
```

- `s_t` : état latent courant (sortie de l'encodeur gelé, Phase 1) — `[B, 128]`
- `a_t` : action discrète (0–16 dans Crafter) — `[B]`
- `ŝ_{t+1}` : **prédiction** de l'état latent suivant — `[B, 128]`

Le predictor ne touche jamais les pixels. Il opère entièrement dans l'espace latent.

---

## Pourquoi "action-conditionné" est crucial

Un predictor sans action prédirait juste "l'état moyen suivant" — utile pour la
dynamique passive (le soleil qui se déplace) mais inutile pour planifier.

Avec l'action en entrée, le predictor apprend des règles causales :
- Action *move_right* + position gauche → position droite
- Action *do* + arbre devant → arbre disparaît + bois en inventaire
- Action *sleep* + énergie faible → énergie remonte

C'est la différence entre **observer** le monde et **comprendre** ce qu'on peut y faire.

---

## L'architecture du predictor (Mine-JEPA)

```python
class ActionConditionedPredictor(nn.Module):
    def __init__(self, embed_dim=128, n_actions=17, action_dim=32):
        self.action_embed = nn.Embedding(n_actions, action_dim)
        self.net = nn.Sequential(
            nn.Linear(embed_dim + action_dim, 256),
            nn.GELU(),
            nn.Linear(256, 256),
            nn.GELU(),
            nn.Linear(256, embed_dim),
        )

    def forward(self, s, a):
        a_emb = self.action_embed(a)           # [B, 32]
        return self.net(torch.cat([s, a_emb])) # [B, 128]
```

**Pourquoi si petit (140K params) ?** On veut que la *compréhension* soit dans
l'encodeur (Phase 1, 688K params). Le predictor doit juste apprendre les
*transitions* — si on le fait trop gros, il peut compenser un mauvais encodeur.

**Pourquoi GELU ?** Activation douce qui ne bloque pas les gradients pour les petites
valeurs négatives, meilleure que ReLU pour des embeddings centrés en 0.

---

## La loss : MSE dans l'espace latent

```
L = MSE(ŝ_{t+1}, s_{t+1})
  = ‖ Predictor(s_t, a_t) - Encoder(frame_{t+1}) ‖²
```

L'encodeur est **gelé** — ses poids ne bougent plus depuis Phase 1. Seul le predictor
reçoit des gradients. Cela garantit que les représentations apprises en Phase 1 restent
stables.

**Pas besoin de VICReg ici** : la cible `s_{t+1}` est fournie par l'encodeur gelé qui
a déjà une variance saine (~1.15 depuis Phase 1). Difficile de colapser contre une
cible qui bouge vraiment.

---

## La baseline et le gate

Pour savoir si le predictor est utile, on compare à la **baseline la plus simple** :
*"l'état ne change pas"*, i.e. `ŝ_{t+1} = s_t`.

```
copy_loss = MSE(s_t, s_{t+1})   # combien les états diffèrent d'un pas
pred_loss = MSE(ŝ_{t+1}, s_{t+1})  # erreur du predictor
ratio     = pred_loss / copy_loss
```

- `ratio > 1` : le predictor est **pire** que ne rien faire
- `ratio < 1` : le predictor **prédit mieux** que la copie → gate validé ✅

---

## Ce qu'on observe (run réel Phase 2)

Premier epoch sur RTX 5060 Ti, encodeur gelé Phase 1 (val_loss=0.080) :

| Step | pred_loss | copy_loss | ratio |
|-----:|----------:|----------:|------:|
|   20 | 1.0193    | 0.0710    | 14.36 |
|   40 | 0.5721    | 0.0905    |  6.32 |
|   60 | 0.2819    | 0.1015    |  2.78 |
|   80 | 0.1877    | 0.1026    |  1.83 |
|  100 | 0.1338    | 0.0806    |  1.66 |

Le ratio chute de 14x à 1.4x en 100 steps — le predictor apprend très vite
les transitions les plus fréquentes (l'agent ne bouge souvent pas beaucoup).
Le gate (ratio < 1.0) est attendu autour de l'epoch 5–10.

---

## L'imagination en latent : dérouler sur k pas

Une fois entraîné, le predictor permet d'**imaginer le futur sans toucher au jeu** :

```python
s_hat_1 = predictor(s_0, a_0)        # imaginer le pas 1
s_hat_2 = predictor(s_hat_1, a_1)    # imaginer le pas 2
...
s_hat_k = predictor(s_hat_{k-1}, a_{k-1})  # imaginer le pas k
```

C'est exactement ce que fait le gate multi-pas de `eval_wm.py` : mesurer si
l'erreur de rollout sur k=1..10 pas reste inférieure à la baseline constante.

**Pourquoi l'erreur monte avec k ?** Chaque pas accumule une petite erreur. C'est
normal et attendu. Ce qui serait anormal : une erreur qui explose ou une erreur
nulle (le predictor aurait appris à ignorer les actions).

---

## Visualisation : retrieval du plus proche voisin

La visualisation la plus parlante du world model n'est pas une courbe de loss —
c'est de **voir ce que le modèle imagine**.

Méthode :
1. Prendre un état initial `s_0` (encodé depuis une frame réelle).
2. Dérouler k pas dans le world model avec une séquence d'actions → `ŝ_1, ..., ŝ_k`.
3. Pour chaque `ŝ_k`, trouver la frame réelle la plus proche dans le dataset
   (par distance cosinus en latent) → afficher cette frame.

Résultat : une "imagination" de ce qui pourrait arriver si l'agent exécutait cette
séquence d'actions. C'est le hook visuel de Phase 2.

→ Implémenté dans `scripts/eval_wm.py` (option future : `--visualize`).

---

## Résumé : la boucle complète jusqu'ici

```
Phase 1 :  Frame → [Encoder] → s_t        (représentation, gelé)
Phase 2 :  s_t + a_t → [Predictor] → ŝ_{t+1}  (world model, entraîné maintenant)
Phase 3 :  s_goal + [WM] → plan d'actions  (planning en latent, à venir)
```

Le world model est la pièce manquante entre "comprendre le jeu" et "jouer au jeu".

---

*Concepts suivants : `docs/05_planning.md` (MPC/CEM latent, goal-conditioned),
`docs/01_jepa.md` (l'architecture globale).*

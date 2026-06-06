# Collapse et anti-collapse en JEPA

> Ce doc explique le problème n°1 de JEPA : le **collapse de représentation**.
> Tu apprendras pourquoi ça arrive, comment l'EMA et VICReg l'empêchent,
> et comment lire les courbes de ton propre entraînement pour détecter un collapse.

---

## Le problème : apprendre à tricher

Imagine que tu donnes cet objectif à un réseau de neurones :

> « Encode des frames de jeu vidéo de façon à ce que l'embedding de la frame *t*
> puisse prédire l'embedding de la frame *t+1*. »

La solution *honnête* : l'encodeur apprend à représenter la structure du jeu (position
du joueur, objets proches, santé…) de sorte que la dynamique soit prévisible en latent.

La solution *malhonnête* : l'encodeur mappe **toutes les frames vers le même vecteur**,
par exemple `[0, 0, 0, …, 0]`. La loss de prédiction tombe à 0 immédiatement — le
prédictor n'a rien à faire. Le modèle a "gagné" sans rien apprendre.

C'est ça le **collapse** : convergence vers une solution triviale et constante.

```
Frames  →  Encoder  →  s = [0, 0, 0, ..., 0]  (toujours)
                                    ↓
           Predictor →  ŝ = [0, 0, 0, ..., 0]  (trivial)
                                    ↓
               Loss = ‖ŝ - s_y‖² = 0  ✓ (mais rien appris)
```

---

## Comment détecter le collapse : `batch_var`

L'indicateur principal est la **variance moyenne des embeddings sur un batch** :

```python
batch_var = embeddings.var(dim=0).mean()
```

- `batch_var` élevée (~1.0) → les embeddings sont dispersés → le modèle encode
  des informations différentes selon les frames → **bonne santé**
- `batch_var` → 0 → tous les embeddings convergent vers le même point → **collapse**

Seuil d'alerte dans Mine-JEPA : `batch_var < 1e-4`.

---

## Pourquoi JEPA collapse facilement (vs. BERT, etc.)

Les architectures comme BERT évitent le collapse par construction : elles travaillent
en **espace pixel/token** avec de la reconstruction. Il est impossible de reconstruire
une image à partir d'un vecteur constant.

JEPA travaille en **espace latent** : l'encodeur ET le décodeur (predictor) sont
libres d'apprendre ensemble n'importe quelle solution, y compris la triviale.

Le modèle contrastif classique (SimCLR) évite ça en **comparant des exemples négatifs**
(push repulsif entre embeddings différents). Mais ça requiert de gros batchs et une
définition explicite de "quelles paires sont différentes".

JEPA veut éviter tout ça (pas de négatifs, pas de reconstruction pixel) — ce qui le
rend puissant *mais* plus vulnérable au collapse.

---

## Parade n°1 : le Target Encoder EMA

La cause profonde du collapse joint-embedding : si context encoder et target encoder
se mettent à jour ensemble par gradient, rien n'empêche les deux de converger vers
la même constante. La loss reste nulle et les gradients ne voient aucun problème.

**Solution** : couper le gradient du target encoder et le mettre à jour lentement
via une **Exponential Moving Average (EMA)** du context encoder :

```
θ̄_{t+1} ← 0.99 · θ̄_t + 0.01 · θ_t
```

- `θ` = poids du context encoder (mis à jour par backprop normalement)
- `θ̄` = poids du target encoder (jamais de gradient direct — uniquement via EMA)

**Pourquoi ça aide** : le target encoder évolue *lentement*. Sa sortie `s_y` est
une cible non-triviale qui change peu, mais assez pour que le predictor ne puisse
pas "dormir" sur une solution constante. C'est une forme de **momentum knowledge
distillation**.

Dans le code (`mine_jepa/encoder/crafter_encoder.py:54`) :

```python
class EMATargetEncoder(nn.Module):
    @torch.no_grad()
    def update(self, source: CrafterEncoder) -> None:
        for ema_p, src_p in zip(self.net.parameters(), source.parameters()):
            ema_p.data.mul_(self.decay).add_(src_p.data, alpha=1.0 - self.decay)
```

Le `@torch.no_grad()` est crucial : aucun gradient ne traverse jamais ce chemin.

---

## Parade n°2 : VICReg (Variance-Invariance-Covariance Regularization)

EMA seul ne suffit pas. On ajoute une **régularisation explicite** qui interdit
directement le collapse.

### La pénalité de variance (anti-collapse)

```
L_std = mean( max(0, 1 - std(s_x, dim=0)) )
```

Cette loss est nulle si toutes les dimensions de l'embedding ont une std ≥ 1.
Si la variance chute (collapse en cours), la loss monte et repousse l'encodeur.

*Intuition* : on "force" l'encodeur à utiliser tout l'espace latent, pas juste un
point.

### La pénalité de covariance (anti-redondance)

```
L_cov = mean( off_diagonal( cov(s_x)² ) )
```

Cette loss pénalise les corrélations entre les dimensions de l'embedding. Si deux
dimensions encodent la même information, elles sont corrélées → pénalité.

*Pourquoi* : un embedding où toutes les dimensions disent la même chose est presque
aussi mauvais qu'un embedding constant. VICReg force la **décorrélation** pour que
chaque dimension encode quelque chose de différent.

### La loss totale de Mine-JEPA Phase 1

```
L = L_JEPA  +  λ_std · L_std  +  λ_cov · L_cov

avec λ_std = 1.0  (configs/train_encoder.yaml)
     λ_cov = 0.04
```

`λ_cov` est petit (0.04) car la décorrélation est moins critique que la variance.
`λ_std = 1.0` est fort pour vraiment interdire le collapse.

---

## Ce qu'on observe dans Mine-JEPA (run réel)

Voici les métriques des premières epochs de l'entraînement Phase 1 sur RTX 5060 Ti,
dataset Crafter 32 676 transitions :

| Epoch | loss total | jepa | std_loss | cov_loss | batch_var | val_loss |
|------:|----------:|-----:|---------:|---------:|----------:|---------:|
| 1     | 0.190      | 0.134 | 0.040   | 0.434    | **1.057** | 0.250    |
| 2     | 0.119      | 0.101 | 0.001   | 0.405    | **1.124** | 0.191    |
| 3     | 0.106      | 0.091 | 0.001   | 0.347    | **1.128** | 0.122    |
| 4     | 0.094      | 0.081 | 0.001   | 0.303    | **1.133** | 0.114    |
| 5     | 0.084      | 0.073 | 0.001   | 0.271    | **1.150** | 0.098    |

**Lecture** :

- `batch_var` **monte** de 1.06 à 1.15 → le modèle utilise de plus en plus l'espace
  latent. Opposé du collapse.
- `std_loss` chute rapidement à ~0.001 → la contrainte de variance est satisfaite
  dès epoch 2. VICReg a fait son travail.
- `cov_loss` décroît (0.43 → 0.27) → les dimensions se décorrèlent progressivement.
- `jepa_loss` divisée par ~2 en 5 epochs → le predictor apprend.

---

## À quoi ressemble un collapse (pour comparaison)

Si on désactivait VICReg et l'EMA, voici ce qu'on verrait typiquement :

```
Epoch  1 | batch_var=1.05  (normal au début)
Epoch  5 | batch_var=0.12  (chute)
Epoch 10 | batch_var=0.003 (collapse en cours)
Epoch 15 | batch_var=8e-7  ← ALERTE
Epoch 20 | batch_var=1e-9  (collapse total — le modèle ne sert à rien)
```

La loss jepa tombe aussi à ~0, ce qui *semble* bien au premier coup d'œil.
C'est le signe trompeur le plus dangereux : **une loss très basse sans variance
= collapse, pas succès**.

---

## Résumé : les 3 signaux à surveiller

| Signal | Valeur saine | Alerte |
|--------|-------------|--------|
| `batch_var` | > 0.1, idéalement ~1 | < 1e-4 |
| `std_loss` | proche de 0 (variance OK) | monte → collapse passif |
| `jepa_loss` | décroît régulièrement | reste haute → predictor trop faible |

Si `batch_var < 1e-4` : augmenter `std_coeff` dans `configs/train_encoder.yaml`
(ex. 1.0 → 5.0) et relancer.

---

## La visualisation qui prouve que ça marche

Le meilleur test n'est pas numérique : c'est la **projection PCA/t-SNE des embeddings**
colorée par un état du jeu (santé, objets proches…).

Si le modèle a appris quelque chose d'utile, des clusters apparaissent — des zones de
l'espace latent correspondent à des situations de jeu similaires, *sans aucun label
pendant l'entraînement*.

→ C'est ce que valide `scripts/probe.py` : un classifieur linéaire sur ces embeddings
gelés doit dépasser la baseline aléatoire (~33 %) pour que le gate Phase 1 soit validé.

---

*Concepts suivants : `docs/04_world_model.md` (le predictor action-conditionné),
`docs/01_jepa.md` (l'architecture complète).*

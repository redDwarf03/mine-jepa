"""
Phase 1 — Gate : linear-probe sur les embeddings JEPA.

Ce script répond à la question : « l'encodeur JEPA a-t-il appris
quelque chose d'utile sur le jeu, sans jamais voir d'étiquettes ? »

Méthode :
  1. Charger l'encodeur entraîné (gelé — aucun gradient).
  2. Extraire les embeddings de toutes les frames du dataset.
  3. Entraîner un classifieur linéaire sur ces embeddings pour prédire
     la valeur de santé (health) du joueur (low/med/high).
  4. Comparer à la baseline (classifieur aléatoire ~33 %).

Si l'accuracy dépasse significativement 33 %, les embeddings capturent
des informations sémantiques sur l'état du jeu — malgré un entraînement
100 % non supervisé.

Gate Phase 1 :
  - accuracy linear-probe > baseline (33 %)
  - batch_var > 1e-4 (pas de collapse)

Usage :
    uv run python scripts/probe.py
    uv run python scripts/probe.py --label food
"""
import argparse
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader

from mine_jepa.encoder.crafter_encoder import CrafterJEPA
from mine_jepa.encoder.dataset import ProbeDataset


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/train_encoder.yaml")
    p.add_argument("--checkpoint", default=None)
    p.add_argument("--label", default="health", choices=["health", "food", "drink", "energy"])
    return p.parse_args()


def load_cfg(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


@torch.no_grad()
def extract_embeddings(encoder: nn.Module, loader: DataLoader, device: torch.device):
    """Extrait les embeddings pour tout le dataset. Encodeur gelé."""
    all_embs, all_labels = [], []
    for frames, labels in loader:
        frames = frames.to(device)
        embs = encoder(frames)  # [B, D]
        all_embs.append(embs.cpu().numpy())
        all_labels.append(labels.numpy())
    return np.concatenate(all_embs), np.concatenate(all_labels)


def probe(cfg: dict, ckpt_path: str, label: str) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # --- Charger le modèle ---
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    m_cfg = ckpt["cfg"]["model"]
    t_cfg = ckpt["cfg"]["training"]
    v_cfg = ckpt["cfg"]["vicreg"]

    model = CrafterJEPA(
        embed_dim=m_cfg["embed_dim"],
        hidden_dim=m_cfg["hidden_dim"],
        predictor_hidden=m_cfg["predictor_hidden"],
        ema_decay=t_cfg["ema_decay"],
        std_coeff=v_cfg["std_coeff"],
        cov_coeff=v_cfg["cov_coeff"],
    ).to(device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    encoder = model.encoder

    print(f"Checkpoint chargé : epoch {ckpt['epoch']}, val_loss={ckpt['val_loss']:.4f}")

    # --- Dataset probe ---
    dataset = ProbeDataset(cfg["data"]["path"], label=label)
    counts = dataset.class_counts()
    print(f"\nDistribution '{label}': low={counts['low']}, med={counts['med']}, high={counts['high']}")
    baseline = max(counts.values()) / sum(counts.values())
    print(f"Baseline (classe majoritaire) : {baseline:.1%}")

    # Extraction des embeddings
    loader = DataLoader(dataset, batch_size=512, shuffle=False, num_workers=0)
    print("Extraction des embeddings...")
    embs, labels = extract_embeddings(encoder, loader, device)

    # Vérification anti-collapse
    batch_var = embs.var(axis=0).mean()
    collapse_ok = batch_var > cfg["logging"]["collapse_threshold"]
    print(f"\nbatch_var = {batch_var:.6f}  {'✅ pas de collapse' if collapse_ok else '❌ COLLAPSE DÉTECTÉ'}")

    # --- Linear probe ---
    # Split 80/20
    n = len(embs)
    idx = np.random.RandomState(42).permutation(n)
    split = int(0.8 * n)
    X_train, X_val = embs[idx[:split]], embs[idx[split:]]
    y_train, y_val = labels[idx[:split]], labels[idx[split:]]

    # Normaliser les embeddings (bonne pratique pour le probe linéaire)
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)

    print("\nEntraînement du classifieur linéaire...")
    clf = LogisticRegression(max_iter=1000, C=1.0, random_state=42)
    clf.fit(X_train, y_train)

    acc_train = accuracy_score(y_train, clf.predict(X_train))
    acc_val = accuracy_score(y_val, clf.predict(X_val))

    # --- Résultats ---
    print(f"\n{'='*50}")
    print(f"Linear-probe '{label}'")
    print(f"{'='*50}")
    print(f"  Train accuracy  : {acc_train:.1%}")
    print(f"  Val   accuracy  : {acc_val:.1%}")
    print(f"  Baseline        : {baseline:.1%}")
    delta = acc_val - baseline
    gate = acc_val > baseline + 0.02  # au moins 2 points au-dessus de la baseline
    print(f"  Δ vs baseline   : {delta:+.1%}")
    print(f"\n  Gate Phase 1    : {'✅ PASSÉ' if gate and collapse_ok else '❌ NON PASSÉ'}")
    if not gate:
        print("  → Relancer train_encoder.py avec plus d'epochs ou de données.")
    if not collapse_ok:
        print("  → Collapse détecté : augmenter std_coeff dans configs/train_encoder.yaml.")


def main():
    args = parse_args()
    cfg = load_cfg(args.config)
    ckpt_path = args.checkpoint or (Path(cfg["checkpoint"]["dir"]) / cfg["checkpoint"]["name"])
    if not Path(ckpt_path).exists():
        print(f"Checkpoint introuvable : {ckpt_path}")
        print("Lance d'abord : uv run python scripts/train_encoder.py")
        return
    probe(cfg, str(ckpt_path), args.label)


if __name__ == "__main__":
    main()

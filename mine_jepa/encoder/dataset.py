"""
Datasets pour Mine-JEPA.

CrafterFrameDataset  — paires (frame_t, frame_t+1) pour entraîner le JEPA (Phase 1)
ProbeDataset         — paires (frame, label) pour le linear-probe (Phase 1)
CrafterWMDataset     — triplets (frame_t, action_t, frame_t+1) pour le world model (Phase 2)
CrafterSeqDataset    — séquences (frames[0..k], actions[0..k-1]) pour l'éval multi-pas
"""
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


def _load_npz(path: str) -> dict:
    d = np.load(path)
    return {k: d[k] for k in d.files}


def _to_float(frames: np.ndarray) -> torch.Tensor:
    """uint8 [0,255] → float32 [0,1], shape [N, 3, H, W]."""
    t = torch.from_numpy(frames).float() / 255.0
    return t.permute(0, 3, 1, 2)  # [N, H, W, 3] → [N, 3, H, W]


class CrafterFrameDataset(Dataset):
    """
    Paires (frame_t, frame_t+1) pour entraîner l'encodeur JEPA.

    On évite soigneusement les frontières d'épisodes (done=True) :
    on ne crée jamais une paire dont la première frame est la dernière
    d'un épisode.

    Pourquoi cette contrainte ? Si frame_t est la dernière frame d'un épisode
    (le joueur est mort ou a gagné), frame_t+1 appartient à un épisode différent
    — le modèle ne peut pas prédire une dynamique cohérente entre les deux.
    """

    def __init__(self, data_path: str):
        data = _load_npz(data_path)
        frames = _to_float(data["frames"])  # [N, 3, H, W]
        dones = data["dones"]               # [N] bool

        # Indices valides : frame t tel que done[t] == False
        # (on peut former la paire (t, t+1) sans franchir une frontière)
        valid = np.where(~dones[:-1])[0]
        self.x_context = frames[valid]       # [M, 3, H, W]
        self.x_target = frames[valid + 1]    # [M, 3, H, W]

    def __len__(self) -> int:
        return len(self.x_context)

    def __getitem__(self, idx: int):
        return self.x_context[idx], self.x_target[idx]


class ProbeDataset(Dataset):
    """
    Dataset pour le linear-probe : (embedding, label).

    Labels disponibles (tirés de l'inventaire Crafter) :
    - 'health'  (0–9) → buckettisé en 3 classes : low/med/high
    - 'food'    (0–9) → idem
    - 'drink'   (0–9) → idem

    Le probe test : un classifieur linéaire peut-il prédire ces valeurs
    à partir des embeddings JEPA gelés ?
    - Baseline aléatoire : ~33%
    - Bon encodeur : devrait capturer les infos visuelles de la HUD

    Note : les frames sont renvoyées brutes (pas pré-encodées) pour permettre
    l'extraction d'embeddings avec l'encodeur entraîné.
    """

    BUCKET_EDGES = [3, 7]  # low: 0-2, med: 3-6, high: 7-9

    def __init__(self, data_path: str, label: str = "health"):
        data = _load_npz(data_path)
        assert label in ("health", "food", "drink", "energy"), f"unknown label: {label}"
        assert label in data, (
            f"'{label}' absent du dataset — relance scripts/collect.py pour le générer"
        )

        self.frames = _to_float(data["frames"])         # [N, 3, H, W]
        raw_labels = data[label].astype(np.int64)       # [N] int 0–9

        # Bucketise en 3 classes (0=low, 1=med, 2=high)
        self.labels = torch.from_numpy(
            np.digitize(raw_labels, self.BUCKET_EDGES).astype(np.int64)
        )  # valeurs 0, 1 ou 2

        self.label_name = label

    def __len__(self) -> int:
        return len(self.frames)

    def __getitem__(self, idx: int):
        return self.frames[idx], self.labels[idx]

    def class_counts(self) -> dict:
        counts = torch.bincount(self.labels, minlength=3)
        return {"low": counts[0].item(), "med": counts[1].item(), "high": counts[2].item()}


class CrafterWMDataset(Dataset):
    """
    Triplets (frame_t, action_t, frame_{t+1}) pour entraîner le world model.

    Le world model doit apprendre : étant donné l'état latent s_t et l'action a_t,
    prédire l'état latent suivant ŝ_{t+1}. On fournit les frames brutes — l'encodeur
    gelé (Phase 1) les convertira en latents pendant l'entraînement.

    Crafter a 17 actions discrètes (noop, déplacements, do, craft…).
    """

    N_ACTIONS: int = 17

    def __init__(self, data_path: str):
        data = _load_npz(data_path)
        frames = _to_float(data["frames"])         # [N, 3, H, W]
        actions = data["actions"].astype(np.int64) # [N]
        dones = data["dones"]                      # [N] bool

        valid = np.where(~dones[:-1])[0]
        self.x_context = frames[valid]
        self.x_target = frames[valid + 1]
        self.actions = torch.from_numpy(actions[valid])

    def __len__(self) -> int:
        return len(self.x_context)

    def __getitem__(self, idx: int):
        return self.x_context[idx], self.actions[idx], self.x_target[idx]


class CrafterSeqDataset(Dataset):
    """
    Séquences (frames[0..k], actions[0..k-1]) pour l'évaluation multi-pas.

    Retourne des fenêtres glissantes de longueur k+1 sans franchir de frontière
    d'épisode. Utilisé par eval_wm.py pour mesurer l'erreur de rollout latent
    sur k pas vs la baseline "copie de l'état initial".
    """

    def __init__(self, data_path: str, k: int = 10):
        data = _load_npz(data_path)
        frames = _to_float(data["frames"])
        actions = data["actions"].astype(np.int64)
        dones = data["dones"]

        # Une fenêtre [i, i+k] est valide si aucun done dans [i, i+k-1]
        # On vérifie en cumulant les dones sur la fenêtre.
        n = len(frames)
        valid_starts = []
        for i in range(n - k):
            if not dones[i : i + k].any():
                valid_starts.append(i)

        self.frames = frames
        self.actions = torch.from_numpy(actions)
        self.starts = valid_starts
        self.k = k

    def __len__(self) -> int:
        return len(self.starts)

    def __getitem__(self, idx: int):
        i = self.starts[idx]
        k = self.k
        seq_frames = self.frames[i : i + k + 1]   # [k+1, 3, H, W]
        seq_actions = self.actions[i : i + k]      # [k]
        return seq_frames, seq_actions

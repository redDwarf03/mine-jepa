"""
Datasets for Mine-JEPA.

CrafterFrameDataset  — (frame_t, frame_t+1) pairs for JEPA encoder training (Phase 1)
ProbeDataset         — (frame, label) pairs for linear-probe (Phase 1)
CrafterWMDataset     — (frame_t, action_t, frame_t+1) triplets for world model (Phase 2)
CrafterSeqDataset    — (frames[0..k], actions[0..k-1]) sequences for multi-step eval
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
    (frame_t, frame_t+1) pairs for JEPA encoder training.

    Episode boundaries (done=True) are carefully avoided: we never
    create a pair whose first frame is the last frame of an episode.

    Why this constraint? If frame_t is the last frame of an episode
    (player died or won), frame_t+1 belongs to a different episode
    — the model cannot predict coherent dynamics across them.
    """

    def __init__(self, data_path: str):
        data = _load_npz(data_path)
        frames = _to_float(data["frames"])  # [N, 3, H, W]
        dones = data["dones"]               # [N] bool

        # Valid indices: frame t such that done[t] == False
        # (we can form the pair (t, t+1) without crossing an episode boundary)
        valid = np.where(~dones[:-1])[0]
        self.x_context = frames[valid]       # [M, 3, H, W]
        self.x_target = frames[valid + 1]    # [M, 3, H, W]

    def __len__(self) -> int:
        return len(self.x_context)

    def __getitem__(self, idx: int):
        return self.x_context[idx], self.x_target[idx]


class ProbeDataset(Dataset):
    """
    Linear-probe dataset: (embedding, label).

    Available labels (from Crafter inventory):
    - 'health'  (0–9) → bucketed into 3 classes: low/med/high
    - 'food'    (0–9) → same
    - 'drink'   (0–9) → same

    Probe test: can a linear classifier predict these values
    from frozen JEPA embeddings?
    - Random baseline: ~33%
    - Good encoder: should capture HUD visual information

    Note: frames are returned raw (not pre-encoded) to allow
    embedding extraction with the trained encoder.
    """

    BUCKET_EDGES = [3, 7]  # low: 0-2, med: 3-6, high: 7-9

    def __init__(self, data_path: str, label: str = "health"):
        data = _load_npz(data_path)
        assert label in ("health", "food", "drink", "energy"), f"unknown label: {label}"
        assert label in data, (
            f"'{label}' missing from dataset — re-run scripts/collect.py to generate it"
        )

        self.frames = _to_float(data["frames"])         # [N, 3, H, W]
        raw_labels = data[label].astype(np.int64)       # [N] int 0–9

        # Bucket into 3 classes (0=low, 1=med, 2=high)
        self.labels = torch.from_numpy(
            np.digitize(raw_labels, self.BUCKET_EDGES).astype(np.int64)
        )  # values 0, 1, or 2

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
    (frame_t, action_t, frame_{t+1}) triplets for world model training.

    The world model must learn: given latent state s_t and action a_t,
    predict the next latent state ŝ_{t+1}. Raw frames are provided —
    the frozen encoder (Phase 1) converts them to latents during training.

    Crafter has 17 discrete actions (noop, movements, do, craft…).
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
    (frames[0..k], actions[0..k-1]) sequences for multi-step evaluation.

    Returns sliding windows of length k+1 without crossing episode boundaries.
    Used by eval_wm.py to measure latent rollout error over k steps
    vs the "copy initial state" baseline.
    """

    def __init__(self, data_path: str, k: int = 10):
        data = _load_npz(data_path)
        frames = _to_float(data["frames"])
        actions = data["actions"].astype(np.int64)
        dones = data["dones"]

        # A window [i, i+k] is valid if no done in [i, i+k-1]
        # Checked by scanning dones over the window.
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

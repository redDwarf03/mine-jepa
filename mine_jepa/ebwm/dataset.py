"""
Sequence dataset for the action-conditioned world model (Phase 4c).

Produces sliding temporal windows [C, T, H, W] + actions [1, T] from
episodes.npz, never crossing an episode boundary (done=True).

Why sequences (vs Phase 2 pairs): video-JEPA models dynamics over T steps →
it can learn that "attacking the same trunk for k steps breaks a log",
something a Markovian 1-step WM cannot represent.
"""
from __future__ import annotations

import numpy as np
import torch
from torch.utils.data import Dataset


def _load_npz(path: str) -> dict:
    d = np.load(path)
    return {k: d[k] for k in d.files}


class MineRLSeqDataset(Dataset):
    """
    Windows (frames[t..t+T], actions[t..t+T-1]) for training video-JEPA.

    Output per item:
      obs     : [3, T, H, W] float32 [0,1]
      actions : [1, T] int64 (action indices, aligned with transitions)
      rewards : [T] float32 (for building the goal / debug)
    """

    def __init__(self, data_path: str, num_frames: int = 8, subsample: int = 1):
        data = _load_npz(data_path)
        self.frames = data["frames"]                       # [N, H, W, 3] uint8
        self.actions = data["actions"].astype(np.int64)    # [N]
        self.dones = data["dones"].astype(bool)            # [N]
        self.rewards = data.get("rewards", np.zeros(len(self.frames), dtype=np.float32)).astype(np.float32)
        self.num_frames = num_frames

        # Valid windows: no episode boundary within [i, i+T-1]
        n = len(self.frames)
        T = num_frames
        valid = []
        for i in range(n - T + 1):
            if not self.dones[i : i + T - 1].any():
                valid.append(i)
        valid = np.array(valid, dtype=np.int64)
        # Subsampling: stride-1 windows overlap heavily.
        # Keep 1 in `subsample` to reduce redundancy and speed up.
        if subsample > 1:
            valid = valid[::subsample]
        self.starts = valid

    def __len__(self) -> int:
        return len(self.starts)

    def __getitem__(self, idx: int):
        i = int(self.starts[idx])
        T = self.num_frames
        frames = self.frames[i : i + T]                    # [T, H, W, 3] uint8
        obs = torch.from_numpy(frames).float() / 255.0     # [T, H, W, 3]
        obs = obs.permute(3, 0, 1, 2).contiguous()         # [3, T, H, W]
        actions = torch.from_numpy(self.actions[i : i + T]).unsqueeze(0)  # [1, T]
        rewards = torch.from_numpy(self.rewards[i : i + T])               # [T]
        return obs, actions, rewards

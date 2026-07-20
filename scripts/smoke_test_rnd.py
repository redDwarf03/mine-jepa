"""
CPU-only smoke test for online RND (Random Network Distillation, arXiv:1810.12894)
— mine_jepa/ebwm/rnd.py — before spending any live MineRL compute on it
(docs/09_curiosity_coldstart.md, docs/10_coldstart_engineering.md).

No MineRL, no Java, no GPU required. Uses real recorded latents (frozen craft_wm_v4
encoder on data/minerl_craft/episodes.npz) rather than synthetic data, since the
question is whether RND separates "revisited" from "novel" on THIS latent space.

Procedure:
  1. Encode a T-frame consecutive slice from one demo episode ("the spawn area the
     agent keeps revisiting") with the frozen craft_wm_v4 encoder.
  2. Pick z_early (an early frame in that slice) and z_novel (a frame from a
     different, distant episode — a genuinely different scene).
  3. Replay the slice in order into an RNDModule: push each real latent into a ring
     buffer, train the predictor online on random buffer batches, and at every tick
     log disagreement(z_early) and disagreement(z_novel) — both read-only, never
     trained on.
  4. Report whether z_early's novelty decays while z_novel's stays high (PASS), or
     one of the documented failure modes (both drop together / z_early never moves /
     both flat and noisy).

Usage: run.bat scripts/smoke_test_rnd.py
"""
from __future__ import annotations

import argparse
import random
from collections import deque

import numpy as np
import torch

from mine_jepa.ebwm.craft_wm import build_craft_wm_v4
from mine_jepa.ebwm.rnd import RNDModule


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", default="checkpoints/craft_wm_v4.pt")
    p.add_argument("--data", default="data/minerl_craft/episodes.npz")
    p.add_argument("--ticks", type=int, default=300)
    p.add_argument("--early-idx", type=int, default=10)
    p.add_argument("--buffer-size", type=int, default=256)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--log-every", type=int, default=10)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--plot", default="", help="optional path to save a .png curve")
    return p.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def load_craft_wm(ckpt_path: str, device):
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    cfg = ckpt["cfg"]
    items = ckpt["inventory_items"]
    wm = build_craft_wm_v4(cfg["model"], cfg["regularizer"], cfg["head"], n_items=len(items))
    wm.load_state_dict(ckpt["model_state"])
    wm.eval()
    return wm.to(device), items


@torch.no_grad()
def encode_frames(wm, frames: np.ndarray, device, batch_size: int = 128) -> torch.Tensor:
    """frames [N,64,64,3] uint8 -> latents [N,D,H',W'] (frozen encoder, T=1 each)."""
    out = []
    for i in range(0, len(frames), batch_size):
        chunk = torch.from_numpy(frames[i:i + batch_size]).float() / 255.0
        chunk = chunk.permute(0, 3, 1, 2).unsqueeze(2).to(device)   # [B,3,1,64,64]
        lat = wm.encode(chunk).squeeze(2)                            # [B,D,H',W']
        out.append(lat)
    return torch.cat(out, dim=0)


def main():
    args = parse_args()
    seed_everything(args.seed)
    device = torch.device("cpu")
    print(f"Device: {device} (CPU-only smoke test, no MineRL/Java/GPU)")

    print(f"\nLoading frozen craft_wm_v4 from {args.checkpoint}...")
    wm, items = load_craft_wm(args.checkpoint, device)
    print(f"  items: {list(items)}")

    print(f"Loading frames from {args.data}...")
    d = np.load(args.data)
    frames, dones = d["frames"], d["dones"].astype(bool)
    done_idx = np.nonzero(dones)[0]
    ep0_end = int(done_idx[0])                 # episode 0 spans [0, ep0_end]
    seq_len = min(args.ticks, ep0_end + 1)
    seq_frames = frames[:seq_len]
    print(f"  episode 0 length: {ep0_end + 1} frames — using first {seq_len} as the replay sequence")

    # z_novel: a frame from a distant, different episode (last episode in the dataset)
    # — a genuinely different demo, spawn, and scene, not just a later timestep.
    novel_ep_start = int(done_idx[-2]) + 1 if len(done_idx) > 1 else ep0_end + 1
    novel_frame_idx = novel_ep_start + (int(done_idx[-1]) - novel_ep_start) // 2
    print(f"  z_novel source: frame {novel_frame_idx} (episode ending at {int(done_idx[-1])}, "
          f"distinct demo from episode 0)")

    print("\nEncoding sequence + probes with the frozen encoder (no grad)...")
    seq_latents = encode_frames(wm, seq_frames, device)                        # [seq_len,D,H,W]
    probe_frames = np.stack([frames[args.early_idx], frames[novel_frame_idx]])
    probe_latents = encode_frames(wm, probe_frames, device)                    # [2,D,H,W]
    z_early = probe_latents[0:1]        # [1,D,H,W]
    z_novel = probe_latents[1:2]        # [1,D,H,W]
    print(f"  z_early = frame {args.early_idx} (episode 0, 'spawn area')")
    print(f"  latent shape per probe: {tuple(z_early.shape)}")

    state_dim = seq_latents.shape[1]
    rnd = RNDModule(state_dim=state_dim).to(device)
    n_params = sum(p.numel() for p in rnd.parameters())
    n_trainable = sum(p.numel() for p in rnd.predictor.parameters())
    print(f"\nRNDModule params: {n_params:,} total ({n_trainable:,} trainable in predictor)")

    opt = torch.optim.Adam(rnd.predictor.parameters(), lr=args.lr)
    buffer: deque[torch.Tensor] = deque(maxlen=args.buffer_size)

    log_ticks, early_curve, novel_curve, loss_curve = [], [], [], []
    print(f"\n{'tick':>5}  {'update_loss':>11}  {'dis(early)':>10}  {'dis(novel)':>10}")
    for t in range(seq_len):
        z_t = seq_latents[t:t + 1]                          # [1,D,H,W]
        buffer.append(z_t.squeeze(0))

        loss_val = float("nan")
        if len(buffer) >= min(args.batch_size, args.buffer_size):
            idx = np.random.choice(len(buffer), size=min(args.batch_size, len(buffer)), replace=False)
            batch = torch.stack([buffer[i] for i in idx], dim=0)   # [b,D,H,W]
            loss_val = rnd.update(batch, opt)

        d_early = float(rnd.disagreement(z_early).item())
        d_novel = float(rnd.disagreement(z_novel).item())

        if t % args.log_every == 0 or t == seq_len - 1:
            log_ticks.append(t)
            early_curve.append(d_early)
            novel_curve.append(d_novel)
            loss_curve.append(loss_val)
            print(f"{t:>5}  {loss_val:>11.6f}  {d_early:>10.6f}  {d_novel:>10.6f}")

    print("\n--- Summary ---")
    print(f"dis(early)  tick0={early_curve[0]:.6f}  "
          f"tick~100={early_curve[min(len(early_curve)-1, 100 // args.log_every)]:.6f}  "
          f"tick~200={early_curve[min(len(early_curve)-1, 200 // args.log_every)]:.6f}  "
          f"final={early_curve[-1]:.6f}")
    print(f"dis(novel)  tick0={novel_curve[0]:.6f}  "
          f"tick~100={novel_curve[min(len(novel_curve)-1, 100 // args.log_every)]:.6f}  "
          f"tick~200={novel_curve[min(len(novel_curve)-1, 200 // args.log_every)]:.6f}  "
          f"final={novel_curve[-1]:.6f}")

    early_drop = early_curve[0] - early_curve[-1]
    novel_drop = novel_curve[0] - novel_curve[-1]
    early_rel_drop = early_drop / max(early_curve[0], 1e-12)
    novel_rel_drop = novel_drop / max(novel_curve[0], 1e-12)
    separation_final = novel_curve[-1] - early_curve[-1]
    print(f"\nearly: abs drop={early_drop:.6f} ({early_rel_drop:.1%})")
    print(f"novel: abs drop={novel_drop:.6f} ({novel_rel_drop:.1%})")
    print(f"final separation (novel - early): {separation_final:.6f}")

    if args.plot:
        try:
            import matplotlib.pyplot as plt
            plt.figure(figsize=(7, 4))
            plt.plot(log_ticks, early_curve, label="disagreement(z_early)")
            plt.plot(log_ticks, novel_curve, label="disagreement(z_novel)")
            plt.xlabel("tick")
            plt.ylabel("RND disagreement (MSE)")
            plt.legend()
            plt.title("Online RND smoke test")
            plt.tight_layout()
            plt.savefig(args.plot)
            print(f"\nPlot saved -> {args.plot}")
        except ImportError:
            print("\nmatplotlib not available — skipping plot, numbers above are the result.")


if __name__ == "__main__":
    main()

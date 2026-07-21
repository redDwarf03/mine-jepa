"""
Cold-start attempt #8, Proposal B (docs/10_coldstart_engineering.md) — train a
small BC actor (mine_jepa/ebwm/actor.py::BCActor) on frozen ebwm.pt latents to
PROPOSE MPC candidate action sequences for DiscreteLatentPlanner /
SwitchingCraftPlanner, replacing/supplementing the uniform/sticky prior in
_sample_actions() — not to act as the final policy (that was Phase 4's failed
pure-BC approach: reward 0, covariate shift, no correction mechanism).

Training data: the same Treechop demos ebwm.pt itself trained on
(data/minerl_goal/episodes.npz, actions already confined to the 17-action
movement space) PLUS the cold-start attempt #3 coverage episodes
(data/minerl_coverage/episodes.npz, collected under the 22-action Obtain
action space — frames whose recorded action is a craft action (index >= 17,
outside the movement-only space this actor predicts over) are DROPPED, not
remapped). Treechop demos almost never show genuine "lost and searching"
behaviour (spawns guarantee forest proximity); folding in the coverage
episodes' random-policy wandering gives the actor at least some exposure to
non-forward-attack actions (strafe, backward, camera turns) before it ever
sees a live cold-start spawn.

ebwm.pt is loaded FROZEN (requires_grad_(False)) — only BCActor's parameters
ever receive a gradient, same isolation discipline as train_value_projector.py.

Mandatory anti-collapse gate before ANY checkpoint is written (this project's
standing culture, applied here even though this isn't the JEPA backbone
itself): refuse to save if the actor's held-out predicted-action distribution
collapses to one dominant action or near-zero entropy — same
refusal-to-save discipline as train_value_projector.py / train_craft_wm_v4.py.

Usage:
  run.bat scripts/train_actor_bc.py --config configs/train_actor_bc.yaml
"""
import argparse
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
import yaml

from mine_jepa.ebwm import build_ac_jepa
from mine_jepa.ebwm.actor import BCActor
from mine_jepa.ebwm.dataset import _load_npz
from scripts.train_value_projector import episode_ranges


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/train_actor_bc.yaml")
    return p.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


class FrameActionPool:
    """
    Frame/action pairs from Treechop demos (+ optionally the attempt #3
    coverage episodes), split by EPISODE (no frame leakage into validation) —
    same discipline as train_value_projector.py::PairPool.

    self.episodes: list of (dataset_idx, start, end) — index ranges into
    self.datasets[dataset_idx].
    """

    def __init__(self, treechop_path: str, coverage_path: str | None,
                 n_actions: int, coverage_chunk_size: int = 400,
                 include_coverage: bool = True):
        d0 = _load_npz(treechop_path)
        assert int(d0["actions"].max()) < n_actions, (
            f"{treechop_path} contains action indices >= {n_actions} — unexpected "
            "for a Treechop (movement-only) demo dataset."
        )
        self.datasets = [d0]
        self.origin = ["treechop"]
        if include_coverage and coverage_path:
            d1 = _load_npz(coverage_path)
            keep = d1["actions"] < n_actions
            dropped = int((~keep).sum())
            self.datasets.append({
                "frames": d1["frames"][keep],
                "actions": d1["actions"][keep],
                "dones": d1["dones"][keep],
            })
            self.origin.append("coverage")
            print(f"  coverage: kept {int(keep.sum()):,}/{len(keep):,} frames "
                  f"(dropped {dropped:,} craft-action frames outside the "
                  f"{n_actions}-action movement space)")

        self.episodes = []
        for di, d in enumerate(self.datasets):
            # coverage_chunk_size fallback (train_value_projector.py's episode_ranges):
            # data/minerl_coverage/episodes.npz's `dones` is all-False (a shard-merge
            # bug documented there) — without the chunk fallback its frames would be
            # treated as one giant episode instead of the ~20 independent ones they are.
            chunk = coverage_chunk_size if self.origin[di] == "coverage" else None
            for s, e in episode_ranges(d["dones"].astype(bool), chunk_size=chunk):
                self.episodes.append((di, s, e))
        print("  FrameActionPool: " + ", ".join(
            f"{self.origin[di]} {len(d['frames']):,} frames "
            f"({sum(1 for e in self.episodes if e[0] == di)} episodes)"
            for di, d in enumerate(self.datasets)
        ))

    def frame_action(self, di: int, idx: int) -> tuple[np.ndarray, int]:
        return self.datasets[di]["frames"][idx], int(self.datasets[di]["actions"][idx])

    def split(self, val_fraction: float, seed: int) -> tuple[list, list]:
        eps = list(self.episodes)
        rng = np.random.RandomState(seed)
        rng.shuffle(eps)
        n_val = max(1, int(len(eps) * val_fraction))
        return eps[n_val:], eps[:n_val]

    def flat_indices(self, episodes: list) -> list[tuple[int, int]]:
        idxs = []
        for di, s, e in episodes:
            idxs.extend((di, i) for i in range(s, e))
        return idxs


def _frames_to_obs(frames: np.ndarray, device) -> torch.Tensor:
    """[B,H,W,3] uint8 -> [B,3,1,64,64] float [0,1]."""
    t = torch.from_numpy(frames).float() / 255.0
    return t.permute(0, 3, 1, 2).unsqueeze(2).to(device)


def sample_batch(pool: FrameActionPool, flat_idxs: list, batch_size: int,
                  rng: np.random.Generator, device):
    choice = rng.integers(0, len(flat_idxs), size=batch_size)
    frames, actions = [], []
    for c in choice:
        di, i = flat_idxs[c]
        f, a = pool.frame_action(di, i)
        frames.append(f)
        actions.append(a)
    obs = _frames_to_obs(np.stack(frames, axis=0), device)
    return obs, torch.tensor(actions, dtype=torch.long, device=device)


@torch.no_grad()
def encode_flat(model, obs: torch.Tensor) -> torch.Tensor:
    z = model.encode(obs).squeeze(2)
    return z.reshape(z.shape[0], -1)


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    seed = int(cfg.get("seed", 0))
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}  |  seed: {seed}")

    print("\nLoading ebwm.pt (frozen — only BCActor trains)...")
    ckpt = torch.load(cfg["model"]["ebwm_checkpoint"], map_location=device, weights_only=False)
    m, r = ckpt["cfg"]["model"], ckpt["cfg"]["regularizer"]
    model = build_ac_jepa(
        embed_dim=m["embed_dim"], encoder_hidden=m["encoder_hidden"],
        n_actions=m["n_actions"], action_embed_dim=m["action_embed_dim"],
        predictor_hidden=m["predictor_hidden"],
        std_coeff=r["std_coeff"], cov_coeff=r["cov_coeff"], sim_coeff_t=r["sim_coeff_t"],
    ).to(device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    model.requires_grad_(False)
    for p_ in model.parameters():
        assert not p_.requires_grad
    n_actions = int(cfg["actor"].get("n_actions", 17))
    print(f"  ebwm.pt loaded, requires_grad_(False) verified on all "
          f"{sum(1 for _ in model.parameters())} params | actor n_actions={n_actions}")

    d_cfg = cfg["data"]
    include_coverage = bool(d_cfg.get("include_coverage", True))
    print(f"\nLoading frame/action pool (include_coverage={include_coverage})...")
    pool = FrameActionPool(
        d_cfg["treechop_path"], d_cfg.get("coverage_path"), n_actions,
        coverage_chunk_size=int(d_cfg.get("coverage_chunk_size", 400)),
        include_coverage=include_coverage,
    )
    train_eps, val_eps = pool.split(float(d_cfg.get("val_fraction", 0.1)), seed)
    train_idx, val_idx = pool.flat_indices(train_eps), pool.flat_indices(val_eps)
    print(f"  Frames: train {len(train_idx):,}  val {len(val_idx):,}")

    f0, _ = pool.frame_action(*train_idx[0])
    probe = encode_flat(model, _frames_to_obs(f0[None], device))
    in_dim = probe.shape[1]
    print(f"\nFlattened latent dim F = {in_dim} (D*H'*W' of ebwm.pt's encode() output)")

    a_cfg = cfg["actor"]
    actor = BCActor(in_dim=in_dim, n_actions=n_actions,
                     hidden_dim=int(a_cfg.get("hidden_dim", 256))).to(device)
    n_params = sum(p_.numel() for p_ in actor.parameters())
    print(f"BCActor params: {n_params:,}")

    t_cfg = cfg["training"]
    opt = torch.optim.Adam(actor.parameters(), lr=float(t_cfg["lr"]),
                            weight_decay=float(t_cfg.get("weight_decay", 0.0)))
    epochs = int(t_cfg["epochs"])
    steps_per_epoch = int(t_cfg["steps_per_epoch"])
    bs = int(t_cfg["batch_size"])
    rng = np.random.default_rng(seed)

    print(f"\n{'Epoch':>5}  {'train_loss':>10}  {'train_acc':>9}")
    for epoch in range(1, epochs + 1):
        actor.train()
        tot_loss, tot_acc, nb = 0.0, 0.0, 0
        for _ in range(steps_per_epoch):
            obs, actions = sample_batch(pool, train_idx, bs, rng, device)
            z = encode_flat(model, obs)
            logits = actor(z)
            loss = F.cross_entropy(logits, actions)
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot_loss += float(loss.item())
            tot_acc += float((logits.argmax(dim=-1) == actions).float().mean().item())
            nb += 1
        print(f"{epoch:>5}  {tot_loss / nb:>10.4f}  {tot_acc / nb:>9.3f}", flush=True)

    # ------------------------------------------------------------------
    # Mandatory anti-collapse gate (this project's standing culture): a
    # degenerate actor that always predicts one action would silently turn
    # "propose diverse candidates" into "action_pool_priming with one macro".
    # ------------------------------------------------------------------
    actor.eval()
    val_batches = int(t_cfg.get("val_batches", 20))
    all_probs, all_actions, all_origin = [], [], []
    with torch.no_grad():
        for _ in range(val_batches):
            choice = rng.integers(0, len(val_idx), size=bs)
            frames, actions, origins = [], [], []
            for c in choice:
                di, i = val_idx[c]
                f, a = pool.frame_action(di, i)
                frames.append(f)
                actions.append(a)
                origins.append(pool.origin[di])
            obs = _frames_to_obs(np.stack(frames, axis=0), device)
            z = encode_flat(model, obs)
            probs = actor.action_probs(z, temperature=1.0)
            all_probs.append(probs.cpu())
            all_actions.extend(actions)
            all_origin.extend(origins)

    probs = torch.cat(all_probs, dim=0)                          # [Nval, n_actions]
    argmax = probs.argmax(dim=-1)
    entropy = -(probs.clamp_min(1e-8) * probs.clamp_min(1e-8).log()).sum(dim=-1)
    mean_entropy = float(entropy.mean())
    max_entropy = float(np.log(n_actions))
    hist = torch.bincount(argmax, minlength=n_actions).float()
    hist_frac = hist / hist.sum()
    top_action_frac = float(hist_frac.max())
    actions_t = torch.tensor(all_actions)
    val_acc = float((argmax == actions_t).float().mean())

    print(f"\n{'='*60}")
    print("ANTI-COLLAPSE SANITY CHECK (held-out episodes, mandatory gate)")
    print(f"  Val accuracy               : {val_acc:.3f}")
    print(f"  Mean predictive entropy    : {mean_entropy:.3f}  (max possible = {max_entropy:.3f})")
    print(f"  Top-action argmax fraction : {top_action_frac:.3f}  "
          f"(action a{int(hist_frac.argmax())})")
    print("  Argmax histogram           : "
          + " ".join(f"a{i}={f:.2f}" for i, f in enumerate(hist_frac.tolist()) if f > 0.01))

    # Does the actor behave differently on treechop-like vs coverage-like
    # held-out frames? (docs/10 attempt #8, Proposal B — the question this
    # dispatch was asked to answer about the training-data mix.)
    if include_coverage:
        origin_arr = np.array(all_origin)
        for origin in ("treechop", "coverage"):
            mask = origin_arr == origin
            if mask.any():
                sub_hist = torch.bincount(argmax[mask], minlength=n_actions).float()
                sub_hist = sub_hist / sub_hist.sum()
                print(f"  {origin:>9} argmax dist    : "
                      + " ".join(f"a{i}={f:.2f}" for i, f in enumerate(sub_hist.tolist()) if f > 0.01))
    print(f"{'='*60}")

    min_entropy = float(cfg["checkpoint"].get("min_mean_entropy", 0.3))
    max_top_frac = float(cfg["checkpoint"].get("max_top_action_frac", 0.9))
    ok = mean_entropy >= min_entropy and top_action_frac <= max_top_frac
    print(f"  Gate: mean_entropy >= {min_entropy} AND top_action_frac <= {max_top_frac} "
          f"-> {'PASS' if ok else 'FAIL'}")

    if not ok:
        print("\nCOLLAPSE CHECK FAILED: the actor's held-out predicted-action "
              f"distribution is too concentrated. Refusing to write "
              f"{cfg['checkpoint']['name']} (anti-collapse guardrail, same discipline "
              "as train_value_projector.py / train_craft_wm_v4.py's refusal-to-save). "
              "Do NOT wire this checkpoint into the planner.")
        return

    ckpt_dir = Path(cfg["checkpoint"]["dir"])
    ckpt_dir.mkdir(exist_ok=True)
    ckpt_path = ckpt_dir / cfg["checkpoint"]["name"]
    actor.save(str(ckpt_path))
    print(f"\nGate passed -> checkpoint saved: {ckpt_path}")


if __name__ == "__main__":
    main()

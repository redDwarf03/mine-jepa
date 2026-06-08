"""
Train WM v3 — inventory- and reward-aware action-conditioned world model.

Same eb-JEPA backbone/recipe as train_eb_jepa.py (T=8, 20 ep, ratio sweet spot ~0.93),
plus two auxiliary heads (reward + inventory). The latent is forced to encode the
crafting mechanics so the MPC planner can target "get planks".

Gates:
  - latent ratio val_pred/val_copy < 1.0  (WM predicts better than copying)
  - batch_var > collapse_threshold each epoch (no collapse — risk #1)
  - reward/inventory MSE decreasing (the latent becomes task-aware)

Usage: run.bat scripts/train_craft_wm.py
"""
import argparse
from pathlib import Path

import torch
import yaml
from torch.utils.data import DataLoader, random_split

from mine_jepa.ebwm.craft_wm import build_craft_wm
from mine_jepa.ebwm.dataset import CraftSeqDataset


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/train_craft_wm.yaml")
    return p.parse_args()


def load_cfg(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


@torch.no_grad()
def evaluate(wm, loader, device):
    """Returns latent ratio, batch_var, reward_mse, inv_mse, planks_mse."""
    wm.eval()
    pred_s = copy_s = var_s = rew_s = inv_s = plk_s = 0.0
    n = 0
    for obs, actions, rewards, inv in loader:
        obs, actions = obs.to(device), actions.to(device)
        rewards, inv = rewards.to(device), inv.to(device)
        state = wm.encode(obs)                                       # [B,D,T,H,W]
        preds, _ = wm.jepa.unroll(obs, actions, nsteps=1,
                                  unroll_mode="parallel", compute_loss=False)
        pred_loss = ((preds[:, :, 1:] - state[:, :, 1:]) ** 2).mean().item()
        copy_loss = ((state[:, :, :-1] - state[:, :, 1:]) ** 2).mean().item()
        bvar = state.var(dim=0).mean().item()
        rew_pred = wm.predict_reward(state)
        inv_pred = wm.predict_inventory(state)
        b = obs.size(0)
        pred_s += pred_loss * b
        copy_s += copy_loss * b
        var_s += bvar * b
        rew_s += ((rew_pred - rewards) ** 2).mean().item() * b
        inv_s += ((inv_pred - inv) ** 2).mean().item() * b
        plk_s += ((inv_pred[..., 1] - inv[..., 1]) ** 2).mean().item() * b  # planks column
        n += b
    ratio = (pred_s / n) / max(copy_s / n, 1e-9)
    return ratio, var_s / n, rew_s / n, inv_s / n, plk_s / n


def main():
    args = parse_args()
    cfg = load_cfg(args.config)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    d = cfg["data"]
    print(f"Loading: {d['path']} (T={d['num_frames']}, subsample={d['subsample']})")
    ds = CraftSeqDataset(d["path"], num_frames=d["num_frames"], subsample=d["subsample"])
    print(f"  Inventory items: {ds.inventory_items}")
    n_val = int(len(ds) * d["val_fraction"])
    n_train = len(ds) - n_val
    train_ds, val_ds = random_split(ds, [n_train, n_val],
                                    generator=torch.Generator().manual_seed(42))
    print(f"  Windows: train {n_train:,}  val {n_val:,}")

    t = cfg["training"]
    train_loader = DataLoader(train_ds, batch_size=t["batch_size"], shuffle=True,
                              num_workers=t["num_workers"], drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=t["batch_size"], shuffle=False,
                            num_workers=t["num_workers"])

    wm = build_craft_wm(cfg["model"], cfg["regularizer"], cfg["head"], ds.n_items).to(device)
    n_params = sum(p.numel() for p in wm.parameters())
    print(f"Params: {n_params:,}")

    opt = torch.optim.Adam(wm.parameters(), lr=t["lr"], weight_decay=t["weight_decay"])
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=t["epochs"])
    collapse_thr = cfg["logging"]["collapse_threshold"]

    print(f"\n{'Epoch':>5}  {'loss':>8}  {'reg':>7}  {'rew':>7}  {'inv':>7}  "
          f"{'ratio':>6}  {'bvar':>7}  {'plkMSE':>7}")

    best_ratio = float("inf")
    best_state = None
    for epoch in range(1, t["epochs"] + 1):
        wm.train()
        tot, nb = 0.0, 0
        comp = {}
        for obs, actions, rewards, inv in train_loader:
            obs, actions = obs.to(device), actions.to(device)
            rewards, inv = rewards.to(device), inv.to(device)
            opt.zero_grad()
            loss, parts = wm.loss(obs, actions, rewards, inv)
            loss.backward()
            opt.step()
            tot += loss.detach().item()
            nb += 1
            for k, v in parts.items():
                comp[k] = comp.get(k, 0.0) + v
        sched.step()

        ratio, bvar, rew_mse, inv_mse, plk_mse = evaluate(wm, val_loader, device)
        collapsed = bvar < collapse_thr
        flag = "  COLLAPSE" if collapsed else ""
        if ratio < best_ratio and not collapsed:
            best_ratio = ratio
            best_state = {k: v.cpu().clone() for k, v in wm.state_dict().items()}

        print(f"{epoch:>5}  {tot/nb:>8.4f}  {comp['reg']/nb:>7.4f}  "
              f"{comp['reward']/nb:>7.4f}  {comp['inv']/nb:>7.4f}  "
              f"{ratio:>6.3f}  {bvar:>7.4f}  {plk_mse:>7.4f}{flag}")

    gate = best_ratio < 1.0
    print(f"\nBest ratio: {best_ratio:.3f}  ({'OK GATE' if gate else 'FAIL GATE'}: <1.0)")

    ckpt_dir = Path(cfg["checkpoint"]["dir"])
    ckpt_dir.mkdir(exist_ok=True)
    ckpt_path = ckpt_dir / cfg["checkpoint"]["name"]
    if best_state is not None:
        wm.load_state_dict(best_state)
    torch.save({"model_state": wm.state_dict(), "cfg": cfg, "ratio": best_ratio,
                "inventory_items": ds.inventory_items}, ckpt_path)
    print(f"Checkpoint -> {ckpt_path}")


if __name__ == "__main__":
    main()

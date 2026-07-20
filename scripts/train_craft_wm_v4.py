"""
Train WM v4 — inventory as a STATE variable (visual eb-JEPA + InventoryDynamics).

The visual eb-JEPA learns perception (tree ahead? near a table?); the InventoryDynamics
MLP learns the near-deterministic crafting/chopping rules conditioned on the visual
latent. Crucially the inventory is an INPUT, so "craft when log>=1 -> planks+4" is a
learnable transition (impossible for v3, where inventory was guessed from the frame).

Key metric: dPlanks@craft — the mean predicted change in planks on the steps where the
demonstrator actually crafted planks (action 17). It should go clearly POSITIVE: that
is the model discovering the craft mechanic.

Usage: run.bat scripts/train_craft_wm_v4.py
"""
import argparse
import random
from pathlib import Path

import numpy as np
import torch
import yaml
from torch.utils.data import DataLoader, random_split

from mine_jepa.ebwm.craft_wm import build_craft_wm_v4
from mine_jepa.ebwm.dataset import INV_SCALE, CraftSeqDataset

CRAFT_PLANKS_ACTION = 17
PLANKS_COL = 1


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/train_craft_wm_v4.yaml")
    return p.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


@torch.no_grad()
def evaluate(wm, loader, device):
    """Returns visual ratio, batch_var, inv-dynamics MSE, and dPlanks@craft (raw count)."""
    wm.eval()
    pred_s = copy_s = var_s = inv_s = 0.0
    dplk_sum = 0.0
    dplk_cnt = 0
    n = 0
    for obs, actions, _rew, inv in loader:
        obs, actions, inv = obs.to(device), actions.to(device), inv.to(device)
        visual = wm.encode(obs)                                      # [B,D,T,H,W]
        preds, _ = wm.jepa.unroll(obs, actions, nsteps=1,
                                  unroll_mode="parallel", compute_loss=False)
        pred_s += ((preds[:, :, 1:] - visual[:, :, 1:]) ** 2).mean().item() * obs.size(0)
        copy_s += ((visual[:, :, :-1] - visual[:, :, 1:]) ** 2).mean().item() * obs.size(0)
        var_s += visual.var(dim=0).mean().item() * obs.size(0)

        vpool = visual.mean(dim=(3, 4)).permute(0, 2, 1)             # [B,T,D]
        act = actions.squeeze(1)                                     # [B,T]
        inv_pred = wm.inv_dyn(inv[:, :-1], act[:, :-1], vpool[:, :-1])  # [B,T-1,K]
        inv_s += ((inv_pred - inv[:, 1:]) ** 2).mean().item() * obs.size(0)

        # dPlanks on craft-planks steps (predicted next planks - current planks)
        mask = act[:, :-1] == CRAFT_PLANKS_ACTION                   # [B,T-1]
        if mask.any():
            dplk = (inv_pred[..., PLANKS_COL] - inv[:, :-1, PLANKS_COL])[mask]
            dplk_sum += dplk.sum().item() * INV_SCALE               # back to raw count
            dplk_cnt += int(mask.sum().item())
        n += obs.size(0)

    ratio = (pred_s / n) / max(copy_s / n, 1e-9)
    dplanks = dplk_sum / dplk_cnt if dplk_cnt else float("nan")
    return ratio, var_s / n, inv_s / n, dplanks, dplk_cnt


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    seed = int(cfg.get("seed", 42))
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}  |  seed: {seed}")

    d = cfg["data"]
    print(f"Loading: {d['path']} (T={d['num_frames']}, subsample={d['subsample']})")
    ds = CraftSeqDataset(d["path"], num_frames=d["num_frames"], subsample=d["subsample"])
    print(f"  Inventory items: {ds.inventory_items}")
    n_val = int(len(ds) * d["val_fraction"])
    train_ds, val_ds = random_split(ds, [len(ds) - n_val, n_val],
                                    generator=torch.Generator().manual_seed(42))
    print(f"  Windows: train {len(ds) - n_val:,}  val {n_val:,}")

    t = cfg["training"]
    train_loader = DataLoader(train_ds, batch_size=t["batch_size"], shuffle=True,
                              num_workers=t["num_workers"], drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=t["batch_size"], shuffle=False,
                            num_workers=t["num_workers"])

    wm = build_craft_wm_v4(cfg["model"], cfg["regularizer"], cfg["head"], ds.n_items).to(device)
    print(f"Params: {sum(p.numel() for p in wm.parameters()):,}")

    # Fine-tune from a previously trained checkpoint (cold-start attempt #3, docs/10):
    # widen the visual distribution with coverage frames without redoing the full
    # from-scratch recipe. Absent key = default behaviour (train from scratch).
    ckpt_cfg = cfg.get("checkpoint", {})
    resume_from = ckpt_cfg.get("resume_from")
    baseline_dplanks = None
    best_inv = float("inf")
    best_state = None
    if resume_from:
        print(f"Resuming from: {resume_from}")
        resume_ckpt = torch.load(resume_from, map_location=device, weights_only=False)
        wm.load_state_dict(resume_ckpt["model_state"])
        pre_ratio, pre_bvar, pre_inv_mse, pre_dplanks, pre_dcnt = evaluate(wm, val_loader, device)
        print(f"  Pre-finetune eval: ratio={pre_ratio:.3f}  bvar={pre_bvar:.4f}  "
              f"invMSE={pre_inv_mse:.4f}  dPlanks@craft={pre_dplanks:+.2f} (n={pre_dcnt})")
        baseline_dplanks = pre_dplanks
        best_inv = pre_inv_mse
        best_state = {k: v.cpu().clone() for k, v in wm.state_dict().items()}

    opt = torch.optim.Adam(wm.parameters(), lr=t["lr"], weight_decay=t["weight_decay"])
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=t["epochs"])
    collapse_thr = cfg["logging"]["collapse_threshold"]
    dplanks_regression_tol = float(cfg["logging"].get("dplanks_regression_tol", 1.5))

    print(f"\n{'Epoch':>5}  {'loss':>8}  {'reg':>7}  {'invLoss':>8}  {'precond':>8}  "
          f"{'ratio':>6}  {'bvar':>7}  {'invMSE':>7}  {'dPlanks@craft':>13}")

    for epoch in range(1, t["epochs"] + 1):
        wm.train()
        tot, nb = 0.0, 0
        comp = {}
        for obs, actions, _rew, inv in train_loader:
            obs, actions, inv = obs.to(device), actions.to(device), inv.to(device)
            opt.zero_grad()
            loss, parts = wm.loss(obs, actions, inv)
            loss.backward()
            opt.step()
            tot += loss.detach().item()
            nb += 1
            for k, v in parts.items():
                comp[k] = comp.get(k, 0.0) + v
        sched.step()

        ratio, bvar, inv_mse, dplanks, dcnt = evaluate(wm, val_loader, device)
        collapsed = bvar < collapse_thr
        regressed = (baseline_dplanks is not None and dcnt > 0
                     and not (dplanks != dplanks)  # nan guard
                     and dplanks < baseline_dplanks - dplanks_regression_tol)
        flag = "  COLLAPSE" if collapsed else ("  DPLANKS-REGRESSION" if regressed else "")
        # Select best by inventory-dynamics MSE (the thing that matters for crafting)
        if inv_mse < best_inv and not collapsed and not regressed:
            best_inv = inv_mse
            best_state = {k: v.cpu().clone() for k, v in wm.state_dict().items()}

        print(f"{epoch:>5}  {tot/nb:>8.4f}  {comp['reg']/nb:>7.4f}  {comp['inv']/nb:>8.4f}  "
              f"{comp.get('precond', 0)/nb:>8.4f}  {ratio:>6.3f}  {bvar:>7.4f}  {inv_mse:>7.4f}  "
              f"{dplanks:>+10.2f} (n={dcnt}){flag}", flush=True)

        if collapsed:
            print(f"  ABORT: batch_var {bvar:.4f} < collapse_threshold {collapse_thr} "
                  f"— stopping, keeping the last non-collapsed state (backup-equivalent "
                  f"if epoch 1).", flush=True)
            break
        if regressed:
            print(f"  ABORT: dPlanks@craft {dplanks:+.2f} regressed more than "
                  f"{dplanks_regression_tol:.2f} below the pre-finetune baseline "
                  f"{baseline_dplanks:+.2f} — stopping, keeping the last good state.",
                  flush=True)
            break

    print(f"\nBest inv-dynamics MSE: {best_inv:.4f}")

    if best_state is None:
        print("No non-collapsed epoch produced a usable state — refusing to write "
              "a checkpoint (anti-collapse guardrail).")
        return

    ckpt_dir = Path(cfg["checkpoint"]["dir"])
    ckpt_dir.mkdir(exist_ok=True)
    ckpt_path = ckpt_dir / cfg["checkpoint"]["name"]
    wm.load_state_dict(best_state)
    torch.save({"model_state": wm.state_dict(), "cfg": cfg, "inv_mse": best_inv,
                "inventory_items": ds.inventory_items}, ckpt_path)
    print(f"Checkpoint -> {ckpt_path}")


if __name__ == "__main__":
    main()

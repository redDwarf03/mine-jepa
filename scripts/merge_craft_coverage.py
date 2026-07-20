"""
Merge the ObtainIronPickaxe expert demos with cheap self-supervised coverage
episodes (cold-start attempt #3, docs/10 follow-up).

Why: the 40 expert demos (data/minerl_craft/episodes.npz) underrepresent
"lost, no tree in view" states — experts reach wood fast. Coverage episodes
(random policy, random spawn, data/minerl_coverage/episodes.npz, built by
collect_minerl_multi.py + configs/collect_minerl_coverage.yaml) add that
missing visual diversity for free, at the cost of having no real inventory
signal (random policy essentially never crafts) — so their inventory rows are
zero-filled. CraftSeqDataset only needs frames/actions/dones to be real; the
zero inventory rows simply contribute no craft-transition signal (they are
never masked as craft_mask=True unless the random policy happens to sample a
craft action, which is harmless: craft-on-empty-inventory is exactly the
precondition-negative behaviour the model should already have learned).

Usage:
    run.bat scripts/merge_craft_coverage.py \
        --demos data/minerl_craft/episodes.npz \
        --coverage data/minerl_coverage/episodes.npz \
        --out data/minerl_craft_v2/episodes.npz
"""
import argparse
from pathlib import Path

import numpy as np


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--demos", default="data/minerl_craft/episodes.npz")
    p.add_argument("--coverage", default="data/minerl_coverage/episodes.npz")
    p.add_argument("--out", default="data/minerl_craft_v2/episodes.npz")
    return p.parse_args()


def main():
    args = parse_args()
    demos = np.load(args.demos)
    coverage = np.load(args.coverage)

    inventory_items = [str(x) for x in demos["inventory_items"]]
    n_items = len(inventory_items)

    n_demo = demos["frames"].shape[0]
    n_cov = coverage["frames"].shape[0]

    frames = np.concatenate([demos["frames"], coverage["frames"]], axis=0)
    actions = np.concatenate([demos["actions"], coverage["actions"]], axis=0)
    dones = np.concatenate([demos["dones"], coverage["dones"]], axis=0)
    # Force a boundary at the demos/coverage junction so no sliding window can
    # bridge two frames that were never actually consecutive in the real env.
    dones[n_demo - 1] = True

    rewards_demo = demos["rewards"].astype(np.float32)
    rewards_cov = np.zeros(n_cov, dtype=np.float32)  # random policy: no craft/reward signal
    rewards = np.concatenate([rewards_demo, rewards_cov], axis=0)

    inv_demo = demos["inventory"].astype(np.int32)
    inv_cov = np.zeros((n_cov, n_items), dtype=np.int32)  # zero-filled: no real inventory read
    inventory = np.concatenate([inv_demo, inv_cov], axis=0)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_path,
        frames=frames, actions=actions, dones=dones, rewards=rewards,
        inventory=inventory, inventory_items=np.array(inventory_items),
    )

    print(f"Demos    : {n_demo:,} transitions ({args.demos})")
    print(f"Coverage : {n_cov:,} transitions ({args.coverage})")
    print(f"Merged   : {frames.shape[0]:,} transitions -> {out_path}")
    print(f"  frames shape : {frames.shape}")
    print(f"  inventory    : {inventory.shape}  items={inventory_items}")


if __name__ == "__main__":
    main()

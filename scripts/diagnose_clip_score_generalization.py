"""
Cold-start attempt #13 (docs/10_coldstart_engineering.md) — cheap "Phase 1" test,
proposed by the Explorer, ahead of any expensive encoder-side fix for the
directional confound attempt #10 found in ebwm.pt's own goal-centroid scoring.

Attempts #7 / #8-followup / #11 each trained a small head on ebwm.pt's FROZEN
latent space and each one found a brightness/lighting shortcut instead of real
tree-proximity (brightness correlation 0.117 -> 0.498 -> 0.643, getting worse each
time) — consistent with the confound living in ebwm.pt's own narrow, Treechop-only
representation, which none of those three attempts touched.

This script asks a cheaper, more targeted question first: does an OFF-THE-SHELF
pretrained vision-language model (CLIP, zero-shot, NO training at all, never sees
ebwm.pt's latent space) already separate "tree nearby" from "no tree" correctly on
the exact same Obtain-domain frames where ebwm.pt's own score reverses? Pure
inference on already-saved images. No MineRL/Java, no GPU strictly required, no
checkpoint (ebwm.pt, craft_wm_v4.pt, or any value-projector) is loaded, touched, or
modified anywhere in this script.

Frame gathering (`gather_treechop_frames`, `gather_obtain_frames`) is imported
VERBATIM from scripts/diagnose_score_generalization.py so the 160 Treechop + 11 real
Obtain spawn (assets/spawn_thumbs/) + 80 Obtain-coverage frames attempt #10 already
scored are exactly reproduced here, directly comparable frame-for-frame.

Ground truth for the two mandatory gates below is attempt #11's own hand-labeled
direction-check set (configs/train_value_projector_obtain.yaml's `direction_check`
block: 2 tree-close + 4 no-tree spawn PNGs, plus coverage indices [0, 2800] as
tree-close and [400, 2000] as no-tree) — read from that file directly, never
re-labeled by eye here.

Gates (mirrors the project's existing dual-gate discipline,
scripts/train_value_projector.py / train_value_projector_obtain.py):
  a. Separation: mean CLIP score (sim(forest_prompt) - sim(open_prompt)) on
     tree-close labeled frames vs. no-tree labeled frames must be higher for
     tree-close, with a >= min_separation_ratio ratio.
  b. Brightness confound: Pearson r between CLIP score and mean pixel brightness
     across the same labeled set must be clearly below attempt #11's 0.643
     (target |r| < 0.3) — a large |r| here would mean CLIP found the same
     shortcut, not a real fix.

Usage: run.bat scripts/diagnose_clip_score_generalization.py --config configs/diagnose_clip_score_generalization.yaml
"""
import argparse
import random
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import open_clip
import torch
import yaml
from PIL import Image

from mine_jepa.ebwm.dataset import _load_npz
from scripts.diagnose_score_generalization import (
    gather_obtain_frames,
    gather_treechop_frames,
    print_summary,
)
from scripts.train_value_projector import brightness_of


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/diagnose_clip_score_generalization.yaml")
    return p.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


@torch.no_grad()
def clip_scores(model, preprocess, text_features: torch.Tensor, frames: list,
                 device, batch_size: int) -> np.ndarray:
    """
    CLIP score per frame = sim(image, forest_prompt) - sim(image, open_prompt),
    both cosine similarities (L2-normalised embeddings, dot product). Positive =
    scored as more forest-like than open-field-like.
    """
    scores = []
    for i in range(0, len(frames), batch_size):
        chunk = frames[i:i + batch_size]
        imgs = torch.stack([preprocess(Image.fromarray(f)) for f in chunk]).to(device)
        feats = model.encode_image(imgs)
        feats = feats / feats.norm(dim=-1, keepdim=True)
        sims = feats @ text_features.T                      # [B, 2] (forest, open)
        scores.append((sims[:, 0] - sims[:, 1]).cpu().numpy())
    return np.concatenate(scores)


def load_labeled_frames(cfg: dict) -> tuple[list, list]:
    """
    Reuses attempt #11's hand-labeled direction_check block from
    configs/train_value_projector_obtain.yaml VERBATIM (same PNGs, same coverage
    indices) — returns (tree_close_frames, no_tree_frames), both lists of
    [H,W,3] uint8 arrays.
    """
    gt_cfg = yaml.safe_load(open(cfg["ground_truth"]["source_config"]))
    dc = gt_cfg["direction_check"]
    thumb_dir = Path(dc["spawn_thumb_dir"])

    def load_spawn(fname: str) -> np.ndarray:
        return imageio.imread(str(thumb_dir / fname))[:, :, :3]

    tree_frames = [load_spawn(f) for f in dc["tree_close_files"]]
    notree_frames = [load_spawn(f) for f in dc["no_tree_files"]]

    coverage_frames = _load_npz(cfg["ground_truth"]["coverage_data_path"])["frames"]
    tree_frames += [coverage_frames[int(i)] for i in dc["coverage_tree_close_idx"]]
    notree_frames += [coverage_frames[int(i)] for i in dc["coverage_no_tree_idx"]]
    return tree_frames, notree_frames


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    seed = int(cfg.get("seed", 0))
    seed_everything(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}  |  seed: {seed}")

    clip_cfg = cfg["clip"]
    print(f"\nLoading CLIP {clip_cfg['model_name']} ({clip_cfg['pretrained']}) "
          f"— off-the-shelf, zero-shot, no training, no ebwm.pt/craft_wm_v4 involved...")
    model, _, preprocess = open_clip.create_model_and_transforms(
        clip_cfg["model_name"], pretrained=clip_cfg["pretrained"],
    )
    model = model.to(device).eval()
    model.requires_grad_(False)
    tokenizer = open_clip.get_tokenizer(clip_cfg["model_name"])

    prompts = [clip_cfg["forest_prompt"], clip_cfg["open_prompt"]]
    with torch.no_grad():
        text_tokens = tokenizer(prompts).to(device)
        text_features = model.encode_text(text_tokens)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
    print(f"  prompts: forest={prompts[0]!r}  open={prompts[1]!r}")

    bs = int(clip_cfg.get("batch_size", 32))

    rng = np.random.RandomState(seed)
    print("\nGathering frames (VERBATIM from scripts/diagnose_score_generalization.py, "
          "same 160 Treechop + 11 real Obtain spawn + 80 Obtain-coverage frames as attempt #10)...")
    treechop_rows = gather_treechop_frames(cfg["treechop"], rng)
    obtain_rows = gather_obtain_frames(cfg["obtain"])
    n_spawn = sum(1 for r in obtain_rows if r["group"] == "obtain_spawn")
    n_cov = sum(1 for r in obtain_rows if r["group"] == "obtain_coverage")
    print(f"  treechop: {len(treechop_rows)} frames | obtain_spawn: {n_spawn} | obtain_coverage: {n_cov}")

    all_rows = treechop_rows + obtain_rows
    print(f"\nScoring {len(all_rows)} frames through CLIP "
          f"(sim(forest_prompt) - sim(open_prompt))...")
    frames = [r["frame"] for r in all_rows]
    scores = clip_scores(model, preprocess, text_features, frames, device, bs)
    for row, s in zip(all_rows, scores):
        row["clip_score"] = float(s)

    out_dir = Path(cfg["output"]["dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    full_csv = out_dir / cfg["output"]["full_csv_name"]
    with open(full_csv, "w") as f:
        f.write("group,episode,offset,frame_idx,clip_score\n")
        for row in all_rows:
            f.write(f"{row['group']},{row['episode']},{row['offset']},{row['frame_idx']},"
                    f"{row['clip_score']:.6f}\n")
    print(f"Full-population CSV saved -> {full_csv}")

    print(f"\n{'=' * 78}\nFULL-POPULATION SUMMARY (CLIP score, for context — not a gate)\n{'=' * 78}")
    groups = {
        "treechop": np.array([r["clip_score"] for r in all_rows if r["group"] == "treechop"]),
        "obtain_spawn": np.array([r["clip_score"] for r in all_rows if r["group"] == "obtain_spawn"]),
        "obtain_coverage": np.array([r["clip_score"] for r in all_rows if r["group"] == "obtain_coverage"]),
    }
    for name, vals in groups.items():
        if len(vals):
            print_summary(name, vals)

    # ------------------------------------------------------------------
    # Ground-truth labeled set (attempt #11's direction_check block, reused
    # verbatim) — the actual gates run on this, not the full population.
    # ------------------------------------------------------------------
    print(f"\n{'=' * 78}\nGATES (attempt #11's hand-labeled direction-check set, reused verbatim)\n{'=' * 78}")
    tree_frames, notree_frames = load_labeled_frames(cfg)
    tree_scores = clip_scores(model, preprocess, text_features, tree_frames, device, bs)
    notree_scores = clip_scores(model, preprocess, text_features, notree_frames, device, bs)
    tree_bright = brightness_of(tree_frames)
    notree_bright = brightness_of(notree_frames)

    labeled_csv = out_dir / cfg["output"]["labeled_csv_name"]
    with open(labeled_csv, "w") as f:
        f.write("label,index,clip_score,brightness\n")
        for i, (s, b) in enumerate(zip(tree_scores, tree_bright)):
            f.write(f"tree_close,{i},{s:.6f},{b:.6f}\n")
        for i, (s, b) in enumerate(zip(notree_scores, notree_bright)):
            f.write(f"no_tree,{i},{s:.6f},{b:.6f}\n")
    print(f"Labeled-set CSV saved -> {labeled_csv}")

    tree_mean, notree_mean = float(tree_scores.mean()), float(notree_scores.mean())
    print(f"\n  Tree-close frames  (n={len(tree_scores)}): clip_score = "
          f"{np.array2string(tree_scores, precision=4)}  mean={tree_mean:.4f}")
    print(f"  No-tree/open frames (n={len(notree_scores)}): clip_score = "
          f"{np.array2string(notree_scores, precision=4)}  mean={notree_mean:.4f}")

    correct_direction = tree_mean > notree_mean
    if notree_mean > 1e-6:
        sep_ratio = tree_mean / notree_mean
    elif notree_mean < -1e-6:
        # notree_mean negative: a positive tree_mean is automatically the
        # correct direction with an unbounded ratio under naive division —
        # report the ratio of |means| instead so the number stays interpretable,
        # but the direction check above is what actually decides "correct".
        sep_ratio = tree_mean / abs(notree_mean) if tree_mean > 0 else tree_mean / notree_mean
    else:
        sep_ratio = float("inf") if tree_mean > 0 else float("-inf")

    min_sep = float(cfg["gates"]["min_separation_ratio"])
    gate_a = correct_direction and sep_ratio >= min_sep
    print(f"\nGATE a — SEPARATION: tree_mean={tree_mean:.4f}  no_tree_mean={notree_mean:.4f}  "
          f"correct_direction(tree>no_tree)={correct_direction}  ratio={sep_ratio:.3f}  "
          f"(required >= {min_sep}) -> {'PASS' if gate_a else 'FAIL'}")

    all_labeled_scores = np.concatenate([tree_scores, notree_scores])
    all_labeled_bright = np.concatenate([tree_bright, notree_bright])
    bright_r = float(np.corrcoef(all_labeled_scores, all_labeled_bright)[0, 1])
    target_abs_r = float(cfg["gates"]["brightness_target_abs_r"])
    gate_b = abs(bright_r) < target_abs_r
    print(f"\nGATE b — BRIGHTNESS CONFOUND: r(clip_score, brightness) over the "
          f"{len(all_labeled_scores)} labeled frames = {bright_r:.4f}  "
          f"(target |r| < {target_abs_r}, attempt #11 baseline r=0.643) -> "
          f"{'PASS' if gate_b else 'FAIL'}")

    print(f"\n{'=' * 78}")
    print(f"OVERALL: gate a = {'PASS' if gate_a else 'FAIL'}, "
          f"gate b = {'PASS' if gate_b else 'FAIL'} -> "
          f"{'BOTH PASS' if (gate_a and gate_b) else 'AT LEAST ONE FAIL'}")
    print(f"{'=' * 78}")

    # ------------------------------------------------------------------
    # Extra due-diligence check (not a mandated gate, but directly relevant to
    # interpreting gate b honestly): is the brightness confound specific to the
    # narrow 10-frame hand-labeled set, or does it hold across the full
    # 251-frame population (both domains, far more scene diversity)? A gate
    # computed only on a small hand-picked set that itself happens to be
    # brightness-confounded by construction (forest scenes are inherently
    # darker than open-field scenes) would not distinguish "CLIP found a real
    # shortcut" from "the ground truth itself is confounded".
    # ------------------------------------------------------------------
    full_bright = brightness_of(frames)
    full_r = float(np.corrcoef(scores, full_bright)[0, 1])
    print(f"\nEXTRA (not a gate): r(clip_score, brightness) over the FULL "
          f"{len(scores)}-frame population (both domains) = {full_r:.4f}")
    for name, vals in groups.items():
        if len(vals):
            mask = np.array([r["group"] for r in all_rows]) == name
            r_g = float(np.corrcoef(scores[mask], full_bright[mask])[0, 1])
            print(f"    {name:<20} n={mask.sum():>4}  r={r_g:.4f}")


if __name__ == "__main__":
    main()

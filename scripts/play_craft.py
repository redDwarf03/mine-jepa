"""
Craft agent — WM v4 + CraftPlannerV4 in MineRLObtainIronPickaxeDense.

Milestone: chop a log, then CRAFT it into planks. The world model knows the craft
rule (dPlanks@craft = +4); the hard part is the visual chopping. The planner unrolls
both the visual latent (perception) and the inventory dynamics (crafting), starting the
inventory rollout from the agent's REAL current inventory.

Prints metrics in the format parsed by play_minerl_multi.py (1 episode per process,
MALMOBUSY workaround).

Usage: run.bat scripts/play_craft.py --config configs/play_craft.yaml --episodes 1
"""
import argparse
import logging
import time
from collections import deque
from pathlib import Path

import cv2
import imageio
import numpy as np
import torch
import yaml

logging.getLogger("minerl").setLevel(logging.CRITICAL)

from mine_jepa.ebwm.craft_wm import build_craft_wm_v4
from mine_jepa.ebwm.dataset import INV_SCALE
from mine_jepa.ebwm.frontier import FrontierTracker
from mine_jepa.ebwm.hazard import detect_underwater
from mine_jepa.ebwm.planner import DiscreteLatentPlanner, SwitchingCraftPlanner
from mine_jepa.ebwm.rnd import RNDModule
from scripts.play import load_action_map, make_minerl_env


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/play_craft.yaml")
    p.add_argument("--episodes", type=int, default=None)
    return p.parse_args()


def load_craft_wm(ckpt_path: str, device):
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    cfg = ckpt["cfg"]
    items = ckpt["inventory_items"]
    wm = build_craft_wm_v4(cfg["model"], cfg["regularizer"], cfg["head"], n_items=len(items))
    wm.load_state_dict(ckpt["model_state"])
    wm.eval()
    return wm.to(device), items


def preprocess(pov: np.ndarray, device):
    """frame [H,W,3] uint8 → [1, 3, 1, 64, 64] float [0,1]."""
    frame = cv2.resize(pov, (64, 64))
    t = torch.from_numpy(frame).float() / 255.0
    return t.permute(2, 0, 1).unsqueeze(0).unsqueeze(2).to(device)


def inv_vector(obs_inv: dict, items: list, device) -> torch.Tensor:
    """MineRL inventory dict → normalised vector [K] in INV_ITEMS order."""
    vec = np.array([float(obs_inv.get(it, 0)) for it in items], dtype=np.float32)
    return torch.from_numpy(vec / INV_SCALE).to(device)


@torch.no_grad()
def build_chop_goal(wm, goal_cfg: dict, device, log_idx: int) -> torch.Tensor:
    """Visual-latent centroid of 'log obtained' frames → [1, D, H', W'] chop goal.

    Frames where the log count increased = "facing a tree, chopping" scenes. Steering
    the visual latent toward this centroid drives the lumberjack gesture (the Treechop
    trick), far better than the weak per-step inventory signal.

    `chop_data_path` (optional) swaps the frame source for a Treechop-format npz
    (frames + rewards): the reward>=threshold frames are the proven Treechop compass
    (docs/10 cold-start finding: the Obtain-demos centroid leaves the agent passive
    inside the forest), still encoded by THIS wm so the centroid lives in its space."""
    chop_path = goal_cfg.get("chop_data_path")
    if chop_path:
        d = np.load(chop_path)
        thr = float(goal_cfg.get("chop_reward_threshold", 0.5))
        good = d["frames"][d["rewards"].astype(np.float32) >= thr]
        print(f"  Chop goal: centroid of {len(good)} reward>={thr} frames ({chop_path})")
    else:
        d = np.load(goal_cfg["data_path"])
        frames, inv, dones = d["frames"], d["inventory"], d["dones"].astype(bool)
        log = inv[:, log_idx].astype(np.int64)
        inc = np.zeros(len(frames), dtype=bool)
        inc[1:] = (log[1:] > log[:-1]) & (~dones[:-1])     # log went up, same episode
        good = frames[inc]
        if len(good) < 10:
            print(f"  ⚠️  only {len(good)} log-gain frames — using all frames for chop goal")
            good = frames
        print(f"  Chop goal: centroid of {len(good)} 'log obtained' frames")
    lat_sum, n = None, 0
    for i in range(0, len(good), 256):
        obs = torch.from_numpy(good[i:i + 256]).float() / 255.0
        obs = obs.permute(0, 3, 1, 2).unsqueeze(2).to(device)   # [B,3,1,64,64]
        lat = wm.encode(obs).squeeze(2)                          # [B,D,H',W']
        s = lat.sum(dim=0)
        lat_sum = s if lat_sum is None else lat_sum + s
        n += lat.size(0)
    return (lat_sum / n).unsqueeze(0)                            # [1,D,H',W']


def apply_action(env, action_int: int, action_map: list):
    a = env.action_space.noop()
    for k, v in action_map[action_int].items():
        if k == "camera":
            a["camera"] = np.array(v, dtype=np.float32)
        else:
            a[k] = v
    return env.step(a)


def main():
    args = parse_args()
    cfg = yaml.safe_load(open(args.config))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}\nEnv: minerl (craft)")

    action_map = load_action_map(cfg.get("actions_config", "configs/minerl_actions_obtain.yaml"))

    print("\nLoading WM v4 (inventory-aware)...")
    wm, items = load_craft_wm(cfg["model"]["checkpoint"], device)
    print(f"  craft_wm_v4.pt loaded | items: {items}")
    planks_idx = items.index("planks")
    log_idx = items.index("log")

    print("\nBuilding chop goal...")
    chop_goal = build_chop_goal(wm, cfg["goal"], device, log_idx)

    p = cfg["planner"]
    item_weights = {log_idx: float(p.get("w_log", 1.0)), planks_idx: float(p.get("w_planks", 2.0))}
    commit_length = int(p.get("commit_length", 1))
    # None/absent (default): _sample_actions() bit-for-bit original sampling
    # (docs/10 attempt #8, Proposal A).
    pool_priming = p.get("action_pool_priming")
    planner = SwitchingCraftPlanner(
        wm, chop_goal=chop_goal, item_weights=item_weights, log_idx=log_idx,
        n_actions=p["n_actions"], horizon=p["horizon"], n_candidates=p["n_candidates"],
        log_threshold=float(p.get("log_threshold", 0.05)),
        sticky_prob=float(p.get("sticky_prob", 0.0)), commit_length=commit_length,
        action_pool_priming=pool_priming,
        device=device,
    )
    print(f"Planner: switching (no log→chop / log→craft), horizon={p['horizon']}, "
          f"candidates={p['n_candidates']}, sticky_prob={planner.sticky_prob}, "
          f"commit_length={planner.commit_length}, "
          f"action_pool_priming={'ON' if pool_priming and pool_priming.get('enabled', False) else 'off'}")

    # Two-brain mode (docs/10 follow-up): the proven Treechop world model drives the
    # CHOP phase (movement actions 0-16, identical in both action maps); WM v4 keeps
    # the CRAFT phase, where its inventory dynamics is the whole point. Config-gated:
    # no `chop_model` block = single-brain SwitchingCraftPlanner, unchanged.
    chop_planner, chop_goals = None, None
    chop_cfg = cfg.get("chop_model") or {}
    rnd_cfg = cfg.get("rnd", {}) or {}
    rnd_enabled = bool(chop_cfg) and bool(rnd_cfg.get("enabled", False))
    rnd_module, rnd_opt, rnd_buffer = None, None, None
    rnd_batch_size = int(rnd_cfg.get("batch_size", 32))
    rnd_update_every = int(rnd_cfg.get("update_every", 4))
    if chop_cfg:
        from scripts.play_ebwm import build_goal_latents, load_model as load_ebwm
        ebwm, ratio = load_ebwm(chop_cfg["checkpoint"], device)
        chop_goals = build_goal_latents(ebwm, {"goal": chop_cfg["goal"]}, device)

        # Trained cost-to-goal metric (docs/10 attempt #7, mine_jepa/ebwm/value_head.py):
        # absent key = None = the two-brain chop planner's original raw-latent squared-L2
        # goal distance, unchanged. Present = DistanceProjector.pairwise_dist replaces it
        # in DiscreteLatentPlanner._score().
        distance_projector = None
        dp_path = chop_cfg.get("distance_projector")
        if dp_path:
            from mine_jepa.ebwm.value_head import DistanceProjector
            distance_projector = DistanceProjector.load(dp_path, device=device)
            print(f"Distance projector: {dp_path} loaded "
                  f"(proj_dim={distance_projector.proj_dim}) — replaces raw-latent goal distance")

        # BC actor prior (docs/10 attempt #8, Proposal B, mine_jepa/ebwm/actor.py):
        # placed under chop_model (not the top-level planner block) because the
        # actor is trained on THIS checkpoint's (ebwm.pt) latent space specifically
        # — same reasoning as distance_projector/RND above, an actor trained here
        # must never be attached to craft_wm_v4's SwitchingCraftPlanner (different
        # encoder, same latent SHAPE, different geometry). Absent/enabled:false
        # (default) leaves chop_actor=None, actor_n_samples=0 — DiscreteLatentPlanner
        # never calls the actor, bit-for-bit the original/Proposal-A sampling.
        actor_cfg = chop_cfg.get("actor_prior") or {}
        chop_actor, actor_n_samples, actor_temperature = None, 0, 1.0
        if actor_cfg.get("enabled", False):
            from mine_jepa.ebwm.actor import BCActor
            chop_actor = BCActor.load(actor_cfg["checkpoint_path"], device=device)
            actor_n_samples = int(actor_cfg.get("n_actor_samples", 128))
            actor_temperature = float(actor_cfg.get("temperature", 1.0))
            print(f"BC actor prior: {actor_cfg['checkpoint_path']} loaded "
                  f"(n_actor_samples={actor_n_samples}, temperature={actor_temperature}) "
                  f"— proposes candidates for the two-brain chop planner")

        # Online RND (docs/09/10, mine_jepa/ebwm/rnd.py): only wired into the
        # two-brain chop planner (ebwm.pt's latent space) — SwitchingCraftPlanner
        # (craft_wm_v4) is untouched, both by construction (no ensemble/novelty_coeff
        # kwargs on it) and because RND would be encoding into the wrong latent space
        # during craft mode. state_dim read from ebwm.pt's own checkpoint config
        # (same field load_model/load_ebwm in play_ebwm.py uses to build the model),
        # never hardcoded — ResNet5 doesn't expose its out_d as an attribute.
        if rnd_enabled:
            _ebwm_ckpt = torch.load(chop_cfg["checkpoint"], map_location=device, weights_only=False)
            chop_embed_dim = _ebwm_ckpt["cfg"]["model"]["embed_dim"]
            rnd_module = RNDModule(state_dim=chop_embed_dim).to(device)
            # Optimizer sees ONLY the predictor's parameters — the target net is
            # frozen (rnd.py) and must never receive gradient updates.
            rnd_opt = torch.optim.Adam(
                rnd_module.predictor.parameters(), lr=float(rnd_cfg.get("lr", 1e-3))
            )
            rnd_buffer = deque(maxlen=int(rnd_cfg.get("buffer_size", 256)))
            print(f"RND: enabled (state_dim={chop_embed_dim}, "
                  f"novelty_coeff={float(rnd_cfg.get('novelty_coeff', 0.5))}, "
                  f"lr={rnd_cfg.get('lr', 1e-3)}, buffer_size={rnd_buffer.maxlen}, "
                  f"batch_size={rnd_batch_size}, update_every={rnd_update_every})")

        cem_cfg = p.get("cem", {}) or {}
        cem_iters = int(cem_cfg.get("iters", 1))
        chop_planner = DiscreteLatentPlanner(
            ebwm, n_actions=int(chop_cfg.get("n_actions", 17)),
            horizon=p["horizon"], n_candidates=p["n_candidates"],
            sticky_prob=float(p.get("sticky_prob", 0.0)), commit_length=commit_length,
            ensemble=rnd_module,
            novelty_coeff=float(rnd_cfg.get("novelty_coeff", 0.5)) if rnd_enabled else 0.0,
            cem_iters=cem_iters,
            cem_elite_frac=float(cem_cfg.get("elite_frac", 0.1)),
            cem_smoothing=float(cem_cfg.get("smoothing", 0.01)),
            distance_projector=distance_projector,
            action_pool_priming=pool_priming,
            actor=chop_actor, actor_n_samples=actor_n_samples, actor_temperature=actor_temperature,
            device=device,
        )
        print(f"Two-brain chop: {chop_cfg['checkpoint']} (ratio={ratio:.3f}), "
              f"{chop_planner.n_actions} movement actions"
              + (f", CEM iters={cem_iters} elite_frac={chop_planner.cem_elite_frac} "
                 f"smoothing={chop_planner.cem_smoothing}" if cem_iters > 1 else ""))

    scan_cfg = cfg.get("scan", {}) or {}
    scan_enabled = bool(scan_cfg.get("enabled", False))
    # "turn" (default, docs/10 attempt #2): the original turn-in-place reflex,
    # unchanged. "bushwhack" (docs/10 attempt #8, Proposal C): a bounded forward-
    # sprint+jump cruise instead — covers ground rather than spinning on the spot,
    # for spawns where nothing is ever found by turning (attempt #5's treeless
    # underground episode). "frontier" (next-cycle proposal 2, mine_jepa/ebwm/
    # frontier.py): steers a bounded forward-sprint+jump cruise toward the
    # LEAST dead-reckoned-visited direction instead of always straight ahead —
    # a genuinely different, non-latent, state-visitation-driven signal (NOT
    # goal-centroid distance, which attempt #10 confirmed reverses direction off
    # the Treechop training distribution; NOT RND, whose online predictor was
    # shown to converge on tick-count rather than scene content in this exact
    # deployment, attempt #4). Same trigger (goal_score_std flat on the chop planner).
    scan_macro = scan_cfg.get("macro", "turn")
    bushwhack_max_ticks = int(scan_cfg.get("bushwhack_max_ticks", 30))
    frontier_cfg = scan_cfg.get("frontier", {}) or {}
    frontier_max_ticks = int(frontier_cfg.get("max_ticks", 30))
    frontier_tracker = None
    # frontier_tracker doubles as the hazard reflex's position source (docs/10
    # attempt #13 follow-up): a single dead-reckoning instance is instantiated
    # whenever EITHER consumer needs it — the scan macro "frontier", or hazard
    # avoidance's steered escape — never two independent trackers. hazard_cfg is
    # read further below; hazard_enabled is resolved first so this instantiation
    # can see it.
    hazard_cfg = cfg.get("hazard_avoidance", {}) or {}
    hazard_enabled = bool(hazard_cfg.get("enabled", False))
    if scan_macro == "frontier" or hazard_enabled:
        frontier_tracker = FrontierTracker(
            cell_size=float(frontier_cfg.get("cell_size", 4.0)),
            move_step=float(frontier_cfg.get("move_step", 1.0)),
            sprint_mult=float(frontier_cfg.get("sprint_mult", 1.6)),
            lookahead_cells=float(frontier_cfg.get("lookahead_cells", 2.0)),
            n_headings=int(frontier_cfg.get("n_headings", 12)),
        )
    if scan_enabled:
        if scan_macro == "turn":
            macro_desc = f"turn_action=a{scan_cfg.get('turn_action', 12)}"
        elif scan_macro == "bushwhack":
            macro_desc = (
                f"bushwhack forward=a{scan_cfg.get('bushwhack_forward_action', 13)} "
                f"jump=a{scan_cfg.get('bushwhack_jump_action', 8)} "
                f"jump_every={scan_cfg.get('bushwhack_jump_every', 4)} "
                f"max_ticks={bushwhack_max_ticks}"
            )
        else:
            macro_desc = (
                f"frontier cell_size={frontier_tracker.cell_size} "
                f"n_headings={frontier_tracker.n_headings} "
                f"lookahead_cells={frontier_tracker.lookahead_cells} "
                f"alignment_deg={frontier_cfg.get('alignment_deg', 15.0)} "
                f"max_ticks={frontier_max_ticks}"
            )
        print(f"Scan macro: ON (chop mode only, macro={scan_macro}, "
              f"flat_threshold={scan_cfg['flat_threshold']}, "
              f"patience={scan_cfg.get('patience', 3)}, {macro_desc}, "
              f"max_replans={scan_cfg.get('max_replans', 40)})")

    # Hazard avoidance (docs/10 cold-start attempt #13): a drowning-specific safety
    # override, independent of scan/scan.macro and of chop-vs-craft mode — the
    # attempt #12 diagnostic found 12/20 episodes ended in a confirmed drowning
    # death, mostly during the scan macros' blind forward cruises, which have no
    # collision/hazard awareness by design (frontier.py's own stated limitation).
    # No health/breath observable exists in this env (verified against
    # minerl.herobraine.env_specs.obtain_specs.Obtain.create_observables()) — the
    # signal here is a calibrated pixel heuristic on the POV frame itself
    # (mine_jepa/ebwm/hazard.py), not a speculative proxy: RELATIVE (ratio-based,
    # lighting-invariant) channel statistics, re-calibrated after an initial
    # absolute-threshold version missed a real dark/night drowning — see
    # hazard.py's docstring for both rounds of calibration data. Absent/
    # enabled:false (default) = zero calls, byte-for-byte the original per-tick
    # action selection. (hazard_cfg/hazard_enabled were already resolved above,
    # alongside frontier_tracker's instantiation, since that tracker is now
    # shared between the "frontier" scan macro and this reflex.)
    hazard_ratio_thresh = float(hazard_cfg.get("ratio_thresh", 1.02))
    hazard_rel_rg_thresh = float(hazard_cfg.get("rel_rg_thresh", 0.15))
    hazard_patience = int(hazard_cfg.get("patience", 1))
    hazard_max_ticks = int(hazard_cfg.get("max_ticks", 60))
    hazard_jump_every = int(hazard_cfg.get("jump_every", 2))
    hazard_jump_action = int(hazard_cfg.get("jump_action", 5))
    hazard_retreat_action = int(hazard_cfg.get("retreat_action", 2))
    # Directional escape (docs/10 attempt #13 follow-up): steer toward the most
    # recent dead-reckoned position at which detect_underwater() returned False
    # this episode, instead of always retreating blindly in a fixed direction —
    # the sanity run found the detector correctly stays triggered for 260+ ticks
    # but a blind retreat direction can oscillate in water forever. Falls back
    # to the old blind jump/retreat_action pattern if no dry position has been
    # recorded yet this episode (e.g. spawned directly in water).
    #
    # attempt #13 follow-up, oscillation fix: one escape-mode turn commitment
    # actually sweeps ~commit_length/2 * action_repeat * 10deg (half the commit
    # slots are jump_action, not a turn) — 4/2*4*10 = 80deg at this file's own
    # commit_length=4/action_repeat=4 defaults — while the old align_deg=20
    # default was far narrower than that sweep, so almost every check overshot
    # past the alignment window and flipped sign next check, ping-ponging
    # forever (observed directly in the N=6 sanity log). Since the agent's
    # position is unchanged by a pure turn (turn/jump actions carry no
    # forward/strafe key), the sweep per check is exact, not approximate, so
    # align_deg >= sweep guarantees the turn can only ever reduce |delta|
    # (never flip its sign) each check — new default 85deg, comfortably above
    # the ~80deg sweep, replaces the old 20deg.
    hazard_align_deg = float(hazard_cfg.get("align_deg", 85.0))
    hazard_turn_right_action = int(hazard_cfg.get("turn_right_action", 12))
    hazard_turn_left_action = int(hazard_cfg.get("turn_left_action", 11))
    hazard_forward_action = int(hazard_cfg.get("forward_action", 1))
    # Anchor debounce (attempt #13 follow-up, bug 2): the sanity log showed
    # hazard_last_dry_pos occasionally jumping right next to the agent's own
    # still-submerged position — a single-tick false "underwater=False" read
    # (surface wave/lighting noise at the water's edge) corrupting the
    # remembered dry point. detect_underwater() is evaluated once per outer
    # replan (not once per real env tick) in this loop, so the debounce below
    # counts consecutive not-underwater REPLAN CHECKS, not literal env ticks —
    # requiring >=2 in a row before trusting the reading, instead of updating
    # the anchor on any single check.
    hazard_dry_debounce = int(hazard_cfg.get("dry_anchor_debounce", 2))
    if hazard_enabled:
        print(f"Hazard avoidance: ON (any mode, ratio_thresh={hazard_ratio_thresh}, "
              f"rel_rg_thresh={hazard_rel_rg_thresh}, patience={hazard_patience}, "
              f"jump_action=a{hazard_jump_action} retreat_action=a{hazard_retreat_action} "
              f"jump_every={hazard_jump_every}, max_ticks={hazard_max_ticks}, "
              f"steered: align_deg={hazard_align_deg} "
              f"turn_right=a{hazard_turn_right_action} turn_left=a{hazard_turn_left_action} "
              f"forward=a{hazard_forward_action}, dry_anchor_debounce={hazard_dry_debounce})")

    # Spawn-viability diagnostic (docs/10 attempt #8 follow-up): honest,
    # observable per-episode evidence of whether ANYTHING findable was ever in
    # view, so a batch's failures can be split into "algorithm didn't find a
    # tree" vs. "there was no tree within reach" without inventing a biome
    # classifier. Two cheap signals, neither claiming to be definitive on its
    # own: (1) the max chop-mode goal_score_std reached over the whole episode
    # (already computed every step regardless of scan/log_std — this just
    # tracks its running max instead of discarding it) against a configured
    # "something was visible at some point" threshold; (2) a first-frame
    # thumbnail dumped to disk for manual human eyeballing, since no automatic
    # signal here has been shown reliable enough to replace that (docs/10
    # attempt #7's lighting-confound finding is a direct warning against
    # trusting an untested automatic proxy). Disabled by default — zero cost,
    # zero behaviour change, when `spawn_diag.enabled` is absent/false.
    spawn_cfg = cfg.get("spawn_diag", {}) or {}
    spawn_diag_enabled = bool(spawn_cfg.get("enabled", False))
    spawn_thumb_dir = Path(spawn_cfg.get("thumb_dir", "assets/spawn_thumbs"))
    spawn_std_viable_threshold = float(spawn_cfg.get("std_viable_threshold", 0.005))
    if spawn_diag_enabled:
        spawn_thumb_dir.mkdir(parents=True, exist_ok=True)
        print(f"Spawn-viability diagnostic: ON (thumb_dir={spawn_thumb_dir}, "
              f"std_viable_threshold={spawn_std_viable_threshold})")

    a_cfg = cfg["agent"]
    n_episodes = args.episodes or a_cfg["episodes"]
    repeat = a_cfg.get("action_repeat", 4)
    env = make_minerl_env(cfg)
    label = cfg.get("minerl_env", "MineRLObtainIronPickaxeDense-v0")
    print(f"\n{'='*55}\nCraft agent — {n_episodes} ep in {label}\n{'='*55}")

    save_gif = cfg["logging"]["save_gif"]
    gif_budget = cfg["logging"].get("gif_episodes", 1)
    # Full-inventory diagnostic (2026-07-22 dispatch): the existing per-episode
    # summary only ever tracked log/planks, silently discarding the other 9+
    # reward-bearing items in MineRLObtainIronPickaxeDense's inventory obs (an
    # episode logged reward=144 with log=planks=0, unexplained by the old
    # print). Default off = zero behaviour/output change (verified: no new
    # tracking dict, no new print line, when absent from the config).
    full_inv_enabled = bool(cfg["logging"].get("full_inventory", False))

    all_reward, all_logs, all_planks, all_steps = [], [], [], []
    for ep in range(1, n_episodes + 1):
        obs = env.reset()
        pov, inv = obs["pov"], obs["inventory"]
        # Measure GAIN vs the starting inventory — debug envs start with items, so
        # "planks > 0" would be trivially true. Success = crafted MORE than the start.
        start_log = int(inv.get("log", 0))
        start_planks = int(inv.get("planks", 0))
        max_log, max_planks = start_log, start_planks
        max_inv = dict(inv) if full_inv_enabled else None
        total_r = 0.0
        step = 0
        action_counts = [0] * p["n_actions"]
        mode_counts = {"chop": 0, "craft": 0}
        record = ep <= gif_budget and save_gif
        gif_frames = [pov] if record else []
        t0 = time.perf_counter()

        spawn_thumb_path = None
        spawn_max_std = 0.0
        if spawn_diag_enabled:
            spawn_thumb_path = spawn_thumb_dir / f"ep{ep:03d}_{int(time.time() * 1000)}.png"
            imageio.imwrite(str(spawn_thumb_path), pov)

        # Scan macro state (docs/10): only meaningful in chop mode — a flat
        # goal-score std means no tree in view → force a camera-yaw sweep (macro
        # "turn"), a bounded forward cruise (macro "bushwhack", attempt #8), or a
        # cruise steered toward unvisited ground (macro "frontier").
        flat_count, scanning, scan_replans, scan_triggers = 0, False, 0, 0
        bushwhack_ticks = 0
        frontier_ticks = 0
        if frontier_tracker is not None:
            frontier_tracker.reset()   # per-episode memory only, fresh spawn
        hazard_flat_count, hazard_active, hazard_ticks, hazard_triggers = 0, False, 0, 0
        # Last dead-reckoned (x, y) at which detect_underwater() was False this
        # episode ("last known dry moment") — None until the first dry reading,
        # e.g. if the episode spawns directly in water.
        hazard_last_dry_pos = None
        hazard_died_during_escape = False
        # Consecutive not-underwater replan checks (attempt #13 follow-up, bug
        # 2 debounce) — reset every episode alongside hazard_last_dry_pos.
        hazard_dry_streak = 0
        # RND tick counter (within-episode only — no cross-episode persistence;
        # each play_minerl_multi.py subprocess is one episode anyway).
        rnd_tick = 0
        while step < a_cfg["max_steps"]:
            obs_t = preprocess(pov, device)
            inv_t = inv_vector(inv, items, device)
            has_log = float(inv_t[log_idx]) >= planner.log_threshold
            if chop_planner is not None and not has_log:
                action, info = chop_planner.plan(obs_t, chop_goals, return_info=True)
                mode = "chop"
            else:
                action, mode, info = planner.plan(obs_t, inv_t, return_info=True)
            mode_counts[mode] += 1
            std = info["goal_score_std"]
            if spawn_diag_enabled and mode == "chop":
                spawn_max_std = max(spawn_max_std, std)
            if scan_cfg.get("log_std", False) and mode == "chop":
                nov = f" novelty_mean={info['novelty_mean']:.6f}" if "novelty_mean" in info else ""
                print(f"    [scan] step={step:4d} goal_score_std={std:.6f}{nov}"
                      f"{'  SCANNING' if scanning else ''}")
            # commit_length>1 (docs/10 sustained-plan experiment): see play_ebwm.py.
            # commit_length=1 (default) → committed is a 1-element list, and the
            # loop below is byte-for-byte the original single-action execution.
            committed = action if isinstance(action, list) else [action]
            if scan_enabled and mode == "chop":
                flat = std < float(scan_cfg["flat_threshold"])
                if not scanning:
                    flat_count = flat_count + 1 if flat else 0
                    if flat_count >= int(scan_cfg.get("patience", 3)):
                        scanning, scan_replans, bushwhack_ticks, frontier_ticks = True, 0, 0, 0
                        scan_triggers += 1
                if scanning:
                    ticks_exceeded = (
                        (scan_macro == "bushwhack" and bushwhack_ticks >= bushwhack_max_ticks)
                        or (scan_macro == "frontier" and frontier_ticks >= frontier_max_ticks)
                    )
                    if not flat or scan_replans >= int(scan_cfg.get("max_replans", 40)) or ticks_exceeded:
                        scanning, flat_count = False, 0
                    elif scan_macro == "bushwhack":
                        # Bounded forward-sprint cruise with periodic jumps (covers
                        # ground instead of turning in place; jumps hop 1-block
                        # obstacles that would otherwise stall a straight sprint).
                        # goal_score_std is rechecked every replan — i.e. every
                        # len(committed) ticks, well inside bushwhack_max_ticks —
                        # not only once the macro's tick budget is exhausted.
                        jump_every = int(scan_cfg.get("bushwhack_jump_every", 4))
                        jump_action = int(scan_cfg.get("bushwhack_jump_action", 8))
                        forward_action = int(scan_cfg.get("bushwhack_forward_action", 13))
                        committed = [
                            jump_action if (bushwhack_ticks + i) % jump_every == 0 else forward_action
                            for i in range(len(committed))
                        ]
                        bushwhack_ticks += len(committed)
                        scan_replans += 1
                    elif scan_macro == "frontier":
                        # Same bounded forward-sprint+jump cruise as "bushwhack",
                        # but steered toward the LEAST dead-reckoned-visited
                        # direction (mine_jepa/ebwm/frontier.py) instead of always
                        # straight ahead: turn toward the frontier heading first if
                        # not roughly aligned with it, then cruise forward once
                        # aligned. goal_score_std (and the frontier heading itself)
                        # are both rechecked every replan.
                        align_deg = float(frontier_cfg.get("alignment_deg", 15.0))
                        delta = frontier_tracker.heading_delta_deg()
                        if abs(delta) > align_deg:
                            steer_action = (
                                int(frontier_cfg.get("turn_right_action", 12)) if delta > 0
                                else int(frontier_cfg.get("turn_left_action", 11))
                            )
                            committed = [steer_action] * len(committed)
                            act_kind = "turn"
                        else:
                            jump_every = int(frontier_cfg.get("jump_every", 4))
                            jump_action = int(frontier_cfg.get("jump_action", 8))
                            forward_action = int(frontier_cfg.get("forward_action", 13))
                            committed = [
                                jump_action if (frontier_ticks + i) % jump_every == 0 else forward_action
                                for i in range(len(committed))
                            ]
                            act_kind = "forward"
                        if scan_cfg.get("log_std", False):
                            heading, cell, count = frontier_tracker.frontier_heading_deg()
                            print(f"    [frontier] step={step:4d} yaw={frontier_tracker.yaw_deg:6.1f} "
                                  f"target_heading={heading:6.1f} delta={delta:6.1f} action={act_kind} "
                                  f"target_cell={cell} target_visits={count} "
                                  f"unique_cells={frontier_tracker.n_unique_cells}")
                        frontier_ticks += len(committed)
                        scan_replans += 1
                    else:
                        committed = [int(scan_cfg.get("turn_action", 12))] * len(committed)
                        scan_replans += 1
            elif scanning:
                # left chop mode (got a log) → drop the scan state
                scanning, flat_count = False, 0

            # Hazard override (docs/10 attempt #13): checked every replan, in ANY
            # mode, and takes priority over whatever scan/planner just picked —
            # runs LAST so it can override a scan macro's own blind forward cruise,
            # the mechanism most often implicated in the attempt #12 drownings.
            if hazard_enabled:
                underwater, ratio, rel_rg = detect_underwater(
                    pov, hazard_ratio_thresh, hazard_rel_rg_thresh
                )
                # Debounced anchor update (attempt #13 follow-up, bug 2): only
                # trust a "dry" reading, and overwrite the remembered point,
                # after hazard_dry_debounce CONSECUTIVE not-underwater checks
                # — a single spurious False (surface wave/lighting noise at
                # the water's edge) can no longer corrupt the anchor by
                # itself, since the streak resets to 0 on the very next
                # underwater=True check.
                hazard_dry_streak = hazard_dry_streak + 1 if not underwater else 0
                if hazard_dry_streak >= hazard_dry_debounce and frontier_tracker is not None:
                    hazard_last_dry_pos = (frontier_tracker.x, frontier_tracker.y)
                if hazard_cfg.get("log", False):
                    print(f"    [hazard] step={step:4d} underwater={underwater} "
                          f"ratio={ratio:.3f} rel_rg={rel_rg:.3f}"
                          f"{'  ESCAPING' if hazard_active else ''}")
                if not hazard_active:
                    hazard_flat_count = hazard_flat_count + 1 if underwater else 0
                    if hazard_flat_count >= hazard_patience:
                        hazard_active, hazard_ticks = True, 0
                        hazard_triggers += 1
                        scanning, flat_count = False, 0   # abort any in-progress scan
                if hazard_active:
                    if not underwater or hazard_ticks >= hazard_max_ticks:
                        hazard_active, hazard_flat_count = False, 0
                    else:
                        # Directional escape: steer toward the last dead-reckoned
                        # dry point instead of always retreating in a fixed
                        # direction — same turn-until-aligned pattern as the
                        # "frontier" scan macro (turn while misaligned, then
                        # move once roughly facing the target), with a jump
                        # interleaved throughout (not just once aligned) so the
                        # agent keeps surfacing whether it is currently turning
                        # or advancing. Falls back to the old blind jump/
                        # retreat_action pattern if no dry position has been
                        # recorded yet this episode.
                        if hazard_last_dry_pos is not None and frontier_tracker is not None:
                            delta = frontier_tracker.heading_delta_to(*hazard_last_dry_pos)
                            aligned = abs(delta) <= hazard_align_deg
                            move_action = (
                                hazard_forward_action if aligned
                                else (hazard_turn_right_action if delta > 0 else hazard_turn_left_action)
                            )
                            steer_kind = "forward" if aligned else "turn"
                        else:
                            delta, move_action, steer_kind = None, hazard_retreat_action, "blind"
                        committed = [
                            hazard_jump_action if (hazard_ticks + i) % hazard_jump_every == 0
                            else move_action
                            for i in range(len(committed))
                        ]
                        if hazard_cfg.get("log", False):
                            # frontier_tracker is always instantiated whenever
                            # hazard_enabled (see its setup above), so this
                            # branch is reached unconditionally here.
                            delta_str = f"{delta:6.1f}" if delta is not None else "  n/a"
                            print(f"    [hazard-escape] step={step:4d} kind={steer_kind} "
                                  f"delta={delta_str} dry_pos={hazard_last_dry_pos} "
                                  f"pos=({frontier_tracker.x:.1f},{frontier_tracker.y:.1f}) "
                                  f"yaw={frontier_tracker.yaw_deg:6.1f}")
                        hazard_ticks += len(committed)
            for act in committed:
                if step >= a_cfg["max_steps"]:
                    break
                for _ in range(repeat):
                    if step >= a_cfg["max_steps"]:
                        break
                    action_counts[act] += 1
                    obs, r, done, _info = apply_action(env, act, action_map)
                    pov, inv = obs["pov"], obs["inventory"]
                    if frontier_tracker is not None:
                        # Dead-reckon once per REAL tick (not once per committed
                        # action) — camera/movement deltas apply once per
                        # env.step() call, so this must match that cadence, not
                        # action_repeat's outer grouping. Not restricted to chop
                        # mode: hazard avoidance (below) needs an accurate
                        # position in ANY mode, and craft actions (a17-a21) have
                        # no forward/back/strafe/camera keys in the action map,
                        # so this is a genuine no-op for them — unchanged
                        # behaviour for the "frontier" scan macro (chop-only by
                        # construction) either way.
                        frontier_tracker.update(action_map[act])
                    total_r += r
                    max_log = max(max_log, int(inv.get("log", 0)))
                    max_planks = max(max_planks, int(inv.get("planks", 0)))
                    if max_inv is not None:
                        for k, v in inv.items():
                            max_inv[k] = max(max_inv.get(k, 0), int(v))
                    step += 1
                    if record:
                        gif_frames.append(pov)
                    if done:
                        if hazard_active:
                            hazard_died_during_escape = True
                        break
                # RND update — once per REAL action (not per action_repeat substep,
                # those frames are near-identical), and only in chop mode: RND is
                # trained on ebwm.pt's latent space, craft_wm_v4's latents during
                # craft mode live in a different space entirely.
                if rnd_module is not None and mode == "chop":
                    with torch.no_grad():
                        z_t = ebwm.encode(preprocess(pov, device)).squeeze(2).detach()
                    rnd_buffer.append(z_t.squeeze(0))
                    rnd_tick += 1
                    if rnd_tick % rnd_update_every == 0 and len(rnd_buffer) >= rnd_batch_size:
                        idx = np.random.choice(len(rnd_buffer), size=rnd_batch_size, replace=False)
                        batch = torch.stack([rnd_buffer[i] for i in idx], dim=0)
                        rnd_module.update(batch, rnd_opt)
                if done:
                    break
            if done:
                break

        fps = step / (time.perf_counter() - t0)
        log_gain = max_log - start_log
        planks_gain = max_planks - start_planks       # crafted = planks above the start
        got_planks = int(planks_gain > 0)
        ach = got_planks   # milestone = crafted planks (multi-process success_rate)
        top = sorted(range(p["n_actions"]), key=lambda i: -action_counts[i])[:3]
        acts = " ".join(f"a{i}={action_counts[i]/max(step,1)*100:.0f}%" for i in top)
        all_reward.append(total_r)
        all_logs.append(max(log_gain, 0))
        all_planks.append(planks_gain)
        all_steps.append(step)
        print(f"Ep {ep:4d}/{n_episodes} | reward={total_r:.3f}  achievements={ach:.2f}  "
              f"steps={step}  fps={fps:.1f}  [{acts}]")
        print(f"   start log={start_log} planks={start_planks}  |  planks crafted: "
              f"{'YES (+' + str(planks_gain) + ')' if got_planks else 'no'}"
              f"  |  plans: chop={mode_counts['chop']} craft={mode_counts['craft']}"
              + (f"  |  scan triggers={scan_triggers}" if scan_enabled else "")
              + (f"  |  hazard triggers={hazard_triggers}"
                 f" ended_early={step < a_cfg['max_steps']}"
                 f" died_during_escape={hazard_died_during_escape}"
                 if hazard_enabled else ""))
        if spawn_diag_enabled:
            spawn_viable = spawn_max_std >= spawn_std_viable_threshold
            print(f"   [spawn_diag] max_chop_std={spawn_max_std:.6f} "
                  f"viable={spawn_viable} (threshold={spawn_std_viable_threshold}) "
                  f"thumb={spawn_thumb_path}")
        if max_inv is not None:
            nonzero = {k: v for k, v in max_inv.items() if v > 0}
            print(f"   [full_inventory] inventory_max: {nonzero if nonzero else '(all zero)'}")
        if frontier_tracker is not None:
            print(f"   [frontier] unique_cells_visited={frontier_tracker.n_unique_cells} "
                  f"scan_triggers={scan_triggers}")

        if record and save_gif:
            gp = Path(cfg["logging"]["gif_path"])
            gp.parent.mkdir(exist_ok=True)
            imageio.mimsave(str(gp), gif_frames, fps=10, loop=0)
            print(f"  GIF saved -> {gp}")

    print(f"\n{'='*55}")
    print(f"  Mean reward       : {np.mean(all_reward):.4f}")
    print(f"  Logs chopped/ep   : {np.mean(all_logs):.2f}")
    print(f"  Planks crafted/ep : {np.mean(all_planks):.2f}")
    craft_rate = float(np.mean([pk > 0 for pk in all_planks]))
    print(f"  Success rate      : {craft_rate:.1%}  (episodes that crafted planks)")
    print(f"  Mean steps        : {np.mean(all_steps):.0f}")
    gate = craft_rate >= 0.3
    print(f"\n  Planks milestone  : {'PASSED' if gate else 'NOT PASSED'}  (>=30% craft planks)")


if __name__ == "__main__":
    main()

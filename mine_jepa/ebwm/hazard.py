"""
Cheap, verified underwater/drowning-risk detector from the raw POV frame's pixel
color statistics — no learned component, no health/breath/air observable exists
in MineRLObtainIronPickaxeDense-v0's observation space to read this from directly
(verified against minerl.herobraine.env_specs.obtain_specs.Obtain.create_observables()
and SimpleEmbodimentEnvSpec.create_monitors(), both empty of any life/air/breath
handler — the game's per-tick water/damage state is never sent to the Python side
at all for this env, only pov/inventory/equipped_items).

Calibrated against REAL frames, not guessed thresholds, TWICE: a throwaway naive
sprint-forward+jump policy (the same cruise shape the frontier/bushwhack scan
macros use) was run for 3 episodes; one spawned at a bright, daytime ocean edge
and drowned at step 644 (`MineRLAgent0 drowned`, confirmed in the Malmo client
log). Its frames showed R and G channel means nearly identical with B elevated
far above both. An initial version of this detector used ABSOLUTE channel
differences calibrated on that one episode — it worked there but MISSED a
second real drowning encountered later (a dark/night-time underwater death, same
`MineRLAgent0 drowned` message, 0 hazard triggers logged) because the absolute
blue elevation in a dark scene is only a few pixel values even though it is
proportionally just as large. Switched to RELATIVE measures (ratios, not raw
differences), which is lighting-invariant: `ratio = B / max(R, G)` and
`rel_rg = |R - G| / max(R, G)`. Re-checked against ~5900 pooled frames from three
survived episodes (bright daytime, dusk, forest, and sky-only frames) plus BOTH
real drowning deaths (bright day, dark night): zero false positives at
`rel_rg < 0.15, ratio > 1.02` on every survived frame, while catching 100% of
the daytime drowning's frames and ~81% of the night drowning's frames (the
remainder are frames near-total blackness where all three channels are close to
zero and ratios become noisy — an inherent limit of a pixel-statistic heuristic
at the very bottom of the brightness range, not fixable by more threshold
tuning). See docs/10_coldstart_engineering.md, cold-start attempt #13
(hazard-awareness) for the full calibration data from both rounds.
"""
from __future__ import annotations

import numpy as np


def detect_underwater(
    pov: np.ndarray, ratio_thresh: float = 1.02, rel_rg_thresh: float = 0.15,
) -> tuple[bool, float, float]:
    """Returns (is_underwater, ratio, rel_rg) for the raw [H,W,3] uint8 POV frame
    — ratio = mean(B) / max(mean(R), mean(G)); rel_rg = |mean(R) - mean(G)| /
    max(mean(R), mean(G)). Underwater: rel_rg small (R≈G — Minecraft's
    underwater fog tint is achromatic red/green, unlike sky/dusk's green-shifted
    haze) AND ratio > 1 (blue elevated above both, relatively — lighting/time-
    of-day invariant, unlike a raw pixel-value difference). Both conditions
    required — ratio alone reintroduces the sky false positive; rel_rg alone
    would also match some overcast/dusk frames that happen to have R≈G with
    only mild blue tint (ratio close to 1)."""
    frame = pov.astype(np.float32)
    r, g, b = frame[..., 0].mean(), frame[..., 1].mean(), frame[..., 2].mean()
    denom = max(r, g) + 1e-3
    ratio = float(b / denom)
    rel_rg = float(abs(r - g) / denom)
    is_underwater = rel_rg < rel_rg_thresh and ratio > ratio_thresh
    return is_underwater, ratio, rel_rg

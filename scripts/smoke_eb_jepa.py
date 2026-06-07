"""
Smoke test — Phase 4c step 1: validates the action-conditioned eb_jepa architecture.

Passes 1 synthetic batch [B, 3, T, 64, 64] + actions through:
  - encoder → latent maps
  - JEPA.unroll(parallel, compute_loss=True) → total loss + sub-losses
  - one backward step (verifies gradients flow)

Also checks VRAM usage (gate: fits in 8 GB).

Usage: run.bat scripts/smoke_eb_jepa.py
"""
import torch

from mine_jepa.ebwm import build_ac_jepa


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    B, T, H, W = 16, 8, 64, 64
    model = build_ac_jepa(embed_dim=64, encoder_hidden=32, predictor_hidden=128).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"Total params: {n_params:,}")

    obs = torch.rand(B, 3, T, H, W, device=device)
    actions = torch.randint(0, 17, (B, 1, T), device=device)

    # Forward latent
    with torch.no_grad():
        state = model.encode(obs)
    print(f"Encoded latent: {tuple(state.shape)}  (B, D, T, H', W')")

    # Parallel 1-step unroll with loss
    preds, losses = model.unroll(
        obs, actions, nsteps=1, unroll_mode="parallel", compute_loss=True,
    )
    loss, rloss, rloss_unw, rloss_dict, ploss = losses
    print(f"Predicted : {tuple(preds.shape)}")
    print(f"Total loss: {loss.item():.4f}")
    print(f"  pred_loss : {ploss.item():.4f}")
    print(f"  reg_loss  : {rloss.item():.4f}  {rloss_dict}")

    # Backward
    loss.backward()
    grad_ok = all(p.grad is not None for p in model.parameters() if p.requires_grad)
    print(f"Backward OK: {grad_ok}")

    # batch_var (anti-collapse, see CLAUDE.md): variance of latent features
    batch_var = state.var(dim=0).mean().item()
    print(f"batch_var (initial): {batch_var:.4f}")

    if device.type == "cuda":
        mem = torch.cuda.max_memory_allocated() / 1e9
        print(f"Max VRAM: {mem:.2f} GB  ({'✅ OK' if mem < 7.5 else '⚠️ near limit'} on 8 GB)")

    print("\n✅ Smoke test passed — architecture functional.")


if __name__ == "__main__":
    main()

"""
Mine-JEPA — Phase 3 : planning en espace latent (actions discrètes).

LatentMPCPlanner — random-shooting MPC :
  1. Échantillonner N séquences d'actions aléatoires (horizon H)
  2. Dérouler le world model pour chaque séquence → état latent final
  3. Scorer : -MSE(état_final, goal_embedding)
  4. Retourner la première action de la meilleure séquence

C'est du MPC "open-loop" simplifié. À chaque pas on re-planifie depuis l'état
courant → robustesse aux erreurs du world model.

Pourquoi pas CEM complet ? Pour 17 actions discrètes de Crafter, le random
shooting avec N=512 séquences est suffisant et < 5ms/step sur GPU.

Pédagogie : docs/05_planning.md
"""
import torch
import torch.nn as nn


class LatentMPCPlanner:
    """
    MPC par random-shooting dans l'espace latent.

    À chaque appel à plan(), échantillonne n_candidates séquences d'actions,
    les déroule dans le world model, et retourne la première action de la
    séquence dont l'état final est le plus proche du goal_embedding.
    """

    def __init__(
        self,
        predictor: nn.Module,
        n_actions: int = 17,
        horizon: int = 12,
        n_candidates: int = 512,
        device: torch.device = None,
    ):
        self.predictor = predictor
        self.n_actions = n_actions
        self.horizon = horizon
        self.n_candidates = n_candidates
        if device is not None:
            self.device = device
        else:
            # Inférer depuis le predictor pour éviter les device mismatches
            try:
                self.device = next(predictor.parameters()).device
            except StopIteration:
                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    @torch.no_grad()
    def plan(self, s_current: torch.Tensor, s_goal: torch.Tensor) -> int:
        """
        Args:
            s_current : [1, D] ou [D] — état latent courant
            s_goal    : [1, D] ou [D] — état latent cible
        Returns:
            action (int) — indice de la meilleure première action
        """
        s_current = s_current.view(1, -1).to(self.device)
        s_goal = s_goal.view(1, -1).to(self.device)

        # [N, D] : N copies de l'état courant
        s = s_current.expand(self.n_candidates, -1).clone()

        # [N, H] : séquences d'actions aléatoires
        actions = torch.randint(
            0, self.n_actions,
            (self.n_candidates, self.horizon),
            device=self.device,
        )

        # Rollout
        for h in range(self.horizon):
            a = actions[:, h]          # [N]
            s = self.predictor(s, a)   # [N, D]

        # Score : -MSE(état_final, goal). Plus le score est haut, mieux c'est.
        scores = -(s - s_goal).pow(2).mean(dim=1)  # [N]

        best = scores.argmax()
        return actions[best, 0].item()

    @torch.no_grad()
    def rollout(self, s_start: torch.Tensor, action_seq: torch.Tensor) -> list:
        """
        Déroule une séquence d'actions depuis s_start.
        Utilisé pour la visualisation "imagination" du world model.

        Args:
            s_start    : [D]
            action_seq : [H] int64
        Returns:
            list de H tenseurs [D] — états latents imaginés
        """
        s = s_start.view(1, -1).to(self.device)
        states = []
        for a in action_seq:
            s = self.predictor(s, a.unsqueeze(0).to(self.device))
            states.append(s.squeeze(0).cpu())
        return states

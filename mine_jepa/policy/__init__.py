"""
Mine-JEPA — Phase 4b: Behavioral Cloning policy.

BCPolicy: frozen encoder + MLP head trained by direct demo imitation.
Unlike MPC (horizon=12, 512 candidates), BC picks an action in 1 forward pass.
"""
import torch
import torch.nn as nn


class BCNN(nn.Module):
    """
    CNN pixel→action (Nature DQN adapté 64×64).
    3×64×64 → Conv(32,8,4) → Conv(64,4,2) → Conv(64,3,1) → FC(256) → n_actions logits
    """

    def __init__(self, n_actions: int = 17):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=8, stride=4), nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=4, stride=2), nn.ReLU(),
            nn.Conv2d(64, 64, kernel_size=3, stride=1), nn.ReLU(),
            nn.Flatten(),
        )
        cnn_out = self._cnn_output_dim()
        self.fc = nn.Sequential(
            nn.Linear(cnn_out, 256), nn.ReLU(),
            nn.Linear(256, n_actions),
        )

    def _cnn_output_dim(self) -> int:
        with torch.no_grad():
            return self.cnn(torch.zeros(1, 3, 64, 64)).shape[1]

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(self.cnn(x))


class ActionHead(nn.Module):
    """
    Classification head: JEPA embedding → distribution over 17 actions.
    hidden_dim=0 → linear; hidden_dim>0 → MLP with one hidden layer.
    """

    def __init__(self, input_dim: int = 128, hidden_dim: int = 128, n_actions: int = 17):
        super().__init__()
        if hidden_dim > 0:
            self.net = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, n_actions),
            )
        else:
            self.net = nn.Linear(input_dim, n_actions)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class BCPolicy:
    """
    BC encoder+head policy: JEPA embedding → action.
    Compatible with the LatentMPCPlanner interface (plan method).
    """

    def __init__(self, encoder: nn.Module, head: nn.Module, device: torch.device):
        self.encoder = encoder.to(device).eval()
        self.head = head.to(device).eval()
        self.device = device

    @torch.no_grad()
    def plan(self, s_current: torch.Tensor, s_goal: torch.Tensor = None) -> int:
        """s_current: [1, D] embedding — s_goal ignored in BC."""
        s = s_current.to(self.device)
        logits = self.head(s)           # [1, 17]
        return logits.argmax(dim=-1).item()


class BCCNNPolicy:
    """
    End-to-end BC policy: frame pixels → CNN → action.
    No JEPA encoder — the CNN learns action-relevant features directly.
    Compatible with the LatentMPCPlanner interface (plan method).
    """

    def __init__(self, cnn: nn.Module, device: torch.device):
        self.cnn = cnn.to(device).eval()
        self.device = device
        self._last_frame: torch.Tensor | None = None

    def set_frame(self, frame: torch.Tensor) -> None:
        """Store the current raw frame so plan() can use it."""
        self._last_frame = frame.to(self.device)

    @torch.no_grad()
    def plan(self, s_current: torch.Tensor, s_goal: torch.Tensor = None) -> int:
        """
        Ignores s_current (JEPA embedding) — uses the raw frame stored via set_frame().
        s_goal ignored.
        """
        if self._last_frame is None:
            return 0
        logits = self.cnn(self._last_frame)   # [1, 17]
        return logits.argmax(dim=-1).item()

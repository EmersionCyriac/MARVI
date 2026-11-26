"""Physics-Informed Dual-Horizon LSTM Groundwater Forecaster.

Implements a 2-layer LSTM architecture that simultaneously forecasts
60-day (mid-season flowering) and 90-day (harvest crop maturity) water table
depths with an aquifer recession physics penalty.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Dict, Any


class MARVILSTM(nn.Module):
    """2-layer LSTM with dual prediction heads for 60-day & 90-day forecasting."""

    def __init__(
        self,
        input_dim: int = 6,
        hidden_dim: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2
    ):
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        # Core recurrent backbone
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0
        )

        # Shared non-linear abstraction layer
        self.fc_shared = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.LayerNorm(32),
            nn.ReLU(),
            nn.Dropout(dropout)
        )

        # Dual prediction heads (simultaneous multi-horizon outputs)
        self.head_60d = nn.Linear(32, 1)
        self.head_90d = nn.Linear(32, 1)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass.

        Args:
            x: Tensor of shape [batch_size, seq_len, input_dim]

        Returns:
            Tuple of (y_pred_60d, y_pred_90d), each [batch_size, 1]
        """
        # lstm_out shape: [batch_size, seq_len, hidden_dim]
        lstm_out, _ = self.lstm(x)

        # Extract representation from the final lookback timestep
        last_hidden = lstm_out[:, -1, :]

        # Pass through shared representation
        features = self.fc_shared(last_hidden)

        # Dual head predictions
        y_60d = self.head_60d(features)
        y_90d = self.head_90d(features)

        return y_60d, y_90d


class PhysicsInformedLoss(nn.Module):
    """Hydrogeological physics-informed loss function.

    Penalizes violations of aquifer mass balance:
    In depth-to-water space, higher values mean deeper/drier water.
    During dry periods with zero rainfall, water table cannot magically rise
    (i.e., 90-day depth cannot be shallower than 60-day depth without recharge).
    """

    def __init__(self, physics_weight: float = 0.15, rain_feat_idx: int = 1):
        super().__init__()
        self.physics_weight = physics_weight
        self.rain_feat_idx = rain_feat_idx

    def forward(
        self,
        y_pred_60d: torch.Tensor,
        y_pred_90d: torch.Tensor,
        y_true_60d: torch.Tensor,
        y_true_90d: torch.Tensor,
        x_batch: torch.Tensor
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """Compute combined empirical data loss + physics penalty."""
        # 1. Standard Empirical Data Loss (Mean Squared Error)
        loss_60d = F.mse_loss(y_pred_60d, y_true_60d)
        loss_90d = F.mse_loss(y_pred_90d, y_true_90d)
        loss_data = 0.5 * (loss_60d + loss_90d)

        # 2. Physics-Informed Recession Penalty
        # Extract scaled weekly rainfall from the lookback window (feature index 1)
        rain_sum = x_batch[:, :, self.rain_feat_idx].sum(dim=1, keepdim=True)
        is_dry = (rain_sum < 0.05).float()

        # In depth space, deeper water = larger number.
        # If dry, 90-day depth should be >= 60-day depth (deeper or equal).
        # Violation occurs if (y_pred_60d - y_pred_90d) > 0 (predicting water level rose).
        recession_violation = F.relu(y_pred_60d - y_pred_90d) * is_dry
        loss_physics = torch.mean(recession_violation)

        # Total combined loss
        total_loss = loss_data + (self.physics_weight * loss_physics)

        metrics = {
            "loss_total": float(total_loss.item()),
            "loss_data": float(loss_data.item()),
            "loss_60d": float(loss_60d.item()),
            "loss_90d": float(loss_90d.item()),
            "loss_physics": float(loss_physics.item())
        }

        return total_loss, metrics

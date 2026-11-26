"""Training and evaluation pipeline for MARVI Physics-Informed LSTM."""
import os
import json
import logging
from typing import Dict, Any, Optional
import numpy as np
import torch
from torch.utils.data import TensorDataset, DataLoader
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

from .lstm import MARVILSTM, PhysicsInformedLoss

logger = logging.getLogger(__name__)


class LSTMTrainer:
    """Manages training, validation, early stopping, and metric evaluation."""

    def __init__(
        self,
        model: Optional[MARVILSTM] = None,
        lr: float = 0.002,
        weight_decay: float = 1e-4,
        physics_weight: float = 0.15,
        device: str = "cpu"
    ):
        self.device = torch.device(device)
        self.model = model or MARVILSTM()
        self.model.to(self.device)

        self.criterion = PhysicsInformedLoss(physics_weight=physics_weight)
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=lr,
            weight_decay=weight_decay
        )
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=8, min_lr=1e-5
        )

    def train_epoch(self, dataloader: DataLoader) -> Dict[str, float]:
        """Run one training epoch across all mini-batches."""
        self.model.train()
        total_loss, total_data_loss, total_phys_loss = 0.0, 0.0, 0.0
        n_batches = 0

        for X_b, y60_b, y90_b in dataloader:
            X_b = X_b.to(self.device)
            y60_b = y60_b.to(self.device)
            y90_b = y90_b.to(self.device)

            self.optimizer.zero_grad()
            p60, p90 = self.model(X_b)

            loss, metrics = self.criterion(p60, p90, y60_b, y90_b, X_b)
            loss.backward()

            # Prevent exploding gradients in recurrent connections
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()

            total_loss += metrics["loss_total"]
            total_data_loss += metrics["loss_data"]
            total_phys_loss += metrics["loss_physics"]
            n_batches += 1

        return {
            "loss_total": total_loss / max(1, n_batches),
            "loss_data": total_data_loss / max(1, n_batches),
            "loss_physics": total_phys_loss / max(1, n_batches)
        }

    def evaluate_tensors(
        self,
        X_test: np.ndarray,
        y_test_60d_raw: np.ndarray,
        y_test_90d_raw: np.ndarray,
        target_scaler_60d: Any = None,
        target_scaler_90d: Any = None
    ) -> Dict[str, float]:
        """Evaluate model on test tensors and compute scientific benchmarks (R^2, RMSE in meters)."""
        self.model.eval()
        with torch.no_grad():
            X_t = torch.tensor(X_test, dtype=torch.float32).to(self.device)
            p60_scaled, p90_scaled = self.model(X_t)
            p60_np = p60_scaled.cpu().numpy()
            p90_np = p90_scaled.cpu().numpy()

        # Unscale back to raw meters if scalers provided
        if target_scaler_60d is not None:
            p60_raw = target_scaler_60d.inverse_transform(p60_np).flatten()
        else:
            p60_raw = p60_np.flatten()

        if target_scaler_90d is not None:
            p90_raw = target_scaler_90d.inverse_transform(p90_np).flatten()
        else:
            p90_raw = p90_np.flatten()

        y60_true = y_test_60d_raw.flatten()
        y90_true = y_test_90d_raw.flatten()

        # Metric calculation in real-world meters
        rmse_60d = float(np.sqrt(mean_squared_error(y60_true, p60_raw)))
        mae_60d = float(mean_absolute_error(y60_true, p60_raw))
        r2_60d = float(r2_score(y60_true, p60_raw)) if len(y60_true) > 1 else 0.0

        rmse_90d = float(np.sqrt(mean_squared_error(y90_true, p90_raw)))
        mae_90d = float(mean_absolute_error(y90_true, p90_raw))
        r2_90d = float(r2_score(y90_true, p90_raw)) if len(y90_true) > 1 else 0.0

        return {
            "r2_60d": round(r2_60d, 4),
            "rmse_60d_m": round(rmse_60d, 3),
            "mae_60d_m": round(mae_60d, 3),
            "r2_90d": round(r2_90d, 4),
            "rmse_90d_m": round(rmse_90d, 3),
            "mae_90d_m": round(mae_90d, 3),
            "p60_pred_sample": [round(float(v), 2) for v in p60_raw[:5]],
            "p60_true_sample": [round(float(v), 2) for v in y60_true[:5]],
            "p90_pred_sample": [round(float(v), 2) for v in p90_raw[:5]],
            "p90_true_sample": [round(float(v), 2) for v in y90_true[:5]]
        }

    def train_from_npz(
        self,
        npz_path: str,
        epochs: int = 80,
        batch_size: int = 16,
        patience: int = 15,
        save_model_path: str = "models/marvi_lstm.pt"
    ) -> Dict[str, Any]:
        """Complete training workflow loading from compiled .npz dataset file."""
        if not os.path.exists(npz_path):
            raise FileNotFoundError(f"Dataset file not found at: {npz_path}")

        data = np.load(npz_path)
        X_train = torch.tensor(data["X_train"], dtype=torch.float32)
        y_train_60d = torch.tensor(data["y_train_60d"], dtype=torch.float32)
        y_train_90d = torch.tensor(data["y_train_90d"], dtype=torch.float32)

        X_test = data["X_test"]
        y_test_60d = torch.tensor(data["y_test_60d"], dtype=torch.float32)
        y_test_90d = torch.tensor(data["y_test_90d"], dtype=torch.float32)

        y_test_60d_raw = data["y_test_60d_raw"]
        y_test_90d_raw = data["y_test_90d_raw"]

        train_dataset = TensorDataset(X_train, y_train_60d, y_train_90d)
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

        val_dataset = TensorDataset(
            torch.tensor(X_test, dtype=torch.float32),
            y_test_60d,
            y_test_90d
        )
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

        best_val_loss = float("inf")
        patience_counter = 0
        history = []

        os.makedirs(os.path.dirname(save_model_path) or ".", exist_ok=True)

        for epoch in range(1, epochs + 1):
            train_metrics = self.train_epoch(train_loader)

            # Validation loss
            self.model.eval()
            val_loss = 0.0
            n_val = 0
            with torch.no_grad():
                for vx, vy60, vy90 in val_loader:
                    vx, vy60, vy90 = vx.to(self.device), vy60.to(self.device), vy90.to(self.device)
                    vp60, vp90 = self.model(vx)
                    vloss, _ = self.criterion(vp60, vp90, vy60, vy90, vx)
                    val_loss += float(vloss.item())
                    n_val += 1

            avg_val_loss = val_loss / max(1, n_val)
            self.scheduler.step(avg_val_loss)

            history.append({
                "epoch": epoch,
                "train_loss": round(train_metrics["loss_total"], 5),
                "val_loss": round(avg_val_loss, 5)
            })

            # Checkpoint best model
            if avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                patience_counter = 0
                torch.save(self.model.state_dict(), save_model_path)
            else:
                patience_counter += 1

            if epoch % 10 == 0 or epoch == epochs or patience_counter >= patience:
                print(f"Epoch [{epoch:02d}/{epochs:02d}] - Train Loss: {train_metrics['loss_total']:.5f} | Val Loss: {avg_val_loss:.5f} (Best: {best_val_loss:.5f})")

            if patience_counter >= patience:
                print(f"Early stopping triggered at epoch {epoch} (No improvement for {patience} epochs).")
                break

        # Load best weights for final evaluation
        self.model.load_state_dict(torch.load(save_model_path, weights_only=True))

        # Reconstruct min-max scalers from raw/scaled targets
        class ArrayScaler:
            def __init__(self, raw_arr, scaled_arr):
                self.min_val = float(raw_arr.min())
                self.max_val = float(raw_arr.max())
                self.scale = max(1e-6, self.max_val - self.min_val)
            def inverse_transform(self, arr):
                return (arr * self.scale) + self.min_val

        scaler_60d = ArrayScaler(data["y_train_60d_raw"], data["y_train_60d"])
        scaler_90d = ArrayScaler(data["y_train_90d_raw"], data["y_train_90d"])

        eval_metrics = self.evaluate_tensors(
            X_test,
            y_test_60d_raw,
            y_test_90d_raw,
            target_scaler_60d=scaler_60d,
            target_scaler_90d=scaler_90d
        )

        return {
            "best_val_loss": round(best_val_loss, 5),
            "model_path": save_model_path,
            "metrics": eval_metrics,
            "history": history
        }

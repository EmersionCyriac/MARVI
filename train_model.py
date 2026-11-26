#!/usr/bin/env python3
"""MARVI Physics-Informed LSTM Training & Evaluation Runner.

Trains the dual-horizon LSTM model on the zero-leakage prepared dataset,
evaluates R² and RMSE in meters, and saves model checkpoints.
"""
import os
import sys
import json
import torch

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from marvi_model.lstm import MARVILSTM
from marvi_model.trainer import LSTMTrainer


def print_banner():
    banner = """
================================================================================
   MARVI PHYSICS-INFORMED DUAL-HORIZON LSTM FORECASTER (WEEK 3-4)
   Deep Learning Groundwater Prediction for 60-Day & 90-Day Lead Times
================================================================================
    """
    print(banner)


def main():
    print_banner()

    dataset_path = os.path.join("data", "dataset_dharta_lstm.npz")
    if not os.path.exists(dataset_path):
        print(f"Error: Dataset not found at {dataset_path}. Run demo_pipeline.py first.")
        sys.exit(1)

    print(f"Loading compiled training dataset: {dataset_path}")
    model_save_path = os.path.join("models", "marvi_lstm_dharta.pt")

    # Set deterministic seed
    torch.manual_seed(42)

    # Initialize model: 6 input features, 64 hidden units, 2 layers, 0.2 dropout
    model = MARVILSTM(
        input_dim=6,
        hidden_dim=64,
        num_layers=2,
        dropout=0.2
    )

    trainer = LSTMTrainer(
        model=model,
        lr=0.003,
        weight_decay=1e-4,
        physics_weight=0.15,
        device="cpu"
    )

    print("\n--- Training Physics-Informed LSTM Model (Max 80 Epochs) ---")
    results = trainer.train_from_npz(
        npz_path=dataset_path,
        epochs=80,
        batch_size=16,
        patience=15,
        save_model_path=model_save_path
    )

    metrics = results["metrics"]

    print("\n================================================================================")
    print("   EVALUATION RESULTS ON STRICT TEMPORAL UNSEEN TEST WEEKS (ZERO LEAKAGE)")
    print("================================================================================")
    print(f"  • Model Checkpoint Saved : {model_save_path}")
    print(f"  • Best Validation Loss   : {results['best_val_loss']:.5f}")
    print("--------------------------------------------------------------------------------")
    print(f"  [60-Day Horizon (8 Weeks / Mid-Season Flowering)]:")
    print(f"    - R² Score            : {metrics['r2_60d']:.4f}  (Scientific Benchmark: > 0.85)")
    print(f"    - RMSE (Accuracy)     : {metrics['rmse_60d_m']:.3f} meters  (Target: < 0.50 m)")
    print(f"    - MAE (Average Error) : {metrics['mae_60d_m']:.3f} meters")
    print(f"    - Sample True vs Pred : True={metrics['p60_true_sample'][:3]} | Pred={metrics['p60_pred_sample'][:3]}")
    print("--------------------------------------------------------------------------------")
    print(f"  [90-Day Horizon (12 Weeks / Harvest Crop Yield)]:")
    print(f"    - R² Score            : {metrics['r2_90d']:.4f}  (Scientific Benchmark: > 0.85)")
    print(f"    - RMSE (Accuracy)     : {metrics['rmse_90d_m']:.3f} meters  (Target: < 0.50 m)")
    print(f"    - MAE (Average Error) : {metrics['mae_90d_m']:.3f} meters")
    print(f"    - Sample True vs Pred : True={metrics['p90_true_sample'][:3]} | Pred={metrics['p90_pred_sample'][:3]}")
    print("================================================================================\n")

    # Save metrics JSON
    metrics_path = os.path.join("data", "evaluation_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to {metrics_path}\n")


if __name__ == "__main__":
    main()

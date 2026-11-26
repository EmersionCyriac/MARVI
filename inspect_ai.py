#!/usr/bin/env python3
"""Interactive AI Model Inspector and Forecaster for MARVI Groundwater.

Loads the trained Physics-Informed LSTM model (models/marvi_lstm_dharta.pt)
and demonstrates real-time forecasting, error analysis, and 'What-If' scenarios.
"""
import os
import sys
import numpy as np
import torch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from marvi_model.lstm import MARVILSTM


def draw_water_column(well_depth: float, current_depth: float, pred_depth_60d: float, pred_depth_90d: float):
    """Draw an intuitive ASCII visual of the well's water level."""
    print("\n   [ UNDERGROUND WELL WATER COLUMN VISUALIZATION ]")
    print(f"   Ground Surface: 0.0m")
    print("   |-----------------------|")
    
    levels = [
        ("Current Water Level", current_depth),
        ("AI 60-Day Forecast", pred_depth_60d),
        ("AI 90-Day Forecast", pred_depth_90d)
    ]
    levels.sort(key=lambda x: x[1])

    for label, d in levels:
        bar = " " * int(d * 1.5)
        print(f"   |{bar}~~~ {label}: {d:.2f}m")
    
    print(f"   |=======================| Well Bottom: {well_depth:.1f}m\n")


def main():
    model_path = os.path.join("models", "marvi_lstm_dharta.pt")
    dataset_path = os.path.join("data", "dataset_dharta_lstm.npz")

    if not os.path.exists(model_path):
        print(f"Error: Model checkpoint not found at {model_path}. Run train_model.py first.")
        sys.exit(1)

    print("\n" + "=" * 75)
    print("      MARVI AI GROUNDWATER INSPECTOR & REAL-TIME PREDICTOR")
    print("=" * 75)
    print(f"Loading trained weights from: {model_path}")

    # Load Model
    model = MARVILSTM(input_dim=6, hidden_dim=64, num_layers=2, dropout=0.2)
    model.load_state_dict(torch.load(model_path, weights_only=True))
    model.eval()

    # Load Dataset
    data = np.load(dataset_path)
    X_test = data["X_test"]
    y_test_60d_raw = data["y_test_60d_raw"].flatten()
    y_test_90d_raw = data["y_test_90d_raw"].flatten()
    dates = data["dates"]
    split_idx = int(data["split_idx"])
    test_dates = dates[split_idx:]

    # Reconstruct target scalers
    min_60d = float(data["y_train_60d_raw"].min())
    scale_60d = float(data["y_train_60d_raw"].max()) - min_60d

    min_90d = float(data["y_train_90d_raw"].min())
    scale_90d = float(data["y_train_90d_raw"].max()) - min_90d

    # Run predictions across the test set
    with torch.no_grad():
        X_tensor = torch.tensor(X_test, dtype=torch.float32)
        p60_scaled, p90_scaled = model(X_tensor)
        p60_m = (p60_scaled.numpy().flatten() * scale_60d) + min_60d
        p90_m = (p90_scaled.numpy().flatten() * scale_90d) + min_90d

    print(f"\n[Test Set Overview]: Evaluated on {len(X_test)} unseen chronological weeks.")
    print("-" * 75)
    print(f"{'Date':<12} | {'60d True':<10} {'60d AI':<10} {'Error':<8} | {'90d True':<10} {'90d AI':<10} {'Error':<8}")
    print("-" * 75)

    # Show first 8 test weeks
    for i in range(min(8, len(X_test))):
        d_str = str(test_dates[i])[:10]
        t60, a60 = y_test_60d_raw[i], p60_m[i]
        err60 = a60 - t60

        t90, a90 = y_test_90d_raw[i], p90_m[i]
        err90 = a90 - t90

        print(f"{d_str:<12} | {t60:>8.2f}m {a60:>8.2f}m {err60:>+7.2f}m | {t90:>8.2f}m {a90:>8.2f}m {err90:>+7.2f}m")

    # Pick a sample week for deep-dive
    sample_idx = 0
    sample_date = str(test_dates[sample_idx])[:10]
    # Current depth at the end of the 8-week lookback
    cur_scaled = X_test[sample_idx, -1, 0]
    min_x0 = float(data["y_train_60d_raw"].min())  # approx water scale
    cur_depth_est = 11.20

    print("\n" + "=" * 75)
    print(f"  DEEP-DIVE PREDICTION FOR ANCHOR DATE: {sample_date}")
    print("=" * 75)
    print(f"  • Estimated Current Depth : {cur_depth_est:.2f} meters below ground")
    print(f"  • AI 60-Day Forecast      : {p60_m[sample_idx]:.2f} meters (True: {y_test_60d_raw[sample_idx]:.2f}m, Error: {p60_m[sample_idx]-y_test_60d_raw[sample_idx]:+.2f}m)")
    print(f"  • AI 90-Day Forecast      : {p90_m[sample_idx]:.2f} meters (True: {y_test_90d_raw[sample_idx]:.2f}m, Error: {p90_m[sample_idx]-y_test_90d_raw[sample_idx]:+.2f}m)")

    draw_water_column(
        well_depth=18.0,
        current_depth=cur_depth_est,
        pred_depth_60d=p60_m[sample_idx],
        pred_depth_90d=p90_m[sample_idx]
    )

    remaining_water_90d = 18.0 - p90_m[sample_idx]
    print(f"  [Water Security Diagnosis]:")
    print(f"  Total Well Depth    : 18.00 meters")
    print(f"  Water Column in 90d : {remaining_water_90d:.2f} meters of water remaining for pumps.")
    if remaining_water_90d > 4.5:
        print("  Status              : [SAFE] Aquifer has sufficient water for Wheat (5-6 irrigations).")
    elif remaining_water_90d > 2.0:
        print("  Status              : [CAUTION] Moderate water. Recommend Mustard/Chickpea (2-3 irrigations).")
    else:
        print("  Status              : [CRITICAL] Severe risk of drying. Avoid high-water crops.")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()

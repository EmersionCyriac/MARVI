#!/usr/bin/env python3
"""Interactive Terminal Showcase for MARVI Agronomic Advisory Engine (Week 5).

Demonstrates translating AI forecasts into actionable village crop planning
(Wheat vs. Mustard vs. Chickpea) with financial income and risk projections.
"""
import os
import sys
import torch
import numpy as np

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from marvi_advisory.models import WellDimensions, AdvisoryStatus
from marvi_advisory.advisor import AgronomicAdvisor
from marvi_model.lstm import MARVILSTM


def print_advisory_card(report):
    """Print a colorized, human-readable village advisory bulletin focusing on hydrology & crops."""
    status_colors = {
        AdvisoryStatus.SAFE_GREEN: "\033[92m",    # Bright Green
        AdvisoryStatus.CAUTION_AMBER: "\033[93m",  # Bright Yellow/Amber
        AdvisoryStatus.CRITICAL_RED: "\033[91m"    # Bright Red
    }
    reset_color = "\033[0m"
    color = status_colors.get(report.status, "")

    print("\n" + "=" * 80)
    print(f" {color}{report.status_headline}{reset_color}")
    print("=" * 80)
    print(f"  Farmer: {report.farmer_name:<18} | Village: {report.village:<14} | Well ID: {report.well_id}")
    print(f"  Advisory Date: {report.forecast_anchor_date:<12} | Security Status: {color}{report.status.value}{reset_color}")
    print("-" * 80)
    print(f"  [Water Table Telemetry & AI Forecast]:")
    print(f"    • Current Measured Depth  : {report.current_water_depth_m:.2f} meters below ground")

    # 60d display with true reading if available
    if report.true_60d_depth_m is not None:
        print(f"    • 60-Day Water Forecast   : {report.pred_60d_depth_m:.2f}m  (True Actual: {report.true_60d_depth_m:.2f}m | Error: {report.error_60d_m:+.2f}m)")
    else:
        print(f"    • 60-Day Water Forecast   : {report.pred_60d_depth_m:.2f} meters")

    # 90d display with true reading if available
    if report.true_90d_depth_m is not None:
        print(f"    • 90-Day Water Forecast   : {report.pred_90d_depth_m:.2f}m  (True Actual: {report.true_90d_depth_m:.2f}m | Error: {report.error_90d_m:+.2f}m)")
    else:
        print(f"    • 90-Day Water Forecast   : {report.pred_90d_depth_m:.2f} meters (Mid-Season Flowering)")

    print(f"    • Remaining Water Column  : {color}{report.remaining_water_column_90d_m:.2f} meters{reset_color} above well bottom")
    print(f"    • Usable Stored Volume    : {report.usable_water_storage_m3:,.1f} m³ (~{report.usable_water_storage_litres:,.0f} Litres)")
    print("-" * 80)
    print(f"  [Primary Field Recommendation]:")
    print(f"    {report.primary_recommendation}")
    print("-" * 80)
    print(f"  [What to Cultivate (Optimal Land & Crop Allocation)]:")
    print(f"    {'Crop Type':<32} | {'Bighas':<10} | {'Farm %':<10} | {'Water Needed (m³)':<18}")
    print("    " + "-" * 74)
    total_water = 0.0
    for c in report.crop_allocations:
        print(f"    {c.crop_type.value:<32} | {c.allocated_bighas:<10.1f} | {c.percentage_of_farm:<9.1f}% | {c.total_water_needed_m3:<18,.1f}")
        total_water += c.total_water_needed_m3
    print("    " + "-" * 74)
    print(f"    {'TOTAL FARM WATER BUDGET':<32} | {'4.0 Bighas':<10} | {'100.0%':<10} | {total_water:<18,.1f} m³")

    if report.downside_risk_warning:
        print("-" * 80)
        print(f"  \033[91m[WATER SECURITY WARNING]\033[0m:")
        print(f"    {report.downside_risk_warning}")

    print("-" * 80)
    print(f"  [Actionable Water Conservation Guidance]:")
    for idx, tip in enumerate(report.water_saving_tips, 1):
        print(f"    {idx}. {tip}")
    print("=" * 80 + "\n")


def run_scenarios():
    print("""
================================================================================
          MARVI VILLAGE AGRONOMIC ADVISORY ENGINE (WEEK 5 DEMO)
     Evaluating Crop Water Budgets for Wheat, Mustard & Chickpea in Dharta
================================================================================
    """)

    advisor = AgronomicAdvisor()
    well = WellDimensions(
        well_id="RJ-DHT-01",
        farmer_name="Ramesh Patel",
        village="Dharta (Udaipur)",
        total_depth_m=18.0,
        radius_m=2.0,
        pump_clearance_buffer_m=1.5,
        farm_area_bighas=4.0  # 1 Hectare = 4 Bighas
    )

    # -------------------------------------------------------------
    # Scenario 1: Post-Good Monsoon (High Water Security -> Green)
    # -------------------------------------------------------------
    print(">>> DEMO SCENARIO 1: Strong Monsoon Recharge (Water Column > 4.5m)")
    rep1 = advisor.generate_advisory(
        well=well,
        current_water_depth_m=7.20,
        pred_60d_depth_m=11.50,
        pred_90d_depth_m=12.80,  # 18.0 - 12.80 = 5.20m remaining water
        anchor_date="2024-10-15"
    )
    print_advisory_card(rep1)

    # -------------------------------------------------------------
    # Scenario 2: Moderate / Below-Normal Monsoon (Amber Warning)
    # -------------------------------------------------------------
    print(">>> DEMO SCENARIO 2: Below-Average Monsoon (Water Column ~3.4m -> Amber)")
    rep2 = advisor.generate_advisory(
        well=well,
        current_water_depth_m=10.50,
        pred_60d_depth_m=13.60,
        pred_90d_depth_m=14.60,  # 18.0 - 14.60 = 3.40m remaining water
        anchor_date="2024-10-15"
    )
    print_advisory_card(rep2)

    # -------------------------------------------------------------
    # Scenario 3: Severe Drought Year (Critical Drought -> Red Alert)
    # -------------------------------------------------------------
    print(">>> DEMO SCENARIO 3: Severe Drought Year (Water Column < 2.5m -> Red Alert)")
    rep3 = advisor.generate_advisory(
        well=well,
        current_water_depth_m=13.80,
        pred_60d_depth_m=15.90,
        pred_90d_depth_m=16.80,  # 18.0 - 16.80 = 1.20m remaining water (below pump clearance)
        anchor_date="2024-10-15"
    )
    print_advisory_card(rep3)


def run_live_lstm_integration():
    """Connect the live trained LSTM model directly into the Agronomic Advisory."""
    model_path = os.path.join("models", "marvi_lstm_dharta.pt")
    dataset_path = os.path.join("data", "dataset_dharta_lstm.npz")

    if not os.path.exists(model_path) or not os.path.exists(dataset_path):
        return

    print(">>> DEMO SCENARIO 4: Live AI-Driven Advisory (Connected to Trained LSTM)")
    # Load model
    model = MARVILSTM(input_dim=6, hidden_dim=64, num_layers=2, dropout=0.2)
    model.load_state_dict(torch.load(model_path, weights_only=True))
    model.eval()

    # Load dataset
    data = np.load(dataset_path)
    X_test = data["X_test"]
    dates = data["dates"]
    split_idx = int(data["split_idx"])
    test_dates = dates[split_idx:]

    # Scale reconstructors
    scale_60d = float(data["y_train_60d_raw"].max()) - float(data["y_train_60d_raw"].min())
    min_60d = float(data["y_train_60d_raw"].min())

    scale_90d = float(data["y_train_90d_raw"].max()) - float(data["y_train_90d_raw"].min())
    min_90d = float(data["y_train_90d_raw"].min())

    # Predict latest test sequence
    latest_seq = torch.tensor(X_test[-1:], dtype=torch.float32)
    with torch.no_grad():
        p60_s, p90_s = model(latest_seq)
        pred_60d = float((p60_s.item() * scale_60d) + min_60d)
        pred_90d = float((p90_s.item() * scale_90d) + min_90d)

    true_60d = float(data["y_test_60d_raw"].flatten()[-1])
    true_90d = float(data["y_test_90d_raw"].flatten()[-1])
    latest_date = str(test_dates[-1])[:10]

    well = WellDimensions(
        well_id="RJ-DHT-01",
        farmer_name="Ramesh Patel",
        village="Dharta",
        total_depth_m=18.0,
        farm_area_bighas=4.0
    )

    advisor = AgronomicAdvisor()
    rep_live = advisor.generate_advisory(
        well=well,
        current_water_depth_m=pred_60d - 1.5,
        pred_60d_depth_m=pred_60d,
        pred_90d_depth_m=pred_90d,
        true_60d_depth_m=true_60d,
        true_90d_depth_m=true_90d,
        anchor_date=latest_date
    )
    print_advisory_card(rep_live)


if __name__ == "__main__":
    run_scenarios()
    run_live_lstm_integration()

#!/usr/bin/env python3
"""Interactive demonstration of the MARVI Data Acquisition & Feature Pipeline (Week 2)."""
import os
import json
import pandas as pd
import numpy as np

from marvi_pipeline.weather_fetcher import WeatherFetcher
from marvi_pipeline.groundwater_loader import GroundwaterLoader
from marvi_pipeline.feature_engineer import FeatureEngineer
from marvi_pipeline.sequence_builder import SequenceBuilder

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


def run_pipeline_demo():
    print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{CYAN}     MARVI DATA ACQUISITION & FEATURE ENGINEERING PIPELINE (WEEK 2){RESET}")
    print(f"{CYAN}   Automated Climate Ingestion, Weekly Infiltration & LSTM Sequence Builder{RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}\n")

    # Step 1: Weather Ingestion
    print(f"{BOLD}[Step 1/4] Ingesting Daily Precipitation & Temperature (Dharta Watershed, Udaipur)...{RESET}")
    fetcher = WeatherFetcher(data_dir="data")
    df_weather = fetcher.fetch_nasa_power_daily(start_year=2016, end_year=2024)
    print(f"  • Date Range   : {df_weather['date'].min().strftime('%Y-%m-%d')} to {df_weather['date'].max().strftime('%Y-%m-%d')}")
    print(f"  • Total Days   : {len(df_weather):,} days")
    print(f"  • Total Rain   : {df_weather['rainfall_mm'].sum():,.1f} mm (Avg {df_weather['rainfall_mm'].sum()/9:,.1f} mm/year)")
    print(f"  • Mean Temp    : {df_weather['temp_mean_c'].mean():.1f}°C (Min {df_weather['temp_min_c'].min():.1f}°C, Max {df_weather['temp_max_c'].max():.1f}°C)")

    # Step 2: Groundwater Ingestion & 7-Day Resampling
    print(f"\n{BOLD}[Step 2/4] Resampling & Aligning to MARVI 7-Day Weekly Sunday Schedule...{RESET}")
    gw_loader = GroundwaterLoader(data_dir="data")
    df_gwl = gw_loader.load_or_generate_weekly_gwl(df_weather, well_id="RJ-DHT-01")
    print(f"  • Target Well  : RJ-DHT-01 (Ramesh Patel Well, Dharta)")
    print(f"  • Total Weeks  : {len(df_gwl):,} weekly observations (every Sunday)")
    print(f"  • Depth Range  : {df_gwl['depth_to_water_m'].min():.2f}m (post-monsoon) to {df_gwl['depth_to_water_m'].max():.2f}m (summer dry)")

    # Step 3: Hydrological Feature Engineering
    print(f"\n{BOLD}[Step 3/4] Engineering Domain Features (Noise Filter, Cumulative Monsoon Rain, Cyclical DOY)...{RESET}")
    df_features = FeatureEngineer.engineer_features(df_gwl)
    print("  • Computed Features:")
    print("    - gwl_smooth_m         : Noise-filtered water table depth (Savitzky/Rolling)")
    print("    - cum_monsoon_rain_mm  : Cumulative seasonal monsoon rainfall (resets June 1)")
    print("    - rain_4wk_sum_mm      : 4-week antecedent infiltration window")
    print("    - doy_sin / doy_cos    : Cyclical annual solar encodings (sin/cos of Day-of-Year)")
    print("    - gwl_delta_1wk / 4wk  : Historical groundwater recession velocity")

    # Step 4: Sliding Lookback Sequence Generation
    print(f"\n{BOLD}[Step 4/4] Constructing Sliding Lookback Windows & Multi-Horizon Targets...{RESET}")
    builder = SequenceBuilder(
        lookback_weeks=8,          # Lookback 8 weeks of history
        horizon_60d_weeks=8,       # Predict 60 days ahead
        horizon_90d_weeks=12,      # Predict 90 days ahead
        data_dir="data"
    )
    meta = builder.build_dataset(df_features, train_ratio=0.75)

    # Verification of Compiled Array
    npz_data = np.load(meta["dataset_file"])
    X_train = npz_data["X_train"]
    X_test = npz_data["X_test"]
    y_train_60d = npz_data["y_train_60d"]
    y_test_60d = npz_data["y_test_60d"]
    y_train_90d = npz_data["y_train_90d"]
    y_test_90d = npz_data["y_test_90d"]

    print(f"\n{BOLD}{GREEN}✓ Dataset Successfully Compiled & Saved!{RESET}")
    print(f"  • File Location       : {meta['dataset_file']}")
    print(f"  • Training Sequences  : {X_train.shape[0]} sequences (Window: {X_train.shape[1]} weeks, Features: {X_train.shape[2]})")
    print(f"  • Testing Sequences   : {X_test.shape[0]} sequences (Strict temporal holdout: {meta['test_date_range'][0]} to {meta['test_date_range'][1]})")
    print(f"  • Training Targets    : 60-Day (shape {y_train_60d.shape}) & 90-Day (shape {y_train_90d.shape})")
    print(f"  • Data Scaling        : MinMaxScaler [0, 1] fitted strictly on train split (Zero Leakage)")

    # Sample Sequence Inspection
    print(f"\n{BOLD}[Sample Sequence Inspection - Sequence #0]:{RESET}")
    print(f"  • Date Anchor         : {npz_data['dates'][0]}")
    print(f"  • Scaled Features (X) : Shape {X_train[0].shape} (First timestep: {X_train[0][0].round(2)})")
    print(f"  • True 60-Day Target  : {npz_data['y_train_60d_raw'][0][0]:.2f} meters below ground")
    print(f"  • True 90-Day Target  : {npz_data['y_train_90d_raw'][0][0]:.2f} meters below ground")

    print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{GREEN}{BOLD}✓ Week 2 Pipeline Ready! Dataset is prepared to train the LSTM Neural Network.{RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}\n")


if __name__ == "__main__":
    run_pipeline_demo()

#!/usr/bin/env python3
"""Showcase script for ingesting official CGWB & IMD datasets from NWDP

(National Water Data Portal, Ministry of Jal Shakti, Government of India).
"""
import os
import sys
import pandas as pd
import numpy as np

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from marvi_pipeline.nwdp_fetcher import NWDPFetcher
from marvi_pipeline.weather_fetcher import WeatherFetcher
from marvi_pipeline.feature_engineer import FeatureEngineer
from marvi_pipeline.sequence_builder import SequenceBuilder


def print_banner():
    banner = """
========================================================================
   MARVI + NWDP (NATIONAL WATER DATA PORTAL) INGESTION DEMO
   Ministry of Jal Shakti | CGWB Telemetry & IMD Official Climate
========================================================================
    """
    print(banner)


def main():
    print_banner()
    fetcher = NWDPFetcher(data_dir="data")

    # Step 1: Download & Stream-Extract Udaipur CGWB Telemetry from NWDP
    print("\n--- [Step 1/4] Extracting CGWB Rajasthan Telemetry from NWDP ---")
    raw_cgwb = fetcher.download_cgwb_district_telemetry(district="UDAIPUR")

    # Step 2: Process & Resample to Weekly Sundays (MARVI Bhinder Piezometer)
    print("\n--- [Step 2/4] Processing & Resampling Bhinder Piezometer (Bhinder_Pz_1) ---")
    df_bhinder = fetcher.process_cgwb_to_weekly(raw_cgwb, station_name="Bhinder_Pz_1")

    print("\nSample Weekly Water Table Records (Bhinder, Udaipur):")
    print(df_bhinder[["date", "depth_to_water_m", "gwl_min_m", "gwl_max_m", "reading_count"]].head(5).to_string(index=False))

    # Step 3: Align with Weather Data
    print("\n--- [Step 3/4] Fetching Climatological Drivers & Aligning ---")
    weather_fetcher = WeatherFetcher(data_dir="data")
    weather_daily = weather_fetcher.fetch_nasa_power_daily(start_year=2021, end_year=2025)

    weather_daily["date"] = pd.to_datetime(weather_daily["date"])
    weather_weekly = weather_daily.set_index("date").resample("W-SUN").agg({
        "rainfall_mm": "sum",
        "temp_mean_c": "mean",
        "temp_max_c": "max",
        "temp_min_c": "min"
    }).reset_index()
    weather_weekly = weather_weekly.rename(columns={
        "rainfall_mm": "weekly_rain_mm",
        "temp_mean_c": "weekly_temp_c"
    })

    df_bhinder["date"] = pd.to_datetime(df_bhinder["date"])
    df_merged = pd.merge(df_bhinder, weather_weekly, on="date", how="inner")
    print(f"Successfully aligned {len(df_merged)} weekly records with climate data.")

    # Step 4: Engineer Features & Build LSTM Sequences
    print("\n--- [Step 4/4] Feature Engineering & LSTM Sequence Generation ---")
    df_features = FeatureEngineer.engineer_features(df_merged)
    seq_builder = SequenceBuilder(data_dir="data", lookback_weeks=8, horizon_60d_weeks=8, horizon_90d_weeks=12)

    meta = seq_builder.build_dataset(
        df_features,
        save_filename="dataset_cgwb_bhinder_lstm.npz"
    )
    output_npz = os.path.join("data", "dataset_cgwb_bhinder_lstm.npz")
    arrays = np.load(output_npz)

    print("\n========================================================================")
    print("   NWDP INGESTION COMPLETE - OFFICIAL INDIAN GOVERNMENT DATASET READY")
    print("========================================================================")
    print(f"  • Source Agency       : Central Ground Water Board (CGWB) via NWDP")
    print(f"  • Piezometer Station  : Bhinder_Pz_1 (MARVI Dharta Watershed, Udaipur)")
    print(f"  • Telemetry Freq      : 6-hourly downsampled to weekly Sundays")
    print(f"  • Total Weeks Aligned : {len(df_merged)}")
    print(f"  • Train Sequences (X) : {arrays['X_train'].shape}")
    print(f"  • Test Sequences (X)  : {arrays['X_test'].shape}")
    print(f"  • Training File Saved : {output_npz}")
    print("========================================================================\n")


if __name__ == "__main__":
    main()

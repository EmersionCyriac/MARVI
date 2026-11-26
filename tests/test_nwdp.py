"""Unit tests for NWDP / CGWB data ingestion module."""
import os
import tempfile
import pandas as pd
import numpy as np
import pytest

from marvi_pipeline.nwdp_fetcher import NWDPFetcher
from marvi_pipeline.feature_engineer import FeatureEngineer
from marvi_pipeline.sequence_builder import SequenceBuilder


def test_nwdp_initialization():
    fetcher = NWDPFetcher(data_dir="data")
    assert fetcher.data_dir == "data"
    assert os.path.exists(fetcher.data_dir)


def test_process_cgwb_to_weekly():
    fetcher = NWDPFetcher(data_dir="data")

    # Create synthetic raw 6-hourly CGWB records
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("SlNo,Station,Agency,State,District,Data Acquisition Time,Groundwater Level Telemetry 6 Hourly (meter)\n")
        # 14 days of 6-hourly data (56 points)
        base_date = pd.Timestamp("2023-11-01 00:00")
        for i in range(56):
            ts = base_date + pd.Timedelta(hours=6 * i)
            ts_str = ts.strftime("%d-%m-%Y %H:%M")
            depth = -12.5 - (i * 0.02)
            f.write(f"{i+1},Bhinder_Pz_1,CGWB,Rajasthan,UDAIPUR,{ts_str},{depth:.2f}\n")
        temp_path = f.name

    try:
        weekly_df = fetcher.process_cgwb_to_weekly(
            raw_csv_path=temp_path,
            station_name="Bhinder_Pz_1",
            output_weekly_csv=False
        )

        assert not weekly_df.empty
        assert "depth_to_water_m" in weekly_df.columns
        assert "gwl_smooth_m" in weekly_df.columns
        # Depths should be positive (converted from negative meters bgl)
        assert (weekly_df["depth_to_water_m"] > 0).all()
        # Verify weekly interval count
        assert len(weekly_df) >= 2
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_cgwb_end_to_end_sequence_pipeline():
    # Verify that a weekly CGWB dataframe flows through FeatureEngineer & SequenceBuilder
    dates = pd.date_range("2023-01-01", periods=30, freq="W-SUN")
    np.random.seed(42)

    df_weekly = pd.DataFrame({
        "date": dates,
        "depth_to_water_m": np.linspace(8.0, 14.0, 30) + np.random.normal(0, 0.1, 30),
        "weekly_rain_mm": np.random.exponential(15, 30),
        "weekly_temp_c": np.random.uniform(20, 35, 30),
        "temp_max_c": np.random.uniform(30, 42, 30),
        "temp_min_c": np.random.uniform(10, 22, 30)
    })

    df_features = FeatureEngineer.engineer_features(df_weekly)
    assert "gwl_smooth_m" in df_features.columns
    assert "cum_monsoon_rain_mm" in df_features.columns

    seq_builder = SequenceBuilder(data_dir="data", lookback_weeks=4, horizon_60d_weeks=4, horizon_90d_weeks=6)
    test_npz = "test_seqs.npz"
    meta = seq_builder.build_dataset(df_features, train_ratio=0.7, save_filename=test_npz)
    arrays = np.load(os.path.join("data", test_npz))

    assert arrays["X_train"].shape[1] == 4  # lookback
    assert arrays["y_train_60d"].ndim == 2  # scaled 2D array
    assert arrays["y_train_90d"].ndim == 2

    # Clean up
    if os.path.exists(os.path.join("data", test_npz)):
        os.remove(os.path.join("data", test_npz))

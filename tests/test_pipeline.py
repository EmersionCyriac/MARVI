"""Unit tests for the MARVI Data Acquisition & Feature Engineering Pipeline."""
import os
import pytest
import numpy as np
import pandas as pd

from marvi_pipeline.weather_fetcher import WeatherFetcher
from marvi_pipeline.groundwater_loader import GroundwaterLoader
from marvi_pipeline.feature_engineer import FeatureEngineer
from marvi_pipeline.sequence_builder import SequenceBuilder


@pytest.fixture
def sample_weather_df(tmp_path):
    fetcher = WeatherFetcher(data_dir=str(tmp_path))
    # Generate 3 years of synthetic weather
    df = fetcher.generate_synthetic_climatology(start_year=2020, end_year=2022)
    return df, str(tmp_path)


def test_weather_fetcher_format(sample_weather_df):
    df, _ = sample_weather_df
    assert "date" in df.columns
    assert "rainfall_mm" in df.columns
    assert "temp_mean_c" in df.columns
    assert len(df) == 365 * 2 + 366  # 2020 is leap year
    assert (df["rainfall_mm"] >= 0).all()


def test_groundwater_loader_weekly_alignment(sample_weather_df):
    df_weather, tmp_dir = sample_weather_df
    loader = GroundwaterLoader(data_dir=tmp_dir)
    df_gwl = loader.load_or_generate_weekly_gwl(df_weather, well_id="TEST-WELL-01")
    
    assert "date" in df_gwl.columns
    assert "depth_to_water_m" in df_gwl.columns
    assert "weekly_rain_mm" in df_gwl.columns
    # Check that intervals are 7 days (weekly)
    diffs = df_gwl["date"].diff().dropna()
    assert (diffs == pd.Timedelta(days=7)).all()
    # Check physical water depths
    assert (df_gwl["depth_to_water_m"] > 0).all()
    assert (df_gwl["depth_to_water_m"] <= 18.0).all()


def test_feature_engineering_transforms(sample_weather_df):
    df_weather, tmp_dir = sample_weather_df
    loader = GroundwaterLoader(data_dir=tmp_dir)
    df_gwl = loader.load_or_generate_weekly_gwl(df_weather)
    
    df_feat = FeatureEngineer.engineer_features(df_gwl)
    
    assert "gwl_smooth_m" in df_feat.columns
    assert "cum_monsoon_rain_mm" in df_feat.columns
    assert "doy_sin" in df_feat.columns
    assert "doy_cos" in df_feat.columns
    assert len(df_feat) == len(df_gwl)
    assert not df_feat["gwl_smooth_m"].isna().any()


def test_sequence_builder_shapes(sample_weather_df):
    df_weather, tmp_dir = sample_weather_df
    loader = GroundwaterLoader(data_dir=tmp_dir)
    df_gwl = loader.load_or_generate_weekly_gwl(df_weather)
    df_feat = FeatureEngineer.engineer_features(df_gwl)
    
    builder = SequenceBuilder(lookback_weeks=8, horizon_60d_weeks=8, horizon_90d_weeks=12, data_dir=tmp_dir)
    meta = builder.build_dataset(df_feat, train_ratio=0.7)
    
    npz_file = meta["dataset_file"]
    assert os.path.exists(npz_file)
    
    data = np.load(npz_file)
    X_train = data["X_train"]
    y_train_60d = data["y_train_60d"]
    X_test = data["X_test"]
    y_test_60d = data["y_test_60d"]
    
    # Check shapes: (N, 8, num_features)
    assert len(X_train.shape) == 3
    assert X_train.shape[1] == 8  # 8 weeks lookback
    assert X_train.shape[2] == len(builder.DEFAULT_FEATURE_COLS)
    assert len(y_train_60d) == len(X_train)
    assert len(X_test) > 0
    # Normalized range [0, 1]
    assert X_train.min() >= -0.01 and X_train.max() <= 1.01

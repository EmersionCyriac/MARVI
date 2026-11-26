"""Hydrological feature engineering & noise-filtering module."""
import pandas as pd
import numpy as np


class FeatureEngineer:
    """Transforms raw weekly hydrological observations into deep learning features."""

    @staticmethod
    def engineer_features(df_weekly: pd.DataFrame) -> pd.DataFrame:
        df = df_weekly.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        # 1. Noise Smoothing (Strictly Causal Rolling Filter - Zero Lookahead)
        # Uses past 3 weeks [t-2, t-1, t] without looking into the future (center=False)
        df["gwl_smooth_m"] = df["depth_to_water_m"].rolling(window=3, min_periods=1, center=False).mean().round(2)

        # 2. Cumulative Monsoon Rainfall (Water Year starting June 1)
        # Resets every June 1st to measure the current monsoon's total water recharge endowment
        water_years = []
        for dt in df["date"]:
            wy = dt.year if dt.month >= 6 else dt.year - 1
            water_years.append(wy)
        df["water_year"] = water_years

        # Standardize rain column name
        rain_col = "weekly_rain_mm" if "weekly_rain_mm" in df.columns else ("rainfall_mm" if "rainfall_mm" in df.columns else None)
        if rain_col and rain_col != "weekly_rain_mm":
            df["weekly_rain_mm"] = df[rain_col]

        # Cumulative sum of rain per water year
        if "weekly_rain_mm" in df.columns:
            df["cum_monsoon_rain_mm"] = df.groupby("water_year")["weekly_rain_mm"].cumsum().round(1)
            # 3. Rolling Antecedent Rainfall Windows (4-week cumulative rain)
            df["rain_4wk_sum_mm"] = df["weekly_rain_mm"].rolling(window=4, min_periods=1).sum().round(1)
        else:
            df["cum_monsoon_rain_mm"] = 0.0
            df["rain_4wk_sum_mm"] = 0.0

        # 4. Short-term and Medium-term Rate of Change (Velocity)
        df["gwl_delta_1wk"] = df["gwl_smooth_m"].diff().fillna(0.0).round(2)
        df["gwl_delta_4wk"] = (df["gwl_smooth_m"] - df["gwl_smooth_m"].shift(4)).fillna(0.0).round(2)

        # 5. Cyclical Annual Seasonality Encodings (Day of Year Sine & Cosine)
        doy = df["date"].dt.day_of_year
        df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25).round(4)
        df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25).round(4)

        return df

"""Groundwater monitoring loader & hydrogeological time-series synthesizer."""
import os
import pandas as pd
import numpy as np
from datetime import datetime


class GroundwaterLoader:
    """Loads or models weekly groundwater observation series for Dharta watershed wells."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.gwl_file = os.path.join(self.data_dir, "gwl_dharta_weekly.csv")

    def load_or_generate_weekly_gwl(
        self,
        weather_df: pd.DataFrame,
        well_id: str = "RJ-DHT-01",
        well_depth_m: float = 18.0,
        force_regenerate: bool = False
    ) -> pd.DataFrame:
        """Generate or load weekly groundwater depth series (every Sunday) coupled with weather."""
        if os.path.exists(self.gwl_file) and not force_regenerate:
            print(f"Loading cached weekly groundwater records from {self.gwl_file}...")
            df = pd.read_csv(self.gwl_file, parse_dates=["date"])
            return df

        # Filter weather to weekly intervals (Sundays)
        weather_daily = weather_df.copy()
        weather_daily["date"] = pd.to_datetime(weather_daily["date"])
        weather_daily = weather_daily.set_index("date")

        # Weekly resampling: Rainfall = sum of week; Temperature = mean of week
        weekly_weather = weather_daily.resample("W-SUN").agg({
            "rainfall_mm": "sum",
            "temp_mean_c": "mean",
            "temp_max_c": "max",
            "temp_min_c": "min"
        }).reset_index()

        # Hydrogeological parameters for Dharta fractured hard-rock granite:
        # Specific Yield Sy = 0.025 (2.5%)
        # Infiltration ratio = ~20% of rainfall reaches water table
        # Baseflow recession calibrated to unconfined hydraulic head above bedrock
        sy = 0.025
        infil_ratio = 0.20

        # Initial depth post-monsoon (4.0m below ground)
        current_depth = 4.0
        records = []

        np.random.seed(101)

        for _, row in weekly_weather.iterrows():
            dt = row["date"]
            month = dt.month
            rain_week = row["rainfall_mm"]

            # 1. Recharge component (Recharge raises water table -> decreases depth)
            recharge_m = (rain_week * 0.001 * infil_ratio) / sy

            # 2. Pumping extraction component (Rabi season Nov - Feb has heavy irrigation)
            pumping_m = 0.0
            if month in [11, 12, 1, 2]:  # Peak Rabi (Wheat / Mustard watering)
                pumping_m = np.random.uniform(0.16, 0.24)  # meters/week
            elif month in [3, 4, 5]:      # Hot dry summer (domestic + orchards)
                pumping_m = np.random.uniform(0.06, 0.12)

            # 3. Natural baseflow recession (proportional to head above bedrock base)
            hydraulic_head = max(0.5, well_depth_m - current_depth)
            recession_m = hydraulic_head * 0.008

            # Water level update (positive delta = water table drops deeper)
            delta_depth = (recession_m + pumping_m) - recharge_m

            # Add minor manual tape measurement jitter (~1-2 cm)
            measurement_noise = np.random.normal(0, 0.015)
            current_depth = np.clip(current_depth + delta_depth, 2.5, well_depth_m - 1.0)

            observed_depth = round(float(current_depth + measurement_noise), 2)

            records.append({
                "date": dt,
                "well_id": well_id,
                "depth_to_water_m": observed_depth,
                "weekly_rain_mm": round(float(rain_week), 2),
                "weekly_temp_c": round(float(row["temp_mean_c"]), 1)
            })

        df_gwl = pd.DataFrame(records)
        df_gwl.to_csv(self.gwl_file, index=False)
        print(f"Generated {len(df_gwl)} weekly groundwater readings ({df_gwl['date'].min().strftime('%Y-%m-%d')} to {df_gwl['date'].max().strftime('%Y-%m-%d')}).")
        return df_gwl

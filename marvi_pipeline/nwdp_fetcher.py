"""NWDP (National Water Data Portal) and CGWB data ingestion module.

Ingests official Ministry of Jal Shakti / CGWB (Central Ground Water Board)
telemetry and periodic observation well datasets from https://nwdp.nwic.gov.in/.
"""
import os
import csv
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np
import requests
import urllib3

urllib3.disable_warnings()
logger = logging.getLogger(__name__)

# Direct NWDP Open Resource URLs
URL_CGWB_TELEMETRY_RJ = (
    "https://nwdp.nwic.gov.in/dataset/3782ba15-9b12-46a8-ae44-410b1f84020e/"
    "resource/467fe983-e1f0-4428-91b7-0ade87b39f6d/download/"
    "gwl_tel_6_hourly_cgwb_rj_2021_2025.csv"
)

URL_IMD_DISTRICT_DAILY = (
    "https://nwdp.nwic.gov.in/dataset/9380580f-9bf0-4708-9773-0cea3cbc595a/"
    "resource/8752174f-1d17-4aaf-8058-2eb396f50157/download/"
    "rainfall_districtwise_daily_imd.csv"
)


class NWDPFetcher:
    """Manages downloading, streaming extraction, and preprocessing of official Indian

    water datasets from the National Water Data Portal (NWDP / CGWB / IMD).
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.default_cgwb_raw = os.path.join(self.data_dir, "cgwb_udaipur_telemetry.csv")
        self.default_cgwb_weekly = os.path.join(self.data_dir, "cgwb_bhinder_weekly.csv")
        self.default_imd_raw = os.path.join(self.data_dir, "raw_imd_districtwise_daily.csv")

    def download_cgwb_district_telemetry(
        self,
        district: str = "UDAIPUR",
        output_csv: Optional[str] = None,
        force_refresh: bool = False,
        timeout: int = 120
    ) -> str:
        """Stream CGWB Rajasthan 6-hourly telemetry (131MB) from NWDP,

        filtering for the target district on-the-fly to keep local storage lightweight (~1MB).
        """
        target_path = output_csv or self.default_cgwb_raw
        if os.path.exists(target_path) and not force_refresh:
            print(f"[NWDP] Found existing cached CGWB telemetry at: {target_path}")
            return target_path

        print(f"[NWDP] Streaming CGWB Rajasthan Telemetry from NWDP for district: '{district}'...")
        r = requests.get(URL_CGWB_TELEMETRY_RJ, stream=True, verify=False, timeout=timeout)
        r.raise_for_status()

        match_count = 0
        header_written = False

        with open(target_path, "w", newline="", encoding="utf-8") as out_f:
            writer = csv.writer(out_f)
            header = None

            for chunk in r.iter_lines():
                if not chunk:
                    continue
                line = chunk.decode("utf-8", errors="ignore")

                if header is None:
                    header = line.split(",")
                    writer.writerow(header)
                    header_written = True
                    continue

                if district.upper() == "ALL" or district.upper() in line.upper():
                    writer.writerow(line.split(","))
                    match_count += 1

        print(f"[NWDP] Extracted {match_count:,} telemetry records for '{district}' -> {target_path}")
        return target_path

    def process_cgwb_to_weekly(
        self,
        raw_csv_path: Optional[str] = None,
        station_name: str = "Bhinder_Pz_1",
        output_weekly_csv: Optional[str] = None
    ) -> pd.DataFrame:
        """Standardize 6-hourly CGWB telemetry and aggregate to weekly Sundays.

        Converts negative depths (meters below ground level) to positive depths,
        smooths noise, and resamples to weekly intervals matching MARVI monitoring.
        """
        raw_path = raw_csv_path or self.default_cgwb_raw
        if not os.path.exists(raw_path):
            raise FileNotFoundError(f"Raw CGWB file not found at: {raw_path}. Run download first.")

        df = pd.read_csv(raw_path)

        # Standardize column names
        # Raw col: 'Groundwater Level Telemetry 6 Hourly (meter)', 'Data Acquisition Time'
        gwl_col = None
        for col in df.columns:
            if "groundwater level" in col.lower() or "telemetry" in col.lower():
                gwl_col = col
                break
        if gwl_col is None:
            gwl_col = df.columns[-1]

        time_col = "Data Acquisition Time" if "Data Acquisition Time" in df.columns else df.columns[19]

        # Filter by station if specified
        if station_name and "Station" in df.columns:
            st_df = df[df["Station"].str.strip().str.upper() == station_name.strip().upper()].copy()
            if st_df.empty:
                print(f"[NWDP] Station '{station_name}' not found, using all stations in district.")
                st_df = df.copy()
        else:
            st_df = df.copy()

        # Parse datetime
        st_df["timestamp"] = pd.to_datetime(
            st_df[time_col],
            format="%d-%m-%Y %H:%M",
            errors="coerce"
        )
        st_df = st_df.dropna(subset=["timestamp"]).copy()

        # Parse water depth (meters below ground level)
        # Raw CGWB values are typically negative, e.g. -13.86 m bgl
        st_df["gwl_raw"] = pd.to_numeric(st_df[gwl_col], errors="coerce")
        st_df = st_df.dropna(subset=["gwl_raw"]).copy()

        # Convert to positive depth to water
        st_df["depth_to_water_m"] = st_df["gwl_raw"].abs()

        # Remove physical sensor outliers (e.g. -999 or depths > 150m)
        st_df = st_df[(st_df["depth_to_water_m"] > 0.1) & (st_df["depth_to_water_m"] < 150.0)]

        st_df = st_df.sort_values("timestamp").reset_index(drop=True)
        st_df = st_df.set_index("timestamp")

        # Resample to weekly Sundays (matching MARVI weekly monitoring frequency)
        weekly = st_df.resample("W-SUN").agg(
            depth_to_water_m=("depth_to_water_m", "mean"),
            gwl_min_m=("depth_to_water_m", "min"),
            gwl_max_m=("depth_to_water_m", "max"),
            reading_count=("depth_to_water_m", "count")
        ).reset_index()

        weekly = weekly.rename(columns={"timestamp": "date"})
        weekly = weekly[weekly["reading_count"] > 0].copy()
        weekly["depth_to_water_m"] = weekly["depth_to_water_m"].round(2)

        # Smooth using strictly causal 3-week rolling average (zero lookahead)
        weekly["gwl_smooth_m"] = weekly["depth_to_water_m"].rolling(
            window=3, min_periods=1, center=False
        ).mean().round(2)

        # Add station metadata
        weekly["station"] = station_name
        weekly["source"] = "CGWB_NWDP_Telemetry"

        if output_weekly_csv is not False:
            out_path = output_weekly_csv or self.default_cgwb_weekly
            weekly.to_csv(out_path, index=False)
            print(f"[NWDP] Processed {len(weekly)} weekly records for '{station_name}' -> {out_path}")
        return weekly

    def download_imd_district_rainfall(
        self,
        output_csv: Optional[str] = None,
        force_refresh: bool = False
    ) -> str:
        """Download IMD district-wise daily rainfall from NWDP (~10MB)."""
        target_path = output_csv or self.default_imd_raw
        if os.path.exists(target_path) and not force_refresh:
            print(f"[NWDP] Found cached IMD rainfall at: {target_path}")
            return target_path

        print(f"[NWDP] Downloading official IMD District Rainfall from NWDP...")
        r = requests.get(URL_IMD_DISTRICT_DAILY, verify=False, timeout=60)
        r.raise_for_status()

        with open(target_path, "wb") as f:
            f.write(r.content)

        print(f"[NWDP] Successfully saved IMD dataset ({len(r.content):,} bytes) -> {target_path}")
        return target_path

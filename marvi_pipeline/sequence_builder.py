"""Sliding window sequence generator & dataset exporter for LSTM training."""
import os
import json
import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any
from sklearn.preprocessing import MinMaxScaler


class SequenceBuilder:
    """Constructs lookback input sequences and multi-step forecast targets."""

    DEFAULT_FEATURE_COLS = [
        "gwl_smooth_m",
        "weekly_rain_mm",
        "rain_4wk_sum_mm",
        "weekly_temp_c",
        "doy_sin",
        "doy_cos"
    ]

    def __init__(
        self,
        lookback_weeks: int = 8,
        horizon_60d_weeks: int = 8,
        horizon_90d_weeks: int = 12,
        data_dir: str = "data"
    ):
        self.lookback_weeks = lookback_weeks
        self.horizon_60d_weeks = horizon_60d_weeks
        self.horizon_90d_weeks = horizon_90d_weeks
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        self.feature_scaler = MinMaxScaler(feature_range=(0, 1))
        self.target_scaler_60d = MinMaxScaler(feature_range=(0, 1))
        self.target_scaler_90d = MinMaxScaler(feature_range=(0, 1))

    def build_dataset(
        self,
        df_features: pd.DataFrame,
        feature_cols: list = None,
        train_ratio: float = 0.75,
        save_filename: str = "dataset_dharta_lstm.npz"
    ) -> Dict[str, Any]:
        """Build normalized sliding window sequences with temporal train/test split."""
        if feature_cols is None:
            feature_cols = self.DEFAULT_FEATURE_COLS

        df = df_features.copy()
        df = df.sort_values("date").reset_index(drop=True)

        # Create future target columns (lead times)
        df["target_60d"] = df["gwl_smooth_m"].shift(-self.horizon_60d_weeks)
        df["target_90d"] = df["gwl_smooth_m"].shift(-self.horizon_90d_weeks)

        # Drop rows with NaN in targets at the end
        df_valid = df.dropna(subset=["target_60d", "target_90d"]).reset_index(drop=True)

        raw_X = df_valid[feature_cols].values
        raw_y_60d = df_valid[["target_60d"]].values
        raw_y_90d = df_valid[["target_90d"]].values
        dates = df_valid["date"].values

        # 1. Sliding Window Assembly
        X_seq, y_60d_seq, y_90d_seq, seq_dates = [], [], [], []

        for i in range(len(df_valid) - self.lookback_weeks + 1):
            x_window = raw_X[i : i + self.lookback_weeks]
            # Target is the value corresponding to the last step of the window
            target_idx = i + self.lookback_weeks - 1
            X_seq.append(x_window)
            y_60d_seq.append(raw_y_60d[target_idx])
            y_90d_seq.append(raw_y_90d[target_idx])
            seq_dates.append(str(dates[target_idx])[:10])

        X_arr = np.array(X_seq, dtype=np.float32)
        y_60d_arr = np.array(y_60d_seq, dtype=np.float32)
        y_90d_arr = np.array(y_90d_seq, dtype=np.float32)

        # 2. Strict Temporal Train/Test Split with Purge Gap (Zero Overlap Leakage)
        split_idx = int(len(X_arr) * train_ratio)
        # Purge gap prevents training targets (which look up to 90 days ahead)
        # from overlapping with the test set's input feature window.
        available_test = len(X_arr) - split_idx
        purge_gap = min(self.horizon_90d_weeks, max(0, available_test - 3))
        test_start_idx = split_idx + purge_gap

        X_train_raw = X_arr[:split_idx]
        X_test_raw = X_arr[test_start_idx:]

        y_train_60d_raw = y_60d_arr[:split_idx]
        y_test_60d_raw = y_60d_arr[test_start_idx:]

        y_train_90d_raw = y_90d_arr[:split_idx]
        y_test_90d_raw = y_90d_arr[test_start_idx:]

        # 3. Fit Scalers ONLY on Training Data (Zero Data Leakage)
        N_train, T_steps, D_feats = X_train_raw.shape
        N_test = X_test_raw.shape[0]

        # Reshape to 2D for scaler fitting
        X_train_2d = X_train_raw.reshape(-1, D_feats)
        X_test_2d = X_test_raw.reshape(-1, D_feats)

        self.feature_scaler.fit(X_train_2d)
        X_train_scaled = self.feature_scaler.transform(X_train_2d).reshape(N_train, T_steps, D_feats)
        X_test_scaled = self.feature_scaler.transform(X_test_2d).reshape(N_test, T_steps, D_feats)

        # Scale targets
        self.target_scaler_60d.fit(y_train_60d_raw)
        y_train_60d_scaled = self.target_scaler_60d.transform(y_train_60d_raw)
        y_test_60d_scaled = self.target_scaler_60d.transform(y_test_60d_raw)

        self.target_scaler_90d.fit(y_train_90d_raw)
        y_train_90d_scaled = self.target_scaler_90d.transform(y_train_90d_raw)
        y_test_90d_scaled = self.target_scaler_90d.transform(y_test_90d_raw)

        out_path = os.path.join(self.data_dir, save_filename)
        np.savez_compressed(
            out_path,
            X_train=X_train_scaled,
            X_test=X_test_scaled,
            y_train_60d=y_train_60d_scaled,
            y_test_60d=y_test_60d_scaled,
            y_train_90d=y_train_90d_scaled,
            y_test_90d=y_test_90d_scaled,
            y_train_60d_raw=y_train_60d_raw,
            y_test_60d_raw=y_test_60d_raw,
            y_train_90d_raw=y_train_90d_raw,
            y_test_90d_raw=y_test_90d_raw,
            feature_names=np.array(feature_cols),
            dates=np.array(seq_dates),
            split_idx=split_idx
        )

        meta = {
            "dataset_file": out_path,
            "total_sequences": len(X_arr),
            "train_sequences": N_train,
            "test_sequences": N_test,
            "lookback_weeks": self.lookback_weeks,
            "num_features": D_feats,
            "feature_names": feature_cols,
            "train_date_range": [seq_dates[0], seq_dates[split_idx - 1]],
            "test_date_range": [seq_dates[test_start_idx], seq_dates[-1]],
            "purge_gap_weeks": purge_gap,
            "targets": ["60_days_ahead (8 weeks)", "90_days_ahead (12 weeks)"]
        }

        meta_path = os.path.join(self.data_dir, "dataset_metadata.json")
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        print(f"Dataset compiled & saved to {out_path}.")
        return meta

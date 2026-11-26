"""Groundwater Extended Kalman Filter (EKF) engine for adaptive tracking & anomaly gating."""
import numpy as np
from typing import Tuple, Dict, Any, Optional
from datetime import datetime


class GroundwaterEKF:
    """Adaptive 2-State Extended Kalman Filter for well water level & velocity tracking.
    
    State vector x = [h, v]^T:
      h: True depth to water level (meters)
      v: Rate of change (meters/day). Positive = water dropping deeper; Negative = water rising.
    """

    COLD_TRAIL_THRESHOLD_DAYS = 45.0  # Beyond 45 days, speed extrapolation stops -> Re-anchor mode

    def __init__(self, initial_depth: float, measurement_noise_R: float = 0.04):
        # State: [depth, velocity]
        self.x = np.array([float(initial_depth), 0.05], dtype=float)

        # Initial estimation error covariance (uncertainty)
        self.P = np.array([
            [0.08, 0.0],
            [0.0, 0.01]
        ], dtype=float)

        # Measurement noise covariance R (manual buzzer-tape reading error ~2-3 cm)
        self.R = float(measurement_noise_R)

        # Base process noise covariance per day Q_base (natural aquifer volatility)
        self.Q_base = np.array([
            [0.008, 0.0005],
            [0.0005, 0.002]
        ], dtype=float)

        self.is_stale: bool = False
        self.last_timestamp: Optional[datetime] = None

    def predict(self, delta_days: float, rainfall_mm: float = 0.0) -> Tuple[float, float, bool]:
        """Predict forward by delta_days incorporating rainfall recharge.
        
        Returns:
            predicted_depth: float
            confidence_band_3sigma: float
            is_stale: bool (True if elapsed time > 45 days)
        """
        # 1. Cold Trail Check
        if delta_days > self.COLD_TRAIL_THRESHOLD_DAYS:
            self.is_stale = True
            # Return current position with wide bounds
            return float(self.x[0]), 99.0, True

        self.is_stale = False
        dt = max(delta_days, 1.0 / 24.0)  # at least 1 hour

        # 2. State Transition Matrix F
        F = np.array([
            [1.0, dt],
            [0.0, 1.0]
        ], dtype=float)

        # 3. Rainfall recharge effect (in hard rock, rain causes water table to rise: negative delta)
        # Empirical conversion: 100mm rain in hard rock typically yields ~0.3 - 0.5m water rise
        recharge_effect = - (float(rainfall_mm) * 0.001 * 3.5)

        # Extrapolate state
        self.x = F @ self.x
        self.x[0] += recharge_effect

        # Extrapolate covariance (uncertainty grows with dt)
        Q = self.Q_base * dt
        self.P = F @ self.P @ F.T + Q

        # 3-sigma confidence width for observation
        S = float(self.P[0, 0] + self.R)
        sigma_3 = 3.0 * np.sqrt(S)

        return float(self.x[0]), float(sigma_3), False

    def evaluate_measurement(self, measured_depth: float) -> Tuple[float, float, float, bool]:
        """Calculates Mahalanobis distance (Z-score) of the measurement against the EKF prediction.
        
        Returns:
            z_score: float (Mahalanobis distance)
            predicted_depth: float
            confidence_3sigma: float
            is_stale: bool
        """
        predicted_depth = float(self.x[0])
        
        if self.is_stale:
            return 0.0, predicted_depth, 99.0, True

        residual = measured_depth - predicted_depth
        S = float(self.P[0, 0] + self.R)
        z_score = abs(residual) / np.sqrt(S)
        sigma_3 = 3.0 * np.sqrt(S)

        return float(z_score), predicted_depth, float(sigma_3), False

    def apply_update(self, measured_depth: float):
        """Update the EKF state with the verified measurement."""
        if self.is_stale:
            self.reanchor(measured_depth)
            return

        H = np.array([1.0, 0.0], dtype=float)
        residual = measured_depth - self.x[0]
        S = float(H @ self.P @ H.T + self.R)

        # Kalman Gain K
        K = (self.P @ H.T) / S

        # State and Covariance Update
        self.x = self.x + K * residual
        self.P = (np.eye(2) - np.outer(K, H)) @ self.P

    def reanchor(self, new_depth: float):
        """Reset the EKF with a fresh anchor point after a long time gap."""
        self.x = np.array([float(new_depth), 0.05], dtype=float)
        self.P = np.array([
            [0.08, 0.0],
            [0.0, 0.01]
        ], dtype=float)
        self.is_stale = False

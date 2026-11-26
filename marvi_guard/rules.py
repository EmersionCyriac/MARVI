"""Validation rules for the 3-layer Smart Data Guard with Extended Kalman Filter (EKF)."""
import math
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
import numpy as np

from .models import (
    WellMetadata,
    WaterReading,
    HistoricalRecord,
    ValidationStatus,
    FlagDetail,
    GuardResult,
)
from .ekf import GroundwaterEKF


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in kilometers."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class PhysicalBoundaryRule:
    """Layer 1: Validates that the reading obeys physical boundaries of the well."""

    @staticmethod
    def evaluate(reading: WaterReading, well: WellMetadata) -> Tuple[bool, Optional[FlagDetail], Optional[float]]:
        depth = reading.depth_to_water_meters

        # Check for negative depth
        if depth < 0:
            return False, FlagDetail(
                code="ERR_NEGATIVE_DEPTH",
                message=f"Negative depth ({depth}m) is physically impossible.",
                severity="ERROR"
            ), None

        # Check for depth exceeding the bottom of the well
        if depth > well.total_depth_meters:
            # Check if this could be a missing decimal point (e.g. typed 25.0 instead of 2.5)
            suggested = None
            if 0 < (depth / 10.0) <= well.total_depth_meters:
                suggested = round(depth / 10.0, 2)
            elif 0 < (depth / 100.0) <= well.total_depth_meters:
                suggested = round(depth / 100.0, 2)

            msg = (f"Reading ({depth}m) exceeds the well's physical depth "
                   f"({well.total_depth_meters}m).")
            if suggested is not None:
                msg += f" Did you mean {suggested}m?"

            return False, FlagDetail(
                code="ERR_EXCEEDS_WELL_DEPTH",
                message=msg,
                severity="ERROR"
            ), suggested

        return True, None, None


class EKFTemporalConsistencyRule:
    """Layer 2: Adaptive Extended Kalman Filter tracking depth and velocity over time."""

    @classmethod
    def evaluate(
        cls,
        reading: WaterReading,
        well: WellMetadata,
        ekf: GroundwaterEKF,
        last_timestamp: Optional[datetime]
    ) -> Tuple[List[FlagDetail], Dict[str, Any]]:
        flags: List[FlagDetail] = []
        telemetry: Dict[str, Any] = {
            "z_score": 0.0,
            "predicted_depth": float(ekf.x[0]),
            "velocity": float(ekf.x[1]),
            "confidence_band": 0.0,
            "is_reanchored": False
        }

        if last_timestamp is None:
            # First observation ever: initialize/reanchor
            ekf.reanchor(reading.depth_to_water_meters)
            telemetry["is_reanchored"] = True
            return flags, telemetry

        delta_days = (reading.timestamp - last_timestamp).total_seconds() / 86400.0

        # Step 1: EKF Predict step
        pred_depth, sigma_3, is_stale = ekf.predict(
            delta_days=delta_days,
            rainfall_mm=reading.recent_rainfall_mm
        )
        telemetry["predicted_depth"] = round(pred_depth, 2)
        telemetry["confidence_band"] = round(sigma_3, 2)

        # Step 2: Handle Multi-Month Gap (Cold Trail)
        if is_stale:
            telemetry["is_reanchored"] = True
            flags.append(FlagDetail(
                code="INFO_COLD_TRAIL_REANCHOR",
                message=(f"Time gap since last reading is {delta_days:.0f} days (>45 days). "
                         f"EKF velocity extrapolation paused. Re-anchoring well with current reading."),
                severity="WARNING"
            ))
            return flags, telemetry

        # Step 3: Evaluate Measurement Mahalanobis Distance (Z-Score)
        z_score, pred_d, conf_3, _ = ekf.evaluate_measurement(reading.depth_to_water_meters)
        telemetry["z_score"] = round(z_score, 2)
        telemetry["velocity"] = round(float(ekf.x[1]), 3)

        # Case A: Active Pump Reported Running
        if reading.is_pump_running:
            flags.append(FlagDetail(
                code="WARN_PUMP_ACTIVE_DRAWDOWN",
                message=(f"Pump is reported RUNNING during measurement (depth {reading.depth_to_water_meters}m). "
                         f"Reading reflects localized suction drawdown cone, not the regional static water table. "
                         f"Remeasure 4–6 hours after pump shutdown."),
                severity="WARNING"
            ))
        elif z_score > 3.5:
            # Case B: Severe Statistical Velocity Violation
            flags.append(FlagDetail(
                code="WARN_EKF_VELOCITY_VIOLATION",
                message=(f"Reading ({reading.depth_to_water_meters}m) is {z_score:.1f}σ away from EKF expected "
                         f"level ({pred_depth:.2f}m ± {sigma_3:.2f}m). Drop/rise rate exceeds physical velocity."),
                severity="WARNING"
            ))
        elif z_score > 2.0:
            # Case C: Moderate Statistical Deviation
            flags.append(FlagDetail(
                code="WARN_EKF_STATISTICAL_DEVIATION",
                message=(f"Reading ({reading.depth_to_water_meters}m) deviates moderately ({z_score:.1f}σ) from "
                         f"predicted {pred_depth:.2f}m. Possible unrecorded pumping or irrigation runoff."),
                severity="WARNING"
            ))

        return flags, telemetry


class SpatialNeighborhoodRule:
    """Layer 3: Cross-checks reading against nearby wells in the same aquifer cluster."""

    MAX_NEIGHBOR_RADIUS_KM = 2.0  # Search within 2km radius
    MAX_NEIGHBOR_TIME_WINDOW_DAYS = 14  # Neighbor readings taken within 14 days
    OUTLIER_DEVIATION_METERS = 3.5  # In hard-rock, wells within 1km usually follow similar water table elevation

    @classmethod
    def evaluate(
        cls,
        reading: WaterReading,
        well: WellMetadata,
        all_wells: List[WellMetadata],
        all_latest_readings: List[WaterReading]
    ) -> List[FlagDetail]:
        flags: List[FlagDetail] = []

        # Find neighboring wells within radius
        well_dict = {w.well_id: w for w in all_wells}
        neighbor_depths = []

        for other_reading in all_latest_readings:
            if other_reading.well_id == well.well_id:
                continue

            other_well = well_dict.get(other_reading.well_id)
            if not other_well:
                continue

            dist = haversine_distance_km(
                well.latitude, well.longitude,
                other_well.latitude, other_well.longitude
            )

            # Check time proximity
            time_diff = abs((reading.timestamp - other_reading.timestamp).total_seconds()) / 86400.0

            if dist <= cls.MAX_NEIGHBOR_RADIUS_KM and time_diff <= cls.MAX_NEIGHBOR_TIME_WINDOW_DAYS:
                neighbor_depths.append(other_reading.depth_to_water_meters)

        if len(neighbor_depths) >= 2:
            median_neighbor = float(np.median(neighbor_depths))
            diff = abs(reading.depth_to_water_meters - median_neighbor)

            if diff > cls.OUTLIER_DEVIATION_METERS:
                flags.append(FlagDetail(
                    code="WARN_SPATIAL_OUTLIER",
                    message=(f"Reading ({reading.depth_to_water_meters}m) deviates by {diff:.2f}m "
                             f"from the neighborhood median ({median_neighbor:.2f}m across {len(neighbor_depths)} wells). "
                             f"Possible local pumping effect or reading typo."),
                    severity="WARNING"
                ))

        return flags

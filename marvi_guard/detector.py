"""SmartDataGuard: Orchestrator for 3-layer anomaly detection with EKF."""
from typing import List, Dict, Optional
from datetime import datetime

from .models import (
    WellMetadata,
    WaterReading,
    HistoricalRecord,
    ValidationStatus,
    GuardResult,
    FlagDetail
)
from .ekf import GroundwaterEKF
from .rules import (
    PhysicalBoundaryRule,
    EKFTemporalConsistencyRule,
    SpatialNeighborhoodRule,
)


class SmartDataGuard:
    """The MARVI Smart Data Guard validation engine with Adaptive EKF."""

    def __init__(self, wells: Optional[List[WellMetadata]] = None):
        wells_list = wells or []
        self.wells_registry: Dict[str, WellMetadata] = {w.well_id: w for w in wells_list}
        self.history_store: Dict[str, List[HistoricalRecord]] = {w.well_id: [] for w in wells_list}
        self.latest_readings_store: Dict[str, WaterReading] = {}
        # One EKF instance per well
        self.ekf_store: Dict[str, GroundwaterEKF] = {
            w.well_id: GroundwaterEKF(initial_depth=w.total_depth_meters * 0.25)
            for w in wells_list
        }

    def register_well(self, well: WellMetadata):
        """Add a new well to the metadata registry."""
        self.wells_registry[well.well_id] = well
        if well.well_id not in self.history_store:
            self.history_store[well.well_id] = []
        if well.well_id not in self.ekf_store:
            self.ekf_store[well.well_id] = GroundwaterEKF(initial_depth=well.total_depth_meters * 0.25)

    def seed_history(self, well_id: str, records: List[HistoricalRecord]):
        """Seed past verified records for a well and train the EKF."""
        if well_id not in self.history_store:
            return

        self.history_store[well_id].extend(records)
        self.history_store[well_id].sort(key=lambda r: r.timestamp)

        if records:
            ekf = self.ekf_store[well_id]
            # Initialize with first record
            ekf.reanchor(records[0].depth_to_water_meters)
            last_t = records[0].timestamp

            # Replay history through EKF to establish realistic velocity and covariance
            for rec in records[1:]:
                dt = (rec.timestamp - last_t).total_seconds() / 86400.0
                ekf.predict(delta_days=dt, rainfall_mm=rec.rainfall_mm)
                ekf.apply_update(rec.depth_to_water_meters)
                last_t = rec.timestamp

            latest = records[-1]
            self.latest_readings_store[well_id] = WaterReading(
                well_id=well_id,
                timestamp=latest.timestamp,
                depth_to_water_meters=latest.depth_to_water_meters,
                measured_by="historical_seed"
            )

    def evaluate_reading(self, reading: WaterReading) -> GuardResult:
        """Run an incoming water level observation through the 3-layer guard."""
        well = self.wells_registry.get(reading.well_id)
        if not well:
            return GuardResult(
                reading=reading,
                status=ValidationStatus.REJECTED,
                flags=[FlagDetail(
                    code="ERR_UNKNOWN_WELL",
                    message=f"Well ID '{reading.well_id}' is not registered in the system.",
                    severity="ERROR"
                )],
                explanation=f"Rejection: Well '{reading.well_id}' does not exist in registry."
            )

        all_flags: List[FlagDetail] = []

        # ============================================================
        # LAYER 1: Physical Boundary & Typo Check
        # ============================================================
        is_valid_phys, phys_flag, suggested_correction = PhysicalBoundaryRule.evaluate(reading, well)
        if not is_valid_phys and phys_flag:
            all_flags.append(phys_flag)
            explanation = f"REJECTED at Layer 1 (Physical Boundary): {phys_flag.message}"
            return GuardResult(
                reading=reading,
                status=ValidationStatus.REJECTED,
                flags=all_flags,
                suggested_correction=suggested_correction,
                explanation=explanation
            )

        # ============================================================
        # LAYER 2: EKF Temporal Consistency & Velocity Check
        # ============================================================
        ekf = self.ekf_store[reading.well_id]
        well_history = self.history_store.get(reading.well_id, [])
        last_timestamp = well_history[-1].timestamp if well_history else None

        temporal_flags, telemetry = EKFTemporalConsistencyRule.evaluate(
            reading=reading,
            well=well,
            ekf=ekf,
            last_timestamp=last_timestamp
        )
        all_flags.extend(temporal_flags)

        # ============================================================
        # LAYER 3: Spatial Neighborhood Consistency Check
        # ============================================================
        spatial_flags = SpatialNeighborhoodRule.evaluate(
            reading=reading,
            well=well,
            all_wells=list(self.wells_registry.values()),
            all_latest_readings=list(self.latest_readings_store.values())
        )
        all_flags.extend(spatial_flags)

        # ============================================================
        # Status Synthesis
        # ============================================================
        if any(f.severity == "ERROR" for f in all_flags):
            status = ValidationStatus.REJECTED
            explanation = "REJECTED: Reading violates critical physical constraints."
        elif all_flags:
            status = ValidationStatus.FLAGGED
            reasons = "; ".join(f.message for f in all_flags)
            explanation = f"FLAGGED FOR REVIEW: {reasons}"
        else:
            status = ValidationStatus.ACCEPTED
            explanation = "ACCEPTED: Reading verified through Physical, EKF, and Spatial layers."

        # If accepted or flagged (soft warning), update EKF state and caches
        if status in (ValidationStatus.ACCEPTED, ValidationStatus.FLAGGED):
            ekf.apply_update(reading.depth_to_water_meters)
            self.latest_readings_store[reading.well_id] = reading
            self.history_store[reading.well_id].append(
                HistoricalRecord(
                    timestamp=reading.timestamp,
                    depth_to_water_meters=reading.depth_to_water_meters,
                    rainfall_mm=reading.recent_rainfall_mm
                )
            )

        return GuardResult(
            reading=reading,
            status=status,
            flags=all_flags,
            suggested_correction=suggested_correction,
            explanation=explanation,
            ekf_z_score=telemetry.get("z_score"),
            ekf_predicted_depth=telemetry.get("predicted_depth"),
            ekf_velocity_m_per_day=telemetry.get("velocity"),
            ekf_confidence_band=telemetry.get("confidence_band"),
            is_reanchored=telemetry.get("is_reanchored", False)
        )


# Alias for backward compatibility / intuitive naming
AnomalyDetector = SmartDataGuard

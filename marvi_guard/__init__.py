"""MARVI Smart Data Guard package with Extended Kalman Filter (EKF)."""
from .models import (
    WellMetadata,
    WaterReading,
    ValidationStatus,
    GuardResult,
    FlagDetail,
    AquiferType,
)
from .ekf import GroundwaterEKF
from .detector import SmartDataGuard, AnomalyDetector
from .rules import (
    PhysicalBoundaryRule,
    EKFTemporalConsistencyRule,
    SpatialNeighborhoodRule,
)

__all__ = [
    "WellMetadata",
    "WaterReading",
    "ValidationStatus",
    "GuardResult",
    "FlagDetail",
    "AquiferType",
    "GroundwaterEKF",
    "SmartDataGuard",
    "PhysicalBoundaryRule",
    "EKFTemporalConsistencyRule",
    "SpatialNeighborhoodRule",
]

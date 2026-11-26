"""Data models for MARVI Smart Data Guard."""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class ValidationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"       # Clean reading, passes all filters
    FLAGGED = "FLAGGED"         # Suspicious reading (e.g. running pump, neighbor discrepancy)
    REJECTED = "REJECTED"       # Impossible reading (e.g. exceeds well bottom, negative depth)


class AquiferType(str, Enum):
    HARD_ROCK_FRACTURED = "HARD_ROCK_FRACTURED"  # Basalt, granite, gneiss (Rajasthan/Gujarat)
    ALLUVIAL = "ALLUVIAL"                        # Gangetic plains, loose sands


class WellMetadata(BaseModel):
    """Static and physical metadata of a registered monitoring well."""
    well_id: str = Field(..., description="Unique well identifier (e.g., RJ-UDA-DHT-01)")
    name: str = Field(..., description="Local name or owner name (e.g., Ramesh Patel Well)")
    village: str = Field(..., description="Village or watershed name")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    total_depth_meters: float = Field(..., gt=0.0, description="Total physical depth drilled/dug to bed rock")
    diameter_meters: Optional[float] = Field(None, gt=0.0)
    aquifer_type: AquiferType = Field(default=AquiferType.HARD_ROCK_FRACTURED)
    has_motor_pump: bool = Field(default=True, description="Whether a diesel/electric pump is installed on this well")


class WaterReading(BaseModel):
    """An incoming crowdsourced water level observation."""
    well_id: str
    timestamp: datetime
    depth_to_water_meters: float = Field(..., description="Depth measured from ground/parapet level down to water surface")
    measured_by: str = Field(..., description="Name or ID of the Bhujal Jankaar / volunteer")
    is_pump_running: Optional[bool] = Field(default=None, description="Self-reported pump status at time of measurement")
    recent_rainfall_mm: float = Field(default=0.0, description="Cumulative rainfall (mm) since previous reading")
    notes: Optional[str] = None


class HistoricalRecord(BaseModel):
    """Historical record for temporal rate-of-change comparison."""
    timestamp: datetime
    depth_to_water_meters: float
    rainfall_mm: float = 0.0


class FlagDetail(BaseModel):
    code: str
    message: str
    severity: str  # "ERROR" for rejection, "WARNING" for flag


class GuardResult(BaseModel):
    """Result of passing a reading through the 3-layer Smart Data Guard with EKF telemetry."""
    reading: WaterReading
    status: ValidationStatus
    flags: List[FlagDetail] = Field(default_factory=list)
    suggested_correction: Optional[float] = None
    explanation: str
    
    # EKF Telemetry
    ekf_z_score: Optional[float] = None
    ekf_predicted_depth: Optional[float] = None
    ekf_velocity_m_per_day: Optional[float] = None
    ekf_confidence_band: Optional[float] = None
    is_reanchored: bool = False

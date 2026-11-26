"""Pydantic schemas and data models for Village Agronomic Advisory Layer."""
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class CropType(str, Enum):
    WHEAT = "Wheat (Gehun)"
    MUSTARD = "Mustard (Sarson)"
    CHICKPEA = "Chickpea / Gram (Chana)"
    FALLOW = "Fallow / Fodder (Pashu Aahar)"


class AdvisoryStatus(str, Enum):
    SAFE_GREEN = "GREEN"      # Sufficient water for full Wheat cultivation
    CAUTION_AMBER = "AMBER"    # Moderate water: Recommend Mustard or 50/50 Split
    CRITICAL_RED = "RED"       # Severe drought risk: Avoid Wheat entirely


class CropSpec(BaseModel):
    """Agronomic specifications for common Rabi crops in Rajasthan."""
    crop_type: CropType
    water_req_mm: float = Field(..., description="Total seasonal evapotranspiration/water need in mm")
    water_req_m3_per_bigha: float = Field(..., description="Water volume needed per bigha (1 ha = 4 bighas)")
    irrigations_needed: int = Field(..., description="Number of critical irrigations required")
    input_cost_inr_per_bigha: float = Field(..., description="Cost of seeds, fertilizer, power per bigha")
    expected_gross_inr_per_bigha: float = Field(..., description="Expected gross harvest income per bigha")
    drought_tolerance: str = Field(..., description="Qualitative drought resilience rating")


# Official ICAR / Rajasthan Agriculture Department Crop Benchmarks
DEFAULT_CROP_SPECS: Dict[CropType, CropSpec] = {
    CropType.WHEAT: CropSpec(
        crop_type=CropType.WHEAT,
        water_req_mm=450.0,
        water_req_m3_per_bigha=1125.0,  # 4,500 m3/ha / 4
        irrigations_needed=5,
        input_cost_inr_per_bigha=7000.0,
        expected_gross_inr_per_bigha=18500.0,
        drought_tolerance="LOW (Sensitive at flowering/milking)"
    ),
    CropType.MUSTARD: CropSpec(
        crop_type=CropType.MUSTARD,
        water_req_mm=240.0,
        water_req_m3_per_bigha=600.0,   # 2,400 m3/ha / 4
        irrigations_needed=3,
        input_cost_inr_per_bigha=4500.0,
        expected_gross_inr_per_bigha=14500.0,
        drought_tolerance="HIGH (Deep taproot, low moisture demand)"
    ),
    CropType.CHICKPEA: CropSpec(
        crop_type=CropType.CHICKPEA,
        water_req_mm=180.0,
        water_req_m3_per_bigha=450.0,   # 1,800 m3/ha / 4
        irrigations_needed=2,
        input_cost_inr_per_bigha=3500.0,
        expected_gross_inr_per_bigha=12000.0,
        drought_tolerance="VERY HIGH (Legume, enriches soil nitrogen)"
    )
}


class WellDimensions(BaseModel):
    """Physical geometry of a farmer's open dug well or tube well."""
    well_id: str = "RJ-DHT-01"
    farmer_name: str = "Ramesh Patel"
    village: str = "Dharta"
    total_depth_m: float = Field(18.0, description="Total depth of well from surface in meters")
    radius_m: float = Field(2.0, description="Well radius in meters (typical dug well r=1.5-2.5m)")
    pump_clearance_buffer_m: float = Field(
        1.5, description="Minimum water column needed at bottom to avoid pump sucking air/burning"
    )
    farm_area_bighas: float = Field(4.0, description="Total cultivable farm area in bighas (1 ha = 4 bighas)")


class CropPlan(BaseModel):
    """Recommended land allocation for a crop."""
    crop_type: CropType
    allocated_bighas: float
    percentage_of_farm: float
    total_water_needed_m3: float
    expected_net_income_inr: Optional[float] = None


class AdvisoryReport(BaseModel):
    """Complete agronomic advice report generated from AI forecasts."""
    well_id: str
    farmer_name: str
    village: str
    forecast_anchor_date: str
    current_water_depth_m: float
    pred_60d_depth_m: float
    pred_90d_depth_m: float
    true_60d_depth_m: Optional[float] = None
    true_90d_depth_m: Optional[float] = None
    error_60d_m: Optional[float] = None
    error_90d_m: Optional[float] = None
    remaining_water_column_90d_m: float
    usable_water_storage_m3: float
    usable_water_storage_litres: float
    status: AdvisoryStatus
    status_headline: str
    primary_recommendation: str
    crop_allocations: List[CropPlan]
    expected_total_net_inr: Optional[float] = None
    downside_risk_warning: Optional[str] = None
    water_saving_tips: List[str]

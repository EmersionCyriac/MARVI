"""Agronomic Advisory Engine for Village Groundwater Management.

Translates AI groundwater forecasts (60-day and 90-day lead times) into
actionable, traffic-light crop planning advice (Wheat vs. Mustard vs. Chickpea)
based on physical well geometry, crop water budgets, and economic risk.
"""
import math
from typing import Dict, List, Optional
import numpy as np

from .models import (
    CropType,
    CropSpec,
    AdvisoryStatus,
    WellDimensions,
    CropPlan,
    AdvisoryReport,
    DEFAULT_CROP_SPECS
)


class AgronomicAdvisor:
    """Evaluates water security and recommends optimal crop allocations."""

    def __init__(self, crop_specs: Optional[Dict[CropType, CropSpec]] = None):
        self.crop_specs = crop_specs or DEFAULT_CROP_SPECS

    def generate_advisory(
        self,
        well: WellDimensions,
        current_water_depth_m: float,
        pred_60d_depth_m: float,
        pred_90d_depth_m: float,
        true_60d_depth_m: Optional[float] = None,
        true_90d_depth_m: Optional[float] = None,
        anchor_date: str = "2024-10-15"
    ) -> AdvisoryReport:
        """Generate comprehensive agronomic advice based on predicted 90-day water table."""
        # 1. Hydrogeological Water Column Math
        err_60d = round(pred_60d_depth_m - true_60d_depth_m, 2) if true_60d_depth_m is not None else None
        err_90d = round(pred_90d_depth_m - true_90d_depth_m, 2) if true_90d_depth_m is not None else None

        # Depth is measured from surface downwards.
        # Remaining water column = Total Well Depth - Predicted Depth
        raw_water_column_90d = max(0.0, well.total_depth_m - pred_90d_depth_m)
        usable_column_90d = max(0.0, raw_water_column_90d - well.pump_clearance_buffer_m)

        # Well storage volume V = pi * r^2 * h (m^3)
        well_cross_section_m2 = math.pi * (well.radius_m ** 2)
        usable_storage_m3 = round(well_cross_section_m2 * usable_column_90d, 1)
        usable_storage_litres = round(usable_storage_m3 * 1000.0, 0)

        # 2. Traffic-Light Classification (Green / Amber / Red)
        # Wheat needs 5-6 irrigations (safe threshold >= 4.5m remaining column)
        # Mustard needs 2-3 irrigations (safe threshold >= 2.5m remaining column)
        if raw_water_column_90d >= 4.5:
            status = AdvisoryStatus.SAFE_GREEN
            headline = "🟢 HIGH WATER SECURITY: Safe for Wheat Cultivation"
            primary_rec = (
                "Aquifer storage is robust. You can safely cultivate high-value Wheat "
                "on up to 75% of your farm, paired with Mustard on 25% for price diversification."
            )
            # Allocation: 75% Wheat, 25% Mustard
            wheat_bighas = round(well.farm_area_bighas * 0.75, 1)
            mustard_bighas = round(well.farm_area_bighas * 0.25, 1)
            chickpea_bighas = 0.0

            risk_warning = None
            tips = [
                "Schedule the 1st Crown Root Irrigation (CRI) exactly 21 days after sowing.",
                "Adopt nighttime furrow irrigation to eliminate daytime solar evaporation.",
                "Ensure soil is laser-leveled to achieve 20% water savings across the field."
            ]

        elif raw_water_column_90d >= 2.5:
            status = AdvisoryStatus.CAUTION_AMBER
            headline = "🟡 MODERATE WATER SECURITY: Caution! Switch to Mustard / Gram"
            primary_rec = (
                "Water table is declining. Planting full Wheat carries high risk of the well "
                "drying up in February during flowering. Recommend planting 80% Mustard and 20% Chickpea."
            )
            # Allocation: 80% Mustard, 20% Chickpea (Zero Wheat)
            wheat_bighas = 0.0
            mustard_bighas = round(well.farm_area_bighas * 0.80, 1)
            chickpea_bighas = round(well.farm_area_bighas * 0.20, 1)

            wheat_spec = self.crop_specs[CropType.WHEAT]
            potential_loss = well.farm_area_bighas * wheat_spec.input_cost_inr_per_bigha
            risk_warning = (
                f"WARNING: If you plant Wheat and water runs dry in February, "
                f"you risk losing up to ₹{potential_loss:,.0f} in wasted seed, fertilizer, and electricity."
            )
            tips = [
                "Mustard requires only 2 to 3 light waterings; apply 1st irrigation at flowering.",
                "Use mulching with crop residue to trap residual soil moisture.",
                "Check neighboring tube wells before pumping to avoid concurrent suction drawdowns."
            ]

        else:
            status = AdvisoryStatus.CRITICAL_RED
            headline = "🔴 CRITICAL DROUGHT RISK: High Probability of Well Exhaustion"
            primary_rec = (
                "CRITICAL ALERT: Predicted water table will fall near the bottom of your well. "
                "Do NOT plant Wheat. Plant drought-hardy Chickpea / Fodder or leave part fallow to preserve drinking water."
            )
            # Allocation: 50% Chickpea, 50% Fallow/Fodder
            wheat_bighas = 0.0
            mustard_bighas = 0.0
            chickpea_bighas = round(well.farm_area_bighas * 0.50, 1)

            risk_warning = (
                "SEVERE RISK: Well water column is under 2.5m. The pump will suck air and may burn out. "
                "Priority must be given to household livestock and drinking security."
            )
            tips = [
                "Apply for PMKSY drip irrigation subsidy immediately (up to 70% government grant).",
                "Construct a farm bund or check-dam recharge pit near the well for next monsoon.",
                "Consult local Bhujal Jankaar (BJ) for communal aquifer sharing arrangements."
            ]

        # 3. Calculate Land Allocations & Financial Returns
        crop_plans: List[CropPlan] = []
        total_net_inr = 0.0

        allocations = [
            (CropType.WHEAT, wheat_bighas),
            (CropType.MUSTARD, mustard_bighas),
            (CropType.CHICKPEA, chickpea_bighas)
        ]

        # If some land is unallocated (e.g. Red status fallow), add fallow plan
        allocated_sum = sum(b for _, b in allocations)
        fallow_bighas = round(max(0.0, well.farm_area_bighas - allocated_sum), 1)

        for crop_t, bighas in allocations:
            if bighas > 0:
                spec = self.crop_specs[crop_t]
                water_vol = bighas * spec.water_req_m3_per_bigha
                net_per_bigha = spec.expected_gross_inr_per_bigha - spec.input_cost_inr_per_bigha
                net_total = bighas * net_per_bigha
                total_net_inr += net_total

                crop_plans.append(CropPlan(
                    crop_type=crop_t,
                    allocated_bighas=bighas,
                    percentage_of_farm=round((bighas / well.farm_area_bighas) * 100.0, 1),
                    total_water_needed_m3=round(water_vol, 1),
                    expected_net_income_inr=round(net_total, 0)
                ))

        if fallow_bighas > 0:
            crop_plans.append(CropPlan(
                crop_type=CropType.FALLOW,
                allocated_bighas=fallow_bighas,
                percentage_of_farm=round((fallow_bighas / well.farm_area_bighas) * 100.0, 1),
                total_water_needed_m3=0.0,
                expected_net_income_inr=0.0
            ))

        return AdvisoryReport(
            well_id=well.well_id,
            farmer_name=well.farmer_name,
            village=well.village,
            forecast_anchor_date=anchor_date,
            current_water_depth_m=round(current_water_depth_m, 2),
            pred_60d_depth_m=round(pred_60d_depth_m, 2),
            pred_90d_depth_m=round(pred_90d_depth_m, 2),
            true_60d_depth_m=round(true_60d_depth_m, 2) if true_60d_depth_m is not None else None,
            true_90d_depth_m=round(true_90d_depth_m, 2) if true_90d_depth_m is not None else None,
            error_60d_m=err_60d,
            error_90d_m=err_90d,
            remaining_water_column_90d_m=round(raw_water_column_90d, 2),
            usable_water_storage_m3=usable_storage_m3,
            usable_water_storage_litres=usable_storage_litres,
            status=status,
            status_headline=headline,
            primary_recommendation=primary_rec,
            crop_allocations=crop_plans,
            expected_total_net_inr=round(total_net_inr, 0),
            downside_risk_warning=risk_warning,
            water_saving_tips=tips
        )

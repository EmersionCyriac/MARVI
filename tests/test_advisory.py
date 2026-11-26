"""Unit tests for MARVI Agronomic Advisory Engine."""
import pytest
import math
from marvi_advisory.models import (
    CropType,
    AdvisoryStatus,
    WellDimensions,
    DEFAULT_CROP_SPECS
)
from marvi_advisory.advisor import AgronomicAdvisor


@pytest.fixture
def standard_well():
    return WellDimensions(
        well_id="TEST-WELL-01",
        farmer_name="Suresh Meena",
        village="Dharta",
        total_depth_m=18.0,
        radius_m=2.0,
        pump_clearance_buffer_m=1.5,
        farm_area_bighas=4.0
    )


def test_green_status_wheat_allocation(standard_well):
    advisor = AgronomicAdvisor()
    # 18.0m total depth - 12.5m predicted depth = 5.5m remaining column (>= 4.5m -> GREEN)
    report = advisor.generate_advisory(
        well=standard_well,
        current_water_depth_m=6.5,
        pred_60d_depth_m=11.0,
        pred_90d_depth_m=12.5,
        anchor_date="2024-10-15"
    )

    assert report.status == AdvisoryStatus.SAFE_GREEN
    assert "HIGH WATER SECURITY" in report.status_headline
    assert report.remaining_water_column_90d_m == 5.5
    # Check that Wheat is included
    crop_names = [c.crop_type for c in report.crop_allocations]
    assert CropType.WHEAT in crop_names
    assert report.expected_total_net_inr > 35000.0


def test_amber_status_mustard_warning(standard_well):
    advisor = AgronomicAdvisor()
    # 18.0m total depth - 14.8m predicted depth = 3.2m remaining column (between 2.5m and 4.5m -> AMBER)
    report = advisor.generate_advisory(
        well=standard_well,
        current_water_depth_m=10.0,
        pred_60d_depth_m=13.5,
        pred_90d_depth_m=14.8,
        anchor_date="2024-10-15"
    )

    assert report.status == AdvisoryStatus.CAUTION_AMBER
    assert "MODERATE WATER SECURITY" in report.status_headline
    # Wheat should NOT be recommended
    crop_names = [c.crop_type for c in report.crop_allocations]
    assert CropType.WHEAT not in crop_names
    assert CropType.MUSTARD in crop_names
    # Downside financial risk warning must be present
    assert report.downside_risk_warning is not None
    assert "₹" in report.downside_risk_warning


def test_red_status_drought_alert(standard_well):
    advisor = AgronomicAdvisor()
    # 18.0m total depth - 16.5m predicted depth = 1.5m remaining column (< 2.5m -> RED)
    report = advisor.generate_advisory(
        well=standard_well,
        current_water_depth_m=13.0,
        pred_60d_depth_m=15.5,
        pred_90d_depth_m=16.5,
        anchor_date="2024-10-15"
    )

    assert report.status == AdvisoryStatus.CRITICAL_RED
    assert "CRITICAL DROUGHT RISK" in report.status_headline
    assert report.remaining_water_column_90d_m == 1.5
    # Usable column above 1.5m clearance should be 0.0m
    assert report.usable_water_storage_m3 == 0.0
    # Wheat and Mustard should NOT be planted
    crop_names = [c.crop_type for c in report.crop_allocations]
    assert CropType.WHEAT not in crop_names
    assert CropType.MUSTARD not in crop_names
    assert CropType.CHICKPEA in crop_names
    assert CropType.FALLOW in crop_names


def test_well_storage_volume_geometry(standard_well):
    advisor = AgronomicAdvisor()
    pred_depth = 12.0
    report = advisor.generate_advisory(
        well=standard_well,
        current_water_depth_m=7.0,
        pred_60d_depth_m=10.0,
        pred_90d_depth_m=pred_depth
    )

    raw_column = 18.0 - pred_depth  # 6.0m
    usable_column = raw_column - standard_well.pump_clearance_buffer_m  # 6.0 - 1.5 = 4.5m
    expected_vol = math.pi * (standard_well.radius_m ** 2) * usable_column

    assert pytest.approx(report.usable_water_storage_m3, rel=1e-2) == expected_vol
    assert pytest.approx(report.usable_water_storage_litres, rel=1e-2) == expected_vol * 1000.0

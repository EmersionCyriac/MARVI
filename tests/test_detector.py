"""Unit tests for MARVI Smart Data Guard with Extended Kalman Filter (EKF)."""
import pytest
from datetime import datetime, timedelta

from marvi_guard.models import (
    WellMetadata,
    WaterReading,
    HistoricalRecord,
    ValidationStatus,
    AquiferType,
)
from marvi_guard.detector import SmartDataGuard
from marvi_guard.mock_data import (
    get_dharta_watershed_wells,
    get_sample_history,
)


@pytest.fixture
def guard_engine():
    now = datetime(2026, 11, 1, 10, 0, 0)
    wells = get_dharta_watershed_wells()
    history = get_sample_history(now)

    guard = SmartDataGuard(wells)
    for well_id, records in history.items():
        guard.seed_history(well_id, records)

    return guard, now


def test_clean_weekly_reading_with_ekf(guard_engine):
    guard, now = guard_engine
    # Last reading was ~2.64m on day -7. EKF predicts ~2.72m on day 0
    reading = WaterReading(
        well_id="RJ-DHT-01",
        timestamp=now,
        depth_to_water_meters=2.75,
        measured_by="BJ_Tester",
        is_pump_running=False
    )
    result = guard.evaluate_reading(reading)
    assert result.status == ValidationStatus.ACCEPTED
    assert len(result.flags) == 0
    assert result.ekf_z_score is not None
    assert result.ekf_z_score < 2.0  # within 95% confidence


def test_decimal_point_typo_correction(guard_engine):
    guard, now = guard_engine
    # Well depth is 12m. Typo: 25.0m
    reading = WaterReading(
        well_id="RJ-DHT-01",
        timestamp=now,
        depth_to_water_meters=25.0,
        measured_by="BJ_Tester",
        is_pump_running=False
    )
    result = guard.evaluate_reading(reading)
    assert result.status == ValidationStatus.REJECTED
    assert result.suggested_correction == 2.5
    assert any(f.code == "ERR_EXCEEDS_WELL_DEPTH" for f in result.flags)


def test_negative_depth_rejection(guard_engine):
    guard, now = guard_engine
    reading = WaterReading(
        well_id="RJ-DHT-02",
        timestamp=now,
        depth_to_water_meters=-2.0,
        measured_by="BJ_Tester",
        is_pump_running=False
    )
    result = guard.evaluate_reading(reading)
    assert result.status == ValidationStatus.REJECTED
    assert any(f.code == "ERR_NEGATIVE_DEPTH" for f in result.flags)


def test_active_pumping_drawdown_flag(guard_engine):
    guard, now = guard_engine
    # Sudden deep reading with pump running
    reading = WaterReading(
        well_id="RJ-DHT-03",
        timestamp=now,
        depth_to_water_meters=6.8,
        measured_by="BJ_Tester",
        is_pump_running=True
    )
    result = guard.evaluate_reading(reading)
    assert result.status == ValidationStatus.FLAGGED
    assert any(f.code == "WARN_PUMP_ACTIVE_DRAWDOWN" for f in result.flags)


def test_spatial_outlier_flag(guard_engine):
    guard, now = guard_engine
    # Neighbors are at ~2.7m. DHT-04 reports 8.5m without pump reported
    reading = WaterReading(
        well_id="RJ-DHT-04",
        timestamp=now,
        depth_to_water_meters=8.5,
        measured_by="BJ_Tester",
        is_pump_running=False
    )
    result = guard.evaluate_reading(reading)
    assert result.status == ValidationStatus.FLAGGED
    assert any(f.code == "WARN_SPATIAL_OUTLIER" for f in result.flags)


def test_multi_month_gap_cold_trail_reanchoring(guard_engine):
    guard, now = guard_engine
    # Gap of 60 days (> 45 days threshold)
    reading = WaterReading(
        well_id="RJ-DHT-02",
        timestamp=now + timedelta(days=60),
        depth_to_water_meters=3.2,
        measured_by="BJ_Tester",
        is_pump_running=False
    )
    result = guard.evaluate_reading(reading)
    # Cold trail triggers re-anchoring
    assert result.is_reanchored is True
    assert any(f.code == "INFO_COLD_TRAIL_REANCHOR" for f in result.flags)


def test_unknown_well_rejection(guard_engine):
    guard, now = guard_engine
    reading = WaterReading(
        well_id="UNKNOWN-WELL-999",
        timestamp=now,
        depth_to_water_meters=5.0,
        measured_by="BJ_Tester"
    )
    result = guard.evaluate_reading(reading)
    assert result.status == ValidationStatus.REJECTED
    assert any(f.code == "ERR_UNKNOWN_WELL" for f in result.flags)

"""Mock dataset and generator based on Dharta watershed (Rajasthan) wells."""
from datetime import datetime, timedelta
from typing import List, Tuple

from .models import WellMetadata, WaterReading, HistoricalRecord, AquiferType


def get_dharta_watershed_wells() -> List[WellMetadata]:
    """Sample wells in the Dharta watershed (Udaipur District, Rajasthan)."""
    return [
        WellMetadata(
            well_id="RJ-DHT-01",
            name="Ramesh Patel Field Well",
            village="Dharta",
            latitude=24.5854,
            longitude=73.7125,
            total_depth_meters=12.0,
            diameter_meters=3.5,
            aquifer_type=AquiferType.HARD_ROCK_FRACTURED,
            has_motor_pump=True
        ),
        WellMetadata(
            well_id="RJ-DHT-02",
            name="Dharta Government School Well",
            village="Dharta",
            latitude=24.5870,
            longitude=73.7140,
            total_depth_meters=14.0,
            diameter_meters=2.8,
            aquifer_type=AquiferType.HARD_ROCK_FRACTURED,
            has_motor_pump=False
        ),
        WellMetadata(
            well_id="RJ-DHT-03",
            name="Shanti Devi Community Well",
            village="Dharta",
            latitude=24.5840,
            longitude=73.7110,
            total_depth_meters=11.5,
            diameter_meters=4.0,
            aquifer_type=AquiferType.HARD_ROCK_FRACTURED,
            has_motor_pump=True
        ),
        WellMetadata(
            well_id="RJ-DHT-04",
            name="Mohan Lal Orchard Well",
            village="Dharta",
            latitude=24.5890,
            longitude=73.7155,
            total_depth_meters=13.0,
            diameter_meters=3.0,
            aquifer_type=AquiferType.HARD_ROCK_FRACTURED,
            has_motor_pump=True
        ),
    ]


def get_sample_history(base_time: datetime) -> dict[str, List[HistoricalRecord]]:
    """Generate 4 weeks of consistent historical readings for the wells."""
    history = {}
    offsets = {"RJ-DHT-01": 2.4, "RJ-DHT-02": 2.3, "RJ-DHT-03": 2.5, "RJ-DHT-04": 2.6}

    for well_id, base_depth in offsets.items():
        records = []
        for week in range(4, 0, -1):
            t = base_time - timedelta(days=week * 7)
            # gradual steady decline of ~0.08m per week (~0.011m/day)
            depth = base_depth + (4 - week) * 0.08
            records.append(HistoricalRecord(
                timestamp=t,
                depth_to_water_meters=round(depth, 2),
                rainfall_mm=0.0
            ))
        history[well_id] = records

    return history


def get_test_cases(now: datetime) -> List[Tuple[str, WaterReading]]:
    """Return a suite of real-world scenarios representing normal, typo, pump, and gap inputs."""
    return [
        (
            "SCENARIO 1: Clean Weekly Reading (Normal Progression)",
            WaterReading(
                well_id="RJ-DHT-01",
                timestamp=now,
                depth_to_water_meters=2.75,  # expected ~2.72m, matches EKF velocity
                measured_by="BJ_Suresh_Kumar",
                is_pump_running=False,
                recent_rainfall_mm=0.0,
                notes="Normal Sunday weekly measurement with buzzer tape."
            )
        ),
        (
            "SCENARIO 2: Decimal Point Keypad Typo (Entered 25.0 instead of 2.5)",
            WaterReading(
                well_id="RJ-DHT-01",
                timestamp=now,
                depth_to_water_meters=25.0,  # exceeds 12.0m total depth!
                measured_by="BJ_Suresh_Kumar",
                is_pump_running=False,
                notes="Accidental typo on mobile keypad."
            )
        ),
        (
            "SCENARIO 3: Physically Impossible Negative Depth",
            WaterReading(
                well_id="RJ-DHT-02",
                timestamp=now,
                depth_to_water_meters=-1.5,  # negative depth!
                measured_by="Volunteer_Anita",
                is_pump_running=False,
                notes="Confused height of parapet with water depth."
            )
        ),
        (
            "SCENARIO 4: Active Pumping Drawdown Cone (Pump reported ON)",
            WaterReading(
                well_id="RJ-DHT-03",
                timestamp=now,
                depth_to_water_meters=6.8,  # sudden deep level while pumping
                measured_by="BJ_Gopal_Lal",
                is_pump_running=True,
                notes="Measured while 5HP diesel pump was running for irrigation."
            )
        ),
        (
            "SCENARIO 5: Spatial Neighbor Outlier (Unreported Pumping / Typo)",
            WaterReading(
                well_id="RJ-DHT-04",
                timestamp=now,
                depth_to_water_meters=8.5,  # Neighbors are at ~2.7m!
                measured_by="Volunteer_Devi",
                is_pump_running=False,
                notes="Measured without noticing neighbor was drawing water."
            )
        ),
        (
            "SCENARIO 6: Multi-Month Gap (>45 Days - Cold Trail Re-Anchoring)",
            WaterReading(
                well_id="RJ-DHT-02",
                timestamp=now + timedelta(days=65),  # 65 days later!
                depth_to_water_meters=3.4,  # reasonable post-monsoon depth
                measured_by="Volunteer_Anita",
                is_pump_running=False,
                recent_rainfall_mm=50.0,
                notes="First measurement taken after 2-month festival/harvest break."
            )
        )
    ]

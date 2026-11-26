#!/usr/bin/env python3
"""Interactive demonstration of the MARVI Smart Data Guard with Extended Kalman Filter (EKF)."""
import sys
from datetime import datetime

from marvi_guard.detector import SmartDataGuard
from marvi_guard.mock_data import (
    get_dharta_watershed_wells,
    get_sample_history,
    get_test_cases,
)
from marvi_guard.models import ValidationStatus

# ANSI Colors for Terminal Output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"


def run_demo():
    print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{CYAN}      MARVI SMART DATA GUARD - ADAPTIVE EXTENDED KALMAN FILTER (EKF){RESET}")
    print(f"{CYAN}   State-Space Velocity Tracking, Anomaly Gating & Cold-Trail Re-anchoring{RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}\n")

    now = datetime(2026, 11, 16, 10, 0, 0)
    wells = get_dharta_watershed_wells()
    history = get_sample_history(now)

    print(f"{BOLD}[1] Initializing Wells Registry (Dharta Watershed, Udaipur, Rajasthan):{RESET}")
    for w in wells:
        print(f"  • {BOLD}{w.well_id}{RESET}: {w.name} | Depth: {w.total_depth_meters}m | Pump: {w.has_motor_pump}")

    print(f"\n{BOLD}[2] Seeding 4 Weeks of Baseline Readings into the EKF State Matrices...{RESET}")
    guard = SmartDataGuard(wells)
    for well_id, records in history.items():
        guard.seed_history(well_id, records)
        ekf = guard.ekf_store[well_id]
        latest = records[-1]
        print(f"  • {well_id} State: Depth = {ekf.x[0]:.2f}m | Velocity = {ekf.x[1]*100:.1f} cm/day | Status: Active EKF")

    print(f"\n{BOLD}[3] Evaluating Live Incoming Crowdsourced Observations:{RESET}")
    scenarios = get_test_cases(now)

    for title, reading in scenarios:
        print(f"\n{'-'*80}")
        print(f"{BOLD}{BLUE}>>> {title}{RESET}")
        print(f"    Well ID      : {BOLD}{reading.well_id}{RESET} | Observer: {reading.measured_by}")
        print(f"    Input Depth  : {BOLD}{reading.depth_to_water_meters}m{RESET} | Pump Running: {reading.is_pump_running} | Rain: {reading.recent_rainfall_mm}mm")
        print(f"    Timestamp    : {reading.timestamp.strftime('%Y-%m-%d')} | Notes: \"{reading.notes}\"")

        result = guard.evaluate_reading(reading)

        # Status Badge
        if result.status == ValidationStatus.ACCEPTED:
            badge = f"{GREEN}{BOLD}[ ✓ ACCEPTED ]{RESET}"
        elif result.status == ValidationStatus.FLAGGED:
            badge = f"{YELLOW}{BOLD}[ ⚠ FLAGGED FOR REVIEW ]{RESET}"
        else:
            badge = f"{RED}{BOLD}[ ✗ REJECTED ]{RESET}"

        print(f"\n    Validation   : {badge}")
        print(f"    Diagnosis    : {result.explanation}")

        # Telemetry Block
        if result.ekf_predicted_depth is not None:
            reanchor_str = f" {MAGENTA}[RE-ANCHORED]{RESET}" if result.is_reanchored else ""
            print(f"    {BOLD}EKF Telemetry:{RESET} Predicted = {result.ekf_predicted_depth}m (±{result.ekf_confidence_band}m) | "
                  f"Z-Score = {result.ekf_z_score}σ | Rate = {result.ekf_velocity_m_per_day*100 if result.ekf_velocity_m_per_day else 0.0:.1f} cm/day{reanchor_str}")

        if result.suggested_correction is not None:
            print(f"    {BOLD}{CYAN}Suggested Fix: Did volunteer mean {result.suggested_correction}m?{RESET}")

        if result.flags:
            print("    Triggered Flags:")
            for flag in result.flags:
                color = RED if flag.severity == "ERROR" else YELLOW
                print(f"      - {color}[{flag.code}]{RESET} {flag.message}")

    print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{GREEN}{BOLD}✓ Adaptive EKF Engine Operational! High precision across seasons, weekly cycles & long gaps.{RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}\n")


if __name__ == "__main__":
    run_demo()

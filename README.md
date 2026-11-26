# MARVI Smart Data Guard (Week 1 Implementation)

Automated Anomaly, Typo, and Pumping-Drawdown Detection Engine for participatory groundwater platforms (such as the MARVI project's **OurWater** app).

## Overview

The **Smart Data Guard** sits directly at the data-ingestion boundary of the crowdsourced water monitoring platform. It inspects every water reading submitted by Bhujal Jankaars (BJs) or village volunteers through a 3-layer hydrogeological verification pipeline before the data enters the central database or is fed to machine learning models.

```
Incoming Volunteer Reading
          │
          ▼
┌─────────────────────────────────┐
│ Layer 1: Physical Boundary      │ ──> [Exceeds Well Depth / Negative?] ──> REJECT (Suggest Typo Fix)
└────────────────┬────────────────┘
                 │ (Pass)
                 ▼
┌─────────────────────────────────┐
│ Layer 2: Temporal Consistency   │ ──> [Daily Drop > 0.5m/day or Pump ON?] ──> FLAG (Cone of Depression)
└────────────────┬────────────────┘
                 │ (Pass)
                 ▼
┌─────────────────────────────────┐
│ Layer 3: Spatial Neighborhood   │ ──> [Deviates > 3.5m from 2km Cluster?] ──> FLAG (Spatial Outlier)
└────────────────┬────────────────┘
                 │
                 ▼
    ✓ ACCEPTED into Database
```

---

## Directory Structure

```
marvi_guard/
├── MARVI/                   # Dedicated Python virtual environment
├── marvi_guard/
│   ├── __init__.py          # Package exports
│   ├── models.py            # Pydantic data schemas (WellMetadata, WaterReading, GuardResult)
│   ├── rules.py             # Layer 1, 2, and 3 rule implementations
│   ├── detector.py          # SmartDataGuard orchestrator engine
│   └── mock_data.py         # Simulated Dharta watershed wells (Udaipur, Rajasthan)
├── tests/
│   └── test_detector.py     # Pytest unit tests covering all edge scenarios
├── demo.py                  # Terminal interactive demonstration
└── README.md
```

---

## How to Run

### 1. Activate the Virtual Environment
```bash
cd /home/emersion/.gemini/antigravity/scratch/marvi_guard
source MARVI/bin/activate
```

### 2. Run the Interactive Demo
```bash
python demo.py
# Or directly via venv:
MARVI/bin/python demo.py
```

### 3. Run the Unit Test Suite
```bash
MARVI/bin/pytest -v
```

---

## The 3 Verification Layers

1. **Layer 1: Physical Boundary & Typo Check (`PhysicalBoundaryRule`)**
   - Validates that $0 \le \text{depth} \le \text{total\_depth\_meters}$.
   - Detects misplaced decimal points (e.g., entering `25.0` instead of `2.5` into a 12-meter well) and automatically suggests the corrected value.
2. **Layer 2: Temporal Consistency & Pumping Check (`TemporalConsistencyRule`)**
   - In hard-rock aquifers (Rajasthan/Gujarat basalt and granite), natural seasonal drop is $< 0.5\text{ m/day}$.
   - If water drops faster or the pump is reported active, flags the reading as a **localized suction cone of depression** rather than true regional static water table.
3. **Layer 3: Spatial Neighborhood Check (`SpatialNeighborhoodRule`)**
   - Computes haversine distances to neighboring wells within 2 km.
   - Compares the reading against the neighborhood median. If the reading diverges by $> 3.5\text{ m}$, it flags a spatial outlier.

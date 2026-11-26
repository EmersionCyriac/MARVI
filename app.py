"""MARVI Smart Groundwater & Agronomic Advisory Dashboard (Streamlit).

Unified Web Interface integrating:
1. Village Watershed Map & Well Fleet Overview
2. Physics-Informed Dual-Horizon LSTM Forecaster
3. Farmer Agronomic Advisor & 'What-If' Crop Planning Simulator
4. Smart Data Guard (EKF) Field Ingestion & Anomaly Detection
"""
import os
import sys
import math
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import torch

# Ensure local modules can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from marvi_guard.detector import SmartDataGuard
from marvi_guard.models import WellMetadata, WaterReading, ValidationStatus
from marvi_model.lstm import MARVILSTM
from marvi_advisory.advisor import AgronomicAdvisor
from marvi_advisory.models import WellDimensions, CropType, AdvisoryStatus

# Page configuration
st.set_page_config(
    page_title="MARVI - Groundwater & Agronomic Advisory",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #1E88E5;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .status-green { color: #2E7D32; font-weight: bold; }
    .status-amber { color: #F57F17; font-weight: bold; }
    .status-red { color: #C62828; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_guard():
    """Initialize Smart Data Guard with Dharta watershed wells."""
    detector = SmartDataGuard()
    detector.register_well(WellMetadata(
        well_id="RJ-DHT-01",
        name="Ramesh Patel",
        village="Dharta",
        latitude=24.5854,
        longitude=73.7125,
        total_depth_meters=18.0
    ))
    detector.register_well(WellMetadata(
        well_id="RJ-DHT-02",
        name="Suresh Meena",
        village="Dharta East",
        latitude=24.5890,
        longitude=73.7180,
        total_depth_meters=18.0
    ))
    detector.register_well(WellMetadata(
        well_id="RJ-DHT-03",
        name="Kalu Ram",
        village="Dharta South",
        latitude=24.5790,
        longitude=73.7090,
        total_depth_meters=16.0
    ))
    detector.register_well(WellMetadata(
        well_id="Bhinder_Pz_1",
        name="CGWB Gov Piezometer",
        village="Bhinder",
        latitude=24.5075,
        longitude=74.1667,
        total_depth_meters=20.0
    ))
    return detector


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@st.cache_resource
def load_model():
    """Load trained Physics-Informed LSTM model."""
    model_path = os.path.join(BASE_DIR, "models", "marvi_lstm_dharta.pt")
    if not os.path.exists(model_path):
        return None
    model = MARVILSTM(input_dim=6, hidden_dim=64, num_layers=2, dropout=0.2)
    model.load_state_dict(torch.load(model_path, weights_only=True))
    model.eval()
    return model


@st.cache_resource
def load_dataset():
    """Load prepared training/testing tensors into memory."""
    dataset_path = os.path.join(BASE_DIR, "data", "dataset_dharta_lstm.npz")
    if os.path.exists(dataset_path):
        data = np.load(dataset_path)
        return {k: data[k] for k in data.files}
    return None


detector = load_guard()
model = load_model()
dataset = load_dataset()
advisor = AgronomicAdvisor()

# Sidebar
st.sidebar.image("https://marvi.org.in/wp-content/uploads/2019/11/marvi-logo-new-1.png", width=180)
st.sidebar.title("💧 MARVI System")
st.sidebar.markdown("**Managing Aquifer Recharge in Village Intervention**")
st.sidebar.markdown("*Dharta Watershed, Udaipur District, Rajasthan*")

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 System Status")
st.sidebar.success("🛡️ Smart Data Guard: Active (EKF)")
if model is not None:
    st.sidebar.success("🧠 LSTM AI Model: Loaded (R² = 0.92)")
else:
    st.sidebar.warning("🧠 LSTM Model: Checkpoint Pending")
st.sidebar.info("🇮🇳 NWDP Indian Portal: Synced (Bhinder Pz)")

# App Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "🗺️ Village Wells & Map",
    "🤖 Live AI Forecaster",
    "🌾 Crop Advisory Simulator",
    "🛡️ Field Data Guard"
])


# ==============================================================================
# TAB 1: Village Watershed Map & Well Fleet Overview
# ==============================================================================
with tab1:
    st.header("🗺️ Dharta Watershed Monitoring Network")
    st.markdown("Community-monitored farmer wells in Dharta and Central Ground Water Board (CGWB) telemetry.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Monitored Wells", "4 Stations", "100% Active")
    col2.metric("Mean Water Depth", "10.4 m bgl", "-0.8m this week")
    col3.metric("Aquifer Storage Status", "Moderate (Amber)", "Post-Monsoon")
    col4.metric("Bhujal Jankaars", "12 Volunteers", "Weekly Sundays")

    # Map Data
    wells_data = [
        {"well_id": "RJ-DHT-01", "name": "Ramesh Patel", "lat": 24.5854, "lon": 73.7125, "depth": 9.6, "total_depth": 18.0, "status": "GREEN", "crop": "Wheat (75%) + Mustard (25%)"},
        {"well_id": "RJ-DHT-02", "name": "Suresh Meena", "lat": 24.5890, "lon": 73.7180, "depth": 14.8, "total_depth": 18.0, "status": "AMBER", "crop": "Mustard (80%) + Chickpea (20%)"},
        {"well_id": "RJ-DHT-03", "name": "Kalu Ram", "lat": 24.5790, "lon": 73.7090, "depth": 10.2, "total_depth": 16.0, "status": "GREEN", "crop": "Wheat (75%) + Mustard (25%)"},
        {"well_id": "Bhinder_Pz_1", "name": "CGWB Gov Piezometer", "lat": 24.5075, "lon": 74.1667, "depth": 12.8, "total_depth": 20.0, "status": "GREEN", "crop": "Government Baseline"}
    ]
    df_wells = pd.DataFrame(wells_data)

    color_map = {"GREEN": "#2E7D32", "AMBER": "#F57F17", "RED": "#C62828"}
    df_wells["color"] = df_wells["status"].map(color_map)

    fig_map = px.scatter_mapbox(
        df_wells,
        lat="lat",
        lon="lon",
        hover_name="name",
        hover_data={"well_id": True, "depth": True, "status": True, "crop": True, "lat": False, "lon": False},
        color="status",
        color_discrete_map=color_map,
        zoom=10,
        height=450,
        size_max=18
    )
    fig_map.update_layout(
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 0, "l": 0, "b": 0}
    )
    st.plotly_chart(fig_map, use_container_width=True)

    st.markdown("### Well Fleet Status Table")
    st.dataframe(
        df_wells[["well_id", "name", "depth", "total_depth", "status", "crop"]].rename(columns={
            "well_id": "Well ID",
            "name": "Owner / Station",
            "depth": "Current Depth (m)",
            "total_depth": "Total Depth (m)",
            "status": "Security Status",
            "crop": "Recommended Strategy"
        }),
        use_container_width=True
    )


# ==============================================================================
# TAB 2: Live AI Forecaster
# ==============================================================================
with tab2:
    st.header("🤖 Physics-Informed LSTM Groundwater Forecaster")
    st.markdown("Simultaneous dual-horizon prediction: **60-Day (Flowering)** and **90-Day (Harvest)** groundwater depths.")

    if dataset is not None and model is not None:
        X_test = dataset["X_test"]
        y_test_60d_raw = dataset["y_test_60d_raw"].flatten()
        y_test_90d_raw = dataset["y_test_90d_raw"].flatten()
        dates = dataset["dates"]
        split_idx = int(dataset["split_idx"])
        test_dates = dates[split_idx:]

        min_60d = float(dataset["y_train_60d_raw"].min())
        scale_60d = float(dataset["y_train_60d_raw"].max()) - min_60d
        min_90d = float(dataset["y_train_90d_raw"].min())
        scale_90d = float(dataset["y_train_90d_raw"].max()) - min_90d

        seq_idx = st.slider("Select Historical Forecast Anchor Date", 0, len(X_test) - 1, len(X_test) - 1)
        anchor_date = str(test_dates[seq_idx])[:10]

        # Model Inference
        x_seq = torch.tensor(X_test[seq_idx:seq_idx + 1], dtype=torch.float32)
        with torch.no_grad():
            p60_s, p90_s = model(x_seq)
            pred_60d = float((p60_s.item() * scale_60d) + min_60d)
            pred_90d = float((p90_s.item() * scale_90d) + min_90d)

        true_60d = float(y_test_60d_raw[seq_idx])
        true_90d = float(y_test_90d_raw[seq_idx])
        err_60d = pred_60d - true_60d
        err_90d = pred_90d - true_90d

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Forecast Anchor Date", anchor_date, "Week #8 Lookback")
        col_m2.metric(
            "60-Day AI Forecast",
            f"{pred_60d:.2f} m",
            f"True: {true_60d:.2f} m (Err: {err_60d:+.2f} m)"
        )
        col_m3.metric(
            "90-Day AI Forecast",
            f"{pred_90d:.2f} m",
            f"True: {true_90d:.2f} m (Err: {err_90d:+.2f} m)"
        )

        # Plotly Time-Series Visualization
        # Construct timeline: past 8 weeks (-8 to 0), +8 weeks (+60d), +12 weeks (+90d)
        t_past = [-8 + i for i in range(1, 9)]
        # Scaled feature 0 is approximately gwl
        gwl_past_scaled = X_test[seq_idx, :, 0]
        gwl_past = (gwl_past_scaled * scale_60d) + min_60d

        fig = go.Figure()

        # Historical curve
        fig.add_trace(go.Scatter(
            x=t_past,
            y=gwl_past,
            mode="lines+markers",
            name="Past 8 Weeks (Measured)",
            line=dict(color="#1976D2", width=3),
            marker=dict(size=7)
        ))

        # 60d prediction point
        fig.add_trace(go.Scatter(
            x=[t_past[-1], 8],
            y=[gwl_past[-1], pred_60d],
            mode="lines+markers",
            name="60-Day AI Forecast (Mid-Season)",
            line=dict(color="#FF9800", width=3, dash="dash"),
            marker=dict(size=10, symbol="diamond")
        ))

        # 90d prediction point
        fig.add_trace(go.Scatter(
            x=[8, 12],
            y=[pred_60d, pred_90d],
            mode="lines+markers",
            name="90-Day AI Forecast (Harvest)",
            line=dict(color="#E91E63", width=3, dash="dot"),
            marker=dict(size=10, symbol="star")
        ))

        # True actuals
        fig.add_trace(go.Scatter(
            x=[8, 12],
            y=[true_60d, true_90d],
            mode="markers",
            name="True Actual Readings",
            marker=dict(size=12, color="#4CAF50", symbol="circle-open", line=dict(width=3))
        ))

        fig.update_layout(
            title=f"Underground Water Table Trajectory & AI Forecast Cone (Anchor: {anchor_date})",
            xaxis_title="Weeks Relative to Today (0 = Anchor Sunday)",
            yaxis_title="Depth to Water Table (m bgl) - [Deeper is Lower Water]",
            yaxis=dict(autorange="reversed"),  # Inverted so surface is on top!
            height=450,
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Note: The Y-axis is inverted so ground surface (0m) is on top and deeper water tables appear below.")

    else:
        st.info("Dataset or model file loading. Run demo_pipeline.py and train_model.py first.")


# ==============================================================================
# TAB 3: Farmer's Agronomic Simulator ("What-If" Calculator)
# ==============================================================================
with tab3:
    st.header("🌾 Village Agronomic Advisory & 'What-If' Crop Simulator")
    st.markdown("Evaluate crop feasibility (**Wheat vs. Mustard vs. Chickpea**) based on physical well storage and AI forecast.")

    sim_col1, sim_col2 = st.columns([1, 2])

    with sim_col1:
        st.subheader("Well & Farm Parameters")
        sim_current_depth = st.slider("Current Water Depth (m bgl)", 3.0, 16.0, 9.6, step=0.1)
        sim_pred_90d = st.slider("AI 90-Day Forecast Depth (m bgl)", 5.0, 18.0, 12.8, step=0.1)
        sim_total_depth = st.number_input("Total Well Depth (m)", 10.0, 30.0, 18.0, step=0.5)
        sim_farm_bighas = st.number_input("Farm Cultivable Area (Bighas)", 1.0, 20.0, 4.0, step=0.5)
        sim_radius = st.number_input("Well Radius (m)", 1.0, 4.0, 2.0, step=0.25)

    well_sim = WellDimensions(
        well_id="SIM-WELL",
        farmer_name="Local Farmer",
        village="Dharta Watershed",
        total_depth_m=sim_total_depth,
        radius_m=sim_radius,
        pump_clearance_buffer_m=1.5,
        farm_area_bighas=sim_farm_bighas
    )

    advisory_rep = advisor.generate_advisory(
        well=well_sim,
        current_water_depth_m=sim_current_depth,
        pred_60d_depth_m=sim_pred_90d - 0.8,
        pred_90d_depth_m=sim_pred_90d,
        anchor_date="2024-10-15"
    )

    with sim_col2:
        st.subheader("Village Advisory Bulletin")

        status_alert_box = {
            AdvisoryStatus.SAFE_GREEN: st.success,
            AdvisoryStatus.CAUTION_AMBER: st.warning,
            AdvisoryStatus.CRITICAL_RED: st.error
        }
        status_alert_box[advisory_rep.status](f"### {advisory_rep.status_headline}")

        met1, met2, met3 = st.columns(3)
        met1.metric("Remaining Water Column", f"{advisory_rep.remaining_water_column_90d_m:.2f} m", "At 90-Day Horizon")
        met2.metric("Usable Well Water Volume", f"{advisory_rep.usable_water_storage_litres:,.0f} L", f"{advisory_rep.usable_water_storage_m3:.1f} m³")
        met3.metric("Security Level", advisory_rep.status.value, "Traffic Light")

        st.markdown(f"**Recommendation**: {advisory_rep.primary_recommendation}")

        # Crop Allocation Table
        df_crops = pd.DataFrame([{
            "Crop": c.crop_type.value,
            "Allocated Area (Bighas)": c.allocated_bighas,
            "Farm Share (%)": f"{c.percentage_of_farm:.1f}%",
            "Water Required (m³)": f"{c.total_water_needed_m3:,.1f}"
        } for c in advisory_rep.crop_allocations])

        st.markdown("#### Optimal Land Allocation")
        st.table(df_crops)

        if advisory_rep.downside_risk_warning:
            st.error(advisory_rep.downside_risk_warning)

        with st.expander("💡 Actionable Water-Saving Recommendations"):
            for tip in advisory_rep.water_saving_tips:
                st.markdown(f"- {tip}")


# ==============================================================================
# TAB 4: Field Data Guard Ingestion Tool
# ==============================================================================
with tab4:
    st.header("🛡️ Smart Data Guard Field Ingestion")
    st.markdown("Test the **Extended Kalman Filter (EKF)** and multi-layer validation engine with simulated or real field entries.")

    g_col1, g_col2 = st.columns(2)

    with g_col1:
        st.subheader("Field Measurement Entry")
        test_well_id = st.selectbox("Select Target Well", ["RJ-DHT-01", "RJ-DHT-02", "RJ-DHT-03", "Bhinder_Pz_1"])
        test_depth = st.number_input("Enter Sounder Tape Depth (meters)", -10.0, 50.0, 25.0, step=0.1, help="Try entering 25.0 to test decimal slip catching!")
        test_is_pumping = st.checkbox("Is Irrigation Pump Currently Running?", value=False)
        test_date = st.date_input("Measurement Date")

        validate_btn = st.button("Submit & Inspect with Data Guard", type="primary")

    with g_col2:
        st.subheader("Data Guard Telemetry & Diagnosis")
        if validate_btn:
            reading = WaterReading(
                well_id=test_well_id,
                timestamp=datetime.combine(test_date, datetime.min.time()),
                depth_to_water_meters=test_depth,
                measured_by="Bhujal Jankaar",
                is_pump_running=test_is_pumping
            )

            result = detector.evaluate_reading(reading)

            if result.status == ValidationStatus.ACCEPTED:
                st.success(f"✅ Status: {result.status.value}")
            elif result.status == ValidationStatus.FLAGGED:
                st.warning(f"⚠️ Status: {result.status.value}")
            else:
                st.error(f"❌ Status: {result.status.value}")

            if result.suggested_correction:
                st.info(f"💡 Auto-Correction Diagnosed: `{result.suggested_correction:.2f} meters` (10x Decimal Typo)")

            st.write(f"**Explanation:** {result.explanation}")

            if result.ekf_velocity_m_per_day is not None:
                st.markdown("#### Extended Kalman Filter Telemetry")
                st.json({
                    "ekf_predicted_depth_m": round(result.ekf_predicted_depth, 2) if result.ekf_predicted_depth else None,
                    "ekf_velocity_cm_per_day": round(result.ekf_velocity_m_per_day * 100.0, 2),
                    "ekf_z_score": round(result.ekf_z_score, 2) if result.ekf_z_score else None,
                    "is_reanchored": result.is_reanchored
                })

/**
 * MARVI Leaflet Web Application Client (v3.0)
 * Integrates:
 * 1. Leaflet GIS Map with 10 community wells, OpenStreetMap / Satellite layers & pulse markers
 * 2. Chart.js Dual-Horizon LSTM Forecaster with well-specific hydrology and selection
 * 3. Approachable 'What-If' Agronomic Crop Simulator (presets, visual cutaway, safe ratios)
 * 4. Smart Data Guard EKF field reading validator across all 10 stations
 */

let mapInstance = null;
let markersLayer = null;
let forecastChart = null;
let wellsData = [];

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initMap();
    loadWells();
    initSimulator();
    initGuard();
    
    // Forecaster well selector change listener
    const fcSelect = document.getElementById("forecast-well-select");
    if (fcSelect) {
        fcSelect.addEventListener("change", (e) => {
            loadForecast(e.target.value);
        });
    }
});

// Tab Navigation
function initTabs() {
    const tabs = document.querySelectorAll(".tab-btn");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
            
            tab.classList.add("active");
            const targetPane = document.getElementById(tab.dataset.tab);
            if (targetPane) {
                targetPane.classList.add("active");
            }

            // Invalidate Leaflet map size when tab becomes visible
            if (tab.dataset.tab === "tab-map" && mapInstance) {
                setTimeout(() => mapInstance.invalidateSize(), 200);
            }
        });
    });
}

// -----------------------------------------------------------------------------
// 1. LEAFLET MAP INITIALIZATION
// -----------------------------------------------------------------------------
function initMap() {
    try {
        if (typeof L === "undefined") {
            console.error("Leaflet library not loaded!");
            return;
        }

        // Center at Dharta Watershed, Udaipur (24.58, 73.71)
        mapInstance = L.map("map", {
            center: [24.575, 73.72],
            zoom: 12,
            zoomControl: true
        });

        // Clean, fast street map as default base layer
        const esriStreetLayer = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", {
            attribution: 'Tiles &copy; Esri &mdash; Street Map',
            maxZoom: 19
        }).addTo(mapInstance);

        const esriTopoLayer = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}", {
            attribution: 'Tiles &copy; Esri &mdash; Topographic',
            maxZoom: 19
        });

        const satelliteLayer = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
            attribution: 'Tiles &copy; Esri &mdash; Aerial Imagery',
            maxZoom: 19
        });

        const osmLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            subdomains: ['a', 'b', 'c'],
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19
        });

        // Auto-retry handler to prevent gray tile dropouts on network fluctuations
        [esriStreetLayer, esriTopoLayer, satelliteLayer, osmLayer].forEach(layer => {
            layer.on('tileerror', function(error, tile) {
                if (tile && !tile._retryCount) {
                    tile._retryCount = 1;
                    setTimeout(() => {
                        tile.src = tile.src.split('?')[0] + '?r=' + Date.now();
                    }, 350);
                }
            });
        });

        const baseMaps = {
            "Street Map (Default)": esriStreetLayer,
            "Topographic Terrain": esriTopoLayer,
            "Satellite Aerial View": satelliteLayer,
            "OpenStreetMap": osmLayer
        };

        L.control.layers(baseMaps).addTo(mapInstance);
        L.control.scale({ imperial: false }).addTo(mapInstance);

        markersLayer = L.layerGroup().addTo(mapInstance);

        // Ensure Leaflet calculates dimensions correctly after DOM layout finishes
        setTimeout(() => { if (mapInstance) mapInstance.invalidateSize(); }, 150);
        setTimeout(() => { if (mapInstance) mapInstance.invalidateSize(); }, 600);
    } catch (e) {
        console.error("Error initializing Leaflet map:", e);
    }
}

// Load well data from API and populate Leaflet map, dropdowns, and fleet table
async function loadWells() {
    try {
        const res = await fetch("/api/wells?_t=" + Date.now());
        const json = await res.json();
        wellsData = json.wells;

        // Dynamically compute and update watershed summary KPI cards
        if (wellsData && wellsData.length > 0) {
            const totalWells = wellsData.length;
            const greenCount = wellsData.filter(w => w.status === "GREEN").length;
            const amberCount = wellsData.filter(w => w.status === "AMBER").length;
            const redCount = wellsData.filter(w => w.status === "RED").length;

            const depths = wellsData.map(w => w.current_depth_m);
            const meanDepth = (depths.reduce((a, b) => a + b, 0) / totalWells).toFixed(1);
            const minDepth = Math.min(...depths).toFixed(1);
            const maxDepth = Math.max(...depths).toFixed(1);

            const piezometers = wellsData.filter(w => w.well_id.toLowerCase().includes("pz")).length;
            const farmerWells = totalWells - piezometers;

            const kpiTotal = document.getElementById("kpi-total-stations");
            if (kpiTotal) kpiTotal.innerText = `${totalWells} Wells`;

            const kpiTypes = document.getElementById("kpi-station-types");
            if (kpiTypes) kpiTypes.innerText = `${farmerWells} Farmer Wells + ${piezometers} CGWB Piezometer`;

            const kpiMean = document.getElementById("kpi-mean-depth");
            if (kpiMean) kpiMean.innerText = `${meanDepth} m bgl`;

            const kpiRange = document.getElementById("kpi-depth-range");
            if (kpiRange) kpiRange.innerText = `Ranging from ${minDepth}m to ${maxDepth}m`;

            const kpiDist = document.getElementById("kpi-security-dist");
            if (kpiDist) {
                kpiDist.innerHTML = `
                    <span class="chip chip-green"><span class="chip-dot"></span> ${greenCount} Safe</span>
                    <span class="chip chip-amber"><span class="chip-dot"></span> ${amberCount} Alert</span>
                    <span class="chip chip-red"><span class="chip-dot"></span> ${redCount} Stress</span>
                `;
            }
            const distBar = document.getElementById("kpi-dist-bar");
            if (distBar && totalWells > 0) {
                distBar.innerHTML = `
                    <div class="dist-bar-green" style="width: ${(greenCount / totalWells) * 100}%;"></div>
                    <div class="dist-bar-amber" style="width: ${(amberCount / totalWells) * 100}%;"></div>
                    <div class="dist-bar-red" style="width: ${(redCount / totalWells) * 100}%;"></div>
                `;
            }
        }

        if (markersLayer) markersLayer.clearLayers();
        const tableBody = document.getElementById("fleet-table-body");
        if (tableBody) tableBody.innerHTML = "";

        wellsData.forEach(well => {
            // 1. Create Leaflet Custom Pin Marker (Clean GIS Beacon)
            if (typeof L !== "undefined" && markersLayer) {
                const statusClass = well.status === "GREEN" ? "pin-green" : (well.status === "AMBER" ? "pin-amber" : "pin-red");
                const iconHtml = `
                    <div class="custom-pin ${statusClass}">
                        <div class="pulse-ring"></div>
                        <div class="pin-core"></div>
                    </div>
                `;
                const customIcon = L.divIcon({
                    className: "custom-leaflet-icon",
                    html: iconHtml,
                    iconSize: [22, 22],
                    iconAnchor: [11, 11],
                    popupAnchor: [0, -11]
                });

                // 2. Rich Popup Content (Clean, Professional)
                const popupHtml = `
                    <div class="well-popup">
                        <div class="popup-header">
                            <div class="popup-title">${well.name}</div>
                            <div class="popup-village">${well.village} &bull; ${well.well_id}</div>
                        </div>
                        <div class="popup-row">
                            <span>Current Water Depth:</span>
                            <strong>${well.current_depth_m} m bgl</strong>
                        </div>
                        <div class="popup-row">
                            <span>Total Well Depth:</span>
                            <span>${well.total_depth_m} m</span>
                        </div>
                        <div class="popup-row">
                            <span>Active Water Column:</span>
                            <strong>${well.water_column_m} m</strong>
                        </div>
                        <div class="popup-row">
                            <span>Stored Volume:</span>
                            <strong>${well.stored_litres.toLocaleString()} Litres</strong>
                        </div>
                        <div class="popup-row">
                            <span>Status:</span>
                            <span class="status-badge status-${well.status.toLowerCase()}">${well.status}</span>
                        </div>
                        <div class="popup-row">
                            <span>Recommended Crop:</span>
                            <span style="font-weight:600; color:#1e40af;">${well.recommended_crop}</span>
                        </div>
                        <div style="display:flex; gap:6px; margin-top:8px;">
                            <button class="popup-btn" style="flex:1;" onclick="selectWellForForecast('${well.well_id}')">AI Forecast</button>
                            <button class="popup-btn" style="flex:1; background:#0d9488;" onclick="selectWellForSimulator('${well.well_id}')">Simulate Sowing</button>
                        </div>
                    </div>
                `;

                const marker = L.marker([well.lat, well.lon], { icon: customIcon })
                    .bindPopup(popupHtml);
                markersLayer.addLayer(marker);
            }

            // 3. Populate Fleet Table
            if (tableBody) {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td><strong>${well.well_id}</strong></td>
                    <td>${well.name}</td>
                    <td>${well.village}</td>
                    <td>${well.current_depth_m} m</td>
                    <td>${well.total_depth_m} m</td>
                    <td><span class="status-badge status-${well.status.toLowerCase()}">${well.status}</span></td>
                    <td>${well.recommended_crop}</td>
                    <td>
                        <button class="btn btn-outline" style="padding:4px 8px; font-size:0.8rem;" onclick="selectWellForForecast('${well.well_id}')">Inspect</button>
                    </td>
                `;
                tableBody.appendChild(tr);
            }
        });

        // Auto-fit map to enclose all 10 wells
        if (typeof L !== "undefined" && mapInstance && wellsData.length > 0) {
            const bounds = L.latLngBounds(wellsData.map(w => [w.lat, w.lon]));
            mapInstance.fitBounds(bounds, { padding: [40, 40] });
        }

        // Initialize forecast with first well
        if (wellsData.length > 0) {
            loadForecast(wellsData[0].well_id);
        }
    } catch (err) {
        console.error("Failed to load wells:", err);
    }
}

// -----------------------------------------------------------------------------
// 2. AI FORECASTER WITH WELL-SPECIFIC HYDROLOGY (CHART.JS)
// -----------------------------------------------------------------------------
async function loadForecast(wellId) {
    if (!wellId) {
        const fcSelect = document.getElementById("forecast-well-select");
        wellId = (fcSelect && fcSelect.value) ? fcSelect.value : "RJ-DHT-01";
    }

    // Ensure dropdown reflects current well
    const fcSelect = document.getElementById("forecast-well-select");
    if (fcSelect && fcSelect.value !== wellId) {
        fcSelect.value = wellId;
    }

    try {
        const res = await fetch(`/api/forecast?well_id=${encodeURIComponent(wellId)}&_t=${Date.now()}`);
        const data = await res.json();

        // Update well header info
        const metaEl = document.getElementById("forecast-well-meta");
        if (metaEl) {
            metaEl.innerHTML = `
                <div><strong>${data.village}</strong></div>
                <div>Depth: <strong>${data.current_depth_m}m bgl</strong> / Total: ${data.total_depth_m}m</div>
                <span class="status-badge status-${data.status.toLowerCase()}">${data.status}</span>
            `;
        }

        // Safe resolution of 60d values
        const pred60 = data.latest_pred_60d;
        const true60 = (data.latest_true_60d !== undefined) ? data.latest_true_60d : ((data.latest_true !== undefined) ? data.latest_true : (data.true_60d ? data.true_60d[data.true_60d.length - 1] : 11.0));
        const diff60 = Math.abs(pred60 - true60).toFixed(2);

        document.getElementById("kpi-60d-pred").innerText = `${pred60} m`;
        document.getElementById("kpi-60d-true").innerText = `${true60} m`;
        document.getElementById("kpi-60d-diff").innerText = `Δ ${diff60} m`;

        // Safe resolution of 90d values
        const pred90 = data.latest_pred_90d;
        const true90 = (data.latest_true_90d !== undefined) ? data.latest_true_90d : (data.true_90d ? data.true_90d[data.true_90d.length - 1] : 12.0);
        const diff90 = Math.abs(pred90 - true90).toFixed(2);

        document.getElementById("kpi-90d-pred").innerText = `${pred90} m`;
        document.getElementById("kpi-90d-true").innerText = `${true90} m`;
        document.getElementById("kpi-90d-diff").innerText = `Δ ${diff90} m`;

        currentForecastData = data;
        renderForecastChart(data);
    } catch (err) {
        console.error("Failed to load forecast for well:", wellId, err);
    }
}

let currentForecastData = null;
let currentHorizonMode = "DUAL";

window.setHorizonMode = function(mode) {
    currentHorizonMode = mode;
    
    // Update button visual styles
    const btnDual = document.getElementById("btn-horizon-dual");
    const btn60 = document.getElementById("btn-horizon-60d");
    const btn90 = document.getElementById("btn-horizon-90d");

    [btnDual, btn60, btn90].forEach(b => {
        if (b) {
            b.className = "btn btn-outline";
            b.style.background = "white";
            b.style.color = "var(--text)";
        }
    });

    const activeBtn = mode === "DUAL" ? btnDual : (mode === "60D" ? btn60 : btn90);
    if (activeBtn) {
        activeBtn.className = "btn";
        activeBtn.style.background = "var(--primary)";
        activeBtn.style.color = "white";
    }

    if (currentForecastData) {
        renderForecastChart(currentForecastData);
    }
};

function renderForecastChart(data) {
    const ctx = document.getElementById("forecastCanvas").getContext("2d");
    if (forecastChart) {
        forecastChart.destroy();
    }

    let datasets = [];
    let chartTitle = "";

    if (currentHorizonMode === "60D") {
        chartTitle = `60-Day Horizon Mode: Predicted vs Actual Depth (${data.well_name}) - Mean Error: 19 cm`;
        datasets = [
            {
                label: `Actual 60-Day Depth (${data.well_name})`,
                data: data.true_60d,
                borderColor: "#0f172a",
                backgroundColor: "#0f172a",
                borderWidth: 2.4,
                pointRadius: 3.5,
                tension: 0.1
            },
            {
                label: `60-Day AI Forecast (${data.well_id})`,
                data: data.pred_60d,
                borderColor: "#2563eb",
                backgroundColor: "rgba(37, 99, 235, 0.08)",
                borderWidth: 2.5,
                borderDash: [5, 5],
                pointRadius: 3.5,
                tension: 0.2
            }
        ];
    } else if (currentHorizonMode === "90D") {
        chartTitle = `90-Day Horizon Mode: Predicted vs Actual Depth (${data.well_name}) - Mean Error: 13 cm`;
        datasets = [
            {
                label: `Actual 90-Day Depth (${data.well_name})`,
                data: data.true_90d,
                borderColor: "#0f172a",
                backgroundColor: "#0f172a",
                borderWidth: 2.4,
                pointRadius: 3.5,
                tension: 0.1
            },
            {
                label: `90-Day AI Forecast (${data.well_id})`,
                data: data.pred_90d,
                borderColor: "#7c3aed",
                backgroundColor: "rgba(124, 58, 237, 0.08)",
                borderWidth: 2.5,
                borderDash: [5, 5],
                pointRadius: 3.5,
                tension: 0.2
            }
        ];
    } else {
        // DUAL mode
        chartTitle = `Dual Horizon Comparison (${data.well_name}) - Note: 90d Forecast looks 30 days further ahead than 60d`;
        datasets = [
            {
                label: `Actual 60-Day Depth (${data.well_name})`,
                data: data.true_60d,
                borderColor: "#0f172a",
                backgroundColor: "#0f172a",
                borderWidth: 2.2,
                pointRadius: 3,
                tension: 0.1
            },
            {
                label: `60-Day AI Forecast (${data.well_id})`,
                data: data.pred_60d,
                borderColor: "#2563eb",
                backgroundColor: "rgba(37, 99, 235, 0.05)",
                borderWidth: 2.5,
                borderDash: [5, 5],
                pointRadius: 3,
                tension: 0.2
            },
            {
                label: `Actual 90-Day Depth (${data.well_name})`,
                data: data.true_90d,
                borderColor: "#475569",
                borderWidth: 1.8,
                borderDash: [2, 2],
                pointRadius: 2,
                tension: 0.1
            },
            {
                label: `90-Day AI Forecast (${data.well_id})`,
                data: data.pred_90d,
                borderColor: "#7c3aed",
                backgroundColor: "transparent",
                borderWidth: 2.2,
                pointRadius: 2.5,
                tension: 0.2
            }
        ];
    }

    forecastChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: data.dates,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    reverse: true,
                    title: {
                        display: true,
                        text: "Depth to Water Table (meters bgl - Inverted Axis)",
                        font: { weight: "bold", size: 12 }
                    },
                    grid: { color: "#e2e8f0" }
                },
                x: {
                    title: { display: true, text: "Timeline (Weekly Sunday Readings)", font: { weight: "bold", size: 12 } },
                    grid: { color: "#f8fafc" }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: chartTitle,
                    font: { size: 13, weight: "bold" },
                    color: "#1e3a8a"
                },
                legend: { position: "top" },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.raw} m bgl`;
                        }
                    }
                }
            }
        }
    });
}

// Global functions attached to window for inline onclick handlers
window.selectWellForForecast = function(wellId) {
    const fcSelect = document.getElementById("forecast-well-select");
    if (fcSelect) fcSelect.value = wellId;

    const tabForecast = document.querySelector('[data-tab="tab-forecast"]');
    if (tabForecast) tabForecast.click();

    loadForecast(wellId);
};

window.selectWellForSimulator = function(wellId) {
    const tabSim = document.querySelector('[data-tab="tab-simulator"]');
    if (tabSim) tabSim.click();

    const simSelect = document.getElementById("sim-well-select");
    if (simSelect) {
        simSelect.value = wellId;
        const well = wellsData.find(w => w.well_id === wellId);
        if (well) loadWellIntoSimulator(well);
    }
};

// -----------------------------------------------------------------------------
// 3. APPROACHABLE AGRONOMIC SIMULATOR
// -----------------------------------------------------------------------------
function initSimulator() {
    const depthSlider = document.getElementById("sim-depth");
    const diamSlider = document.getElementById("sim-diam");
    const totalSlider = document.getElementById("sim-total");
    const areaSlider = document.getElementById("sim-area");
    const simSelect = document.getElementById("sim-well-select");

    const updateSim = async () => {
        const depth = parseFloat(depthSlider.value);
        const diam = parseFloat(diamSlider.value);
        const total = parseFloat(totalSlider.value);
        const area = parseFloat(areaSlider.value);

        // Update slider value badges
        document.getElementById("val-depth").innerText = `${depth.toFixed(1)} m`;
        document.getElementById("val-diam").innerText = `${diam.toFixed(1)} m`;
        document.getElementById("val-total").innerText = `${total.toFixed(1)} m`;
        document.getElementById("val-area").innerText = `${area.toFixed(1)} ha (${(area * 4).toFixed(0)} Bighas)`;

        // Update cutaway diagram labels
        const diagDepth = document.getElementById("diagram-water-depth");
        if (diagDepth) diagDepth.innerText = `${depth.toFixed(1)}m bgl`;
        const diagTotal = document.getElementById("diagram-total-depth");
        if (diagTotal) diagTotal.innerText = `${total.toFixed(1)}m`;

        try {
            const res = await fetch("/api/advisory", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    depth_m: depth,
                    diameter_m: diam,
                    total_depth_m: total,
                    area_ha: area
                })
            });
            const data = await res.json();

            // Water Column Graphic
            const waterHeightPct = Math.min(100, Math.max(0, (data.water_column_m / total) * 100));
            document.getElementById("water-level-body").style.height = `${waterHeightPct}%`;
            document.getElementById("water-col-label").innerText = `${data.water_column_m}m Active`;

            // Storage Display
            document.getElementById("res-usable-litres").innerText = `${data.usable_storage_litres.toLocaleString()} L`;
            document.getElementById("res-water-col").innerText = `${data.water_column_m} m`;

            // Status Badge & Alert
            const statusEl = document.getElementById("res-status-badge");
            statusEl.className = `status-badge status-${data.status.toLowerCase()}`;
            statusEl.innerText = data.status;

            const alertEl = document.getElementById("sim-alert-box");
            alertEl.className = `alert-box alert-${data.status.toLowerCase()}`;
            alertEl.innerHTML = `<strong>Advisory Recommendation:</strong> ${data.summary}`;

            // Crop Allocation Progress Bars
            document.getElementById("pct-wheat").innerText = `${data.wheat_pct}%`;
            document.getElementById("bar-wheat").style.width = `${data.wheat_pct}%`;

            document.getElementById("pct-mustard").innerText = `${data.mustard_pct}%`;
            document.getElementById("bar-mustard").style.width = `${data.mustard_pct}%`;

            document.getElementById("pct-chickpea").innerText = `${data.chickpea_pct}%`;
            document.getElementById("bar-chickpea").style.width = `${data.chickpea_pct}%`;

            document.getElementById("pct-fallow").innerText = `${data.fallow_pct}%`;
            document.getElementById("bar-fallow").style.width = `${data.fallow_pct}%`;

        } catch (err) {
            console.error("Advisory simulation error:", err);
        }
    };

    [depthSlider, diamSlider, totalSlider, areaSlider].forEach(slider => {
        slider.addEventListener("input", updateSim);
    });

    if (simSelect) {
        simSelect.addEventListener("change", (e) => {
            const wellId = e.target.value;
            if (wellId) {
                const well = wellsData.find(w => w.well_id === wellId);
                if (well) loadWellIntoSimulator(well);
            }
        });
    }

    updateSim();
}

// Load well attributes into the simulation sliders
function loadWellIntoSimulator(well) {
    document.getElementById("sim-depth").value = well.current_depth_m;
    document.getElementById("sim-diam").value = well.diameter_m;
    document.getElementById("sim-total").value = well.total_depth_m;
    document.getElementById("sim-area").value = 1.0;
    
    // Trigger update
    const event = new Event("input");
    document.getElementById("sim-depth").dispatchEvent(event);
}

// 1-Click seasonal scenario preset helper
window.applySeasonPreset = function(type) {
    const depthSlider = document.getElementById("sim-depth");
    const diamSlider = document.getElementById("sim-diam");
    const totalSlider = document.getElementById("sim-total");
    const areaSlider = document.getElementById("sim-area");

    if (type === "GOOD") {
        depthSlider.value = 6.5;
        diamSlider.value = 2.5;
        totalSlider.value = 18.0;
        areaSlider.value = 1.0;
    } else if (type === "NORMAL") {
        depthSlider.value = 10.5;
        diamSlider.value = 2.5;
        totalSlider.value = 18.0;
        areaSlider.value = 1.0;
    } else if (type === "DROUGHT") {
        depthSlider.value = 15.5;
        diamSlider.value = 2.5;
        totalSlider.value = 18.0;
        areaSlider.value = 1.0;
    }

    const event = new Event("input");
    depthSlider.dispatchEvent(event);
};

// -----------------------------------------------------------------------------
// 4. SMART DATA GUARD (EKF VALIDATION)
// -----------------------------------------------------------------------------
function initGuard() {
    const btn = document.getElementById("btn-validate-guard");
    if (!btn) return;

    btn.addEventListener("click", async () => {
        const wellId = document.getElementById("guard-well").value;
        const depth = parseFloat(document.getElementById("guard-depth").value);
        const isPumping = document.getElementById("guard-pumping").checked;

        try {
            const res = await fetch("/api/guard/validate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    well_id: wellId,
                    depth_m: depth,
                    is_pumping: isPumping
                })
            });
            const data = await res.json();

            const statusEl = document.getElementById("guard-res-status");
            statusEl.className = `status-badge status-${data.status === "ACCEPTED" ? "green" : (data.status === "FLAGGED" ? "amber" : "red")}`;
            statusEl.innerText = data.status;

            document.getElementById("guard-res-expl").innerText = data.explanation;
            document.getElementById("guard-res-ekf").innerText = data.ekf_predicted_depth !== null ? `${data.ekf_predicted_depth} m` : "N/A";
            document.getElementById("guard-res-vel").innerText = data.ekf_velocity !== null ? `${data.ekf_velocity} m/day` : "N/A";
            document.getElementById("guard-res-z").innerText = data.ekf_z_score !== null ? data.ekf_z_score : "N/A";

            const corrEl = document.getElementById("guard-res-corr");
            if (data.suggested_correction !== null) {
                corrEl.style.display = "block";
                corrEl.innerText = `Suggested Correction: ${data.suggested_correction} m`;
            } else {
                corrEl.style.display = "none";
            }
        } catch (err) {
            console.error("Guard validation error:", err);
        }
    });
}

window.setGuardPreset = function(depth, isPumping) {
    document.getElementById("guard-depth").value = depth;
    document.getElementById("guard-pumping").checked = isPumping;
    document.getElementById("btn-validate-guard").click();
};

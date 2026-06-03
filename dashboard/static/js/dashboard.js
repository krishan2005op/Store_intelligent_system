// Dashboard Application State
const state = {
    storeId: '',
    ws: null,
    funnelChart: null,
    wsReconnectTimeout: null,
    pollingInterval: null,
    isWsConnected: false,
    knownStoreNames: {
        "00000000-0000-4000-8000-000000001008": {
            name: "Store 1",
            subtext: "ST1008 - zone, entry, billing camera intelligence",
            cameras: ["CAM 3 Entry", "CAM 1 Zone", "CAM 2 Zone", "CAM 5 Billing"]
        },
        "00000000-0000-4000-8000-000000001076": {
            name: "Store 2",
            subtext: "ST1076 - sample JSONL plus live CCTV camera intelligence",
            cameras: ["Entry 1", "Entry 2", "Zone", "Billing Area"]
        },
        "00000000-0000-4000-8000-000000000001": {
            name: "AURA Simulation",
            subtext: "ST0001 - deterministic event replay",
            cameras: ["Sim Entry", "Sim Zone", "Sim Billing"]
        }
    }
};

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', () => {
    state.storeId = document.getElementById('store-selector').value;
    updateStoreHeader();
    renderCameraTopology();
    
    // Set up Chart.js for Funnel
    initFunnelChart();

    // Fetch initial data
    refreshDashboard();

    // Register Event Listeners
    document.getElementById('store-selector').addEventListener('change', handleStoreChange);
    document.getElementById('refresh-btn').addEventListener('click', refreshDashboard);

    // Dynamic Time
    setInterval(updateClock, 1000);
});

// Update the visual clock
function updateClock() {
    const timeContainer = document.getElementById('current-time');
    const now = new Date();
    timeContainer.textContent = now.toLocaleDateString() + ' ' + now.toLocaleTimeString();
}

// Handle Store Dropdown Change
function handleStoreChange(e) {
    state.storeId = e.target.value;
    updateStoreHeader();
    renderCameraTopology();

    // Reset components & refresh
    document.getElementById('event-feed-rows').innerHTML = '<tr class="empty-feed"><td colspan="6">Waiting for camera feed events...</td></tr>';
    refreshDashboard();
}

function updateStoreHeader() {
    const details = state.knownStoreNames[state.storeId] || { name: "Custom Store", subtext: "CCTV Analytics Feed" };
    document.getElementById('store-name').textContent = details.name;
    document.getElementById('store-subtext').textContent = details.subtext;
}

// Full Dashboard Refresh
function refreshDashboard() {
    fetchMetrics();
    fetchHeatmap();
    fetchFunnel();
    fetchAnomalies();
    checkHealth();
    setupWebSocket();
}

// Initialize Funnel Chart.js Instance
function initFunnelChart() {
    const canvas = document.getElementById('funnel-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    state.funnelChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Entry', 'Browse', 'Dwell', 'Billing Intent', 'Purchase Proxy'],
            datasets: [{
                label: 'Unique Shoppers',
                data: [0, 0, 0, 0, 0],
                backgroundColor: [
                    'rgba(6, 182, 212, 0.78)',
                    'rgba(16, 185, 129, 0.70)',
                    'rgba(245, 158, 11, 0.66)',
                    'rgba(249, 115, 22, 0.62)',
                    'rgba(239, 68, 68, 0.58)'
                ],
                borderColor: 'rgba(103, 232, 249, 0.75)',
                borderWidth: 1.5,
                borderRadius: 6,
                barPercentage: 0.6
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return ` Shoppers: ${context.parsed.x}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8', stepSize: 1 }
                },
                y: {
                    grid: { display: false },
                    ticks: { color: '#f8fafc', font: { family: 'Outfit', weight: 'bold' } }
                }
            }
        }
    });
}

// Fetch Metrics Card Data
async function fetchMetrics() {
    try {
        const response = await fetch(`/stores/${state.storeId}/metrics`);
        if (!response.ok) throw new Error('Network error fetching metrics');
        const data = await response.json();
        
        // Update stats DOM elements
        document.getElementById('kpi-visitors').textContent = data.unique_visitors;
        document.getElementById('kpi-reentries').textContent = `${data.reentry_count} re-entries`;
        document.getElementById('kpi-active').textContent = data.active_sessions;
        document.getElementById('kpi-dwell').textContent = `${Math.round(data.avg_dwell_seconds)}s`;
        document.getElementById('kpi-conversion').textContent = `${(data.conversion_rate * 100).toFixed(2)}%`;
        document.getElementById('kpi-queue').textContent = `${data.current_queue_depth} / ${data.max_queue_depth}`;
        document.getElementById('kpi-abandon-rate').textContent = `${(data.abandonment_rate * 100).toFixed(1)}% abandon rate`;

        const completed = Math.round(data.unique_visitors * data.conversion_rate);
        document.getElementById('kpi-purchases').textContent = `${completed} purchases`;
    } catch (err) {
        console.error(err);
    }
}

// Fetch Heatmap Grid Data
async function fetchHeatmap() {
    try {
        const response = await fetch(`/stores/${state.storeId}/heatmap`);
        if (!response.ok) throw new Error('Error fetching heatmap');
        const data = await response.json();
        
        const grid = document.getElementById('heatmap-grid');
        grid.innerHTML = ''; // clear grid

        if (!data.cells || data.cells.length === 0) {
            grid.innerHTML = '<div style="grid-column: span 2; text-align: center; color: #64748b; padding: 20px;">No active zone data</div>';
            return;
        }

        data.cells.forEach(cell => {
            const cellDiv = document.createElement('div');
            cellDiv.className = 'heatmap-cell';

            // Determine intensity style class
            let intensityClass = 'intensity-none';
            if (cell.normalized_intensity > 0.6) {
                intensityClass = 'intensity-high';
            } else if (cell.normalized_intensity > 0.3) {
                intensityClass = 'intensity-medium';
            } else if (cell.normalized_intensity > 0) {
                intensityClass = 'intensity-low';
            }
            cellDiv.classList.add(intensityClass);

            cellDiv.innerHTML = `
                <span class="cell-zone">${cell.zone_id.replace('-', ' ')}</span>
                <span class="cell-value">${cell.event_count} <span style="font-size: 11px; font-weight: normal; color: #94a3b8;">hits</span></span>
                <span class="cell-dwell">Avg dwell: ${Math.round(cell.dwell_seconds / Math.max(cell.event_count, 1))}s</span>
            `;
            grid.appendChild(cellDiv);
        });
    } catch (err) {
        console.error(err);
    }
}

// Fetch Funnel Data
async function fetchFunnel() {
    try {
        const response = await fetch(`/stores/${state.storeId}/funnel`);
        if (!response.ok) throw new Error('Error fetching funnel');
        const data = await response.json();

        // Sort data relative to stages
        const stageOrder = ['ENTRY', 'BROWSE', 'DWELL', 'BILLING_INTENT', 'PURCHASE_PROXY'];
        const values = stageOrder.map(stageName => {
            const stageData = data.stages.find(s => s.stage === stageName);
            return stageData ? stageData.count : 0;
        });

        // Update Chart
        state.funnelChart.data.datasets[0].data = values;
        state.funnelChart.update();
    } catch (err) {
        console.error(err);
    }
}

// Fetch Anomalies Data
async function fetchAnomalies() {
    try {
        const response = await fetch(`/stores/${state.storeId}/anomalies`);
        if (!response.ok) throw new Error('Error fetching anomalies');
        const data = await response.json();

        const container = document.getElementById('anomalies-list');
        const countBadge = document.getElementById('anomaly-badge-count');
        container.innerHTML = '';

        if (!data.anomalies || data.anomalies.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>No operational anomalies detected in this time window.</p>
                </div>`;
            countBadge.textContent = '0 Alerts';
            countBadge.className = 'counter-badge counter-zero';
            return;
        }

        countBadge.textContent = `${data.anomalies.length} Alerts`;
        countBadge.className = 'counter-badge counter-active';

        data.anomalies.forEach(anomaly => {
            const card = document.createElement('div');
            card.className = 'anomaly-card';

            const severityClass = `severity-${anomaly.severity.toLowerCase()}`;

            card.innerHTML = `
                <div class="anomaly-header">
                    <span class="anomaly-title">${anomaly.title}</span>
                    <span class="severity-indicator ${severityClass}">${anomaly.severity}</span>
                </div>
                <p class="anomaly-desc">${anomaly.description}</p>
                <div class="anomaly-action">Suggested action: ${anomaly.suggested_action}</div>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        console.error(err);
    }
}

// Health check indicators
async function checkHealth() {
    try {
        const response = await fetch('/health');
        if (!response.ok) throw new Error();
        const data = await response.json();
        
        const dbBadge = document.getElementById('db-status');
        if (data.database_connected) {
            dbBadge.textContent = 'Online';
            dbBadge.className = 'badge badge-connected';
        } else {
            dbBadge.textContent = 'Offline';
            dbBadge.className = 'badge badge-disconnected';
        }

        const freshnessBadge = document.getElementById('freshness-status');
        if (data.feed_stale) {
            freshnessBadge.textContent = 'Stale';
            freshnessBadge.className = 'badge badge-disconnected';
        } else {
            freshnessBadge.textContent = 'Fresh';
            freshnessBadge.className = 'badge badge-connected';
        }
    } catch (err) {
        document.getElementById('db-status').className = 'badge badge-disconnected';
        document.getElementById('db-status').textContent = 'Error';
    }
}

// Setup WebSocket live connection
function setupWebSocket() {
    if (state.ws) {
        state.ws.close();
    }

    clearTimeout(state.wsReconnectTimeout);

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/stores/${state.storeId}/live`;
    
    const wsStatusBadge = document.getElementById('ws-status');
    wsStatusBadge.textContent = 'Connecting';
    wsStatusBadge.className = 'badge badge-unknown';

    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        state.isWsConnected = true;
        wsStatusBadge.textContent = 'Live';
        wsStatusBadge.className = 'badge badge-connected';
        clearInterval(state.pollingInterval); // Disable polling backup
    };

    state.ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.events && data.events.length > 0) {
                appendEventsToFeed(data.events);
                // Refresh dashboard summaries to account for new events
                fetchMetrics();
                fetchHeatmap();
                fetchFunnel();
                fetchAnomalies();
            }
        } catch (err) {
            console.error('Error parsing live WS payload', err);
        }
    };

    state.ws.onclose = () => {
        state.isWsConnected = false;
        wsStatusBadge.textContent = 'Offline';
        wsStatusBadge.className = 'badge badge-disconnected';
        
        // Trigger backup polling
        if (!state.pollingInterval) {
            state.pollingInterval = setInterval(() => {
                fetchMetrics();
                fetchHeatmap();
                fetchFunnel();
                fetchAnomalies();
            }, 5000);
        }

        // Schedule Reconnect
        state.wsReconnectTimeout = setTimeout(setupWebSocket, 3000);
    };

    state.ws.onerror = (err) => {
        console.error('WebSocket encountered an error', err);
        state.ws.close();
    };
}

// Append new live events to feed
function appendEventsToFeed(events) {
    const feedBody = document.getElementById('event-feed-rows');
    
    // Remove empty placeholder if present
    const emptyRow = feedBody.querySelector('.empty-feed');
    if (emptyRow) {
        feedBody.innerHTML = '';
    }

    events.forEach(event => {
        const row = document.createElement('tr');
        row.className = 'new-row-highlight';

        // Format Date
        const time = new Date(event.occurred_at);
        const timeStr = time.toTimeString().split(' ')[0] + '.' + String(time.getMilliseconds()).padStart(3, '0');

        row.innerHTML = `
            <td><strong>${timeStr}</strong></td>
            <td><code>${event.camera_id}</code></td>
            <td><span class="event-type-badge">${event.event_type}</span></td>
            <td>${event.zone_id ? event.zone_id : '<span style="color: #64748b;">-</span>'}</td>
            <td>${event.global_person_id ? event.global_person_id : 'anonymous'} (${event.person_type})</td>
            <td>${(event.confidence * 100).toFixed(0)}%</td>
        `;

        // Insert at the top
        feedBody.insertBefore(row, feedBody.firstChild);
    });

    // Limit to 20 rows
    while (feedBody.children.length > 20) {
        feedBody.removeChild(feedBody.lastChild);
    }
}

function renderCameraTopology() {
    const topology = document.getElementById('camera-topology');
    if (!topology) return;

    const fallbackStoreId = "00000000-0000-4000-8000-000000001008";
    const details = state.knownStoreNames[state.storeId] || state.knownStoreNames[fallbackStoreId];
    const cameras = details.cameras || [];

    topology.innerHTML = cameras.map((camera, index) => {
        const cameraName = camera.toLowerCase();
        const role = cameraName.includes('billing')
            ? 'billing'
            : cameraName.includes('entry')
                ? 'entrance'
                : 'zone';
        const connector = index < cameras.length - 1 ? '<div class="camera-path"></div>' : '';
        return `<div class="camera-node ${role}"><span>CAM</span>${camera}</div>${connector}`;
    }).join('');
}

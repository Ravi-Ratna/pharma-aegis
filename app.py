from flask import Flask, jsonify, render_template_string, request
import serial
import json
import time
from threading import Thread, Lock
import platform
import random
from agents import data_analyzer, risk_evaluator, decision_agent, action_agent
from models import SensorReading

app = Flask(__name__)

PORT = 'COM5'
BAUD = 115200

# ── Arduino Door Controller serial config ────────────────────────────────────
# Change ARDUINO_PORT to whichever COM port your Arduino is on
ARDUINO_PORT = 'COM6'
ARDUINO_BAUD = 9600

ser = None
arduino_ser = None
arduino_lock = Lock()
latest_data = {"air_quality": 0, "fire": 0, "vibration": 0, "timestamp": "N/A"}
latest_analysis = {
    "sensor_data": {"air_quality": 0, "fire": 0, "vibration": 0, "timestamp": ""},
    "analysis": {"vibration": "normal", "fire": "safe", "anomaly_score": 0},
    "risk": {"level": "LOW", "reason": "Initializing..."},
    "decision": {"action": "MONITOR", "requires_human": False},
    "action": {"led": "GREEN_SOLID", "buzzer": "OFF", "log_level": "INFO", "log_message": "Initializing..."}
}
data_lock = Lock()
connection_status = "⏳ Initializing..."


def connect_arduino():
    """Try to open a serial connection to the Arduino door controller."""
    global arduino_ser
    try:
        arduino_ser = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1)
        time.sleep(2)  # Wait for Arduino bootloader to finish
        print(f"✅ Arduino door controller connected on {ARDUINO_PORT}")
    except Exception as e:
        print(f"⚠️  Arduino not found on {ARDUINO_PORT}: {e}")
        print(f"   → Door controller commands will be skipped until reconnected")
        arduino_ser = None


def send_arduino_command(door: str, led: str):
    """Send a JSON command line to the Arduino door controller.

    Args:
        door: "open" | "close"
        led:  "red"  | "green" | "off"
    """
    global arduino_ser
    cmd = json.dumps({"door": door, "led": led}) + "\n"

    with arduino_lock:
        if arduino_ser and arduino_ser.is_open:
            try:
                arduino_ser.write(cmd.encode())
            except Exception as e:
                print(f"⚠️  Arduino send error: {e} — will skip future commands")
                try:
                    arduino_ser.close()
                except Exception:
                    pass
                arduino_ser = None
        # Silently skip if Arduino is not connected


def run_agent_pipeline(sensor_payload):
    """Run all 4 agents and build a normalized output bundle."""
    # Handle ESP32 data format conversion: "air" -> synthetic temperature/humidity
    air_quality = float(sensor_payload.get("air", 400.0))  # Default ~400 ppm CO2

    # Convert air quality to synthetic temperature/humidity for analysis
    # Higher air quality value = more CO2/contaminants = simulate temp/humidity stress
    if air_quality < 350:  # Very clean air
        synth_temp = 20.0
        synth_humid = 45.0
    elif air_quality < 450:  # Good air
        synth_temp = 22.0
        synth_humid = 50.0
    elif air_quality < 600:  # Acceptable
        synth_temp = 24.0
        synth_humid = 60.0
    elif air_quality < 800:  # Fair
        synth_temp = 26.0
        synth_humid = 70.0
    else:  # Poor air quality
        synth_temp = 28.0
        synth_humid = 80.0

    reading = SensorReading(
        temperature=float(sensor_payload.get("temperature", synth_temp)),
        humidity=float(sensor_payload.get("humidity", synth_humid)),
        vibration=float(sensor_payload.get("vibration", 1.0)),
        fire=int(sensor_payload.get("fire", 0)),
    )

    analysis = data_analyzer(reading)
    risk = risk_evaluator(analysis)
    decision = decision_agent(risk)
    action = action_agent(decision, risk, analysis)

    # ── Arduino door & LED commands derived from agent analysis ──────────────
    # Door: close on elevated or high vibration, open when normal
    door_cmd = "close" if analysis.vibration_status in ("elevated", "high") else "open"

    # LED: red on high humidity, green on low humidity, off when optimal
    if analysis.humidity_status in ("humid", "too_humid"):
        led_cmd = "red"
    elif analysis.humidity_status in ("dry", "too_dry"):
        led_cmd = "green"
    else:
        led_cmd = "off"

    send_arduino_command(door_cmd, led_cmd)
    print(f"🚪 Arduino | Door: {door_cmd.upper()} | LED: {led_cmd.upper()}")

    # Include original ESP32 data in response (air quality, fire, vibration)
    sensor_data_out = {
        "air_quality": air_quality,
        "fire": sensor_payload.get("fire", 0),
        "vibration": sensor_payload.get("vibration", 1.0),
        "timestamp": sensor_payload.get("timestamp", ""),
    }

    return {
        "sensor_data": sensor_data_out,
        "analysis": {
            "vibration": analysis.vibration_status,
            "fire": analysis.fire_status,
            "anomaly_score": analysis.anomaly_score,
            "compliance_score": analysis.compliance_score,
            "recommendations": analysis.recommendations,
            "trends": {
                "vibration": {"trend": analysis.trends.get("vibration", ("stable", 0))[0], "change_pct": round(analysis.trends.get("vibration", ("stable", 0))[1], 1)},
            }
        },
        "risk": {
            "level": risk.risk_level,
            "reason": risk.reason,
            "risk_score": risk.risk_score,
            "confidence": risk.confidence,
        },
        "decision": {
            "action": decision.decision,
            "requires_human": decision.requires_human,
            "urgency": decision.urgency,
        },
        "action": {
            "led": action.led,
            "buzzer": action.buzzer,
            "log_level": action.log_level,
            "log_message": action.log_message,
        },
    }

def find_com_ports():
    """Find available COM ports"""
    ports = []
    if platform.system() == 'Windows':
        import winreg
        try:
            reg = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,
                                   r"HARDWARE\DEVICEMAP\SERIALCOMM")
            for i in range(winreg.QueryInfoKey(reg)[1]):
                try:
                    name, value, _ = winreg.EnumValue(reg, i)
                    ports.append(value)
                except:
                    pass
        except:
            pass
    elif platform.system() == 'Linux':
        import glob
        ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')

    return ports if ports else ["COM1", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9"]


def find_preferred_port():
    """Prefer the actual USB serial device when available."""
    try:
        from serial.tools import list_ports
        detected = list(list_ports.comports())
        if not detected:
            return None

        # Prefer common USB bridge identifiers used by ESP boards.
        preferred_keywords = ("CH910", "CH340", "CP210", "USB", "UART", "Silicon Labs")
        for p in detected:
            desc = (p.description or "").upper()
            if any(keyword.upper() in desc for keyword in preferred_keywords):
                return p.device

        return detected[0].device
    except Exception:
        return None

# 🌐 HTML Dashboard - Enhanced Professional
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Pharma Aegis - Advanced Monitoring System</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: white;
            border-radius: 20px;
            padding: 40px;
            margin-bottom: 30px;
            box-shadow: 0 15px 40px rgba(0,0,0,0.2);
        }
        h1 {
            color: #333;
            font-size: 36px;
            margin-bottom: 5px;
        }
        .status-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 2px solid #f0f0f0;
        }
        .status-text {
            font-size: 14px;
            color: #666;
        }
        .demo-badge {
            background: #ff9800;
            color: white;
            padding: 8px 16px;
            border-radius: 25px;
            font-size: 12px;
            font-weight: bold;
        }
        .grid-1 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }
        .card:hover { transform: translateY(-5px); }
        .card h2 {
            color: #667eea;
            font-size: 14px;
            margin-bottom: 20px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            font-weight: 600;
        }
        /* Sensor Readings */
        .reading-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #f5f5f5;
        }
        .reading-row:last-child { border-bottom: none; }
        .reading-label {
            font-size: 13px;
            color: #666;
            font-weight: 500;
        }
        .reading-value {
            font-size: 20px;
            font-weight: bold;
            color: #333;
            font-family: 'Courier New', monospace;
        }
        .reading-unit {
            font-size: 12px;
            color: #999;
            margin-left: 5px;
        }
        .trend-indicator {
            display: inline-block;
            font-size: 16px;
            margin-left: 10px;
        }
        /* Compliance Score */
        .compliance-display {
            text-align: center;
            padding: 20px;
        }
        .compliance-circle {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            margin: 0 auto 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 48px;
            font-weight: bold;
            color: white;
            position: relative;
        }
        .compliance-90-100 { background: linear-gradient(135deg, #4CAF50, #66BB6A); }
        .compliance-70-89 { background: linear-gradient(135deg, #FFC107, #FFB300); }
        .compliance-50-69 { background: linear-gradient(135deg, #FF9800, #FB8C00); }
        .compliance-below-50 { background: linear-gradient(135deg, #f44336, #E53935); }
        .compliance-label {
            font-size: 12px;
            color: #666;
            margin-top: 10px;
            font-weight: 500;
        }
        /* Trends */
        .trend-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #f5f5f5;
        }
        .trend-item:last-child { border-bottom: none; }
        .trend-name {
            font-size: 13px;
            color: #666;
            flex: 1;
        }
        .trend-direction {
            font-size: 18px;
            width: 25px;
            text-align: center;
        }
        .trend-percent {
            font-size: 13px;
            color: #999;
            width: 50px;
            text-align: right;
            font-family: 'Courier New', monospace;
        }
        /* Status Badges */
        .status-badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .status-optimal { background: #E8F5E9; color: #2E7D32; }
        .status-warning { background: #FFF3E0; color: #E65100; }
        .status-danger { background: #FFEBEE; color: #B71C1C; }
        /* Risk Assessment */
        .risk-main {
            text-align: center;
        }
        .risk-level-display {
            font-size: 54px;
            font-weight: bold;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 15px;
            margin-top: 10px;
            animation: softPulse 2s ease-in-out infinite;
        }
        .risk-low { background: #C8E6C9; color: #1B5E20; }
        .risk-medium { background: #FFE0B2; color: #E65100; }
        .risk-high { background: #FFCCBC; color: #D84315; }
        .risk-critical { background: #FFCDD2; color: #B71C1C; animation: fastPulse 0.8s ease-in-out infinite; }
        @keyframes softPulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.9; }
        }
        @keyframes fastPulse {
            0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(244, 67, 54, 0.7); }
            50% { opacity: 0.8; box-shadow: 0 0 0 10px rgba(244, 67, 54, 0); }
        }
        .risk-reason {
            font-size: 13px;
            color: #666;
            margin-top: 12px;
            font-style: italic;
        }
        .risk-metrics {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-top: 15px;
        }
        .metric-box {
            background: #f5f5f5;
            padding: 12px;
            border-radius: 8px;
            font-size: 12px;
        }
        .metric-label {
            color: #999;
            font-size: 11px;
            text-transform: uppercase;
        }
        .metric-value {
            font-size: 16px;
            font-weight: bold;
            color: #333;
            margin-top: 5px;
        }
        /* Decision Card */
        .decision-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .decision-action {
            font-size: 32px;
            font-weight: bold;
            padding: 25px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            margin: 15px 0;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .urgency-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: bold;
            background: rgba(255,255,255,0.2);
            margin-top: 10px;
        }
        /* Recommendations */
        .recommendations {
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
            padding: 15px;
            border-radius: 10px;
            border-left: 4px solid #667eea;
        }
        .recommendation-item {
            padding: 8px 0;
            font-size: 13px;
            color: #333;
        }
        .recommendation-item:before {
            content: "→ ";
            color: #667eea;
            font-weight: bold;
            margin-right: 8px;
        }
        /* Footer */
        .footer {
            text-align: center;
            color: white;
            margin-top: 30px;
            font-size: 12px;
            padding: 15px;
            border-top: 1px solid rgba(255,255,255,0.2);
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🏥 Pharma Aegis <span id="demoBadge"></span></h1>
            <div class="status-bar">
                <div class="status-text" id="status">● Initializing...</div>
                <div class="status-text" id="timestamp" style="text-align: right;">--:--:--</div>
            </div>
        </div>

        <!-- Main Grid: Sensors, Compliance, Risk -->
        <div class="grid-1">
            <!-- Sensor Readings -->
            <div class="card">
                <h2>📊 Sensor Data</h2>
                <div id="sensorReadings">
                    <div style="text-align: center; color: #ccc; padding: 20px;">Waiting...</div>
                </div>
            </div>

            <!-- Compliance Score -->
            <div class="card">
                <h2>✅ Compliance Score</h2>
                <div class="compliance-display">
                    <div class="compliance-circle" id="complianceCircle">--</div>
                    <div class="compliance-label">Facility Compliance</div>
                </div>
            </div>

            <!-- Trends -->
            <div class="card">
                <h2>📈 Trends (Last 30 samples)</h2>
                <div id="trendsDisplay">
                    <div style="text-align: center; color: #ccc; padding: 20px;">Analyzing...</div>
                </div>
            </div>
        </div>

        <!-- Analysis & Risk Grid -->
        <div class="grid-2" style="margin-top: 20px;">
            <!-- Analysis Results -->
            <div class="card">
                <h2>🔍 Status Analysis</h2>
                <div id="analysisResults">
                    <div style="text-align: center; color: #ccc; padding: 20px;">Analyzing...</div>
                </div>
            </div>

            <!-- Risk Assessment -->
            <div class="card risk-main">
                <h2>⚠️  Risk Assessment</h2>
                <div class="risk-level-display" id="riskLevel">--</div>
                <div class="risk-reason" id="riskReason">--</div>
                <div class="risk-metrics">
                    <div class="metric-box">
                        <div class="metric-label">Risk Score</div>
                        <div class="metric-value" id="riskScore">--</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">Confidence</div>
                        <div class="metric-value" id="confidence">--</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Decision & Recommendations -->
        <div class="grid-2" style="margin-top: 20px;">
            <!-- Decision Card -->
            <div class="card decision-card">
                <h2 style="color: rgba(255,255,255,0.9);">✅ Recommended Action</h2>
                <div class="decision-action" id="decision">--</div>
                <div style="text-align: center;">
                    <div class="urgency-badge" id="urgency">--</div>
                    <div style="margin-top: 12px; font-size: 12px;" id="humanReview">--</div>
                </div>
            </div>

            <!-- Recommendations -->
            <div class="card">
                <h2>💡 Recommendations</h2>
                <div class="recommendations" id="recommendationsBox">
                    <div class="recommendation-item" style="color: #ccc;">Waiting for analysis...</div>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <div class="footer">
            Pharma Aegis v1.0 | Real-time Environmental Monitoring System
        </div>
    </div>

    <script>
        function getComplianceClass(score) {
            if (score >= 90) return 'compliance-90-100';
            if (score >= 70) return 'compliance-70-89';
            if (score >= 50) return 'compliance-50-69';
            return 'compliance-below-50';
        }

        function getRiskClass(level) {
            if (level === 'LOW') return 'risk-low';
            if (level === 'MEDIUM') return 'risk-medium';
            if (level === 'HIGH') return 'risk-high';
            if (level === 'CRITICAL') return 'risk-critical';
            return 'risk-low';
        }

        function getStatusClass(status) {
            if (status.includes('optimal') || status.includes('normal') || status.includes('safe')) return 'status-optimal';
            if (status.includes('warm') || status.includes('cool') || status.includes('elevated') || status.includes('humid') || status.includes('dry')) return 'status-warning';
            if (status.includes('too_') || status.includes('high') || status.includes('detected')) return 'status-danger';
            return 'status-optimal';
        }

        function getTrendIcon(trend) {
            if (trend === 'rising') return '📈';
            if (trend === 'falling') return '📉';
            return '➡️';
        }

        function updateData() {
            const eventSource = new EventSource('/stream');

            eventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);

                    // Sensor Readings
                    const sensorHtml = Object.entries(data.sensor_data || {})
                        .filter(([k]) => !['timestamp'].includes(k))
                        .map(([key, value]) => {
                            const formatted = typeof value === 'number' ? value.toFixed(2) : value;
                            let unit = '';
                            let label = key.replace(/_/g, ' ').toUpperCase();

                            if (key === 'air_quality') {
                                unit = 'ppm';
                                label = 'AIR QUALITY';
                            } else if (key === 'vibration') {
                                unit = 'g';
                            }

                            return `
                                <div class="reading-row">
                                    <span class="reading-label">${label}</span>
                                    <span>
                                        <span class="reading-value">${formatted}</span>
                                        <span class="reading-unit">${unit}</span>
                                    </span>
                                </div>
                            `;
                        }).join('');
                    document.getElementById('sensorReadings').innerHTML = sensorHtml || '<div style="color: #ccc; text-align: center; padding: 20px;">No data</div>';

                    // Compliance Score
                    const analysis = data.analysis || {};
                    const compliance = analysis.compliance_score || 100;
                    const complianceClass = getComplianceClass(compliance);
                    document.getElementById('complianceCircle').className = `compliance-circle ${complianceClass}`;
                    document.getElementById('complianceCircle').textContent = compliance + '%';

                    // Trends
                    const trends = analysis.trends || {};
                    const trendsHtml = Object.entries(trends).map(([key, val]) => {
                        const trend = val.trend || 'stable';
                        const pct = val.change_pct || 0;
                        const icon = getTrendIcon(trend);
                        return `
                            <div class="trend-item">
                                <span class="trend-name">${key.replace(/_/g, ' ')}</span>
                                <span class="trend-direction">${icon}</span>
                                <span class="trend-percent">${(pct >= 0 ? '+' : '')}${pct.toFixed(1)}%</span>
                            </div>
                        `;
                    }).join('');
                    document.getElementById('trendsDisplay').innerHTML = trendsHtml || '<div style="color: #ccc; text-align: center;">No trend data</div>';

                    // Analysis Results
                    const analysisHtml = Object.entries(analysis)
                        .filter(([k]) => !['anomaly_score', 'compliance_score', 'recommendations', 'trends', 'temperature', 'humidity'].includes(k))
                        .map(([key, value]) => `
                            <div class="reading-row">
                                <span class="reading-label">${key.replace(/_/g, ' ').toUpperCase()}</span>
                                <span class="status-badge ${getStatusClass(value)}">${value}</span>
                            </div>
                        `).join('') + `
                        <div class="reading-row" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #f5f5f5;">
                            <span class="reading-label">ANOMALY SCORE</span>
                            <span class="reading-value">${analysis.anomaly_score || 0}</span>
                        </div>
                    `;
                    document.getElementById('analysisResults').innerHTML = analysisHtml || '<div style="color: #ccc; text-align: center;">Analyzing...</div>';

                    // Risk Assessment
                    const risk = data.risk || {};
                    const riskClass = getRiskClass(risk.level);
                    document.getElementById('riskLevel').className = `risk-level-display ${riskClass}`;
                    document.getElementById('riskLevel').textContent = risk.level || '--';
                    document.getElementById('riskReason').textContent = risk.reason || '--';
                    document.getElementById('riskScore').textContent = (risk.risk_score || 0).toFixed(0);
                    document.getElementById('confidence').textContent = ((risk.confidence || 0) * 100).toFixed(0) + '%';

                    // Decision
                    const decision = data.decision || {};
                    document.getElementById('decision').textContent = decision.action || '--';
                    document.getElementById('urgency').textContent = '🎚️ ' + (decision.urgency || 'low').toUpperCase();
                    document.getElementById('humanReview').textContent = decision.requires_human
                        ? '👤 Human Review Required'
                        : '✅ Autonomous Control';

                    // Recommendations
                    const recs = analysis.recommendations || [];
                    const recsHtml = recs.length > 0
                        ? recs.map(rec => `<div class="recommendation-item">${rec}</div>`).join('')
                        : '<div class="recommendation-item" style="color: #999;">No recommendations at this time</div>';
                    document.getElementById('recommendationsBox').innerHTML = recsHtml;

                    // Status
                    document.getElementById('status').textContent = '✅ Connected & Monitoring (Real-time ESP32 Data)';
                    document.getElementById('timestamp').textContent = new Date().toLocaleTimeString();
                } catch(e) {
                    console.error('Error:', e);
                }
            };

            eventSource.onerror = function() {
                document.getElementById('status').textContent = '⏳ Reconnecting...';
            };
        }

        updateData();
    </script>
</body>
</html>
"""

def read_sensor():
    """Background thread to continuously read sensor data from ESP32 - REAL DATA ONLY"""
    global ser, latest_data, latest_analysis, connection_status, PORT

    preferred_port = find_preferred_port()
    available_ports = find_com_ports()
    if preferred_port and preferred_port in available_ports:
        available_ports.remove(preferred_port)
        available_ports.insert(0, preferred_port)
    elif preferred_port and preferred_port not in available_ports:
        available_ports.insert(0, preferred_port)

    print(f"Available COM ports: {available_ports}")

    # Try each port until one works
    for attempt_port in available_ports:
        try:
            PORT = attempt_port
            print(f"🔍 Attempting to connect to {attempt_port}...")
            ser = serial.Serial(attempt_port, BAUD, timeout=1)
            print(f"✅ Serial connected on {PORT}")
            connection_status = f"✅ Connected on {PORT}"

            time.sleep(5)  # 🔥 wait for ESP reset
            print("⏳ Waiting for ESP READY signal...")

            # Wait until ESP says READY or starts sending JSON.
            start = time.time()
            ready_seen = False
            while time.time() - start < 10:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    print("INIT:", line)
                    if "READY" in line or line.startswith("{"):
                        print("✅ ESP Active")
                        ready_seen = True
                        break

            if not ready_seen:
                print("⚠️ READY signal not seen in 10s, continuing to read stream...")

            # Now read sensor data in a loop
            while True:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    print("RAW:", line)

                    if line.startswith("{"):
                        try:
                            data = json.loads(line)
                            data['timestamp'] = time.strftime('%H:%M:%S')

                            with data_lock:
                                latest_data = data.copy()
                                latest_analysis = run_agent_pipeline(data)

                            print(f"✅ Updated: {latest_data}")
                            print(
                                f"🧠 Agents | Risk: {latest_analysis['risk']['level']} "
                                f"| Decision: {latest_analysis['decision']['action']} "
                                f"| LED: {latest_analysis['action']['led']} "
                                f"| Buzzer: {latest_analysis['action']['buzzer']}"
                            )
                            print(f"📝 {latest_analysis['action']['log_level']}: {latest_analysis['action']['log_message']}")
                        except Exception as e:
                            print(f"Parse error: {e}")
            break  # Exit port loop if successful

        except (OSError, serial.SerialException) as e:
            print(f"❌ Failed on {attempt_port}: {e}")
            if ser:
                try:
                    ser.close()
                except:
                    pass
            ser = None
            connection_status = f"❌ Port {attempt_port} failed: {str(e)[:50]}"
            time.sleep(1)  # Wait before trying next port

    if not ser:
        print(f"\n⚠️  Could not connect to any serial port!")
        print(f"📝 Troubleshooting:")
        print(f"   1. Check if device is plugged in to {PORT}")
        print(f"   2. Verify COM port in Device Manager")
        print(f"   3. Close any other programs using the port")
        print(f"   4. Try a different USB cable or port")
        print(f"   5. Restart the ESP32 and ensure it's sending JSON data\n")
        connection_status = "❌ No serial connection - Check ESP32 and cables"


@app.route("/")
def dashboard():
    """Serve the live dashboard"""
    return render_template_string(DASHBOARD_HTML)


@app.route("/debug", methods=["GET"])
def debug():
    """Return debug information"""
    return jsonify({
        "available_ports": find_com_ports(),
        "current_port": PORT,
        "connection_status": connection_status,
        "latest_data": latest_data,
        "latest_analysis": latest_analysis
    })


@app.route("/sensor/latest", methods=["GET"])
def get_sensor():
    """Get latest sensor data as JSON"""
    with data_lock:
        return jsonify(latest_data)


@app.route("/stream", methods=["GET"])
def stream():
    """Server-Sent Events stream for live updates"""
    def generate():
        while True:
            with data_lock:
                response_data = latest_analysis.copy() if latest_analysis else {
                    "sensor_data": {},
                    "analysis": {},
                    "risk": {},
                    "decision": {},
                    "action": {},
                }
            yield f"data: {json.dumps(response_data)}\n\n"
            time.sleep(0.5)

    return app.response_class(generate(), mimetype='text/event-stream')


if __name__ == "__main__":
    # Connect to Arduino door controller (non-blocking — failure is OK)
    arduino_thread = Thread(target=connect_arduino, daemon=True)
    arduino_thread.start()

    # Start ESP32 sensor reading in background thread
    sensor_thread = Thread(target=read_sensor, daemon=True)
    sensor_thread.start()

    print("\n🚀 Starting Pharma Aegis Dashboard...")
    print("📊 Open your browser: http://localhost:5000")
    print(f"🚪 Arduino door controller port: {ARDUINO_PORT}")
    print("=" * 50)

    app.run(host="0.0.0.0", port=5000, debug=False)

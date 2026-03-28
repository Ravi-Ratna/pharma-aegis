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
DEMO_MODE = False  # Use real serial sensor data by default

ser = None
latest_data = {"status": "Waiting for connection...", "timestamp": "N/A"}
latest_analysis = {
    "analysis": {"temperature": "normal", "humidity": "normal", "vibration": "normal", "fire": "safe", "anomaly_score": 0},
    "risk": {"level": "LOW", "reason": "Initializing..."},
    "decision": {"action": "MONITOR", "requires_human": False},
    "action": {"led": "GREEN_SOLID", "buzzer": "OFF", "log_level": "INFO", "log_message": "Initializing..."}
}
data_lock = Lock()
connection_status = "⏳ Initializing..."
demo_enabled = DEMO_MODE


def run_agent_pipeline(sensor_payload):
    """Run all 4 agents and build a normalized output bundle."""
    reading = SensorReading(
        temperature=float(sensor_payload.get("temperature", 20.0)),
        humidity=float(sensor_payload.get("humidity", 50.0)),
        vibration=float(sensor_payload.get("vibration", 1.0)),
        fire=int(sensor_payload.get("fire", 1)),
    )

    analysis = data_analyzer(reading)
    risk = risk_evaluator(analysis)
    decision = decision_agent(risk)
    action = action_agent(decision, risk, analysis)

    return {
        "analysis": {
            "temperature": analysis.temperature_status,
            "humidity": analysis.humidity_status,
            "vibration": analysis.vibration_status,
            "fire": analysis.fire_status,
            "anomaly_score": analysis.anomaly_score,
        },
        "risk": {
            "level": risk.risk_level,
            "reason": risk.reason,
        },
        "decision": {
            "action": decision.decision,
            "requires_human": decision.requires_human,
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

# 🌐 HTML Dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Pharma Aegis - Live Sensor Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            background: white;
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            text-align: center;
        }
        h1 {
            color: #333;
            font-size: 32px;
            margin-bottom: 10px;
        }
        .demo-badge {
            display: inline-block;
            background: #ff9800;
            color: white;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 10px;
        }
        .status-bar {
            text-align: center;
            font-size: 14px;
            color: #666;
            margin-top: 10px;
        }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .card h2 {
            color: #667eea;
            font-size: 16px;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .sensor-reading {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #f0f0f0;
        }
        .sensor-reading:last-child { border-bottom: none; }
        .sensor-name {
            color: #666;
            font-weight: 500;
        }
        .sensor-value {
            font-size: 18px;
            font-weight: bold;
            color: #333;
            font-family: 'Courier New', monospace;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .status-optimal { background: #4CAF50; color: white; }
        .status-warning { background: #ff9800; color: white; }
        .status-danger { background: #f44336; color: white; }
        .status-safe { background: #4CAF50; color: white; }
        .status-detected { background: #f44336; color: white; }
        .risk-card {
            text-align: center;
            padding: 30px;
        }
        .risk-level {
            font-size: 48px;
            font-weight: bold;
            margin-bottom: 15px;
            padding: 20px;
            border-radius: 10px;
        }
        .risk-low { background: #c8e6c9; color: #2e7d32; }
        .risk-medium { background: #ffe0b2; color: #e65100; }
        .risk-high { background: #ffccbc; color: #d84315; }
        .risk-critical { background: #ffcdd2; color: #b71c1c; animation: pulse 1s infinite; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.8; }
        }
        .risk-reason {
            color: #666;
            font-size: 14px;
            margin-top: 15px;
            font-style: italic;
        }
        .decision-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            padding: 30px;
        }
        .decision-action {
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 15px;
            text-transform: uppercase;
        }
        .human-review {
            background: rgba(255,255,255,0.2);
            padding: 10px;
            border-radius: 8px;
            margin-top: 15px;
            font-size: 12px;
        }
        .full-width { grid-column: 1 / -1; }
        .timestamp {
            text-align: center;
            color: #999;
            font-size: 12px;
            margin-top: 20px;
        }
        .grid-row { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; }
        .mini-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        .mini-card-label { font-size: 11px; opacity: 0.9; text-transform: uppercase; }
        .mini-card-value { font-size: 24px; font-weight: bold; margin-top: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏥 Pharma Aegis <span id="demoBadge"></span></h1>
            <div class="status-bar" id="status">● Initializing...</div>
        </div>

        <div class="grid">
            <!-- Sensor Readings -->
            <div class="card">
                <h2>📊 Sensor Readings</h2>
                <div id="sensorReadings">
                    <div style="text-align: center; color: #999;">Waiting for data...</div>
                </div>
            </div>

            <!-- Analysis Results -->
            <div class="card">
                <h2>🔍 Analysis Status</h2>
                <div id="analysisResults">
                    <div style="text-align: center; color: #999;">Analyzing...</div>
                </div>
            </div>

            <!-- Risk Assessment -->
            <div class="card risk-card">
                <h2 style="text-align: left; margin-bottom: 20px;">⚠️  Risk Level</h2>
                <div class="risk-level" id="riskLevel">--</div>
                <div class="risk-reason" id="riskReason">--</div>
            </div>

            <!-- Decision/Action -->
            <div class="card decision-card">
                <h2 style="text-align: left; margin-bottom: 20px; color: white;">✅ Recommended Action</h2>
                <div class="decision-action" id="decision">--</div>
                <div class="human-review" id="humanReview">--</div>
            </div>
        </div>

        <div class="timestamp">
            Last Updated: <span id="timestamp">--:--:--</span>
        </div>
    </div>

    <script>
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

        function updateData() {
            const eventSource = new EventSource('/stream');
            
            eventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    console.log('Received:', data);
                    
                    // Update sensor readings
                    const sensorHtml = Object.entries(data.sensor_data || {})
                        .filter(([k]) => !['timestamp', 'fire'].includes(k))
                        .map(([key, value]) => {
                            const formatted = typeof value === 'number' ? value.toFixed(2) : value;
                            const unit = key === 'temperature' ? '°C' : key === 'humidity' ? '%' : '';
                            return `
                                <div class="sensor-reading">
                                    <span class="sensor-name">${key.replace(/_/g, ' ').toUpperCase()}</span>
                                    <span class="sensor-value">${formatted}${unit}</span>
                                </div>
                            `;
                        }).join('');
                    document.getElementById('sensorReadings').innerHTML = sensorHtml || '<div style="color: #999;">No data</div>';
                    
                    // Update analysis results
                    const analysis = data.analysis || {};
                    const analysisHtml = Object.entries(analysis)
                        .filter(([k]) => k !== 'anomaly_score')
                        .map(([key, value]) => `
                            <div class="sensor-reading">
                                <span class="sensor-name">${key.replace(/_/g, ' ').toUpperCase()}</span>
                                <span class="status-badge ${getStatusClass(value)}">${value}</span>
                            </div>
                        `).join('') + `
                        <div class="sensor-reading">
                            <span class="sensor-name">ANOMALY SCORE</span>
                            <span class="sensor-value">${analysis.anomaly_score || 0}</span>
                        </div>
                    `;
                    document.getElementById('analysisResults').innerHTML = analysisHtml || '<div style="color: #999;">Analyzing...</div>';
                    
                    // Update risk level
                    const risk = data.risk || {};
                    const riskClass = getRiskClass(risk.level);
                    document.getElementById('riskLevel').className = `risk-level ${riskClass}`;
                    document.getElementById('riskLevel').textContent = risk.level || '--';
                    document.getElementById('riskReason').textContent = risk.reason || '--';
                    
                    // Update decision
                    const decision = data.decision || {};
                    document.getElementById('decision').textContent = decision.action || '--';
                    document.getElementById('humanReview').textContent = decision.requires_human 
                        ? '👤 Human Review Required' 
                        : '✅ Autonomous Monitoring';
                    
                    // Update status
                    document.getElementById('status').textContent = '✅ Connected & Analyzing';
                    document.getElementById('timestamp').textContent = new Date().toLocaleTimeString();
                    
                    // Demo badge
                    if (data.demo_mode) {
                        document.getElementById('demoBadge').innerHTML = '<span class="demo-badge">🎮 DEMO MODE</span>';
                    }
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
    """Background thread to continuously read sensor data"""
    global ser, latest_data, latest_analysis, connection_status, PORT, demo_enabled
    
    if demo_enabled:
        print("\n🎮 DEMO MODE ENABLED - Generating simulated sensor data\n")
        connection_status = "🎮 DEMO MODE - Simulated Data"
        demo_counter = 0
        
        while True:
            demo_counter += 1
            with data_lock:
                # Generate demo data
                temp = round(22 + random.uniform(-2, 2), 2)
                humid = round(55 + random.uniform(-10, 10), 2)
                vib = round(random.uniform(0.5, 2.5), 3)
                fire = 1
                
                latest_data = {
                    "temperature": temp,
                    "humidity": humid,
                    "vibration": vib,
                    "fire": fire,
                    "timestamp": time.strftime('%H:%M:%S')
                }

                latest_analysis = run_agent_pipeline(latest_data)

            print(
                f"[DEMO #{demo_counter}] Temp: {temp}°C, Humidity: {humid}%, Vibration: {vib} "
                f"| Risk: {latest_analysis['risk']['level']} "
                f"| LED: {latest_analysis['action']['led']} "
                f"| Buzzer: {latest_analysis['action']['buzzer']}"
            )
            time.sleep(1)
        return
    
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
                            with data_lock:
                                latest_data = data
                                latest_data['timestamp'] = time.strftime('%H:%M:%S')
                                latest_analysis = run_agent_pipeline(latest_data)
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
        print(f"   5. Set DEMO_MODE=True to see the dashboard with sample data\n")
        connection_status = "❌ No serial connection - Enable DEMO_MODE to test"


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
        "demo_mode": demo_enabled,
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
                response_data = {
                    "sensor_data": latest_data.copy(),
                    "analysis": latest_analysis["analysis"] if latest_analysis else {},
                    "risk": latest_analysis["risk"] if latest_analysis else {},
                    "decision": latest_analysis["decision"] if latest_analysis else {},
                    "action": latest_analysis["action"] if latest_analysis else {},
                    "demo_mode": demo_enabled
                }
            yield f"data: {json.dumps(response_data)}\n\n"
            time.sleep(0.5)
    
    return app.response_class(generate(), mimetype='text/event-stream')


if __name__ == "__main__":
    # Start sensor reading in background thread
    sensor_thread = Thread(target=read_sensor, daemon=True)
    sensor_thread.start()
    
    print("\n🚀 Starting Pharma Aegis Dashboard...")
    print("📊 Open your browser: http://localhost:5000")
    print("=" * 50)
    
    app.run(host="0.0.0.0", port=5000, debug=False)
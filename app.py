from flask import Flask, jsonify, render_template_string, request
import serial
import json
import time
from threading import Thread, Lock
import platform
import random

app = Flask(__name__)

PORT = 'COM5'
BAUD = 115200
DEMO_MODE = True  # Set to True to use fake data for testing

ser = None
latest_data = {"status": "Waiting for connection...", "timestamp": "N/A"}
data_lock = Lock()
connection_status = "⏳ Initializing..."
demo_enabled = DEMO_MODE

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
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 800px;
            width: 100%;
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .status {
            text-align: center;
            font-size: 12px;
            color: #888;
            margin-bottom: 30px;
            padding: 10px;
            border-radius: 5px;
        }
        .status.connected { 
            color: #fff; 
            background: #4CAF50;
        }
        .status.disconnected { 
            color: #fff; 
            background: #f44336;
        }
        .metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .metric {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            transition: transform 0.3s ease;
        }
        .metric:hover { transform: translateY(-5px); }
        .metric-label {
            font-size: 11px;
            opacity: 0.9;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
            word-break: break-word;
        }
        .metric-value {
            font-size: 32px;
            font-weight: bold;
            font-family: 'Courier New', monospace;
            word-break: break-word;
        }
        .timestamp {
            text-align: center;
            color: #999;
            font-size: 12px;
            margin-top: 20px;
            font-family: monospace;
        }
        .controls {
            text-align: center;
            margin-top: 20px;
        }
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.3s;
            margin: 5px;
        }
        button:hover { background: #764ba2; }
        .info-box {
            background: #e3f2fd;
            color: #1565c0;
            padding: 15px;
            border-radius: 5px;
            margin-top: 20px;
            border-left: 4px solid #1565c0;
        }
        .debug-info {
            background: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            margin-top: 20px;
            font-family: monospace;
            font-size: 12px;
            max-height: 300px;
            overflow-y: auto;
            border-left: 4px solid #667eea;
        }
        input[type="text"] {
            padding: 8px 12px;
            border: 2px solid #667eea;
            border-radius: 5px;
            font-size: 14px;
            width: 100px;
        }
        .demo-badge {
            display: inline-block;
            background: #ff9800;
            color: white;
            padding: 4px 8px;
            border-radius: 3px;
            font-size: 10px;
            margin-left: 10px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏥 Pharma Aegis <span id="demoBadge"></span></h1>
        <div class="status disconnected" id="status">● Checking Connection...</div>
        
        <div class="metrics" id="metrics">
            <div style="grid-column: 1 / -1; text-align: center; color: #999;">Waiting for sensor data...</div>
        </div>
        
        <div class="info-box">
            <strong>📡 Connection Troubleshooting:</strong>
            <ul style="margin-top: 10px; margin-left: 20px;">
                <li>Check if ESP32/device is plugged in</li>
                <li>Verify the correct COM port is set (default: COM5)</li>
                <li>Try a different USB cable or port</li>
                <li>Make sure no other app is using the serial port</li>
            </ul>
        </div>

        <div class="debug-info" id="debug">
            <strong>Debug Info:</strong><br>
            <div id="debugLog">Loading...</div>
        </div>
        
        <div class="timestamp">Last Updated: <span id="timestamp">--:--:--</span></div>
        <div class="controls">
            <button onclick="location.reload()">🔄 Refresh</button>
        </div>
    </div>

    <script>
        function formatValue(value) {
            if (typeof value === 'number') {
                if (Number.isInteger(value)) return value.toString();
                return value.toFixed(2);
            }
            return value;
        }

        function renderMetrics(data) {
            const metricsContainer = document.getElementById('metrics');
            metricsContainer.innerHTML = '';
            
            let count = 0;
            for (const [key, value] of Object.entries(data)) {
                if (key === 'timestamp' || key === 'status') continue;
                
                const metric = document.createElement('div');
                metric.className = 'metric';
                
                const label = key.replace(/_/g, ' ').toUpperCase();
                metric.innerHTML = `
                    <div class="metric-label">${label}</div>
                    <div class="metric-value">${formatValue(value)}</div>
                    <div class="metric-unit"></div>
                `;
                metricsContainer.appendChild(metric);
                count++;
            }
            
            if (count === 0) {
                metricsContainer.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; color: #999;">No sensor data received yet...</div>';
            }
        }

        function updateDebug(text) {
            const debugLog = document.getElementById('debugLog');
            const timestamp = new Date().toLocaleTimeString();
            debugLog.innerHTML = `[${timestamp}] ${text}<br>` + debugLog.innerHTML;
            if (debugLog.innerHTML.split('<br>').length > 10) {
                debugLog.innerHTML = debugLog.innerHTML.split('<br>').slice(0, 10).join('<br>');
            }
        }

        function updateData() {
            const eventSource = new EventSource('/stream');
            
            eventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    console.log('Received data:', data);
                    
                    renderMetrics(data);
                    
                    document.getElementById('timestamp').textContent = 
                        new Date().toLocaleTimeString();
                    
                    document.getElementById('status').textContent = '✅ Connected & Receiving Data';
                    document.getElementById('status').className = 'status connected';
                    updateDebug('✅ Data received successfully');
                } catch(e) {
                    console.error('Parse error:', e);
                    updateDebug('❌ Parse error: ' + e.message);
                }
            };
            
            eventSource.onerror = function() {
                document.getElementById('status').textContent = '⏳ Reconnecting...';
                document.getElementById('status').className = 'status';
                updateDebug('⏳ Connection lost, attempting to reconnect...');
            };
        }
        
        updateDebug('🔍 Initializing connection...');
        setTimeout(updateData, 1000);
        
        // Fetch debug info
        fetch('/debug').then(r => r.json()).then(data => {
            updateDebug('Available Ports: ' + data.available_ports.join(', '));
            updateDebug('Current Port: ' + data.current_port);
            updateDebug('Status: ' + data.connection_status);
            
            if (data.demo_mode) {
                document.getElementById('demoBadge').innerHTML = '<span class="demo-badge">🎮 DEMO MODE</span>';
                document.getElementById('status').textContent = '🎮 DEMO MODE - Simulated Data';
                document.getElementById('status').className = 'status connected';
                updateDebug('✅ Running in DEMO MODE with simulated sensor data');
            }
        });
    </script>
</body>
</html>
"""

def read_sensor():
    """Background thread to continuously read sensor data"""
    global ser, latest_data, connection_status, PORT, demo_enabled
    
    if demo_enabled:
        print("\n🎮 DEMO MODE ENABLED - Generating simulated sensor data\n")
        connection_status = "🎮 DEMO MODE - Simulated Data"
        demo_counter = 0
        
        while True:
            demo_counter += 1
            with data_lock:
                latest_data = {
                    "temperature": round(22 + random.uniform(-2, 2), 2),
                    "humidity": round(55 + random.uniform(-10, 10), 2),
                    "vibration": round(random.uniform(0.5, 2.5), 3),
                    "acceleration": round(random.uniform(9.7, 10.0), 3),
                    "pressure": round(1013 + random.uniform(-5, 5), 2),
                    "timestamp": time.strftime('%H:%M:%S')
                }
            print(f"[DEMO #{demo_counter}] {latest_data}")
            time.sleep(1)
        return
    
    available_ports = find_com_ports()
    print(f"Available COM ports: {available_ports}")
    
    # Try each port until one works
    for attempt_port in available_ports:
        try:
            print(f"🔍 Attempting to connect to {attempt_port}...")
            ser = serial.Serial(attempt_port, BAUD, timeout=1)
            PORT = attempt_port
            print(f"✅ Serial connected on {PORT}")
            connection_status = f"✅ Connected on {PORT}"

            time.sleep(5)  # 🔥 wait for ESP reset
            print("⏳ Waiting for ESP READY signal...")

            # 🔥 wait until ESP says READY (with timeout)
            start = time.time()
            while time.time() - start < 10:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    print("INIT:", line)
                    if "READY" in line or line.startswith("{"):
                        print("✅ ESP Active")
                        break

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
                            print(f"✅ Updated: {latest_data}")
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
        "latest_data": latest_data
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
                data = latest_data.copy()
            yield f"data: {json.dumps(data)}\n\n"
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
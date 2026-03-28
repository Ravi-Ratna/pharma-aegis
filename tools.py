import requests

def get_latest_sensor_data():
    try:
        res = requests.get("http://localhost:5000/sensor/latest")
        return res.json()
    except:
        return {"error": "Cannot fetch sensor data"}
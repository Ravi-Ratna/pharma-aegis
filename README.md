# Pharma Aegis

Pharma Aegis is a real-time warehouse monitoring system with a 4-agent pipeline.
It reads sensor values from ESP32, evaluates risk, decides response, and outputs dashboard/hardware/log actions.

## Agent Pipeline

1. Data Analyzer
- Classifies each sensor value into status bands.
- Produces an anomaly score.

2. Risk Evaluator
- Converts sensor statuses + anomaly score into risk level.
- Risk levels: LOW, MEDIUM, HIGH, CRITICAL.

3. Decision Agent
- Chooses action policy from risk level.
- Decisions: MONITOR, CHECK_WAREHOUSE, ALERT_AND_STABILIZE, TRIGGER_EMERGENCY.

4. Action Agent
- Converts decision into concrete outputs:
  - Dashboard payload
  - LED pattern
  - Buzzer pattern
  - Log level/message

## Sensor Thresholds

### Temperature (C)
- optimal: 18.0 to 25.0
- cool (warning): 15.0 to 17.99
- warm (warning): 25.01 to 28.0
- too_cold (critical): below 15.0
- too_hot (critical): above 28.0

### Humidity (%)
- optimal: 35.0 to 60.0
- dry (warning): 30.0 to 34.99
- humid (warning): 60.01 to 70.0
- too_dry (critical): below 30.0
- too_humid (critical): above 70.0

### Vibration
- normal (optimal): 0.0 to 1.0
- elevated (warning): 1.01 to 1.8
- high (critical): above 1.8

### Fire Sensor
- safe default state: 1
- detected fire state: 0

Note: Fire sensor handling is active-low in this project. If your hardware wiring changes, update the mapping.

## Risk Logic

- CRITICAL:
  - fire detected, or
  - two or more sensors in critical bands, or
  - anomaly score >= 5

- HIGH:
  - one critical-band sensor, or
  - anomaly score >= 3

- MEDIUM:
  - anomaly score >= 1

- LOW:
  - no anomalies

## Decision Mapping

- LOW -> MONITOR
- MEDIUM -> CHECK_WAREHOUSE
- HIGH -> ALERT_AND_STABILIZE
- CRITICAL -> TRIGGER_EMERGENCY

## Action Mapping

- LOW:
  - LED: GREEN_SOLID
  - Buzzer: OFF
  - Log: INFO

- MEDIUM:
  - LED: YELLOW_SOLID
  - Buzzer: BEEP_PATTERN_SLOW
  - Log: WARNING

- HIGH:
  - LED: RED_BLINK
  - Buzzer: BEEP_PATTERN_FAST
  - Log: ERROR

- CRITICAL:
  - LED: RED_BLINK_FAST
  - Buzzer: SIREN
  - Log: CRITICAL

## Run

1. Upload ESP sketch in esp/esp.ino.
2. Close Arduino Serial Monitor/Plotter (to free COM port).
3. Start app:

   python app.py

4. Open dashboard:

   http://localhost:5000

5. Debug endpoint:

   http://localhost:5000/debug

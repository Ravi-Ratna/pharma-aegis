"""Pharma Aegis Analysis Agents - Real-time sensor analysis"""
from models import SensorReading, AnalysisResult, RiskResult, DecisionResult, ActionResult
from tools import get_latest_sensor_data


SENSOR_RANGES = {
    "temperature": {
        "optimal": (18.0, 25.0),
        "warning_low": (15.0, 17.99),
        "warning_high": (25.01, 28.0),
    },
    "humidity": {
        "optimal": (35.0, 60.0),
        "warning_low": (30.0, 34.99),
        "warning_high": (60.01, 70.0),
    },
    "vibration": {
        "optimal": (0.0, 1.0),
        "warning": (1.01, 1.8),
    },
}


def data_analyzer(reading: SensorReading) -> AnalysisResult:
    """Analyze raw sensor data and determine status"""
    t_opt_min, t_opt_max = SENSOR_RANGES["temperature"]["optimal"]
    t_warn_low_min, t_warn_low_max = SENSOR_RANGES["temperature"]["warning_low"]
    t_warn_high_min, t_warn_high_max = SENSOR_RANGES["temperature"]["warning_high"]

    if t_opt_min <= reading.temperature <= t_opt_max:
        temperature_status = "optimal"
        temperature_score = 0
    elif t_warn_low_min <= reading.temperature <= t_warn_low_max:
        temperature_status = "cool"
        temperature_score = 1
    elif t_warn_high_min <= reading.temperature <= t_warn_high_max:
        temperature_status = "warm"
        temperature_score = 1
    elif reading.temperature < t_warn_low_min:
        temperature_status = "too_cold"
        temperature_score = 2
    else:
        temperature_status = "too_hot"
        temperature_score = 2

    h_opt_min, h_opt_max = SENSOR_RANGES["humidity"]["optimal"]
    h_warn_low_min, h_warn_low_max = SENSOR_RANGES["humidity"]["warning_low"]
    h_warn_high_min, h_warn_high_max = SENSOR_RANGES["humidity"]["warning_high"]

    if h_opt_min <= reading.humidity <= h_opt_max:
        humidity_status = "optimal"
        humidity_score = 0
    elif h_warn_low_min <= reading.humidity <= h_warn_low_max:
        humidity_status = "dry"
        humidity_score = 1
    elif h_warn_high_min <= reading.humidity <= h_warn_high_max:
        humidity_status = "humid"
        humidity_score = 1
    elif reading.humidity < h_warn_low_min:
        humidity_status = "too_dry"
        humidity_score = 2
    else:
        humidity_status = "too_humid"
        humidity_score = 2

    v_opt_min, v_opt_max = SENSOR_RANGES["vibration"]["optimal"]
    v_warn_min, v_warn_max = SENSOR_RANGES["vibration"]["warning"]

    if v_opt_min <= reading.vibration <= v_opt_max:
        vibration_status = "normal"
        vibration_score = 0
    elif v_warn_min <= reading.vibration <= v_warn_max:
        vibration_status = "elevated"
        vibration_score = 1
    else:
        vibration_status = "high"
        vibration_score = 2

    # Fire sensor is binary; any non-zero value is treated as detected.
    fire_status = "detected" if int(reading.fire) != 0 else "safe"
    fire_score = 6 if fire_status == "detected" else 0

    return AnalysisResult(
        temperature_status=temperature_status,
        humidity_status=humidity_status,
        vibration_status=vibration_status,
        fire_status=fire_status,
        anomaly_score=temperature_score + humidity_score + vibration_score + fire_score,
    )


def risk_evaluator(analysis: AnalysisResult) -> RiskResult:
    """Evaluate risk based on analysis"""
    if analysis.fire_status == "detected":
        return RiskResult(
            risk_level="CRITICAL",
            reason="🚨 Fire signal detected! Immediate action required!"
        )

    critical_markers = {
        analysis.temperature_status in {"too_cold", "too_hot"},
        analysis.humidity_status in {"too_dry", "too_humid"},
        analysis.vibration_status == "high",
    }
    critical_count = sum(1 for marker in critical_markers if marker)

    if critical_count >= 2 or analysis.anomaly_score >= 5:
        return RiskResult(
            risk_level="CRITICAL",
            reason="Multiple critical sensor limits exceeded"
        )

    if analysis.anomaly_score >= 3 or critical_count == 1:
        return RiskResult(
            risk_level="HIGH",
            reason="At least one sensor is in a critical band"
        )

    if analysis.anomaly_score >= 1:
        return RiskResult(
            risk_level="MEDIUM",
            reason="Minor anomalies detected"
        )

    return RiskResult(
        risk_level="LOW",
        reason="All parameters within acceptable range"
    )


def decision_agent(risk: RiskResult) -> DecisionResult:
    """Make decision based on risk assessment"""
    if risk.risk_level == "CRITICAL":
        return DecisionResult(
            decision="TRIGGER_EMERGENCY",
            requires_human=True
        )

    if risk.risk_level == "HIGH":
        return DecisionResult(
            decision="ALERT_AND_STABILIZE",
            requires_human=True
        )

    if risk.risk_level == "MEDIUM":
        return DecisionResult(
            decision="CHECK_WAREHOUSE",
            requires_human=True
        )

    return DecisionResult(
        decision="MONITOR",
        requires_human=False
    )


def action_agent(decision: DecisionResult, risk: RiskResult, analysis: AnalysisResult) -> ActionResult:
    """Convert decision into concrete output actions for dashboard, LED/buzzer, and logs."""
    if risk.risk_level == "CRITICAL":
        return ActionResult(
            led="RED_BLINK_FAST",
            buzzer="SIREN",
            log_level="CRITICAL",
            log_message=(
                f"Emergency: {risk.reason} | "
                f"T={analysis.temperature_status}, H={analysis.humidity_status}, "
                f"V={analysis.vibration_status}, F={analysis.fire_status}"
            ),
        )

    if risk.risk_level == "HIGH":
        return ActionResult(
            led="RED_BLINK",
            buzzer="BEEP_PATTERN_FAST",
            log_level="ERROR",
            log_message=(
                f"High risk action: {decision.decision} | "
                f"T={analysis.temperature_status}, H={analysis.humidity_status}, "
                f"V={analysis.vibration_status}"
            ),
        )

    if risk.risk_level == "MEDIUM":
        return ActionResult(
            led="YELLOW_SOLID",
            buzzer="BEEP_PATTERN_SLOW",
            log_level="WARNING",
            log_message=(
                f"Attention required: {decision.decision} | "
                f"Anomaly score={analysis.anomaly_score}"
            ),
        )

    return ActionResult(
        led="GREEN_SOLID",
        buzzer="OFF",
        log_level="INFO",
        log_message="System normal: all parameters within optimal/acceptable range",
    )


def run_analysis_pipeline():
    """Execute full analysis pipeline"""
    print("\n" + "="*60)
    print("🏥 PHARMA AEGIS ANALYSIS PIPELINE")
    print("="*60)
    
    # Get latest sensor data
    sensor_data = get_latest_sensor_data()
    print(f"\n📊 Raw Sensor Data: {sensor_data}")
    
    # Create reading object
    reading = SensorReading(
        temperature=float(sensor_data.get("temperature", 20)),
        humidity=float(sensor_data.get("humidity", 50)),
        vibration=float(sensor_data.get("vibration", 1.0)),
        fire=int(sensor_data.get("fire", 0))
    )
    
    # Run analysis
    analysis = data_analyzer(reading)
    print(f"\n🔍 Analysis:")
    print(f"   Temperature: {analysis.temperature_status}")
    print(f"   Humidity: {analysis.humidity_status}")
    print(f"   Vibration: {analysis.vibration_status}")
    print(f"   Fire: {analysis.fire_status}")
    print(f"   Anomaly Score: {analysis.anomaly_score}")
    
    # Evaluate risk
    risk = risk_evaluator(analysis)
    print(f"\n⚠️  Risk Assessment:")
    print(f"   Level: {risk.risk_level}")
    print(f"   Reason: {risk.reason}")
    
    # Make decision
    decision = decision_agent(risk)
    print(f"\n✅ Decision:")
    print(f"   Action: {decision.decision}")
    print(f"   Human Review: {'Required' if decision.requires_human else 'Not required'}")

    # Trigger actions
    action = action_agent(decision, risk, analysis)
    print(f"\n🛠️  Action Agent:")
    print(f"   LED: {action.led}")
    print(f"   Buzzer: {action.buzzer}")
    print(f"   Log Level: {action.log_level}")
    print(f"   Log: {action.log_message}")
    print("="*60 + "\n")

    return analysis, risk, decision, action
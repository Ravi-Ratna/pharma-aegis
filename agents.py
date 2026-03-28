"""Pharma Aegis Analysis Agents - Real-time sensor analysis"""
from collections import deque
from models import SensorReading, AnalysisResult, RiskResult, DecisionResult, ActionResult
from tools import get_latest_sensor_data

# ==================== CONFIGURATION CONSTANTS ====================
# Temperature thresholds (°C) for pharma storage
TEMP_OPTIMAL_MIN = 18
TEMP_OPTIMAL_MAX = 25
TEMP_WARN_LOW = 15
TEMP_WARN_HIGH = 28

# Humidity thresholds (%) for pharma storage
HUMIDITY_OPTIMAL_MIN = 35
HUMIDITY_OPTIMAL_MAX = 60
HUMIDITY_WARN_LOW = 30
HUMIDITY_WARN_HIGH = 75

# Vibration thresholds
VIBRATION_NORMAL_MAX = 1.0
VIBRATION_ELEVATED_MAX = 1.5

# Risk scoring parameters
FIRE_RISK_SCORE = 100.0
CRITICAL_ANOMALY_THRESHOLD = 5
HIGH_ANOMALY_THRESHOLD = 3
MEDIUM_ANOMALY_THRESHOLD = 1

# Compliance calculation weights
COMPLIANCE_WEIGHT = {
    "temperature": 0.35,
    "humidity": 0.35,
    "vibration": 0.20,
    "fire": 0.10,
}

# Trend tracking (keep last 30 readings)
sensor_history = deque(maxlen=30)

# ================================================================


def data_analyzer(reading: SensorReading) -> AnalysisResult:
    """Analyze raw sensor data and determine status with compliance and recommendations"""
    
    # Add current reading to history for trend analysis
    sensor_history.append({
        "temperature": reading.temperature,
        "humidity": reading.humidity,
        "vibration": reading.vibration,
        "fire": reading.fire,
    })
    
    # Temperature analysis (Pharma storage: 18-25°C optimal)
    if reading.temperature < TEMP_WARN_LOW:
        temperature_status = "too_cold"
        temperature_score = 2
        temp_compliance = 0
    elif reading.temperature < TEMP_OPTIMAL_MIN:
        temperature_status = "cool"
        temperature_score = 1
        temp_compliance = 50
    elif reading.temperature <= TEMP_OPTIMAL_MAX:
        temperature_status = "optimal"
        temperature_score = 0
        temp_compliance = 100
    elif reading.temperature <= TEMP_WARN_HIGH:
        temperature_status = "warm"
        temperature_score = 1
        temp_compliance = 60
    else:
        temperature_status = "too_hot"
        temperature_score = 2
        temp_compliance = 20

    # Humidity analysis (Pharma storage: 35-60% optimal)
    if reading.humidity < HUMIDITY_WARN_LOW:
        humidity_status = "too_dry"
        humidity_score = 1
        humidity_compliance = 50
    elif reading.humidity < HUMIDITY_OPTIMAL_MIN:
        humidity_status = "dry"
        humidity_score = 0
        humidity_compliance = 80
    elif reading.humidity <= HUMIDITY_OPTIMAL_MAX:
        humidity_status = "optimal"
        humidity_score = 0
        humidity_compliance = 100
    elif reading.humidity <= HUMIDITY_WARN_HIGH:
        humidity_status = "humid"
        humidity_score = 1
        humidity_compliance = 70
    else:
        humidity_status = "too_humid"
        humidity_score = 2
        humidity_compliance = 30

    # Vibration analysis
    if reading.vibration < VIBRATION_NORMAL_MAX:
        vibration_status = "normal"
        vibration_score = 0
        vibration_compliance = 100
    elif reading.vibration < VIBRATION_ELEVATED_MAX:
        vibration_status = "elevated"
        vibration_score = 1
        vibration_compliance = 70
    else:
        vibration_status = "high"
        vibration_score = 2
        vibration_compliance = 40

    # Fire detection (highest priority)
    fire_status = "detected" if reading.fire == 1 else "safe"
    fire_score = 5 if reading.fire == 1 else 0
    fire_compliance = 0 if reading.fire == 1 else 100

    # Calculate overall compliance score (0-100%)
    compliance_score = int(
        (temp_compliance * COMPLIANCE_WEIGHT["temperature"] +
         humidity_compliance * COMPLIANCE_WEIGHT["humidity"] +
         vibration_compliance * COMPLIANCE_WEIGHT["vibration"] +
         fire_compliance * COMPLIANCE_WEIGHT["fire"])
    )

    # Calculate trends from history
    trends = _calculate_trends()

    # Generate recommendations based on analysis
    recommendations = _generate_recommendations(
        reading, temperature_status, humidity_status, vibration_status, fire_status
    )

    anomaly_score = temperature_score + humidity_score + vibration_score + fire_score

    return AnalysisResult(
        temperature_status=temperature_status,
        humidity_status=humidity_status,
        vibration_status=vibration_status,
        fire_status=fire_status,
        anomaly_score=anomaly_score,
        compliance_score=compliance_score,
        trends=trends,
        recommendations=recommendations,
    )


def _calculate_trends() -> dict:
    """Calculate trends from sensor history"""
    trends = {}
    
    if len(sensor_history) < 2:
        # Not enough data yet, return stable trends
        return {
            "temperature": ("stable", 0.0),
            "humidity": ("stable", 0.0),
            "vibration": ("stable", 0.0),
        }
    
    # Get first and last readings
    first_reading = sensor_history[0]
    last_reading = sensor_history[-1]
    
    for param in ["temperature", "humidity", "vibration"]:
        old_value = first_reading[param]
        new_value = last_reading[param]
        
        if old_value == 0:
            change_pct = 0.0
        else:
            change_pct = ((new_value - old_value) / old_value) * 100
        
        # Determine trend direction
        if change_pct > 1.0:
            trend = "rising"
        elif change_pct < -1.0:
            trend = "falling"
        else:
            trend = "stable"
        
        trends[param] = (trend, round(change_pct, 1))
    
    return trends


def _generate_recommendations(reading: SensorReading, temp_status: str, 
                             humidity_status: str, vibration_status: str, 
                             fire_status: str) -> list:
    """Generate actionable recommendations based on sensor analysis"""
    recommendations = []
    
    # Temperature recommendations
    if temp_status == "too_cold":
        recommendations.append("⚠️ Increase room temperature - below safety threshold")
    elif temp_status == "too_hot":
        recommendations.append("⚠️ Reduce temperature immediately - exceeds storage limit")
    elif temp_status == "cool" or temp_status == "warm":
        diff = TEMP_OPTIMAL_MIN - reading.temperature if temp_status == "cool" else reading.temperature - TEMP_OPTIMAL_MAX
        recommendations.append(f"🔧 Adjust temperature by ~{diff:.1f}°C toward optimal range")
    
    # Humidity recommendations
    if humidity_status == "too_dry":
        recommendations.append("💧 Increase humidity - air too dry for pharmaceutical products")
    elif humidity_status == "too_humid":
        recommendations.append("💨 Reduce humidity immediately - moisture levels too high")
    elif humidity_status == "dry" or humidity_status == "humid":
        recommendations.append("🎯 Fine-tune humidity control systems for stability")
    
    # Vibration recommendations
    if vibration_status == "elevated":
        recommendations.append("🔧 Inspect equipment - vibration levels elevated")
    elif vibration_status == "high":
        recommendations.append("🚨 Check equipment immediately - abnormal vibration detected")
    
    # Fire recommendations
    if fire_status == "detected":
        recommendations.append("🚨 EMERGENCY: Fire detected - activate emergency protocols immediately!")
    
    # Limit to 3 recommendations
    return recommendations[:3]


def risk_evaluator(analysis: AnalysisResult) -> RiskResult:
    """Evaluate risk based on analysis with scoring and confidence metrics"""
    
    if analysis.fire_status == "detected":
        return RiskResult(
            risk_level="CRITICAL",
            reason="🚨 Fire signal detected! Immediate action required!",
            risk_score=100.0,
            confidence=1.0,
        )

    # Calculate risk score based on anomaly score and compliance
    # Higher anomaly score = lower compliance = higher risk
    risk_score = (100.0 - analysis.compliance_score) * (analysis.anomaly_score / 10.0)
    risk_score = min(100.0, max(5.0, risk_score))  # Clamp between 5 and 100
    
    # Confidence decreases slightly if we're right at threshold boundaries
    base_confidence = 0.95
    confidence = max(0.85, base_confidence - (abs(analysis.anomaly_score - 2.5) * 0.02))

    if analysis.anomaly_score >= CRITICAL_ANOMALY_THRESHOLD:
        return RiskResult(
            risk_level="CRITICAL",
            reason="Multiple critical sensor anomalies detected",
            risk_score=risk_score,
            confidence=confidence,
        )

    if analysis.anomaly_score >= HIGH_ANOMALY_THRESHOLD:
        return RiskResult(
            risk_level="HIGH",
            reason="Multiple sensor anomalies indicate potential issues",
            risk_score=risk_score,
            confidence=confidence,
        )

    if analysis.anomaly_score >= MEDIUM_ANOMALY_THRESHOLD:
        return RiskResult(
            risk_level="MEDIUM",
            reason="Minor anomalies detected - manual inspection recommended",
            risk_score=risk_score,
            confidence=confidence,
        )

    return RiskResult(
        risk_level="LOW",
        reason="All parameters within acceptable range",
        risk_score=max(5.0, risk_score),
        confidence=confidence,
    )


def decision_agent(risk: RiskResult) -> DecisionResult:
    """Make decision based on risk assessment with urgency levels"""
    
    if risk.risk_level == "CRITICAL":
        return DecisionResult(
            decision="TRIGGER_EMERGENCY",
            requires_human=True,
            urgency="critical"
        )

    if risk.risk_level == "HIGH":
        return DecisionResult(
            decision="ALERT_AND_STABILIZE",
            requires_human=True,
            urgency="high"
        )

    if risk.risk_level == "MEDIUM":
        return DecisionResult(
            decision="CHECK_WAREHOUSE",
            requires_human=True,
            urgency="medium"
        )

    return DecisionResult(
        decision="MONITOR",
        requires_human=False,
        urgency="low"
    )


def action_agent(decision: DecisionResult, risk: RiskResult, 
                 analysis: AnalysisResult) -> ActionResult:
    """Generate action outputs for external systems (LED, buzzer, logging)"""
    
    # Determine LED state based on risk level
    if risk.risk_level == "CRITICAL":
        led_state = "RED_BLINK"
        buzzer_state = "ON"
        log_level = "ERROR"
    elif risk.risk_level == "HIGH":
        led_state = "RED_SOLID"
        buzzer_state = "ON"
        log_level = "WARNING"
    elif risk.risk_level == "MEDIUM":
        led_state = "YELLOW_SOLID"
        buzzer_state = "OFF"
        log_level = "WARNING"
    else:  # LOW
        led_state = "GREEN_SOLID"
        buzzer_state = "OFF"
        log_level = "INFO"
    
    # Generate log message
    if analysis.fire_status == "detected":
        log_message = "🚨 FIRE DETECTED - Emergency protocols activated"
    elif analysis.anomaly_score >= CRITICAL_ANOMALY_THRESHOLD:
        log_message = f"Critical anomaly detected (score: {analysis.anomaly_score})"
    elif analysis.anomaly_score >= HIGH_ANOMALY_THRESHOLD:
        log_message = f"High anomaly detected (score: {analysis.anomaly_score}) - {decision.decision}"
    elif analysis.anomaly_score >= MEDIUM_ANOMALY_THRESHOLD:
        log_message = f"Minor anomaly detected (score: {analysis.anomaly_score}) - {decision.decision}"
    else:
        log_message = f"System operating normally (compliance: {analysis.compliance_score}%)"
    
    return ActionResult(
        led=led_state,
        buzzer=buzzer_state,
        log_level=log_level,
        log_message=log_message,
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
    print("="*60 + "\n")
    
    return analysis, risk, decision
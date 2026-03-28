"""Data models for Pharma Aegis sensor analysis"""
from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class SensorReading:
    """Raw sensor data from ESP32"""
    temperature: float
    humidity: float
    vibration: float
    fire: int = 0  # 0 = safe, 1 = fire detected


@dataclass
class AnalysisResult:
    """Analysis of sensor data"""
    temperature_status: str
    humidity_status: str
    vibration_status: str
    fire_status: str
    anomaly_score: int
    compliance_score: int = 100  # 0-100 compliance rating
    trends: Dict[str, Tuple[str, float]] = field(default_factory=lambda: {})  # {param: (trend, pct)}
    recommendations: list = field(default_factory=list)  # List of recommendations


@dataclass
class RiskResult:
    """Risk evaluation result"""
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    reason: str
    risk_score: float = 0.0  # 0-100 risk score
    confidence: float = 1.0  # 0-1 confidence in assessment


@dataclass
class DecisionResult:
    """Decision/action from risk assessment"""
    decision: str  # MONITOR, CHECK_DOOR, ALERT_AND_STABILIZE, TRIGGER_EMERGENCY
    requires_human: bool
    urgency: str = "low"  # low, medium, high, critical


@dataclass
class ActionResult:
    """Action output for external systems (dashboard, LED/buzzer, logs)"""
    led: str
    buzzer: str
    log_level: str
    log_message: str

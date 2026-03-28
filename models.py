"""Data models for Pharma Aegis sensor analysis"""
from dataclasses import dataclass


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


@dataclass
class RiskResult:
    """Risk evaluation result"""
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    reason: str


@dataclass
class DecisionResult:
    """Decision/action from risk assessment"""
    decision: str  # MONITOR, CHECK_DOOR, ALERT_AND_STABILIZE, TRIGGER_EMERGENCY
    requires_human: bool


@dataclass
class ActionResult:
    """Action output for external systems (dashboard, LED/buzzer, logs)"""
    led: str
    buzzer: str
    log_level: str
    log_message: str

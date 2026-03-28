from agents import run_analysis_pipeline


def run_system():
    """Execute Pharma Aegis analysis system"""
    print("\n🚀 Starting Pharma Aegis Analysis System\n")
    
    # Run the analysis pipeline
    analysis, risk, decision, action = run_analysis_pipeline()
    
    # Additional logic based on decision
    if decision.decision == "TRIGGER_EMERGENCY":
        print("🚨 EMERGENCY TRIGGERED - Activating emergency protocols!")
    elif decision.decision == "ALERT_AND_STABILIZE":
        print("⚠️  HIGH RISK - Alerting monitoring team for stabilization")
    elif decision.decision == "CHECK_WAREHOUSE":
        print("🔍 Manual inspection recommended - Check warehouse conditions")
    else:
        print("✅ System operating normally - Continuing to monitor")

    print(f"🛠️  Action Output -> LED: {action.led}, Buzzer: {action.buzzer}")


if __name__ == "__main__":
    run_system()
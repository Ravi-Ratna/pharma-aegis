from agents import sensor_agent, risk_agent, prediction_agent, response_agent

def run_system():
    print("\n--- RUNNING AGENT SYSTEM ---\n")

    sensor_output = sensor_agent()
    print("\nSensor Analyst:\n", sensor_output)

    risk_output = risk_agent(sensor_output)
    print("\nRisk Agent:\n", risk_output)

    prediction_output = prediction_agent(sensor_output)
    print("\nPrediction Agent:\n", prediction_output)

    final_output = response_agent(sensor_output, risk_output, prediction_output)
    print("\nFinal Decision:\n", final_output)


if __name__ == "__main__":
    run_system()
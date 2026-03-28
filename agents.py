from langchain_openai import ChatOpenAI
from tools import get_latest_sensor_data
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(temperature=0)

# 1. SENSOR ANALYST
def sensor_agent():
    data = get_latest_sensor_data()
    prompt = f"""
    You are a sensor analyst.

    Sensor Data: {data}

    1. Is it normal or abnormal?
    2. Give severity (0-10)
    3. Explain briefly
    """
    return llm.invoke(prompt).content


# 2. RISK AGENT
def risk_agent(sensor_output):
    prompt = f"""
    You are a risk evaluator.

    Based on this:
    {sensor_output}

    Classify risk as LOW / MEDIUM / HIGH / CRITICAL.
    """
    return llm.invoke(prompt).content


# 3. PREDICTION AGENT
def prediction_agent(sensor_output):
    prompt = f"""
    You are a prediction system.

    Based on:
    {sensor_output}

    Will temperature exceed 8°C?
    If yes, in how many minutes?
    """
    return llm.invoke(prompt).content


# 4. RESPONSE AGENT
def response_agent(sensor_output, risk_output, prediction_output):
    prompt = f"""
    You are a response controller.

    Sensor: {sensor_output}
    Risk: {risk_output}
    Prediction: {prediction_output}

    Decide action:
    LOW → Log
    MEDIUM → Notify
    HIGH → Alert
    CRITICAL → Emergency alarm
    """
    return llm.invoke(prompt).content
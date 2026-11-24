import subprocess
import json
import os
from typing import Literal
from pydantic import BaseModel, Field
import time
import httpx
from dotenv import load_dotenv
from groq import BadRequestError, Groq
load_dotenv()
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
SERVICES = os.getenv("SERVICES", "").split(",")
client = Groq(api_key=os.getenv("GROQ_API_KEY"), max_retries=5)   # NEW: auto-retry on 429 rate limits
MODEL = "openai/gpt-oss-20b"
LOG_DIR = "data/logs"



# ============================================================================
# TOOL 1: read_logs (yours, from Day 1)
# ============================================================================

def read_logs(service:str) -> str:
    if SERVICES != [""] and service not in SERVICES:
      return f"Service '{service}' is not allowed. Allowed: {SERVICES}"

    result = subprocess.run(
        ["docker","logs","--since","2m","--tail","500",service],   # only the last 2 minutes
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return f"Could not read logs for {service}: {result.stderr}"

    lines = (result.stdout+result.stderr).splitlines()

    important = [line for line in lines if "ERROR" in line or "WARN" in line]

    if not important:
        return f"No errors or warning in recent logs for {service}"

    return "\n".join(important[-30:])




read_logs_tool = {
    "type": "function",
    "function": {
        "name": "read_logs",
        "description": "Read recent log lines for a given service. Use this to find errors, exceptions and timestamps when investigating an incident.",
        "parameters": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Exact service name. Available: 'order-service', 'payment-service', 'redis' (hyphen, not underscore)",
                }
            },
            "required": ["service"],
        },
    },
}


# ============================================================================
# TOOL 2: get_metrics (NEW, written for you as an example)
# ============================================================================
def get_metrics(service: str) -> str:
    if SERVICES != [""] and service not in SERVICES:
      return f"Service '{service}' is not allowed. Allowed: {SERVICES}"


    # with open("data/metrics.json") as file:
    #     all_metrics = json.load(file)          # json.load = read a JSON FILE into a dict (json.loads = from a STRING)

    # if service not in all_metrics:             # "key in dict" = Java's map.containsKey(key)
    #     return f"No metrics found for service: {service}"

    # return json.dumps(all_metrics[service])    # dict/list → JSON string (the LLM only accepts text)
    # increase(...[2m]) = how many requests in the LAST 2 MINUTES (not since the app started)
    query = f'round(increase(http_server_requests_seconds_count{{job="{service}", uri!~"/actuator.*"}}[2m])) > 0'   # > 0 = hide rows with no requests

    response = httpx.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query":query},
        timeout=5
    )

    results = response.json()["data"]["result"]

    if not results:
        return f"No requests recorded for {service} in the last 2 minutes"

    return json.dumps(results);

get_metrics_tool = {
    "type": "function",
    "function": {
        "name": "get_metrics",
        "description": "Get recent per-minute metrics for a service (error rate, latency, traffic; for redis: command latency, clients, ops/sec). Use this to see WHEN a problem started and how bad it is.",
        "parameters": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Exact service name. Available: 'order-service', 'payment-service', 'redis'",
                }
            },
            "required": ["service"],
        },
    },
}

def get_service_status() -> str:
    result = subprocess.run(
        ["docker","ps","-a","--format","{{.Names}}:{{.Status}}"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode !=0:
        return f"Could not get service status:{result.stderr}"

    return result.stdout


get_service_status_tool = {
    "type":"function",
    "function":{
        "name":"get_service_status",
        "description":"List all services/containers and whether each is running or stopped (Up / Exited).Use this when a service can't connect to another service, to check if that dependency is down.",
        "parameters": {"type": "object", "properties": {}}, 
    },
}


# ============================================================================
# TOOL 3: get_recent_deploys (NEW, YOUR PART)
# ============================================================================
# BLANK 1: write this function.
#   - open "data/deploys.json"
#   - return its contents as a string
#   It takes NO parameters: it always returns all recent deploys.
#   (hint: it's like read_logs, but there's no path to build and no "not found" check)
def get_recent_deploys() -> str:
    with open("data/deploys.json") as file:
        all_deploy = json.load(file)

    return json.dumps(all_deploy)

ALL_TOOLS = [read_logs_tool, get_metrics_tool, get_service_status_tool]   # the "menu" sent to the LLM

# BLANK 2: map each tool NAME (the string the LLM sends) → the Python FUNCTION.
#   Like a Java Map<String, Function>. Note: no () after the function name,
#   because we store the function itself, we don't call it here.
#   e.g.  "read_logs": read_logs,
TOOLS = {
    "read_logs":read_logs,
    "get_metrics":get_metrics,
    "get_service_status": get_service_status
}

class IncidentReport(BaseModel):
    root_cause: str = Field(description="One sentence: what broke and why")
    root_cause_service: str = Field(description="The ONE service where the problem started, e.g. 'redis'")
    affected_services: list[str] = Field(description="Services showing symptoms (errors, slowness)")
    evidence: list[str] = Field(description="Exact log lines, metric values or status lines from tools")
    confidence: Literal["low", "medium", "high"]
    suggested_action: str = Field(description="The first safe action a human should take")

SYSTEM_PROMPT = (
    "You are an on-call SRE assistant. You have access to tools like get_metrics, read_logs and get_service_status,"
    "Use them to investigate. "
    "Only state cause when u have evidence from the tools."
    "If unsure say what u dont know but dont assume anything."
    "Check metrics to see when the problem started, logs to see what is failing, "
    "If a service's errors come from a call to another service, the root cause is that other service. "
    "Don't stop at the first symptom: keep digging until you find the underlying root cause. "
    "Quote log lines, metrics and timestamps as evidence."
)



def write_report(messages:list) -> IncidentReport:
    messages.append({
        "role":"user",
        "content":"Now write the final incident report. Use only evidence you found with the tools."
    })
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        response_format={
            "type":"json_schema",
            "json_schema":{"name":"incident_report","schema":IncidentReport.model_json_schema()}
        },
    )
    text = response.choices[0].message.content
    return IncidentReport.model_validate_json(text)

# ============================================================================
# The agent loop (yours, from Day 2) + tool lookup (NEW)
# ============================================================================
def run_agent(alert: str, max_steps: int = 6) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": alert},
    ]

    for step in range(max_steps):
        for attempt in range(3):   # the model sometimes sends a broken tool call → Groq rejects it → ask again
            try:
                response = client.chat.completions.create(model=MODEL, messages=messages, tools=ALL_TOOLS)
                break
            except BadRequestError:
                print("Bad tool call from model, retrying...")
        msg = response.choices[0].message

        if not msg.tool_calls:
            messages.append(msg) 
            return write_report(messages)

        messages.append(msg)

        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            print(f"Step {step + 1}: {name}({tool_call.function.arguments})")

            # BLANK 3: find the Python function for this name in TOOLS.
            #   Use TOOLS.get(name): it returns None if the name isn't there
            #   (TOOLS[name] would crash instead, like a missing key in Java but worse).
            func =  TOOLS.get(name)

            # NEW: never crash on a bad tool call. Send the error back to the LLM instead.
            if func is None:
                result = f"Error: unknown tool '{name}'. Available tools: {list(TOOLS)}"
            else:
                try:                                            # Python's try/catch
                    args = json.loads(tool_call.function.arguments or "{}")
                    result = func(**args)                       # ** unpacks the dict into named arguments:
                                                                # {"service": "redis"} → func(service="redis")
                                                                # {}                   → func()
                except Exception as e:                          # catch (Exception e)
                    result = f"Error running {name}: {e}"

            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})

    return write_report(messages)


if __name__ == "__main__":
    answer = run_agent("ALERT: order-service error rate is above 5% for the last 2 minutes.")
    print("\nFINAL ANSWER:\n", answer)

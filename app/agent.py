"""
Day 3: several tools, and the agent picks which one to use.

Day 2: one tool (read_logs), always called directly.
Day 3: three tools + a TOOLS dict that maps the name the LLM asks for → the Python function.

Run:   python -m app.agent
"""
import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"), max_retries=5)   # NEW: auto-retry on 429 rate limits
MODEL = "openai/gpt-oss-20b"
LOG_DIR = "data/logs"


# ============================================================================
# TOOL 1: read_logs (yours, from Day 1)
# ============================================================================
def read_logs(service: str) -> str:
    path = f"{LOG_DIR}/{service}.log"
    if not os.path.exists(path):
        return f"No logs found for service: {service}"
    with open(path) as file:
        return file.read()


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
    with open("data/metrics.json") as file:
        all_metrics = json.load(file)          # json.load = read a JSON FILE into a dict (json.loads = from a STRING)

    if service not in all_metrics:             # "key in dict" = Java's map.containsKey(key)
        return f"No metrics found for service: {service}"

    return json.dumps(all_metrics[service])    # dict/list → JSON string (the LLM only accepts text)


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


get_recent_deploys_tool = {
    "type": "function",
    "function": {
        "name": "get_recent_deploys",
        "description": "List recent deployments and config changes across all services (time, service, version, what changed). Use this to answer 'what changed right before the problem started?'",
        "parameters": {"type": "object", "properties": {}},    # no parameters
    },
}


ALL_TOOLS = [read_logs_tool, get_metrics_tool, get_recent_deploys_tool]   # the "menu" sent to the LLM

# BLANK 2: map each tool NAME (the string the LLM sends) → the Python FUNCTION.
#   Like a Java Map<String, Function>. Note: no () after the function name,
#   because we store the function itself, we don't call it here.
#   e.g.  "read_logs": read_logs,
TOOLS = {
    "read_logs":read_logs,
    "get_metrics":get_metrics,
    "get_recent_deploys":get_recent_deploys
}


SYSTEM_PROMPT = (
    "You are an on-call SRE assistant. Use the tools to investigate. "
    "Check metrics to see when the problem started, logs to see what is failing, "
    "and recent deploys to see what changed. "
    "Don't stop at the first symptom: keep digging until you find the underlying root cause. "
    "Quote log lines, metrics and timestamps as evidence."
)


# ============================================================================
# The agent loop (yours, from Day 2) + tool lookup (NEW)
# ============================================================================
def run_agent(alert: str, max_steps: int = 6) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": alert},
    ]

    for step in range(max_steps):
        response = client.chat.completions.create(model=MODEL, messages=messages, tools=ALL_TOOLS)
        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content

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

    return "Stopped: reached max_steps without a final answer."


if __name__ == "__main__":
    answer = run_agent("ALERT: order-service error rate is above 5% for the last 2 minutes.")
    print("\nFINAL ANSWER:\n", answer)

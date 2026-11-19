"""
Day 2: the agent LOOP.

Yesterday (agent_v0.py): call the LLM exactly twice.
Today: keep going until the LLM stops asking for tools (or we hit max_steps).

Run:   python -m app.agent
"""
import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "openai/gpt-oss-20b"
LOG_DIR = "data/logs"


# ----- the tool (same as yesterday) -----------------------------------------
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
                    # NEW: tells the LLM which logs exist (tomorrow a tool will do this instead)
                    "description": "Exact service name. Available: 'order-service', 'payment-service', 'redis' (hyphen, not underscore)",
                }
            },
            "required": ["service"],
        },
    },
}


SYSTEM_PROMPT = (
    "You are an on-call SRE assistant. Use the tools to investigate. "
    # NEW: without this line the LLM often stops at the first symptom ("Redis timeouts")
    "Don't stop at the first symptom: keep digging until you find the underlying root cause. "
    "Quote log lines and timestamps as evidence."
)


# ----- the agent loop (YOUR PART: 2 blanks) ---------------------------------
def run_agent(alert: str, max_steps: int = 5) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": alert},
    ]

    for step in range(max_steps):                      # step = 0, 1, 2, 3, 4
        response = client.chat.completions.create(model=MODEL, messages=messages, tools=[read_logs_tool])
        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content

        messages.append(msg)                           # remember what it asked for

        for tool_call in msg.tool_calls:               # it can ask for several tools at once
            args = json.loads(tool_call.function.arguments)
            print(f"Step {step + 1}: {tool_call.function.name}({args})")

            # BLANK 2: run the tool and store the text in `result`
            result = read_logs(args["service"])

            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})

    return "Stopped: reached max_steps without a final answer."


if __name__ == "__main__":
    answer = run_agent("ALERT: order-service error rate is above 5% for the last 2 minutes.")
    print("\nFINAL ANSWER:\n", answer)

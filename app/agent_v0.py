"""
Day 1: one tool call, done by hand (no loop yet).

Flow:  alert -> LLM -> asks for read_logs -> WE run it -> send result back -> LLM answers
Run:   python -m app.agent_v0
"""
import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "openai/gpt-oss-20b"
LOG_DIR = "data/logs"


run_log_tool = {
    "type":"function",
    "function":{
        "name":"read_logs",
        "description":"Read recent log lines for a given service. Use this to find errors, exceptions and timestamps when investigating an incident",       
        "parameters":{
            "type":"object",
             "properties":{
                 "service":{
                     "type":"string",
                     "description":"Exact service name, e.g. 'order-service' or 'payment-service' (hyphen, not underscore)"
                 }
             },
             "required":["service"]
        }
        
         
    }
}
def read_logs(service: str) -> str:
    path = f"{LOG_DIR}/{service}.log"
    if not os.path.exists(path):
        return f"No logs found for service: {service}"

    with open(path) as file:
        content = file.read()
        return content

    


def main():
    alert = "ALERT: order-service error rate is above 5% for the last 2 minutes."

    # logs = read_logs("order-service")

    messages = [
        {"role":"system","content":"You are an on-call SRE assistant. Find the root cause of the alert. Quote log lines and timestamps as evidence."},
        {"role":"user","content":alert},
    ]

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools = [run_log_tool]
    )

    msg = response.choices[0].message

    # here we are getting the tool name
    tool_call = msg.tool_calls[0]
    print(tool_call)
    args = json.loads(tool_call.function.arguments)
    result = read_logs(args["service"])

    messages.append(msg)
    messages.append({"role":"tool","tool_call_id":tool_call.id, "content":result})  

    final = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools = [run_log_tool]
    )
    print("\nFinal answer:\n", final.choices[0].message.content)
    print("Final tool calls:", final.choices[0].message.tool_calls)



if __name__ == "__main__":
    main()


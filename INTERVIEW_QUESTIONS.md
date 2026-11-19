# 🎯 Interview Questions

Questions that come up in AI Engineer / GenAI / Agentic AI interviews, answered from what I built in this project.
⭐ = very likely to be asked. **How to use:** answer out loud first, then read the answer.

---

## 1. Agents: the basics

**⭐ What is an AI agent?**
An LLM + tools + a loop. The LLM decides the next action based on what it has seen so far, my code runs the tool, the result goes back, and this repeats until the LLM gives a final answer.

**⭐ What's the difference between a workflow and an agent?**
In a workflow, my code decides the steps and their order (e.g. RAG: retrieve → rerank → generate). In an agent, the LLM decides the next step at runtime.

**⭐ When should you NOT use an agent?**
When the steps are known in advance. Then use a single LLM call or a fixed workflow: it's cheaper, faster, predictable and easier to test. Use an agent only when the next step depends on intermediate results, as in incident investigation.

> *"I start with the simplest thing that works: one call, then a workflow. I only move to an agent when the steps genuinely depend on what the previous step found."*

---

## 2. Tool calling

**⭐ Does the LLM execute the tool?**
No. It returns a structured request: tool name + JSON arguments. **My code** validates it and runs the function, then sends the result back. That makes tool calling a security boundary: I decide what actually runs.

**⭐ Walk me through one tool call, message by message.**
```
1. me → LLM:   system prompt + user message + tool schemas
2. LLM → me:   assistant message with tool_calls (content = None)
               e.g. read_logs({"service": "order-service"})
3. me:         json.loads(arguments) → run read_logs("order-service")
4. me → LLM:   history + assistant message + {"role": "tool", "tool_call_id": ..., "content": result}
5. LLM → me:   final text answer
```

**How does the LLM choose which tool to call, and with what arguments?**
Only from the tool's **name, description and parameter schema**. A vague description leads to wrong choices and wrong arguments.

**What is `tool_call_id` for?**
It links each tool result to the request it answers. That matters when the LLM asks for several tools in one turn.

**Why do you need `json.loads` on the arguments?**
The arguments arrive as a JSON **string**, not a dict. Models can also produce invalid JSON, so in production you validate it (e.g. with Pydantic) and send an error back if it's malformed.

**What should a tool return when something goes wrong?**
An error message as the result, not an exception that crashes the program. The LLM can read "No logs found for service X" and try something else.

**⭐ Tell me about a bug you hit while building an agent.**
My tool description mentioned `order_service`, so the LLM asked for `order_service` instead of `order-service`. The file wasn't found and the agent returned no answer. I fixed it with a generic description and a parameter description containing exact example values. Lesson: the tool description is the model's only documentation, so treat it like an API contract.

---

## 3. The agent loop

**⭐ Write a minimal agent loop (whiteboard).**
```python
for step in range(max_steps):
    msg = llm(messages, tools)
    if not msg.tool_calls:          # no request → final answer
        return msg.content
    messages.append(msg)
    for tc in msg.tool_calls:
        result = TOOLS[tc.function.name](**json.loads(tc.function.arguments))
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
return "stopped: max steps"
```

**⭐ How does the agent know it's done?**
The LLM replies without `tool_calls`, just text. That's the final answer.

**⭐ Why do you need `max_steps`?**
A confused agent can loop forever (re-reading the same logs, retrying a failing tool), and every step costs money and time. `max_steps` is a hard stop. Others: a token/cost budget, a timeout, detecting repeated identical calls.

**⭐ Why does each agent step get more expensive?**
The LLM is stateless, so every call re-sends the whole history, including every tool result so far. Tokens per call grow with each step. Fixes: return only relevant data from tools (e.g. ERROR/WARN lines), truncate or summarize old tool results, and cap steps.

**Your agent hit a `429`. What is it and how do you handle it?**
A rate limit (my Groq free tier: 8,000 tokens/minute). Handle it with retries plus exponential backoff (respect the `retry-after` hint), a fallback model or provider, smaller prompts, and queuing requests instead of firing them all at once.

**How did your agent find a root cause a single LLM call couldn't?**
The order-service logs only showed Redis timeouts. The agent decided on its own to read the Redis logs, found an `analytics-job` running `KEYS order:*` (which blocks Redis's single thread), and correlated timestamps. That second step depended on what the first step found, which is exactly when an agent is justified.

---

## 4. The project pitch (have this ready)

**⭐ "Tell me about a project you built."**
> *"I'm building an AI SRE: a multi-agent system that investigates production incidents. An alert comes in, a supervisor agent sends specialist agents to check logs, metrics, recent deploys and runbooks, and it produces a root-cause report with evidence. Risky actions like restarts need human approval. I test it by injecting real failures into a Spring Boot + Kafka + Redis system, and since each failure has a known root cause, I can measure accuracy."*

*(This grows as the project grows.)*

---

*New sections get added as each topic is covered: the agent loop, memory, multi-agent, MCP, A2A, guardrails, evals, LLMOps.*

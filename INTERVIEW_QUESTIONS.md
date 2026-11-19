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

## 3. The project pitch (have this ready)

**⭐ "Tell me about a project you built."**
> *"I'm building an AI SRE: a multi-agent system that investigates production incidents. An alert comes in, a supervisor agent sends specialist agents to check logs, metrics, recent deploys and runbooks, and it produces a root-cause report with evidence. Risky actions like restarts need human approval. I test it by injecting real failures into a Spring Boot + Kafka + Redis system, and since each failure has a known root cause, I can measure accuracy."*

*(This grows as the project grows.)*

---

*New sections get added as each topic is covered: the agent loop, memory, multi-agent, MCP, A2A, guardrails, evals, LLMOps.*

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

## 4. Multiple tools + error handling

**⭐ How does your code run the right tool when there are many?**
A dict mapping tool name → Python function: `func = TOOLS.get(tool_call.function.name)`, then `func(**args)`. Adding a tool = function + schema + one dict entry.

**⭐ What happens if the LLM calls a tool that doesn't exist, or sends bad arguments?**
Never crash. Unknown name → return "Error: unknown tool X, available: [...]". Bad JSON or a wrong argument → `try/except` → return the error text as the tool result. The LLM reads it and usually corrects itself. My agent once sent `{"": ""}` to a no-argument tool, got the error, and retried correctly with `{}` on the next step.

**Why return errors to the LLM instead of raising?**
The LLM can recover (retry, try another tool, or explain what it couldn't do). An exception just kills the run. Same idea as returning a proper error response from an API instead of a 500.

**⭐ My agent called the same failing tool 5 times in a row. What guards stop that?**
`max_steps` (it stopped it here), plus detecting repeated identical calls (same name + args failing twice → stop or tell the LLM to try something else), and a token/cost budget.

**How do you decide what tools an agent needs?**
Mirror how an expert works. An SRE asks: what do the metrics say (when, how bad), what do the logs say (what's failing), what changed (deploys). One tool per question, with clear descriptions and narrow parameters.

**Too many tools: what goes wrong?**
The model picks the wrong tool more often, and every tool schema costs tokens on every call. Keep tool sets small and descriptions distinct; split into specialist agents when the list grows (that's where multi-agent comes in).

---

## 5. The demo system: Docker, observability, failures

**What's the difference between a Dockerfile and docker-compose?**
The Dockerfile is the recipe for building ONE image (my app + Java). Compose starts SEVERAL containers together and connects them on one network, where they reach each other by container name (`redis:6379`, `payment-service:8080`).

**Why a multi-stage Dockerfile?**
Stage 1 has Maven and builds the jar. Stage 2 copies only the jar into a small JRE image. The final image doesn't carry Maven or the source code, so it's smaller and has less attack surface.

**Where do `docker logs` come from?**
The app writes to stdout. Docker captures stdout/stderr and stores it per container. Those logs are lost when the container is removed, so production ships logs to a central store (Loki, ELK, Datadog).

**⭐ Logs vs metrics: when do you use each?**
Metrics (Prometheus) answer *when* and *how bad*: the error rate jumped at 10:42 to 30%. Logs answer *why*: `Redis command timed out`. Investigate metrics first to find the time window, then read logs from that window.

**How does Prometheus get its data?**
It **pulls**. Every N seconds it scrapes each service's `/actuator/prometheus` endpoint (Spring Actuator + Micrometer). If a scrape fails, the target shows as DOWN, which is itself a signal.

**⭐ Why does every remote call need a timeout?**
Without one, a slow dependency makes every request wait, threads pile up, and the caller freezes too: a cascading failure. In my demo, payment latency of 20s made every order take 20s. A timeout (2s) turns a hang into a fast, visible error that can be retried or shown to the user.

**⭐ Redis came back, but the service still failed for 30 seconds. Why?**
The client reconnects with **exponential backoff** (1s, 2s, 4s… up to ~30s), so it hadn't retried yet. Backoff prevents a "thundering herd" of clients hammering a server that's just recovering. Lesson: a recovered dependency doesn't mean a recovered service, so check for the reconnect.

**Why is `KEYS *` dangerous in production Redis?**
Redis runs commands on a single thread. `KEYS` scans every key, so on millions of keys it blocks all other commands. Use `SCAN` instead.

**How do you test an incident-response tool?**
Chaos engineering: inject known failures (a dependency down, latency, errors) and check whether the tool finds the known root cause. Since each failure has a known answer, you get a score.

---

## 6. Agents on real data: grounding and hallucination

**⭐ Your agent hallucinated a root cause. What happened and how did you fix it?**
Redis was stopped. The logs said `Failed to resolve 'redis'`, and the agent had no tool to check whether Redis was running, so it invented a plausible story: "Redis was renamed in a Kubernetes deployment" (I don't use Kubernetes). I fixed it two ways: (1) a `get_service_status` tool, so it can *check* instead of guessing, and (2) a grounded system prompt: "only state causes supported by tool evidence, say what you don't know, don't assume an environment." The next run correctly said "Redis container exited," with three pieces of evidence.

**⭐ How does the LLM decide which tool to call?**
From the tool's name, description and parameter schema, plus the system prompt and the conversation so far. It never sees the code. That's why descriptions should say *when* to use the tool ("use this when a service can't connect to a dependency").

**⭐ Why filter tool output before sending it to the LLM?**
Noise hurts both accuracy and cost. When Redis broke, 211 of 219 log lines were stack traces, and 441 "successful requests" in the metrics were Prometheus scraping itself, which could make the system look healthy. I keep only ERROR/WARN lines (last 30) and exclude `/actuator` requests.

**What's the most dangerous kind of tool bug?**
A wrong answer that looks valid. My log tool returned "No errors" for a container that didn't exist, because Docker's error text didn't match my `ERROR` filter. The LLM would conclude the service was healthy. Fix: check the command's exit code first and return an explicit error.

**Why must the system prompt match the tools?**
My prompt still said "check recent deploys" after I removed that tool, which pushed the model toward guessing about deploys. Every instruction in the prompt should be something the agent can actually do.

**What is ReAct?**
Reason + Act: the model thinks about what it needs, calls a tool, observes the result, and repeats. A tool-calling loop like mine is ReAct in practice.

**How do you make an agent tool reusable by other teams?**
No hard-coded environment: endpoints like `PROMETHEUS_URL` come from config, sources are pluggable (Docker today, Kubernetes/Loki later), and the tools are read-only by default. Exposing the tools as an MCP server lets any MCP client use them.

---

## 7. Structured output, evals and MCP

**⭐ How do you get reliable structured output from an LLM?**
Define the shape as a Pydantic model, send its JSON schema as `response_format`, then validate the reply with `model_validate_json()`. Field descriptions are part of the prompt. If validation fails, retry, or send the error back to the model.

**⭐ How do you evaluate an agent?**
Scenarios with known answers. I inject a failure (Redis down, payment errors, latency), run the agent, and compare `root_cause_service` with the expected one. That gives a score (2/5 → 3/5 → better), so prompt changes are measured, not guessed. Include a "no incident" case so it can't just always blame something.

**My eval failed because of the test, not the agent. How?**
The tools look at the last 2 minutes, but scenarios were only 30s apart, so the "no incident" run saw the previous scenario's errors. Evals need isolation between runs, just like unit tests.

**⭐ What is MCP and why use it?**
Model Context Protocol, a standard way to expose tools (and resources, and prompts) to any AI app. Without it, every app × every tool needs custom glue code. I wrapped my 3 tools as an MCP server, and Claude Code used them to find a Redis outage with no extra integration.

**How does MCP work under the hood?**
The client starts the server as a process (stdio transport) or connects over HTTP. They speak JSON-RPC: `tools/list` returns names, descriptions and schemas; `tools/call` runs one. In the Python SDK, `@mcp.tool()` builds the schema from type hints and the description from the docstring.

**MCP server vs agent?**
The server only has tools (hands). The agent is the LLM + loop (brain) that decides when to call them. One MCP server can serve many different agents.

**How do you make an MCP server safe to plug into someone else's system?**
Read-only tools, plus a config allow-list (`SERVICES` in `.env`), so the AI can only touch listed services. Anything risky (restarts) needs human approval.

---

## 8. LangGraph

**⭐ What is LangGraph and why use it over a plain loop?**
It models an agent as a graph: **state** (shared data), **nodes** (functions), **edges** (control flow). A plain loop is fine for one agent. LangGraph gives you multi-agent routing, human-in-the-loop interrupts, checkpointing (memory/resume), streaming and retries out of the box.

**⭐ What are state, nodes and edges?**
State = a typed dict passed through the graph. A node gets the state and returns an *update* (e.g. `{"messages": [reply]}`, which is appended). Edges set the order. Conditional edges choose the next node at runtime from a function's return value.

**How is a ReAct agent drawn in LangGraph?**
`START → llm`, conditional edge from `llm` (tool calls → `tools`, else → `END`), and `tools → llm`. That last edge is the loop.

**LangChain vs LangGraph?**
LangChain = building blocks (model wrappers, tools, structured output). LangGraph = orchestration (how the blocks are wired, with state). I use LangChain lightly, for `ChatGroq` + `@tool`, and LangGraph for the agent.

**How did you handle flaky LLM calls in LangGraph?**
A per-node `RetryPolicy(max_attempts=3, retry_on=BadRequestError)`. Groq sometimes rejects malformed tool calls from the model, and the node just reruns.

---

## 9. The project pitch (have this ready)

**⭐ "Tell me about a project you built."**
> *"I'm building an AI SRE: a multi-agent system that investigates production incidents. An alert comes in, a supervisor agent sends specialist agents to check logs, metrics, recent deploys and runbooks, and it produces a root-cause report with evidence. Risky actions like restarts need human approval. I test it by injecting real failures into a Spring Boot + Kafka + Redis system, and since each failure has a known root cause, I can measure accuracy."*

*(This grows as the project grows.)*

---

*New sections get added as each topic is covered: the agent loop, memory, multi-agent, MCP, A2A, guardrails, evals, LLMOps.*

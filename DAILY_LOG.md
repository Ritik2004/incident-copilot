# 📅 Daily Log

What I built each day, why, and what I learned, written so anyone can follow along and build it too.
Newest day at the top.

---

## Day 2 (Nov 19): the agent loop 🔁

**Goal:** stop calling the LLM a fixed number of times. Keep going until the LLM says "I'm done."

### Why
A real engineer doesn't stop at the first symptom. "Redis is timing out" isn't a root cause; *why* is Redis slow? The number of steps isn't known in advance, so the code needs a **loop**.

### What I built
```
repeat (max 5 times):
    ask the LLM (with the full history + tools)
    no tool calls?  → that's the final answer → return it
    tool calls?     → run each tool → add results to history → go round again
```
I also added a `redis.log` with a deeper problem hidden in it.

### 🎉 The result
```
Step 1: read_logs({'service': 'order-service'})   → sees Redis timeouts
Step 2: read_logs({'service': 'redis'})           → decided ON ITS OWN to check Redis
FINAL: analytics-job runs `KEYS order:*`, which blocks Redis's single thread for ~1.9 s
       → order-service times out → connection pool exhausted → HTTP 500s
```
`analytics-job` appears **only** in the Redis logs. A single call could never have found it.

### 🐛 Bugs of the day
1. **`msg.tool_calls[0] == ""` crashed.** When the LLM gives its final answer, `tool_calls` is `None` (Python's `null`), and `None[0]` raises `TypeError`. Fix: `if not msg.tool_calls:`, which is true for `None` *and* an empty list.
2. **`429 RateLimitError`, only sometimes.** The Groq free tier allows 8,000 tokens per minute, and one run uses ~5,000+. Fix for now: `Groq(..., max_retries=5)` and don't run back-to-back.

### 🧠 What I learned
- **An agent = an LLM + tools + a loop.** The loop ends when the LLM stops asking for tools.
- **`max_steps` is a safety limit.** Without it, a confused agent could loop (and bill you) forever.
- **Every step costs more than the last.** The LLM has no memory, so the full history (all the logs so far) is re-sent every step. That's why real agents trim or summarize tool results.
- **The system prompt shapes behaviour.** "Don't stop at the first symptom: keep digging" is what makes it go one level deeper.
- The LLM can ask for **several tools in one turn**, so we loop over `msg.tool_calls`.

### ⏭️ Next
More tools (`get_metrics`, `get_recent_deploys`) and a **name → function dict**, so the agent can choose between tools. Plus handling bad tool calls without crashing.

**Code:** [app/agent.py](app/agent.py)

---

## Day 1 (Nov 18–19): the first tool call

**Goal:** get an LLM to investigate an incident by *asking* for the logs it needs.

### What I built (in 3 small pieces)

**Piece 1: a plain Python function (no AI yet)**
`read_logs(service)` reads `data/logs/<service>.log`. If the file doesn't exist, it returns a message instead of crashing, because later that message goes back to the LLM so it can react.

**Piece 2: the "automated copy-paste" (a workflow)**
My code reads the logs and sends them to the LLM along with the alert. It's what you'd do by hand with ChatGPT.
→ The LLM found the root cause (Redis timeouts → connection pool exhausted → HTTP 500s) and ignored the two red herrings I planted in the logs.

**Piece 3: the LLM asks for the logs itself (a tool call)**
Now my code sends only the alert, plus a description of the `read_logs` tool. The flow:

```
Call 1:  alert + tool description  →  LLM replies: "run read_logs(service='order-service')"
My code: runs read_logs("order-service") → log text
         appends the LLM's request + the log text to the chat history
Call 2:  whole history  →  LLM reads the logs → root cause with timestamps
```

### 🐛 The bug of the day
The LLM asked for `order_service` (underscore), but the file is `order-service.log` (hyphen). So the tool returned "No logs found" and the agent never answered.

**Why:** my tool description said *"look at the **order_service** log file"*, and the parameter description was empty. The LLM copied the only example it had.
**Fix:** a generic description, plus a parameter description with exact example values (`'order-service'`, hyphen not underscore).
**Lesson:** the tool description is the LLM's *only* documentation. If it's vague or wrong, the agent is wrong.

### 🧠 What I learned
- **Workflow vs agent:** in a workflow, my code decides the steps. In an agent, the LLM decides the next step based on what it has seen. If the steps are known in advance, use a workflow.
- **The LLM never runs anything.** It returns a structured request (tool name + JSON arguments), and my code runs it.
- The tool's arguments arrive as a JSON **string**, so they need `json.loads()`.
- `tool_call_id` links each tool result to the request it answers.
- When the LLM asks for a tool, `message.content` is `None`. It's a request, not an answer.

### ⏭️ Next
Day 2: **the agent loop.** Keep going ("LLM asks → run tool → send back") until the LLM gives a final answer, with a step limit so it can't loop forever. Then add a second tool and pick the right Python function by tool name.

**Code:** [app/agent_v0.py](app/agent_v0.py)

---

## Day 0 (Nov 18): why this project

I wanted one project that covers everything a production AI engineer needs: RAG, agents, multi-agent systems, human-in-the-loop, MCP, A2A, guardrails, evals and LLMOps. It also had to be something people immediately understand.

**An AI SRE** fits all of that naturally:
- the steps depend on what you find, so an agent is actually justified
- it can take dangerous actions, so guardrails and human approval are *needed*, not decoration
- every injected failure has a known root cause, so there's a real eval score
- it builds on my backend background (Spring, Kafka, Redis)

# 📅 Daily Log

What I built each day, why, and what I learned, written so anyone can follow along and build it too.
Newest day at the top.

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

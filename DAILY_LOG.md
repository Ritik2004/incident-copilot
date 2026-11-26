# 📅 Daily Log

What I built each day, why, and what I learned, written so anyone can follow along and build it too.
Newest day at the top.

---

## Day 8 (Nov 26): my agent, rebuilt in LangGraph 🕸️

**Goal:** learn LangGraph on an agent I already understand, before going multi-agent.

### What I built
[app/graph_agent.py](app/graph_agent.py): the same incident agent, now a graph:
```
START → llm ──tool calls?── yes → tools ─┐
         ▲                                │
         └────────────────────────────────┘
         └── no → END
```
It found `redis: Exited` on a live incident, same as the hand-written loop.

### 🧠 What I learned
- **State** = one shared dict that every node reads and updates. `MessagesState` = just a `messages` list, and a node's returned messages get **appended**.
- **Node** = a plain function (`add_node("llm", call_llm)` registers name → function).
- **Edge** = the order (`add_edge(START, "llm")`). Edges use **names**, and LangGraph looks up the function at run time.
- **Conditional edge** = an arrow with an if (`tools_condition`: tool calls → `tools`, otherwise → `END`). That replaces my `if not msg.tool_calls`.
- **The `tools → llm` arrow *is* the loop.** No more `for step in range(...)`.
- **Retries are built in:** `RetryPolicy(max_attempts=3, retry_on=BadRequestError)` replaced my hand-written try/except retry for Groq's broken tool calls.
- **LangChain vs LangGraph:** LangChain = the parts (model wrapper `ChatGroq`, `@tool`, `bind_tools`). LangGraph = the flow.

### 🐛 Bugs of the day
- My node computed the LLM reply but didn't `return` it, so the reply never reached the state.
- I drew `llm → END` instead of `tools → llm`, so there was no way back to the LLM after a tool ran.

### ⏭️ Next
A `write_report` node (structured IncidentReport), then a multi-agent supervisor.

---

## Day 7 (Nov 24): evals fixed + my tools as an MCP server 🔌

**Goal:** fix two failing evals, then let *any* AI app use my tools, not just my own agent.

### What I built
- **Eval fixes:** wait 130s between scenarios (the tools look at the last 2 minutes, so a 30s wait left the previous scenario's errors visible), and a prompt rule: *"if a service's errors come from a call to another service, the root cause is that other service"*. The first 3 scenarios passed, including `payment-errors`, which failed before.
- **An MCP server** ([app/mcp_server.py](app/mcp_server.py)): it wraps my 3 tools with `@mcp.tool()`. The docstring becomes the description, and the type hints become the schema. About 25 lines, reusing the functions from `agent.py`.
- Tested it in the **MCP Inspector**, then plugged it into **Claude Code** (`claude mcp add`). Claude used my tools and confirmed: *"redis: Exited (0) 9 minutes ago. Exit code 0 means a clean stop, not a crash."*
- **An allow-list from config:** `SERVICES=order-service,payment-service,redis` in `.env`. Any other container is refused, so it's safe to plug into someone else's machine.

### 🐛 The bug of the day
`get_service_status` had a `service` parameter in the MCP server, but the real function takes none, so every call crashed. Claude could only say *"likely Redis, not confirmed"*. After the fix it said *"confirmed"*. Same lesson as Day 5: when an AI can't check, it can only guess.

### 🧠 What I learned
- **MCP = USB-C for AI tools.** You write the tools once as a server, and any MCP client (Claude Code, Claude Desktop, Cursor, my own agent) can use them.
- **Tools vs agent:** the MCP server is just the hands. The brain is whichever AI connects to it.
- Under the hood: the client starts the server as a process and talks **JSON-RPC over stdio**: `tools/list`, then `tools/call`.
- `mcp` 2.x renamed `FastMCP` → `MCPServer` (`from mcp.server.mcpserver import MCPServer`).
- `load_dotenv()` must run **before** `os.getenv(...)`, or `.env` values are ignored.

### ⏭️ Next
Multi-agent with LangGraph: a supervisor plus specialist agents.

---

## Day 6 (Nov 23): a structured report + the first eval score 📊

**Goal:** stop judging the agent by "it worked once". Give it a number.

### What I built
- **`IncidentReport`** (Pydantic): `root_cause`, `root_cause_service`, `affected_services`, `evidence`, `confidence` (low/medium/high), `suggested_action`
- **Two phases:** investigate with tools → then one more LLM call fills the form (Groq `response_format` = the Pydantic JSON schema → `model_validate_json`)
- **`evals/scenarios.json`**: 5 incidents with known answers (redis-down, payment-errors, payment-down, payment-slow, no-incident)
- **`evals/run_evals.py`**: break → send orders → run agent → compare `root_cause_service` → fix → score

### 📊 Scores
| Run | Score | What changed |
|---|---|---|
| 1 | **2/5** | 2 crashes (the model sent broken tool calls), no-incident blamed old errors |
| 2 | **3/5** | retry on broken tool calls + tools only look at the **last 2 minutes** |

Still failing: **payment-errors** (blamed order-service) and **no-incident** (the 30s wait between tests is shorter than the 2-minute window, so it saw the previous test's chaos logs).

### 🧠 What I learned
- **Field names and descriptions are part of the prompt.** `affected_services` was ambiguous, so the LLM left redis out. Fixed by adding `root_cause_service` + `Field(description=...)`.
- **Evals catch what demos hide:** crashes, stale data, wrong blame.
- **A wrong expected answer is the worst eval bug** (I copy-pasted "redis" into a payment scenario).
- **LLMs sometimes send broken tool calls.** Retrying is normal production practice.
- **Tools need a time window.** Old errors look exactly like new ones.

### ⏭️ Next
`time.sleep(130)` between scenarios, then fix the payment-errors blame with the prompt.

---

## Day 5 (Nov 22): the agent investigates a REAL incident 🕵️

**Goal:** stop reading fake files. Point the agent's tools at the real shop from Day 4.

### What I built (this time I wrote the code myself)
| Tool | Before | Now |
|---|---|---|
| `read_logs(service)` | opened a fake `.log` file | runs `docker logs`, keeps only **ERROR/WARN** lines, last 30 |
| `get_metrics(service)` | opened a fake `metrics.json` | asks **Prometheus** for request counts by status (hides Prometheus's own `/actuator` requests) |
| 🆕 `get_service_status()` | — | runs `docker ps -a`: which services are **Up** and which have **Exited** |
| `get_recent_deploys()` | fake deploys | **removed** for now. Fake data would mislead the agent on a real system |

- First plug-and-play setting: `PROMETHEUS_URL` comes from `.env` (default `localhost:9090`), so anyone can point it at their own Prometheus.

### 🎉 The result: two runs, same incident (Redis stopped)

**Run 1** (only logs + metrics):
```
Step 1: get_metrics(order-service)
Step 2: read_logs(order-service)        → "Failed to resolve 'redis'"
Step 3: get_metrics(redis)              → no data
FINAL: "Redis was renamed in a Kubernetes deployment, run kubectl..."   ❌ made up
```
There's no Kubernetes and nothing was renamed. In Docker, a **stopped** container's name disappears from the network, so "can't resolve redis" just meant **Redis wasn't running**. The agent had no tool to check that, so it **guessed** the most common story from its training.

**Run 2** (+ `get_service_status` + a stricter prompt):
```
Step 1: get_metrics(order-service)      → 500s with RedisConnectionFailureException
Step 2: read_logs(order-service)        → "Cannot reconnect to redis", "Redis command timed out"
Step 3: get_service_status()            → redis: Exited (0) About an hour ago
FINAL: "Redis container exited → order-service can't connect → 500s. Restart Redis, check why it exited." ✅
```

### 🐛 Bugs of the day
1. **`--tail` without a number.** `docker logs --tail order-service` treats the service name as the number.
2. **A missing container looked "healthy".** Docker says `Error response...` (not `ERROR`), so my filter found nothing and returned "no errors". Fix: check `returncode` first. **A wrong answer that looks right is the worst kind of bug.**
3. **`http_server__requests`** (two underscores). Prometheus doesn't complain, it just returns nothing.
4. **441 "successful requests"** were Prometheus scraping itself. Filtered with `uri!~"/actuator.*"`.
5. **The prompt mentioned a deploys tool that no longer existed.** The prompt and the tools must match.

### 🧠 What I learned
- **An agent is only as good as its tools.** When it can't check something, it guesses, and the guess sounds confident.
- **Ground the prompt:** "only claim what the evidence shows, say what you don't know, don't assume an environment."
- **How the LLM picks a tool:** only from the name + description + what it has seen so far. It never sees the code.
- **Filter before the LLM sees it**, for logs (219 → 8 lines) and metrics (hide self-scrapes). Less noise = better answers + fewer tokens.
- Python: `subprocess.run` (like `ProcessBuilder`), list comprehensions (like `stream().filter()`), slicing `[-30:]`, `httpx.get(..., params=...)`, `{{ }}` inside f-strings, `if __name__ == "__main__"` (like `main`).
- Agent patterns: my loop **is** the ReAct pattern (reason → act → observe → repeat).

### ⏭️ Next
Step 2: a **structured report** (root cause, evidence, confidence, suggested action) instead of free text, so a UI, Slack, or an eval can read it.

**Code:** [app/agent.py](app/agent.py)

---

## Day 4 (Nov 21): a real system to break 💥

**Goal:** stop investigating fake files. Build a small real "shop" that I can break on purpose.

### What I built (in `demo-system/`)
```
curl → order-service ──▶ Redis (saves the order)
             └──────────▶ payment-service ("PAID")
Prometheus collects numbers from both every 5s
```
- **order-service** and **payment-service**: two Spring Boot apps, each in its own Docker container
- **Redis** and **Prometheus**: ready-made images, nothing to build
- **One command starts everything:** `docker compose up --build`
- **Chaos switches** in payment-service:
  ```bash
  curl -X POST "localhost:8081/chaos/errors?on=true"     # every payment fails
  curl -X POST "localhost:8081/chaos/latency?ms=5000"    # every payment is slow
  curl -X POST  localhost:8081/chaos/reset               # back to normal
  ```

### 💥 Incidents I caused today
| What I broke | What I saw |
|---|---|
| `docker stop redis` | at first, curl **hung for 60s** (default Redis timeout) → added a 2s timeout → fast 500. Log: `QueryTimeoutException: Redis command timed out` |
| `docker start redis` | **still 500s for ~30s!** The client retries with exponential backoff, so it hadn't reconnected yet. Log: `Reconnected to redis:6379` |
| payment errors ON | order-service returned 500, but **its own code was fine**. The cause was downstream. |
| payment latency 20s | each order took **20 seconds**: no timeout on the HTTP call. One slow dependency can freeze the caller (a cascading failure). |

In Prometheus, the metric even named the exception:
```
http_server_requests_seconds_count{status="500", exception="RedisConnectionFailureException", uri="/orders"}
```

### 🐛 Bugs of the day
1. **Controller not found → 404.** Spring only scans the main class's package and the packages *under* it. VS Code also generated `package main.java.com.shop...`: wrong package, so no endpoint.
2. **`app.jarx`**: a stray keypress in the Dockerfile → "Unable to access jarfile".
3. **Prometheus said DOWN (HTTP 406)**: a metrics-format mismatch. Fixed with `scrape_protocols: [PrometheusText0.0.4]`.
4. **Build failed with no clear reason**: the real error is *higher up*. `docker compose build x 2>&1 | grep "ERROR.*java"` shows the file + line.

### 🧠 What I learned
- **Dockerfile** = the recipe to pack one app into an image. **docker-compose** = start all the boxes together. Containers find each other **by name** (`redis`, `payment-service`).
- **Where `docker logs` comes from:** the app prints to the console → Docker saves it → `docker logs` reads it.
- **Logs vs metrics:** metrics say *when* and *how bad*, logs say *why*.
- **Only 8 of 219 log lines mattered** (ERROR/WARN). The rest were stack traces. My agent's log tool must filter, or it wastes tokens.
- **Always set timeouts.** A fast error is better than a hang.
- **"The dependency is back" ≠ "the service has recovered".** Check for the reconnect.

### ⏭️ Next
- Add the 2s timeout to the payment call (and watch 20s become 2s)
- **Rewire my agent** (on my own this time): `read_logs` → real `docker logs` (ERROR/WARN only), `get_metrics` → real Prometheus queries

**Code:** [demo-system/](demo-system/)

---

## Day 3 (Nov 20–21): three tools, and the agent picks 🧰

**Goal:** give the agent the 3 questions a real on-call engineer asks: *what do the logs say?*, *what do the numbers say?*, *what changed?*

### What I built
- 🆕 `get_metrics(service)`: per-minute error rate, latency and traffic (from `data/metrics.json`)
- 🆕 `get_recent_deploys()`: recent deploys across all services (from `data/deploys.json`), a tool with **no parameters**
- 🆕 a **`TOOLS` dict** mapping the name the LLM asks for → the Python function:
  ```python
  TOOLS = {"read_logs": read_logs, "get_metrics": get_metrics, "get_recent_deploys": get_recent_deploys}
  func = TOOLS.get(name)        # returns None (not a crash) if the LLM invents a tool
  result = func(**args)         # {"service": "redis"} → func(service="redis")
  ```
- 🆕 **error handling:** unknown tool → error message; bad arguments or a crashing tool → `try/except` → error message. The agent never crashes; the LLM reads the error and adapts.

### 🎉 The result
```
Step 1: get_metrics(order-service)   → errors jumped at 10:42
Step 2: read_logs(order-service)     → Redis timeouts
Step 3: get_metrics(redis)           → Redis latency 2 ms → 1890 ms
Step 4: get_recent_deploys({"":""})  → the LLM sent BROKEN arguments → error returned, no crash
Step 5: get_recent_deploys({})       → the LLM fixed its own mistake
FINAL: analytics-job v2.3.0 deployed at 10:41:30 (KEYS order:*) → Redis blocked → order-service 500s
```
It ignored the two unrelated deploys (payment-service timeout change, order-service TTL config).

### 🐛 Bugs of the day
1. **`json.dump` vs `json.dumps`.** `dump` writes to a *file*; `dumps` returns a *string* (the `s` = string). The LLM needs a string.
2. **`func = ...` left in.** `...` isn't a function, so every call failed and the LLM retried the *same* call 5 times until `max_steps` stopped it. Lesson: `max_steps` really matters, and real agents also stop on repeated identical failures.
3. **`tools` / `Tools` vs `TOOLS`.** Python is case-sensitive. Worse, VS Code "helpfully" auto-added `from asyncio import tools`, which crashed on start. Always check imports you didn't write.

### 🧠 What I learned
- **A real investigation uses several sources:** metrics (*when* and *how bad*), logs (*what* is failing), deploys (*what changed*). Most incidents are caused by a change.
- **Dispatching tools:** the LLM returns a *name*, and a dict maps the name → function. Adding a tool = write the function + schema + one dict entry.
- **Never let a tool crash the agent.** Return the error as text; the LLM can often recover on its own.
- Python: `try/except` = try/catch · `dict.get(key)` returns `None` instead of raising · `**args` unpacks a dict into named arguments · ALL_CAPS = a constant.

### ⏭️ Next
The weekend: the **Java demo system** (Spring Boot + Kafka + Redis + Postgres + Prometheus) that we can break for real. Then the tools stop reading fake files and read the real system.

**Code:** [app/agent.py](app/agent.py) · **Data:** [data/metrics.json](data/metrics.json), [data/deploys.json](data/deploys.json)

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

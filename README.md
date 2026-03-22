# ✈️ VOYAGER v4 — RCG Multi-Agent Travel Intelligence

A production-grade multi-agent AI travel assistant built with LangGraph, FastAPI and OpenAI.
Uses RCG (Retrieval-Contextual Grounding) prompting — every agent retrieves live data from
the internet before reasoning, so answers are always current and source-cited.

---

## Quick Start

```bash
# 1. Add your API key
cp .env.example .env
# Open .env and set: OPENAI_API_KEY=sk-...

# 2. Create virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Run
uvicorn app.main:app --reload --port 8000
```

Open your browser → **http://localhost:8000**

---

## How It Works

```
User message
     │
     ▼
[Clarifier]  — checks if enough context exists to proceed
     │           for planning queries: needs destination + dates/duration
     │           for safety/weather:   needs destination only
     │           asks ONE question if missing, then waits for reply
     ▼
[Supervisor] — decides which specialist agents to invoke
     │
     ├──► [Planner Agent]    ┐
     ├──► [Weather Agent]    │  run in PARALLEL
     ├──► [Advisory Agent]   │  each has own LLM + tools
     ├──► [Activities Agent] │  each retrieves live web data
     └──► [Rescue Agent]     ┘
                  │
                  ▼
          [Synthesiser]  — merges all outputs into final response
                  │
            Browser UI
```

---

## RCG Prompting — What It Means

RCG (Retrieval-Contextual Grounding) is the core prompting strategy used throughout.

**The principle:** agents are reasoners over retrieved data, not knowledge stores.

| Without RCG | With RCG |
|---|---|
| Model recalls visa rules from training data | Model calls official immigration API, cites source + date |
| Possibly outdated or wrong | Always current, always cited |
| "Japan is visa-free for Singapore" (no source) | "Per Japan Immigration Bureau (retrieved 2025-03-01): visa-free 90 days" |

**4 RCG goals implemented:**

1. **Comprehensive context** — every agent gets a structured context packet with destination, dates, duration, origin and purpose before calling tools
2. **Structured inputs** — synthesiser receives agent outputs wrapped in XML tags (`<agent_output>`, `<retrieved_data>`, `<agent_reasoning>`) for clean multi-source navigation
3. **Task-model alignment** — model strength matched to task complexity (see table below)
4. **Leverage** — agents are instructed to ground every claim in tool results, never training memory

**Model assignment:**

| Component | Model | Reason |
|---|---|---|
| Clarifier | gpt-4o-mini | Simple context classification |
| Supervisor | gpt-4o-mini | Simple routing decision |
| Planner, Weather, Activities, Rescue | gpt-4o-mini | Structured retrieval tasks |
| **Advisory Agent** | **gpt-4o** | Safety-critical reasoning requires accuracy |
| **Synthesiser** | **gpt-4o** | Complex multi-source merging |

---

## Agent Network

| Agent | Responsibility | Tools |
|---|---|---|
| 🎯 Orchestrator | Routes queries, coordinates all agents | — |
| 🗺️ Planner | Day-by-day itineraries, flights, hotels | `build_itinerary`, `search_flights`, `search_hotels` |
| 🌤️ Weather | Forecasts, seasonal patterns, packing | `get_weather_forecast`, `get_seasonal_info` |
| 🎭 Activities | Attractions, restaurants, experiences | `search_activities`, `search_restaurants` |
| 🛡️ Advisory | Safety, visa, vaccines, local laws | `get_travel_advisory`, `get_visa_requirements`, `get_vaccine_requirements`, `get_local_laws` |
| 🚨 Rescue | Emergency contacts, hospitals, embassies | `get_emergency_contacts`, `get_nearest_hospital` |

All tools use OpenAI with `web_search_preview` — no hardcoded data anywhere.

---

## Project Structure

```
voyager-v4/
├── app/
│   ├── main.py                    ← FastAPI entry point
│   ├── config.py                  ← Settings from .env (model routing config)
│   │
│   ├── agents/
│   │   ├── base.py                ← BaseAgent: agentic tool-calling loop + full history
│   │   └── specialists.py         ← 5 agents with RCG system prompts
│   │
│   ├── graph/
│   │   ├── state.py               ← TravelState: shared data between all nodes
│   │   ├── clarifier.py           ← Checks context, asks for missing info (planning needs dates)
│   │   ├── supervisor.py          ← Routes query to correct agents
│   │   ├── nodes.py               ← Node functions with _build_context_packet()
│   │   ├── synthesiser.py         ← Merges parallel outputs using XML-tagged inputs
│   │   └── builder.py             ← Wires the graph, compiles with MemorySaver
│   │
│   ├── routers/
│   │   ├── chat.py                ← POST /api/chat (handles clarification + normal flow)
│   │   └── health.py              ← GET /api/health, /api/ready
│   │
│   ├── tools/
│   │   └── travel_tools.py        ← All @tool functions — AI-powered with web search
│   │
│   └── static/
│       └── index.html             ← Web UI (marked.js, agent cards, session memory)
│
├── requirements.txt
├── .env.example                   ← Copy to .env and add your API key
├── .gitignore
└── README.md
```

---

## Key Files Explained

### `app/graph/state.py`
The shared data baton passed between every node. Uses `operator.add` on
`messages` and `agent_responses` so parallel agents can write results
simultaneously without overwriting each other.

### `app/graph/clarifier.py`
Runs first on every message. Extracts travel context (destination, dates,
duration, origin) from the full conversation history. Crucially, it links
short follow-up answers to prior questions — so "7 days in september" after
being asked when you're travelling correctly maps to travel_dates + trip_duration.

For **planning queries**: requires destination + dates or duration before proceeding.
For **safety/weather/activities**: only requires destination.

### `app/graph/nodes.py`
Each node calls `_build_context_packet()` which gives agents a structured brief:
```
=== TRIP CONTEXT ===
Destination:  Japan
Travel dates: September
Duration:     7 days

=== GROUNDING REMINDER ===
Call tools FIRST. Base response on retrieved data.
```

### `app/agents/base.py`
The agentic loop that all specialists inherit. Passes the full conversation
history to each agent (not just the latest message) so agents understand
multi-turn references like "change Day 3" or "make it cheaper".

### `app/tools/travel_tools.py`
Every tool calls `client.responses.create()` with `web_search_preview` enabled.
No hardcoded data. Itineraries, advisories, visa rules, weather and emergency
contacts are all retrieved live from the internet.

### `app/graph/synthesiser.py`
Wraps each agent's output in `<agent_output>` XML tags before sending to gpt-4o.
The grounding rule prevents the synthesiser from adding claims not present in
retrieved data.

---

## Conversation Flow Examples

**Planning query:**
```
User:      "plan a trip to japan"
Clarifier: destination=Japan ✓, dates=missing → asks "When and how many days?"
User:      "7 days in september"
Clarifier: links answer → travel_dates=September, trip_duration=7 days → proceed
Supervisor: routes to planner + weather + activities + advisory
Agents:    each retrieves live data, gets full 9-message history
Synthesiser: merges all outputs → full travel plan returned
```

**Safety query:**
```
User:      "is bangkok safe right now?"
Clarifier: destination=Bangkok ✓, safety query → proceed immediately (no dates needed)
Supervisor: routes to advisory
Advisory:  calls get_travel_advisory, get_visa_requirements, get_vaccine_requirements
           cites US State Dept + UK FCO with dates
Synthesiser: merges → safety summary with source cards
```

**Follow-up:**
```
User:      "change day 3 to focus on food"
Clarifier: destination known, dates known → proceed
Supervisor: routes to planner + activities
Agents:    receive full conversation history including prior plan
Planner:   understands what Day 3 was → updates accordingly
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | required | Your OpenAI API key from platform.openai.com |
| `OPENAI_MODEL` | gpt-4o | Complex reasoning: advisory agent, synthesiser |
| `OPENAI_MODEL_MINI` | gpt-4o-mini | Simple agents: planner, weather, activities, rescue |
| `OPENAI_MODEL_ROUTER` | gpt-4o-mini | Routing only: clarifier, supervisor |
| `ENV` | development | Environment name |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web UI |
| `POST` | `/api/chat` | Send message, get agent response |
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/ready` | Readiness check (verifies API key) |
| `GET` | `/api/graph` | Graph structure info |

**POST /api/chat request:**
```json
{
  "messages": [{"role": "user", "content": "Plan a trip to Japan"}],
  "session_id": "optional-uuid-for-memory-continuity"
}
```

**POST /api/chat response:**
```json
{
  "result": {
    "orchestrator_message": "Here is your 7-day Japan itinerary...",
    "destination": "Japan",
    "agents_involved": ["planner", "weather", "activities", "advisory"],
    "agent_responses": { ... }
  },
  "session_id": "uuid",
  "clarification_needed": false,
  "clarification_question": null
}
```

---

## Adding a New Agent

1. **`app/tools/travel_tools.py`** — add `@tool` functions and a tool registry
2. **`app/agents/specialists.py`** — add agent class with RCG system prompt
3. **`app/graph/nodes.py`** — add node function passing full history + context packet
4. **`app/graph/builder.py`** — register node, add to `AGENT_NODE_MAP`, add edge to synthesiser
5. **`app/graph/supervisor.py`** — update `SUPERVISOR_SYSTEM` to include the new agent

---

## Troubleshooting

| Error | Fix |
|---|---|
| `OPENAI_API_KEY not configured` | Check `.env` file exists and has your key |
| `client.responses.create` not found | Run `pip install --upgrade openai` (needs ≥1.66.0) |
| `ImportError: DLL load failed` | Run `pip install greenlet --only-binary=:all:` then reinstall |
| `Port 8000 already in use` | Change to `--port 8001` |
| Agents returning generic data | Web search tools need internet access — check firewall |
| Long response times | Normal — each agent makes 1-3 web search calls in parallel |

---

## Memory

Sessions are tracked by `session_id`. The browser generates one on first message
and reuses it for the entire conversation. LangGraph stores state under this ID
using `MemorySaver` — conversation history persists for the duration of the server session.

Restarting the server clears all memory. For persistent memory across restarts,
install C++ Build Tools then uncomment the SQLite lines in `requirements.txt`.

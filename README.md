# ✈️ TRAVELBUDDY — LangGraph Multi-Agent Edition

Real multi-agent travel assistant using LangGraph supervisor pattern.

## How it actually works

```
User message
     │
     ▼
[Supervisor]  — gpt-4o decides which agents to invoke
     │
     ├──► [Planner Agent]    — flights, hotels, itinerary  (gpt-4o-mini + tools)
     ├──► [Weather Agent]    — forecast, packing           (gpt-4o-mini + tools)
     ├──► [Activities Agent] — things to do, restaurants   (gpt-4o-mini + tools)
     ├──► [Advisory Agent]   — safety, visa, vaccines      (gpt-4o-mini + tools)
     └──► [Rescue Agent]     — emergency contacts          (gpt-4o-mini + tools)
                  │ (all run in PARALLEL)
                  ▼
          [Synthesiser]  — gpt-4o merges all outputs
                  │
                  ▼
            Final response
```

Each agent has its own LLM instance, its own tools, and runs independently.

## Quick start

```bash
# 1. Add your API key
cp .env.example .env
# edit .env — set OPENAI_API_KEY=sk-...

# 2. Install
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt

# 3. Run
uvicorn app.main:app --reload --port 8000
```

Open → http://localhost:8000

## Project structure

```
app/
├── main.py                   ← FastAPI entry point
├── config.py                 ← Settings from .env
├── agents/
│   ├── base.py               ← BaseAgent: agentic tool-calling loop
│   └── specialists.py        ← 5 agents: Planner, Weather, Activities, Advisory, Rescue
├── graph/
│   ├── state.py              ← TravelState: shared data between nodes
│   ├── supervisor.py         ← Routing node: decides which agents to call
│   ├── nodes.py              ← One LangGraph node per agent
│   ├── synthesiser.py        ← Merges all agent outputs into final response
│   └── builder.py            ← Wires the graph, compiles with memory
├── routers/
│   ├── chat.py               ← POST /api/chat
│   └── health.py             ← GET /api/health
├── tools/
│   └── travel_tools.py       ← All @tool functions each agent can call
└── static/
    └── index.html            ← Web UI
```

## Memory

Sessions are tracked by `session_id`. The frontend generates one per browser session
and sends it with every message. LangGraph uses it as `thread_id` to maintain
conversation history in MemorySaver.

To switch to persistent memory (survives restarts), change in `builder.py`:
```python
build_graph(use_sqlite=True)
```

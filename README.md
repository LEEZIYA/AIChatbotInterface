# ✈️ TravelBuddy — AI Travel Intelligence

Multi-agent AI travel assistant powered by OpenAI GPT-4o.

---

## Prerequisites

- Python 3.11+ **or** Docker Desktop installed
- An OpenAI API key → https://platform.openai.com/api-keys

---

## Step 1 — Add your API key

```bash
# Rename the example file
cp .env.example .env

# Open .env and replace sk-... with your real key
OPENAI_API_KEY=sk-your-real-key-here
```

---

## Option A — Run with Python (no Docker)

```bash
# 1. Create a virtual environment
python -m venv venv
py -m venv venv

# 2. Activate it
#    Mac/Linux:
source venv/bin/activate
#    Windows:
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the server
uvicorn app.main:app --reload --port 8000
```

Open your browser → **http://localhost:8000**

To stop: press `Ctrl + C`

---

## Option B — Run with Docker

```bash
# 1. Build the image (only needed once, or after code changes)
docker build -t TravelBuddy .

# 2. Run the container
docker run -p 8000:8000 --env-file .env TravelBuddy
```

Open your browser → **http://localhost:8000**

To stop: press `Ctrl + C`

---

## Project structure

```
TravelBuddy/
├── app/
│   ├── main.py              ← FastAPI app
│   ├── config.py            ← Settings (reads from .env)
│   ├── agents/
│   │   └── orchestrator.py  ← All 6 agents + OpenAI call
│   ├── routers/
│   │   ├── chat.py          ← POST /api/chat
│   │   └── health.py        ← GET /api/health
│   └── static/
│       └── index.html       ← The web UI
├── .env.example             ← Copy this to .env
├── Dockerfile
└── requirements.txt
```

---

## API endpoints

| Method | URL | Description |
|---|---|---|
| `GET` | `/` | Opens the web UI |
| `GET` | `/api/health` | Check if server is running |
| `POST` | `/api/chat` | Send a message to the agents |

---

## Changing the model

Open `.env` and change:
```
OPENAI_MODEL=gpt-4o        # Best quality
OPENAI_MODEL=gpt-4o-mini   # Faster and cheaper
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `OPENAI_API_KEY not configured` | Make sure `.env` exists and has your key |
| `Port 8000 already in use` | Change `--port 8000` to `--port 8001` |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| Docker: `Cannot connect to Docker daemon` | Open Docker Desktop first |

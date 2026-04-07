# Using uvicorn (recommended ASGI server)
uvicorn APIAgent:app --reload

# Or specify host and port
uvicorn APIAgent:app --host 0.0.0.0 --port 8000 --reload\

# Development
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production (no reload, multiple workers)
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# With logging level
uvicorn main:app --reload --log-level debug

# Custom configuration
uvicorn main:app --reload --reload-dir ./app --reload-delay 2

curl -v -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Test"}'

## test demo
### in /app/
python run_chat.py
### in main directory
python ./app/run_chat.py


## test APIAgent.py
python -m app.agents.APIAgent.py

curl -X POST "http://localhost:8000/api/chat" -H "Content-Type: application/json" -d "{\"question\":\"Is Bali safe for solo travellers?\",\"context\":{}}"

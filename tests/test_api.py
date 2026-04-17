"""Basic API tests — no real OpenAI calls (mocked)."""
import os
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy")
os.environ.setdefault("OPENAI_MODEL",        "gpt-4o")
os.environ.setdefault("OPENAI_MODEL_MINI",   "gpt-4o-mini")
os.environ.setdefault("OPENAI_MODEL_ROUTER", "gpt-4o-mini")
os.environ.setdefault("ENV", "test")

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app

MOCK_RESULT = {
    "orchestrator_message": "Here is your 3-day Bangkok itinerary.",
    "destination": "Bangkok, Thailand",
    "trip_duration": "3 days",
    "travel_dates": "July",
    "agents_involved": ["transport", "accommodation", "weather", "activities", "advisory"],
    "itinerary": [
        {"day": 1, "items": [{"time": "09:00", "activity": "Wat Pho Temple — see the giant reclining Buddha"}]},
        {"day": 2, "items": [{"time": "09:00", "activity": "Chatuchak Weekend Market — best on weekends"}]},
        {"day": 3, "items": [{"time": "09:00", "activity": "Grand Palace — arrive early to beat crowds"}]},
    ],
    "agent_responses": {
        "transport":     {"active": True,  "response": "Flights from Singapore to Bangkok are available.", "flights": []},
        "accommodation": {"active": True,  "response": "Sukhumvit is ideal for first-time visitors.", "hotels": []},
        "weather":       {"active": True,  "response": "July is rainy season in Bangkok.", "forecast": []},
        "activities":    {"active": True,  "response": "Bangkok has incredible temples and street food.", "highlights": []},
        "advisory":      {"active": True,  "response": "Bangkok is rated LOW risk.", "risk_level": "LOW"},
        "rescue":        {"active": False, "response": "", "emergency_numbers": None},
    },
}

MOCK_STATE = {
    "clarification_needed": False,
    "clarification_question": None,
    "final_response": MOCK_RESULT,
    "destination": "Bangkok, Thailand",
    "trip_duration": "3 days",
    "travel_dates": "July",
    "traveler_origin": None,
}

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.anyio
async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

@pytest.mark.anyio
async def test_ready(client):
    r = await client.get("/api/ready")
    assert r.status_code == 200

@pytest.mark.anyio
async def test_chat_returns_itinerary(client):
    with patch("app.routers.chat.get_graph") as mock:
        g = AsyncMock()
        g.ainvoke = AsyncMock(return_value=MOCK_STATE)
        mock.return_value = g
        r = await client.post("/api/chat", json={
            "messages": [{"role": "user", "content": "plan 3 day trip to bangkok in july"}]
        })
    assert r.status_code == 200
    data = r.json()
    assert data["clarification_needed"] is False
    assert data["result"]["itinerary"] is not None
    assert len(data["result"]["itinerary"]) == 3

@pytest.mark.anyio
async def test_chat_empty_messages(client):
    r = await client.post("/api/chat", json={"messages": []})
    assert r.status_code == 422

@pytest.mark.anyio
async def test_chat_invalid_role(client):
    r = await client.post("/api/chat", json={"messages": [{"role": "system", "content": "hi"}]})
    assert r.status_code == 422

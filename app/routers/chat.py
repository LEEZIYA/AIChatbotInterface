"""
Chat Router
POST /api/chat  — accepts conversation history, returns multi-agent response
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Any
import logging
import time

from app.agents.orchestrator import OrchestratorAgent

logger = logging.getLogger("TravelBuddy.chat")
router = APIRouter(tags=["chat"])

# Simple in-memory rate limiter (per IP, resets each minute)
_rate_store: dict[str, list[float]] = {}
RATE_LIMIT = 30  # requests per minute


def check_rate_limit(ip: str) -> bool:
    now = time.time()
    window = 60.0
    hits = _rate_store.get(ip, [])
    hits = [t for t in hits if now - t < window]
    if len(hits) >= RATE_LIMIT:
        return False
    hits.append(now)
    _rate_store[ip] = hits
    return True


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=50)


class ChatResponse(BaseModel):
    result: dict[str, Any]
    tokens_used: int = 0


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    client_ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")

    try:
        agent = OrchestratorAgent()
        messages = [{"role": m.role, "content": m.content} for m in body.messages]
        result = await agent.run(messages)
        logger.info(f"Chat OK — ip={client_ip} agents={result.get('agents_involved', [])}")
        return ChatResponse(result=result)

    except Exception as exc:
        logger.error(f"Chat error — ip={client_ip} error={exc}")
        raise HTTPException(status_code=500, detail=str(exc))

"""
Chat Router
-----------
POST /api/chat  — runs the LangGraph multi-agent graph
GET  /api/graph — returns a description of the graph structure (for debugging)
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import logging
import time
import uuid

from app.graph.builder import get_graph
from app.config import settings

logger = logging.getLogger("TRAVELBUDDY.chat")
router = APIRouter(tags=["chat"])

# Rate limiter
_rate_store: Dict[str, List[float]] = {}


def check_rate_limit(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _rate_store.get(ip, []) if now - t < 60.0]
    if len(hits) >= settings.RATE_LIMIT_RPM:
        return False
    hits.append(now)
    _rate_store[ip] = hits
    return True


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1, max_length=50)
    session_id: Optional[str] = None  # client can pass a session ID for continuity


class ChatResponse(BaseModel):
    result: Dict[str, Any]
    session_id: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    client_ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")

    # Use provided session_id or generate a new one
    # The session_id is the LangGraph thread_id — it links to stored memory
    session_id = body.session_id or str(uuid.uuid4())

    try:
        graph = get_graph()

        # Build the initial state for this graph run
        messages = [{"role": m.role, "content": m.content} for m in body.messages]

        initial_state = {
            "messages":        messages,
            "next_agents":     [],
            "destination":     None,
            "travel_dates":    None,
            "traveler_origin": None,
            "agent_responses": [],
            "final_response":  None,
            "session_id":      session_id,
        }

        # LangGraph config — thread_id links this run to the session's memory
        config = {"configurable": {"thread_id": session_id}}

        # ── Run the graph ──────────────────────────────────────────────────────
        # ainvoke runs all nodes asynchronously, returns final state
        final_state = await graph.ainvoke(initial_state, config=config)

        result = final_state.get("final_response", {})

        logger.info(
            f"Chat OK — ip={client_ip} session={session_id} "
            f"agents={result.get('agents_involved', [])} "
            f"dest={result.get('destination')}"
        )

        return ChatResponse(result=result, session_id=session_id)

    except Exception as exc:
        logger.error(f"Chat error — session={session_id} error={exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/graph")
async def graph_info():
    """Returns the graph node structure — useful for debugging."""
    return {
        "nodes": ["supervisor", "planner", "weather", "activities", "advisory", "rescue", "synthesiser"],
        "flow": "START → supervisor → [parallel agents] → synthesiser → END",
        "memory": "MemorySaver (session)",
        "model_supervisor": settings.OPENAI_MODEL,
        "model_agents": settings.OPENAI_MODEL_MINI,
    }

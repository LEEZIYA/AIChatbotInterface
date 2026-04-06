"""
Chat Router — POST /api/chat
Handles both normal agent responses and clarification questions.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import logging, time, uuid

from app.graph.builder import get_graph
from app.config import settings

logger = logging.getLogger("travelbuddy.chat")
router = APIRouter(tags=["chat"])
_rate_store: Dict[str, List[float]] = {}


def check_rate_limit(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _rate_store.get(ip, []) if now - t < 60.0]
    if len(hits) >= settings.RATE_LIMIT_RPM: return False
    hits.append(now); _rate_store[ip] = hits; return True


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1, max_length=50)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    result: Dict[str, Any]
    session_id: str
    clarification_needed: bool = False
    clarification_question: Optional[str] = None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

    session_id = body.session_id or str(uuid.uuid4())

    try:
        graph = get_graph()
        messages = [{"role": m.role, "content": m.content} for m in body.messages]

        initial_state = {
            "messages": messages,
            "next_agents": [],
            "destination": None, "travel_dates": None,
            "traveler_origin": None, "trip_duration": None, "travel_purpose": None,
            "clarification_needed": False, "clarification_question": None,
            "clarification_field": None, "collected_info": {},
            "agent_responses": [], "final_response": None,
            "session_id": session_id,
        }

        config = {"configurable": {"thread_id": session_id}}
        final_state = await graph.ainvoke(initial_state, config=config)

        # Clarification response
        if final_state.get("clarification_needed"):
            question = final_state.get("clarification_question", "Could you tell me more about your trip?")
            logger.info(f"Clarification: session={session_id} q='{question}'")
            return ChatResponse(
                result={
                    "orchestrator_message": question,
                    "destination": final_state.get("destination"),
                    "agents_involved": ["clarifier"],
                    "agent_responses": {
                        "planner":    {"active": False, "response": "", "itinerary": None},
                        "weather":    {"active": False, "response": "", "forecast": None},
                        "activities": {"active": False, "response": "", "highlights": None},
                        "advisory":   {"active": False, "response": "", "risk_level": "LOW",
                                       "hazards": None, "visa": None, "vaccines": None,
                                       "local_rules": None, "sources": []},
                        "rescue":     {"active": False, "response": "", "emergency_numbers": None},
                    }
                },
                session_id=session_id,
                clarification_needed=True,
                clarification_question=question,
            )

        result = final_state.get("final_response") or {}
        logger.info(f"Chat OK — session={session_id} agents={result.get('agents_involved')} dest={result.get('destination')}")
        return ChatResponse(result=result, session_id=session_id)

    except Exception as exc:
        logger.error(f"Chat error — {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/graph")
async def graph_info():
    return {
        "nodes": ["clarifier","supervisor","planner","weather","activities","advisory","rescue","synthesiser"],
        "flow": "START → clarifier → supervisor → [parallel agents] → synthesiser → END",
        "model_supervisor": settings.OPENAI_MODEL,
        "model_agents": settings.OPENAI_MODEL_MINI,
    }

"""
Chat router — POST /api/chat
Passes already_generated list from frontend so supervisor knows
what has already been produced and can protect it from accidental overwrites.
"""
import uuid
import time
import logging
from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, validator

from app.graph.builder import get_graph
from app.config import settings

logger  = logging.getLogger("travelbuddy.chat")
router  = APIRouter()
_rate_store: dict = defaultdict(list)


class Message(BaseModel):
    role: str
    content: str

    @validator("role")
    def role_valid(cls, v):
        if v not in ("user", "assistant"):
            raise ValueError("role must be user or assistant")
        return v

    @validator("content")
    def content_length(cls, v):
        if len(v) > 4000:
            raise ValueError("message too long (max 4000 chars)")
        return v


class ChatRequest(BaseModel):
    messages:          List[Message]
    session_id:        Optional[str] = None
    # Frontend sends which agents have already produced output this session
    already_generated: Optional[List[str]] = []

    @validator("messages")
    def messages_not_empty(cls, v):
        if not v:
            raise ValueError("messages cannot be empty")
        return v


def _check_rate_limit(ip: str):
    now = time.time()
    _rate_store[ip] = [t for t in _rate_store[ip] if now - t < 60]
    if len(_rate_store[ip]) >= settings.RATE_LIMIT_RPM:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({settings.RATE_LIMIT_RPM}/min)"
        )
    _rate_store[ip].append(now)


@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    ip         = request.client.host if request.client else "unknown"
    _check_rate_limit(ip)

    session_id        = body.session_id or str(uuid.uuid4())
    messages          = [{"role": m.role, "content": m.content} for m in body.messages]
    already_generated = body.already_generated or []

    latest = messages[-1]["content"] if messages else ""
    logger.info(
        f"\n{'='*60}\n"
        f"REQUEST | session={session_id[:8]}\n"
        f"USER: {latest[:200]}\n"
        f"Already generated: {already_generated}\n"
        f"{'='*60}"
    )

    try:
        graph     = get_graph()
        thread_id = str(uuid.uuid4())  # fresh thread prevents stale state
        config    = {"configurable": {"thread_id": thread_id}}

        initial_state = {
            "messages":               messages,
            "destination":            None,
            "travel_dates":           None,
            "trip_duration":          None,
            "traveler_origin":        None,
            "travel_purpose":         None,
            "collected_info":         {},
            "next_agents":            [],
            "clarification_needed":   False,
            "clarification_question": None,
            "clarification_field":    None,
            "pending_change_agent":   None,
            "pending_change_reason":  None,
            "already_generated":      already_generated,
            "agent_responses":        [],
            "final_response":         None,
        }

        final_state = await graph.ainvoke(initial_state, config=config)

        # ── Clarification or confirmation request ──────────────────────────────
        if final_state.get("clarification_needed"):
            question = (
                final_state.get("clarification_question")
                or "Could you tell me more about your trip?"
            )
            is_confirm = final_state.get("pending_change_agent") is not None
            logger.info(
                f"{'CONFIRMATION' if is_confirm else 'CLARIFICATION'}: {question}"
            )
            return {
                "session_id":             session_id,
                "clarification_needed":   True,
                "clarification_question": question,
                "is_confirmation":        is_confirm,
                "result":                 None,
            }

        # ── Normal response ────────────────────────────────────────────────────
        final = final_state.get("final_response")
        if not final:
            logger.error("No final_response — check agent logs")
            raise ValueError("No response produced")

        # Inject trip context
        for field in ["destination", "travel_dates", "trip_duration", "traveler_origin"]:
            if not final.get(field) and final_state.get(field):
                final[field] = final_state[field]

        # Tell frontend which agents ran so it can update already_generated
        active_agents = [
            k for k, v in final.get("agent_responses", {}).items()
            if v.get("active")
        ]

        logger.info(
            f"RESPONSE | dest={final.get('destination')} | "
            f"itinerary={len(final.get('itinerary',[]))}d | "
            f"active={active_agents}"
        )

        return {
            "session_id":           session_id,
            "clarification_needed": False,
            "is_confirmation":      False,
            "active_agents":        active_agents,
            "result":               final,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

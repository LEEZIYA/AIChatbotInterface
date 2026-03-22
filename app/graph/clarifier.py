"""
Clarifier Node — RCG Edition
-----------------------------
Uses OPENAI_MODEL_ROUTER (gpt-4o-mini) — routing is a simple classification task.
RCG Goal 3: align task complexity with model strength.
"""

import json
import logging
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings
from app.graph.state import TravelState

logger = logging.getLogger("voyager.clarifier")

CLARIFIER_SYSTEM = """You are a context extractor for VOYAGER, an AI travel assistant.

Read the FULL conversation carefully. Users often give short answers to questions
asked in previous turns — you MUST link these together.

KEY RULE: If the last ASSISTANT message was a question and the latest USER message
is a short reply, treat that reply as the direct answer to that question,
regardless of how brief it seems on its own.

Examples of linking:
  ASSISTANT: "When are you planning to travel to Japan?"
  USER: "7 days in september"
  → travel_dates="September", trip_duration="7 days", destination="Japan" (from earlier)
  → proceed=true

  ASSISTANT: "Where are you planning to travel?"
  USER: "tokyo"
  → destination="Tokyo, Japan", proceed=true

Respond ONLY with valid JSON:
{
  "extracted": {
    "destination":     "city/country or null",
    "travel_dates":    "month/dates or null",
    "traveler_origin": "home country or null",
    "trip_duration":   "number of days or null",
    "travel_purpose":  "holiday/business/other or null"
  },
  "query_type": "planning or safety or weather or activities or emergency or general",
  "missing_critical": true | false,
  "question":         "single question to ask user, or null",
  "missing_field":    "field name or null",
  "proceed":          true | false
}

Rules for query_type:
- planning   : user wants trip plan, itinerary, full trip, flights, hotels
- safety     : user asks about safety, visa, vaccines, advisories, laws
- weather    : user asks about weather, climate, packing, best time to visit
- activities : user asks about things to do, food, restaurants, experiences
- emergency  : user needs emergency contacts, hospitals, urgent help
- general    : greeting, off-topic, vague

Rules for proceed:
- planning   : proceed=false if destination unknown → ask destination
               proceed=false if destination known but BOTH travel_dates AND trip_duration null → ask "When and how many days?"
               proceed=true if destination AND (travel_dates OR trip_duration) known
- safety / weather / activities : proceed=false if destination unknown, else proceed=true
- emergency / general : proceed=true always
- After user answers a clarification question → always proceed=true
- Never ask the same question twice
- After 2 assistant questions already asked → always proceed=true
- ONE question maximum, question=null when proceed=true
"""


async def clarifier_node(state: TravelState) -> Dict[str, Any]:
    messages = state.get("messages", [])
    collected = state.get("collected_info", {})

    clarification_rounds = sum(
        1 for m in messages
        if m.get("role") == "assistant" and "?" in m.get("content", "")
    )

    if clarification_rounds >= 2:
        logger.info("Clarifier: 2+ rounds done — proceeding")
        return {
            "clarification_needed": False, "clarification_question": None,
            "clarification_field": None, "messages": [], "agent_responses": [],
        }

    convo_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in messages[-20:]
    )

    # RCG Goal 3: use router model (gpt-4o-mini) — classification is a simple task
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL_ROUTER,
        api_key=settings.OPENAI_API_KEY,
        temperature=0,
        response_format={"type": "json_object"},
    )

    response = await llm.ainvoke([
        SystemMessage(content=CLARIFIER_SYSTEM),
        HumanMessage(content=f"Full conversation:\n{convo_text}\n\nAlready collected: {json.dumps(collected)}"),
    ])

    raw = response.content if isinstance(response.content, str) else "{}"

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Clarifier JSON parse failed — proceeding")
        result = {"proceed": True, "missing_critical": False, "extracted": {}, "query_type": "general"}

    extracted  = result.get("extracted", {})
    proceed    = result.get("proceed", True)
    question   = result.get("question")
    field      = result.get("missing_field")
    query_type = result.get("query_type", "general")

    logger.info(f"Clarifier: type={query_type} proceed={proceed} dest={extracted.get('destination')}")

    new_collected = {**collected}
    updates: Dict[str, Any] = {
        "messages": [], "agent_responses": [], "collected_info": new_collected,
    }

    for key in ["destination", "travel_dates", "traveler_origin", "trip_duration", "travel_purpose"]:
        val = extracted.get(key) or state.get(key)
        if val:
            updates[key] = val
            new_collected[key] = val

    if not proceed and question:
        logger.info(f"Clarifier: asking for '{field}' → '{question}'")
        updates.update({
            "clarification_needed": True,
            "clarification_question": question,
            "clarification_field": field,
            "messages": [{"role": "assistant", "content": question}],
        })
    else:
        updates.update({
            "clarification_needed": False,
            "clarification_question": None,
            "clarification_field": None,
        })

    return updates

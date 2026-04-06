"""
Supervisor Node — RCG Edition
------------------------------
Uses OPENAI_MODEL_ROUTER (gpt-4o-mini) — routing is a classification task,
not complex reasoning. RCG Goal 3: align task complexity with model strength.
"""

import json
import logging
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings
from app.graph.state import TravelState

logger = logging.getLogger("travelbuddy.supervisor")

SUPERVISOR_SYSTEM = """You are the Supervisor of travelbuddy, an AI travel intelligence system.
You coordinate 5 specialist agents:
  - planner    : flights, hotels, day-by-day itineraries, routes
  - weather    : forecasts, seasonal patterns, packing advice
  - activities : experiences, restaurants, things to do, culture
  - advisory   : safety advisories, visa requirements, vaccines, local laws
  - rescue     : emergency contacts, hospitals, embassies, crisis help

Your ONLY job: analyse the user's query and decide which agents to invoke.

Respond ONLY with valid JSON:
{
  "next_agents": ["list of agent names to invoke"],
  "routing_reason": "brief explanation"
}

Routing rules:
- Always include "advisory" for any destination-specific query
- Include "planner" for trip planning, itinerary, flights, hotels, duration queries
- Include "weather" for weather, climate, packing, best time to visit
- Include "activities" for things to do, food, restaurants, culture, experiences
- Include "rescue" only if emergency, hospital or urgent safety help requested
- Include multiple agents for broad queries like "plan a trip to X"
- For greetings or off-topic: return next_agents: ["orchestrator_only"]
"""


async def supervisor_node(state: TravelState) -> Dict[str, Any]:
    logger.info("Supervisor: routing")

    # RCG Goal 3: use router model for simple routing classification
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL_ROUTER,
        api_key=settings.OPENAI_API_KEY,
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    context_parts = []
    for k, label in [("destination","Destination"),("travel_dates","Dates"),
                     ("trip_duration","Duration"),("traveler_origin","Origin")]:
        if state.get(k):
            context_parts.append(f"{label}: {state[k]}")

    # Also pass last 3 messages so supervisor sees full phrasing like "3 day trip to bali"
    recent_msgs = state["messages"][-3:] if state.get("messages") else []
    recent_text = " | ".join(f"{m['role'].upper()}: {m['content']}" for m in recent_msgs)

    response = await llm.ainvoke([
        SystemMessage(content=SUPERVISOR_SYSTEM),
        HumanMessage(content=(
            f"Extracted context: {' | '.join(context_parts) or 'none yet'}\n"
            f"Recent messages: {recent_text}"
        )),
    ])

    raw = response.content if isinstance(response.content, str) else ""

    try:
        routing = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Supervisor JSON parse failed — defaulting")
        routing = {"next_agents": ["planner", "advisory"]}

    next_agents = routing.get("next_agents", ["advisory"])
    logger.info(f"Supervisor → {next_agents}")

    return {"next_agents": next_agents, "messages": [], "agent_responses": []}
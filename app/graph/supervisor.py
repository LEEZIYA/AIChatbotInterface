"""
Supervisor Node
---------------
The supervisor is the brain of the graph. It:

1. Receives the user message
2. Decides which specialist agents to invoke (routing)
3. Extracts structured context (destination, dates, etc.)
4. Returns next_agents list which LangGraph uses to route the graph

The supervisor does NOT call agents directly — it just decides who should run.
LangGraph's conditional edges handle the actual routing.
"""

import json
import logging
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings
from app.graph.state import TravelState

logger = logging.getLogger("TRAVELBUDDY.supervisor")

SUPERVISOR_SYSTEM = """You are the Supervisor of TRAVELBUDDY, an AI travel intelligence system.
You coordinate 5 specialist agents:
  - planner    : flights, hotels, day-by-day itineraries
  - weather    : forecasts, seasonal patterns, packing
  - activities : experiences, restaurants, things to do
  - advisory   : safety advisories, visa, vaccines, local laws
  - rescue     : emergency contacts, hospitals, embassies

Your ONLY job is to analyse the user's message and decide:
1. Which agents to invoke (can be multiple)
2. What destination is mentioned
3. Any travel dates or origin country mentioned

Respond ONLY with a valid JSON object:
{
  "next_agents": ["planner", "weather", "activities", "advisory", "rescue"],
  "destination": "city, country or null",
  "travel_dates": "date range or null",
  "traveler_origin": "country or null",
  "routing_reason": "brief explanation of why you chose these agents"
}

Rules:
- Always include "advisory" for any destination-specific query
- Include "rescue" only if emergency, hospital, or safety help is requested
- Include "planner" for trip planning, itinerary, flights, hotels
- Include "weather" for weather, climate, packing, seasonal questions
- Include "activities" for things to do, restaurants, experiences, culture
- You may include multiple agents for broad queries like "plan a trip to X"
- For greetings or off-topic messages, return next_agents: ["orchestrator_only"]
"""


async def supervisor_node(state: TravelState) -> Dict[str, Any]:
    """
    LangGraph node: Supervisor
    Analyses the latest user message and decides which agents to route to.
    """
    logger.info("Supervisor: analysing query for routing")

    # Use full gpt-4o for the supervisor — routing decisions matter
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0,                        # deterministic routing
        response_format={"type": "json_object"},
    )

    # Get the latest user message
    latest_message = ""
    for msg in reversed(state["messages"]):
        if msg.get("role") == "user":
            latest_message = msg.get("content", "")
            break

    messages = [
        SystemMessage(content=SUPERVISOR_SYSTEM),
        HumanMessage(content=latest_message),
    ]

    response = await llm.ainvoke(messages)
    raw = response.content if isinstance(response.content, str) else ""

    try:
        routing = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Supervisor JSON parse failed — defaulting to advisory")
        routing = {
            "next_agents": ["advisory"],
            "destination": None,
            "travel_dates": None,
            "traveler_origin": None,
        }

    logger.info(f"Supervisor routing → {routing.get('next_agents')} | dest={routing.get('destination')}")

    return {
        "next_agents":     routing.get("next_agents", ["advisory"]),
        "destination":     routing.get("destination"),
        "travel_dates":    routing.get("travel_dates"),
        "traveler_origin": routing.get("traveler_origin"),
        # Pass through — don't add new messages at this stage
        "messages":        [],
        "agent_responses": [],
    }

"""
Agent Nodes — travelbuddy v4
--------------------------
6 agents (no itinerary node — synthesiser generates itinerary).
Rich terminal logging shows each agent's start, context, and response.
"""

import logging
from typing import Dict, Any

from app.graph.state import TravelState
from app.agents.specialists import (
    TransportAgent,
    AccommodationAgent,
    WeatherAgent,
    ActivitiesAgent,
    AdvisoryAgent,
    RescueAgent,
)

logger = logging.getLogger("travelbuddy.nodes")

AGENT_ICONS = {
    "transport":     "✈️ ",
    "accommodation": "🏨 ",
    "weather":       "🌤️ ",
    "activities":    "🎭 ",
    "advisory":      "🛡️ ",
    "rescue":        "🚨 ",
}

role_map = {
    "transport":     "Retrieve transport using search_flights (international), search_trains_buses (intercity), get_local_transport (within destination), get_airport_transfer (arrival). Use destination and travel_dates from TRIP CONTEXT.",
    "accommodation": "Retrieve accommodation using get_best_areas_to_stay first, then search_hotels. Use destination and trip_duration from TRIP CONTEXT.",
    "weather":       "Retrieve forecast using get_weather_forecast. Use destination and travel_dates from TRIP CONTEXT.",
    "activities":    "Retrieve activities using search_activities and search_restaurants. Use destination from TRIP CONTEXT.",
    "advisory":      "Retrieve using get_travel_advisory (always), get_visa_requirements, get_vaccine_requirements, get_local_laws. Use destination and traveler_origin from TRIP CONTEXT.",
    "rescue":        "Retrieve emergency contacts using get_emergency_contacts ONCE. Use destination from TRIP CONTEXT.",
}


def _build_context_packet(state: TravelState, agent_name: str) -> str:
    """RCG: inject structured trip context before agent runs."""
    lines = ["=== TRIP CONTEXT ==="]
    if state.get("destination"):    lines.append(f"Destination:  {state['destination']}")
    if state.get("travel_dates"):   lines.append(f"Dates:        {state['travel_dates']}")
    if state.get("trip_duration"):  lines.append(f"Duration:     {state['trip_duration']}")
    if state.get("traveler_origin"):lines.append(f"Origin:       {state['traveler_origin']}")
    if state.get("travel_purpose"): lines.append(f"Purpose:      {state['travel_purpose']}")
    lines.append("\n=== YOUR ROLE ===")
    lines.append(role_map.get(agent_name, "Retrieve relevant travel information."))
    lines.append("\n=== GROUNDING ===")
    lines.append("Call tools FIRST. Every claim must come from a tool result.")
    return "\n".join(lines)


def _log_start(name: str, state: TravelState):
    icon = AGENT_ICONS.get(name, "🤖 ")
    logger.info(
        f"\n{'─'*60}\n"
        f"{icon}AGENT START: {name.upper()}\n"
        f"  Destination : {state.get('destination', 'unknown')}\n"
        f"  Duration    : {state.get('trip_duration', 'not set')}\n"
        f"  Dates       : {state.get('travel_dates', 'not set')}\n"
        f"  Role        : {role_map.get(name,'')[:100]}\n"
        f"{'─'*60}"
    )


def _log_done(name: str, result: Dict):
    icon = AGENT_ICONS.get(name, "🤖 ")
    text = (result.get("response") or result.get("text") or "")[:200].replace("\n", " ")
    data_keys = [k for k in result if k not in ("agent","active","response","text","error")]
    summary = []
    for k in data_keys[:5]:
        v = result[k]
        if isinstance(v, list):
            summary.append(f"{k}:[{len(v)}]")
        elif isinstance(v, dict):
            summary.append(f"{k}:{{{','.join(list(v.keys())[:3])}}}")
        elif v is not None:
            summary.append(f"{k}:{str(v)[:40]}")
    logger.info(
        f"\n{'─'*60}\n"
        f"{icon}AGENT DONE: {name.upper()}\n"
        f"  Active   : {result.get('active', False)}\n"
        f"  Response : {text or '(none)'}\n"
        f"  Data     : {' | '.join(summary) or '(none)'}\n"
        f"{'─'*60}\n"
    )


async def _run(cls, name: str, state: TravelState) -> Dict[str, Any]:
    """Generic runner with start/done logging."""
    context = _build_context_packet(state, name)
    _log_start(name, state)
    try:
        result = await cls().run(
            conversation_history=state["messages"],
            destination=state.get("destination"),
            extra_context=context,
        )
        _log_done(name, result)
        return {"agent_responses": [result], "messages": []}
    except Exception as e:
        logger.error(f"❌ {name} agent failed: {e}")
        return {
            "agent_responses": [{"agent": name, "active": False, "response": "", "error": str(e)}],
            "messages": [],
        }


async def transport_node(state: TravelState) -> Dict[str, Any]:
    return await _run(TransportAgent, "transport", state)

async def accommodation_node(state: TravelState) -> Dict[str, Any]:
    return await _run(AccommodationAgent, "accommodation", state)

async def weather_node(state: TravelState) -> Dict[str, Any]:
    return await _run(WeatherAgent, "weather", state)

async def activities_node(state: TravelState) -> Dict[str, Any]:
    return await _run(ActivitiesAgent, "activities", state)

async def advisory_node(state: TravelState) -> Dict[str, Any]:
    return await _run(AdvisoryAgent, "advisory", state)

async def rescue_node(state: TravelState) -> Dict[str, Any]:
    return await _run(RescueAgent, "rescue", state)

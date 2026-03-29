"""
Agent Nodes — RCG Edition
-------------------------
Each node builds a structured context packet (RCG Goal: Comprehensive Context)
and passes the full conversation history to the agent.

_build_context_packet() gives every agent a rich grounded brief:
- What destination, dates, duration, origin and purpose are known
- What their specific role is
- The instruction to retrieve before reasoning
"""

import logging
from typing import Dict, Any, List

from app.graph.state import TravelState
from app.agents.specialists import (
    PlannerAgent, WeatherAgent, ActivitiesAgent, AdvisoryAgent, RescueAgent,
)

logger = logging.getLogger("voyager.nodes")


def _build_context_packet(state: TravelState, agent_name: str) -> str:
    """
    RCG: Build a structured context packet for each agent.

    Instead of just passing the raw user query, each agent receives
    a structured brief of everything known about the trip so far.
    This grounds the agent in real extracted context before it calls tools.

    Structure:
      === TRIP CONTEXT ===      <- extracted travel facts
      === YOUR ROLE ===         <- agent-specific instructions
      === GROUNDING REMINDER == <- RCG core instruction
    """
    lines = ["=== TRIP CONTEXT (extracted from conversation) ==="]

    if state.get("destination"):
        lines.append(f"Destination:      {state['destination']}")
    if state.get("travel_dates"):
        lines.append(f"Travel dates:     {state['travel_dates']}")
    if state.get("trip_duration"):
        lines.append(f"Duration:         {state['trip_duration']}")
    if state.get("traveler_origin"):
        lines.append(f"Traveller origin: {state['traveler_origin']}")
    if state.get("travel_purpose"):
        lines.append(f"Purpose:          {state['travel_purpose']}")

    if not any([state.get(k) for k in ["destination","travel_dates","trip_duration"]]):
        lines.append("(No structured context extracted yet — infer from conversation history)")

    role_map = {
        "planner":    "Retrieve a detailed day-by-day itinerary using build_itinerary. Use destination and duration from TRIP CONTEXT above.",
        "weather":    "Retrieve current forecast using get_weather_forecast. Use destination and travel_dates from TRIP CONTEXT above.",
        "activities": "Retrieve current activities using search_activities. Use destination from TRIP CONTEXT above.",
        "advisory":   "Retrieve safety advisory, visa, vaccines and local laws. Use destination and traveler_origin from TRIP CONTEXT above.",
        "rescue":     "Retrieve emergency contacts using get_emergency_contacts. Use destination from TRIP CONTEXT above.",
    }

    lines.append(f"\n=== YOUR ROLE ===")
    lines.append(role_map.get(agent_name, f"You are the {agent_name} specialist."))

    lines.append(f"\n=== GROUNDING REMINDER ===")
    lines.append("Call your tools FIRST. Base your response on what the tools return.")
    lines.append("Do not answer from training memory — retrieved data is always more current.")

    return "\n".join(lines)


async def planner_node(state: TravelState) -> Dict[str, Any]:
    logger.info("Node: planner")
    result = await PlannerAgent().run(
        conversation_history=state["messages"],
        destination=state.get("destination"),
        extra_context=_build_context_packet(state, "planner"),
    )
    return {"agent_responses": [result], "messages": []}


async def weather_node(state: TravelState) -> Dict[str, Any]:
    logger.info("Node: weather")
    result = await WeatherAgent().run(
        conversation_history=state["messages"],
        destination=state.get("destination"),
        extra_context=_build_context_packet(state, "weather"),
    )
    return {"agent_responses": [result], "messages": []}


async def activities_node(state: TravelState) -> Dict[str, Any]:
    logger.info("Node: activities")
    result = await ActivitiesAgent().run(
        conversation_history=state["messages"],
        destination=state.get("destination"),
        extra_context=_build_context_packet(state, "activities"),
    )
    return {"agent_responses": [result], "messages": []}


async def advisory_node(state: TravelState) -> Dict[str, Any]:
    logger.info("Node: advisory")
    result = await AdvisoryAgent().run(
        conversation_history=state["messages"],
        destination=state.get("destination"),
        extra_context=_build_context_packet(state, "advisory"),
    )
    return {"agent_responses": [result], "messages": []}


async def rescue_node(state: TravelState) -> Dict[str, Any]:
    logger.info("Node: rescue")
    result = await RescueAgent().run(
        conversation_history=state["messages"],
        destination=state.get("destination"),
        extra_context=_build_context_packet(state, "rescue"),
    )
    return {"agent_responses": [result], "messages": []}

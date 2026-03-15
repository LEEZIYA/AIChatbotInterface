"""
Agent Nodes
-----------
These are the LangGraph node functions — one per specialist agent.
Each node:
  1. Instantiates its agent
  2. Runs the agentic tool-calling loop
  3. Writes its AgentResponse back into the shared state

Because operator.add is used for agent_responses in the state,
all parallel agent responses get merged automatically.
"""

import logging
from typing import Dict, Any

from app.graph.state import TravelState
from app.agents.specialists import (
    PlannerAgent,
    WeatherAgent,
    ActivitiesAgent,
    AdvisoryAgent,
    RescueAgent,
)

logger = logging.getLogger("TRAVELBUDDY.nodes")


def _get_latest_user_message(state: TravelState) -> str:
    """Extract the most recent user message from state."""
    for msg in reversed(state["messages"]):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return ""


async def planner_node(state: TravelState) -> Dict[str, Any]:
    """LangGraph node: Planner Agent"""
    query = _get_latest_user_message(state)
    logger.info("Node: planner_node invoked")
    agent = PlannerAgent()
    result = await agent.run(
        user_query=query,
        destination=state.get("destination"),
        extra_context=f"Travel dates: {state.get('travel_dates')}" if state.get("travel_dates") else None,
    )
    return {
        "agent_responses": [result],
        "messages": [],
    }


async def weather_node(state: TravelState) -> Dict[str, Any]:
    """LangGraph node: Weather Agent"""
    query = _get_latest_user_message(state)
    logger.info("Node: weather_node invoked")
    agent = WeatherAgent()
    result = await agent.run(
        user_query=query,
        destination=state.get("destination"),
        extra_context=f"Travel dates: {state.get('travel_dates')}" if state.get("travel_dates") else None,
    )
    return {
        "agent_responses": [result],
        "messages": [],
    }


async def activities_node(state: TravelState) -> Dict[str, Any]:
    """LangGraph node: Activities Agent"""
    query = _get_latest_user_message(state)
    logger.info("Node: activities_node invoked")
    agent = ActivitiesAgent()
    result = await agent.run(
        user_query=query,
        destination=state.get("destination"),
    )
    return {
        "agent_responses": [result],
        "messages": [],
    }


async def advisory_node(state: TravelState) -> Dict[str, Any]:
    """LangGraph node: Advisory Agent"""
    query = _get_latest_user_message(state)
    logger.info("Node: advisory_node invoked")
    agent = AdvisoryAgent()
    result = await agent.run(
        user_query=query,
        destination=state.get("destination"),
        extra_context=f"Traveler origin: {state.get('traveler_origin')}" if state.get("traveler_origin") else None,
    )
    return {
        "agent_responses": [result],
        "messages": [],
    }


async def rescue_node(state: TravelState) -> Dict[str, Any]:
    """LangGraph node: Rescue Agent"""
    query = _get_latest_user_message(state)
    logger.info("Node: rescue_node invoked")
    agent = RescueAgent()
    result = await agent.run(
        user_query=query,
        destination=state.get("destination"),
    )
    return {
        "agent_responses": [result],
        "messages": [],
    }

"""
Graph Builder —  v4
Fan-out parallel execution.
add_conditional_edges WITHOUT path_map dict for supervisor → agents.
"""

import logging
from typing import List

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import TravelState
from app.graph.clarifier import clarifier_node
from app.graph.supervisor import supervisor_node
from app.graph.synthesiser import synthesiser_node
from app.graph.nodes import (
    transport_node, accommodation_node, weather_node,
    activities_node, advisory_node, rescue_node,
)

logger = logging.getLogger("travelbuddy.builder")

AGENT_NODE_MAP = {
    "transport":     transport_node,
    "accommodation": accommodation_node,
    "weather":       weather_node,
    "activities":    activities_node,
    "advisory":      advisory_node,
    "rescue":        rescue_node,
}


def route_after_clarifier(state: TravelState) -> str:
    if state.get("clarification_needed"):
        return "__end__"
    return "supervisor"


def route_to_agents(state: TravelState) -> List[str]:
    """
    Returns LIST of node names → LangGraph runs all in parallel.
    Must NOT have a path_map dict — that restricts to single routing.
    """
    next_agents = state.get("next_agents", [])
    if not next_agents:
        return ["synthesiser"]
    valid = [a for a in next_agents if a in AGENT_NODE_MAP]
    if not valid:
        logger.warning(f"No valid agents in {next_agents} — direct to synthesiser")
        return ["synthesiser"]
    logger.info(f"Fan-out → {valid} (parallel)")
    return valid


def build_graph() -> StateGraph:
    builder = StateGraph(TravelState)

    builder.add_node("clarifier",     clarifier_node)
    builder.add_node("supervisor",    supervisor_node)
    builder.add_node("transport",     transport_node)
    builder.add_node("accommodation", accommodation_node)
    builder.add_node("weather",       weather_node)
    builder.add_node("activities",    activities_node)
    builder.add_node("advisory",      advisory_node)
    builder.add_node("rescue",        rescue_node)
    builder.add_node("synthesiser",   synthesiser_node)

    builder.add_edge(START, "clarifier")

    # clarifier → supervisor (dict OK here, single routing)
    builder.add_conditional_edges(
        "clarifier",
        route_after_clarifier,
        {"supervisor": "supervisor", "__end__": END},
    )

    # supervisor → agents (NO dict — list return = parallel fan-out)
    builder.add_conditional_edges(
        "supervisor",
        route_to_agents,
    )

    for name in AGENT_NODE_MAP:
        builder.add_edge(name, "synthesiser")

    builder.add_edge("synthesiser", END)

    graph = builder.compile(checkpointer=MemorySaver())
    logger.info("✅ Graph compiled — parallel fan-out ready")
    return graph


_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph

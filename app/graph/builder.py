"""
Graph Builder
-------------
This is where LangGraph wires everything together.

The graph looks like this:

  [START]
     │
     ▼
 [supervisor]  ← decides which agents to call
     │
     ├─── "planner"    ──► [planner_node]    ──┐
     ├─── "weather"    ──► [weather_node]    ──┤
     ├─── "activities" ──► [activities_node] ──┤── all run in PARALLEL
     ├─── "advisory"   ──► [advisory_node]   ──┤
     └─── "rescue"     ──► [rescue_node]     ──┘
                                                │
                                                ▼
                                         [synthesiser]  ← merges all outputs
                                                │
                                              [END]
"""

import logging
from typing import List

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import TravelState
from app.graph.supervisor import supervisor_node
from app.graph.synthesiser import synthesiser_node
from app.graph.nodes import (
    planner_node,
    weather_node,
    activities_node,
    advisory_node,
    rescue_node,
)
from app.config import settings

logger = logging.getLogger("TRAVELBUDDY.graph")

AGENT_NODE_MAP = {
    "planner":    planner_node,
    "weather":    weather_node,
    "activities": activities_node,
    "advisory":   advisory_node,
    "rescue":     rescue_node,
}


def route_to_agents(state: TravelState) -> List[str]:
    """
    Conditional edge function — called after supervisor runs.
    Returns list of node names to execute next (in parallel).
    """
    next_agents = state.get("next_agents", [])
    valid = [a for a in next_agents if a in AGENT_NODE_MAP]

    if not valid or "orchestrator_only" in next_agents:
        logger.info("Routing: no agents → synthesiser directly")
        return ["synthesiser"]

    logger.info(f"Routing: dispatching to agents → {valid}")
    return valid


def build_graph():
    """
    Construct and compile the LangGraph StateGraph.
    Uses MemorySaver — session memory, fast, no C++ dependencies needed.
    Conversations persist for the duration of the server session.
    """
    builder = StateGraph(TravelState)

    # Register all nodes
    builder.add_node("supervisor",   supervisor_node)
    builder.add_node("planner",      planner_node)
    builder.add_node("weather",      weather_node)
    builder.add_node("activities",   activities_node)
    builder.add_node("advisory",     advisory_node)
    builder.add_node("rescue",       rescue_node)
    builder.add_node("synthesiser",  synthesiser_node)

    # Entry point
    builder.add_edge(START, "supervisor")

    # Conditional routing from supervisor → parallel agents
    builder.add_conditional_edges(
        "supervisor",
        route_to_agents,
        {
            "planner":     "planner",
            "weather":     "weather",
            "activities":  "activities",
            "advisory":    "advisory",
            "rescue":      "rescue",
            "synthesiser": "synthesiser",
        },
    )

    # All agents flow into synthesiser
    for agent_name in AGENT_NODE_MAP:
        builder.add_edge(agent_name, "synthesiser")

    # Synthesiser exits the graph
    builder.add_edge("synthesiser", END)

    # MemorySaver — no SQLite, no C++ needed
    checkpointer = MemorySaver()
    logger.info("Graph: using MemorySaver (session memory)")

    graph = builder.compile(checkpointer=checkpointer)
    logger.info("Graph compiled successfully")
    return graph


# Singleton — built once at startup
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph

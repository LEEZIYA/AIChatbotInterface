"""
Graph Builder — wires all nodes into the LangGraph StateGraph.

Flow:
  START → clarifier → (needs info?) → END (shows question)
                    → supervisor → [parallel agents] → synthesiser → END
"""

import logging
from typing import List

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import TravelState
from app.graph.clarifier import clarifier_node
from app.graph.supervisor import supervisor_node
from app.graph.synthesiser import synthesiser_node
from app.graph.nodes import planner_node, weather_node, activities_node, advisory_node, rescue_node

logger = logging.getLogger("voyager.graph")

AGENT_NODE_MAP = {
    "planner":    planner_node,
    "weather":    weather_node,
    "activities": activities_node,
    "advisory":   advisory_node,
    "rescue":     rescue_node,
}


def route_after_clarifier(state: TravelState) -> str:
    if state.get("clarification_needed"):
        logger.info("Clarifier: question sent → ending run")
        return "end"
    return "supervisor"


def route_to_agents(state: TravelState) -> List[str]:
    valid = [a for a in state.get("next_agents", []) if a in AGENT_NODE_MAP]
    if not valid or "orchestrator_only" in state.get("next_agents", []):
        return ["synthesiser"]
    logger.info(f"Routing to: {valid}")
    return valid


def build_graph():
    builder = StateGraph(TravelState)

    builder.add_node("clarifier",   clarifier_node)
    builder.add_node("supervisor",  supervisor_node)
    builder.add_node("planner",     planner_node)
    builder.add_node("weather",     weather_node)
    builder.add_node("activities",  activities_node)
    builder.add_node("advisory",    advisory_node)
    builder.add_node("rescue",      rescue_node)
    builder.add_node("synthesiser", synthesiser_node)

    builder.add_edge(START, "clarifier")

    builder.add_conditional_edges(
        "clarifier", route_after_clarifier,
        {"supervisor": "supervisor", "end": END},
    )

    builder.add_conditional_edges(
        "supervisor", route_to_agents,
        {"planner":"planner","weather":"weather","activities":"activities",
         "advisory":"advisory","rescue":"rescue","synthesiser":"synthesiser"},
    )

    for name in AGENT_NODE_MAP:
        builder.add_edge(name, "synthesiser")

    builder.add_edge("synthesiser", END)

    graph = builder.compile(checkpointer=MemorySaver())
    logger.info("Graph compiled ✅")
    return graph


_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph

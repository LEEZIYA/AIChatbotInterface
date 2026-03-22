"""
Graph State — shared data baton passed between every node.
operator.add on messages and agent_responses enables safe parallel merging.
"""
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict, Annotated
import operator


class AgentResponse(TypedDict):
    agent: str
    response: str
    data: Optional[Dict[str, Any]]
    error: Optional[str]


class TravelState(TypedDict):
    # Full conversation history — passed to every agent
    messages: Annotated[List[Dict[str, str]], operator.add]

    # Routing
    next_agents: List[str]

    # Context extracted from conversation
    destination:      Optional[str]
    travel_dates:     Optional[str]
    traveler_origin:  Optional[str]
    trip_duration:    Optional[str]
    travel_purpose:   Optional[str]

    # Clarifier
    clarification_needed:   bool
    clarification_question: Optional[str]
    clarification_field:    Optional[str]
    collected_info:         Dict[str, Any]

    # Agent outputs — accumulated across parallel branches
    agent_responses: Annotated[List[AgentResponse], operator.add]

    # Final merged response
    final_response: Optional[Dict[str, Any]]

    # Session memory key
    session_id: str

"""
LangGraph state for .
Uses TypedDict (not MessagesState) so messages stay as plain dicts
and state.get("messages") works correctly everywhere.
"""
import operator
from typing import Dict, Any, List, Optional, Annotated
from typing_extensions import TypedDict


class TravelState(TypedDict, total=False):
    # Conversation history — plain dicts {"role": ..., "content": ...}
    # operator.add merges lists when parallel nodes write to it
    messages: Annotated[List[Dict[str, Any]], operator.add]

    # Trip context — extracted by clarifier
    destination:      Optional[str]
    travel_dates:     Optional[str]
    trip_duration:    Optional[str]
    traveler_origin:  Optional[str]
    travel_purpose:   Optional[str]
    collected_info:   Dict[str, Any]

    # Supervisor routing
    next_agents: List[str]

    # Clarification
    clarification_needed:   bool
    clarification_question: Optional[str]
    clarification_field:    Optional[str]

    # Confirmation gate
    pending_change_agent:  Optional[str]
    pending_change_reason: Optional[str]

    # Already-generated agents — sent from frontend each request
    already_generated: List[str]

    # Agent outputs — merged from parallel agents
    agent_responses: Annotated[List[Dict[str, Any]], operator.add]

    # Final synthesised response
    final_response: Optional[Dict[str, Any]]

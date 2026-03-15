"""
Graph State
-----------
This is the shared data structure that flows through every node in the graph.
Think of it as a baton passed between agents — each agent reads from it and
writes its results back into it.

LangGraph uses TypedDict so it knows which fields exist and how to merge them
across parallel branches.
"""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict, Annotated
import operator


class AgentResponse(TypedDict):
    """Output structure for each specialist agent."""
    agent: str                        # which agent produced this
    response: str                     # natural language response
    data: Optional[Dict[str, Any]]    # structured data (itinerary, forecast, etc.)
    error: Optional[str]              # set if the agent failed


class TravelState(TypedDict):
    """
    The single shared state object passed through the entire graph.

    Annotated[List, operator.add] means: when two branches both write to
    'messages' or 'agent_responses', LangGraph merges them by appending
    (not overwriting). This is what enables parallel agent execution.
    """

    # ── Conversation ──────────────────────────────────────────────────────────
    # Full message history: [{"role": "user"|"assistant", "content": "..."}]
    messages: Annotated[List[Dict[str, str]], operator.add]

    # ── Routing ───────────────────────────────────────────────────────────────
    # Supervisor fills this to tell the graph which agents to invoke
    next_agents: List[str]

    # ── Context extracted by supervisor ───────────────────────────────────────
    destination: Optional[str]
    travel_dates: Optional[str]
    traveler_origin: Optional[str]

    # ── Agent outputs (accumulated via operator.add across parallel branches) ──
    agent_responses: Annotated[List[AgentResponse], operator.add]

    # ── Final synthesised response sent back to the user ──────────────────────
    final_response: Optional[Dict[str, Any]]

    # ── Session ID for memory checkpointing ───────────────────────────────────
    session_id: str

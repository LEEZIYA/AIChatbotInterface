"""
Synthesiser Node
----------------
After all specialist agents have run in parallel, the synthesiser:
1. Collects all AgentResponse objects from state
2. Extracts structured tool data from each agent's output
3. Calls GPT-4o to merge them into one coherent response
4. Builds the final structured response the frontend renders
"""

import json
import logging
from typing import Dict, Any, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings
from app.graph.state import TravelState, AgentResponse

logger = logging.getLogger("TRAVELBUDDY.synthesiser")

SYNTHESISER_SYSTEM = """You are the Response Synthesiser for TRAVELBUDDY, an AI travel intelligence system.

You receive outputs from multiple specialist agents and must synthesise them into one
coherent structured JSON response. The agent outputs include both text responses and
raw tool call results (nested under tool names).

You MUST respond with ONLY a valid JSON object in exactly this structure:

{
  "orchestrator_message": "A warm 2-3 sentence summary tying all findings together",
  "destination": "destination name or null",
  "agents_involved": ["list of agent names that were active"],
  "agent_responses": {
    "planner": {
      "active": true,
      "response": "planner's text response",
      "itinerary": [{"day": 1, "items": [{"time": "09:00", "activity": "..."}]}]
    },
    "weather": {
      "active": true,
      "response": "weather agent's text response",
      "forecast": [{"day": "Mon", "icon": "🌤", "temp": "24°C", "desc": "Partly cloudy"}]
    },
    "activities": {
      "active": true,
      "response": "activities agent's text response",
      "highlights": ["activity 1", "activity 2"]
    },
    "advisory": {
      "active": true,
      "response": "advisory agent's text response",
      "risk_level": "LOW",
      "hazards": [{"type": "Natural Disaster", "level": "LOW", "detail": "..."}],
      "visa": {"requirement": "Visa on Arrival", "details": "...", "source": "...", "updated": "..."},
      "vaccines": [{"name": "Hepatitis A", "requirement": "Recommended", "notes": "..."}],
      "local_rules": ["🚭 No smoking in public", "👗 Dress modestly at temples"],
      "sources": [{"name": "US State Department", "type": "Government", "updated": "2025-01-01"}]
    },
    "rescue": {
      "active": true,
      "response": "rescue agent's text response",
      "emergency_numbers": [{"service": "Police", "number": "191"}]
    }
  }
}

CRITICAL RULES:
- For inactive agents set active: false and use null for all array/object fields
- Extract forecast array from weather tool output — it must be a flat array of day objects
- Extract itinerary array from planner tool output — it must be array of {day, items} objects
- Extract highlights as a flat array of strings from activities tool output
- Extract emergency_numbers as flat array from rescue tool output
- NEVER nest data inside extra wrapper objects
- forecast, itinerary, highlights, emergency_numbers must be arrays (not objects) or null
"""


def _extract_tool_data(agent_response: AgentResponse) -> Dict[str, Any]:
    """
    Pull structured data out of the agent's tool_outputs dict.
    Returns a flat dict of the most useful data for each agent type.
    """
    agent_name = agent_response.get("agent", "")
    data = agent_response.get("data") or {}
    text = agent_response.get("response", "")

    extracted = {"text": text, "raw": data}

    if agent_name == "weather":
        # Tool: get_weather_forecast returns {"forecast": [...]}
        for key, val in data.items():
            if isinstance(val, dict) and "forecast" in val:
                extracted["forecast"] = val["forecast"]
                break

    elif agent_name == "planner":
        # Tool: build_itinerary returns {"itinerary": [...]}
        for key, val in data.items():
            if isinstance(val, dict) and "itinerary" in val:
                extracted["itinerary"] = val["itinerary"]
                break

    elif agent_name == "activities":
        # Tool: search_activities returns {"highlights": [...]}
        for key, val in data.items():
            if isinstance(val, dict) and "highlights" in val:
                extracted["highlights"] = [h["name"] if isinstance(h, dict) else h for h in val["highlights"]]
                break

    elif agent_name == "advisory":
        extracted["advisory_data"] = {}
        for key, val in data.items():
            if isinstance(val, dict):
                extracted["advisory_data"].update(val)

    elif agent_name == "rescue":
        for key, val in data.items():
            if isinstance(val, dict) and "emergency_numbers" in val:
                extracted["emergency_numbers"] = val["emergency_numbers"]
                break

    return extracted


async def synthesiser_node(state: TravelState) -> Dict[str, Any]:
    """
    LangGraph node: Synthesiser
    Merges all parallel agent responses into the final structured output.
    """
    agent_responses: List[AgentResponse] = state.get("agent_responses", [])
    destination = state.get("destination")

    logger.info(f"Synthesiser: merging {len(agent_responses)} agent response(s)")

    if not agent_responses:
        final = _empty_response()
        return {"final_response": final, "messages": [], "agent_responses": []}

    # Extract and summarise each agent's output for the LLM
    summaries = []
    for ar in agent_responses:
        extracted = _extract_tool_data(ar)
        summary = f"=== {ar['agent'].upper()} AGENT ===\n"
        summary += f"Text response: {extracted['text']}\n"
        if extracted.get("forecast"):
            summary += f"Forecast data: {json.dumps(extracted['forecast'])}\n"
        if extracted.get("itinerary"):
            summary += f"Itinerary data: {json.dumps(extracted['itinerary'])}\n"
        if extracted.get("highlights"):
            summary += f"Highlights data: {json.dumps(extracted['highlights'])}\n"
        if extracted.get("advisory_data"):
            summary += f"Advisory data: {json.dumps(extracted['advisory_data'])}\n"
        if extracted.get("emergency_numbers"):
            summary += f"Emergency numbers: {json.dumps(extracted['emergency_numbers'])}\n"
        if extracted.get("raw"):
            summary += f"Full tool output: {json.dumps(extracted['raw'])}\n"
        summaries.append(summary)

    combined = "\n\n".join(summaries)

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    messages = [
        SystemMessage(content=SYNTHESISER_SYSTEM),
        HumanMessage(content=f"Destination: {destination}\n\nAgent outputs:\n\n{combined}"),
    ]

    response = await llm.ainvoke(messages)
    raw = response.content if isinstance(response.content, str) else ""

    try:
        final = json.loads(raw)
        # Sanitise — ensure arrays are actually arrays
        final = _sanitise_response(final, agent_responses, destination)
    except json.JSONDecodeError as exc:
        logger.warning(f"Synthesiser JSON parse failed: {exc}")
        final = _build_fallback_response(agent_responses, destination)

    assistant_message = final.get("orchestrator_message", "Here is your travel information.")

    return {
        "final_response": final,
        "messages": [{"role": "assistant", "content": assistant_message}],
        "agent_responses": [],
    }


def _sanitise_response(final: Dict, agent_responses: List[AgentResponse], destination: Optional[str]) -> Dict:
    """
    Defensive cleanup — ensure all array fields are actually arrays.
    If the LLM returned wrong types, fix them or set to null.
    """
    ar = final.get("agent_responses", {})

    def ensure_list(val):
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            # Unwrap if LLM wrapped it: {"forecast": [...]} → [...]
            for v in val.values():
                if isinstance(v, list):
                    return v
        return None

    for agent_name in ["planner", "weather", "activities", "advisory", "rescue"]:
        if agent_name not in ar:
            ar[agent_name] = {"active": False, "response": ""}

    # Fix weather forecast
    if ar.get("weather", {}).get("active"):
        ar["weather"]["forecast"] = ensure_list(ar["weather"].get("forecast"))

    # Fix planner itinerary
    if ar.get("planner", {}).get("active"):
        ar["planner"]["itinerary"] = ensure_list(ar["planner"].get("itinerary"))

    # Fix activities highlights — must be list of strings
    if ar.get("activities", {}).get("active"):
        highlights = ensure_list(ar["activities"].get("highlights"))
        if highlights:
            ar["activities"]["highlights"] = [
                h["name"] if isinstance(h, dict) else str(h) for h in highlights
            ]
        else:
            ar["activities"]["highlights"] = None

    # Fix advisory arrays
    if ar.get("advisory", {}).get("active"):
        ar["advisory"]["hazards"]     = ensure_list(ar["advisory"].get("hazards"))
        ar["advisory"]["vaccines"]    = ensure_list(ar["advisory"].get("vaccines"))
        ar["advisory"]["local_rules"] = ensure_list(ar["advisory"].get("local_rules"))
        ar["advisory"]["sources"]     = ensure_list(ar["advisory"].get("sources")) or []
        if not ar["advisory"].get("risk_level"):
            ar["advisory"]["risk_level"] = "LOW"

    # Fix rescue emergency_numbers
    if ar.get("rescue", {}).get("active"):
        ar["rescue"]["emergency_numbers"] = ensure_list(ar["rescue"].get("emergency_numbers"))

    final["agent_responses"] = ar
    if not final.get("destination"):
        final["destination"] = destination

    return final


def _empty_response() -> Dict:
    return {
        "orchestrator_message": "Hello! I'm TRAVELBUDDY, your AI travel assistant. Ask me anything about your trip — planning, weather, activities, safety, or emergency information.",
        "destination": None,
        "agents_involved": ["orchestrator"],
        "agent_responses": {
            "planner":    {"active": False, "response": "", "itinerary": None},
            "weather":    {"active": False, "response": "", "forecast": None},
            "activities": {"active": False, "response": "", "highlights": None},
            "advisory":   {"active": False, "response": "", "risk_level": "LOW", "hazards": None, "visa": None, "vaccines": None, "local_rules": None, "sources": []},
            "rescue":     {"active": False, "response": "", "emergency_numbers": None},
        }
    }


def _build_fallback_response(agent_responses: List[AgentResponse], destination: Optional[str]) -> Dict:
    """Build a safe minimal response if the LLM call fails."""
    active_agents = [ar["agent"] for ar in agent_responses]
    combined_text = " | ".join(ar["response"] for ar in agent_responses if ar.get("response"))
    base = _empty_response()
    base["orchestrator_message"] = combined_text or "Travel information gathered."
    base["destination"] = destination
    base["agents_involved"] = active_agents
    for ar in agent_responses:
        name = ar["agent"]
        if name in base["agent_responses"]:
            base["agent_responses"][name]["active"] = True
            base["agent_responses"][name]["response"] = ar.get("response", "")
    return base

"""
Synthesiser Node — RCG Edition
-------------------------------
RCG improvements:
1. Agent outputs wrapped in structured XML <agent_output> tags
   → Model can navigate large inputs clearly without losing context
2. SYNTHESISER_SYSTEM updated with grounding rule
   → Synthesiser can only include claims present in retrieved data
3. _agent_role() helper for clear section labelling
4. Uses full gpt-4o — merging 5 parallel agent outputs is complex reasoning
"""

import json
import logging
from typing import Dict, Any, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings
from app.graph.state import TravelState, AgentResponse

logger = logging.getLogger("travelbuddy.synthesiser")


def _agent_role(name: str) -> str:
    """Human-readable role description for each agent."""
    roles = {
        "planner":    "Trip logistics, itineraries, flights and hotels",
        "weather":    "Weather forecasts, seasonal patterns and packing advice",
        "activities": "Attractions, restaurants and local experiences",
        "advisory":   "Safety advisories, visa requirements, vaccines and local laws",
        "rescue":     "Emergency contacts, hospitals and embassy information",
    }
    return roles.get(name, "General travel assistance")


SYNTHESISER_SYSTEM = """You are the Response Synthesiser for travelbuddy, an AI travel intelligence system.

You receive structured outputs from specialist agents wrapped in <agent_output> XML tags.
Each tag contains:
  <agent_name>       : which specialist produced this output
  <agent_role>       : what they are responsible for
  <retrieved_data>   : raw data fetched from live web search tools
  <agent_reasoning>  : the agent's plain text analysis of the retrieved data
  <structured_outputs>: parsed arrays ready for UI rendering (forecast, itinerary, etc.)

YOUR JOB:
1. Read ALL <agent_output> sections carefully
2. Synthesise into one coherent JSON response
3. Preserve ALL structured data arrays exactly as provided — do not modify them
4. Write orchestrator_message in 2-3 warm plain sentences

RCG GROUNDING RULE:
Your orchestrator_message must ONLY contain claims that appear in the
<retrieved_data> or <agent_reasoning> sections. Do not add information
from your own training memory. If data is missing, omit that claim.

FORMATTING:
- orchestrator_message: plain text, no markdown, no asterisks
- All agent response fields: plain text only
- Preserve exact array structures for itinerary, forecast, highlights, emergency_numbers

Return ONLY valid JSON in exactly this structure:
{
  "orchestrator_message": "2-3 warm plain sentences grounded in retrieved data",
  "destination": "destination name or null",
  "agents_involved": ["list of active agent names"],
  "agent_responses": {
    "planner":    { "active": true, "response": "plain text", "itinerary": [...] | null },
    "weather":    { "active": true, "response": "plain text", "forecast": [...] | null },
    "activities": { "active": true, "response": "plain text", "highlights": [...] | null },
    "advisory":   {
      "active": true, "response": "plain text",
      "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
      "hazards":     [...] | null,
      "visa":        {...} | null,
      "vaccines":    [...] | null,
      "local_rules": [...] | null,
      "sources":     [...]
    },
    "rescue": { "active": true, "response": "plain text", "emergency_numbers": [...] | null }
  }
}

Set active: false and null data fields for agents that did not run.
"""


def _extract(ar: AgentResponse) -> Dict[str, Any]:
    """Pull structured arrays out of nested tool output dicts."""
    name = ar.get("agent", "")
    data = ar.get("data") or {}
    out  = {"text": ar.get("response", ""), "raw": data}

    for val in data.values():
        if not isinstance(val, dict):
            continue
        if name == "weather"    and "forecast"          in val: out["forecast"]          = val["forecast"]
        if name == "planner"    and "itinerary"         in val: out["itinerary"]         = val["itinerary"]
        if name == "activities" and "highlights"        in val:
            out["highlights"] = [h["name"] if isinstance(h, dict) else h for h in val["highlights"]]
        if name == "advisory":
            out.setdefault("advisory_data", {}).update(val)
        if name == "rescue"     and "emergency_numbers" in val:
            out["emergency_numbers"] = val["emergency_numbers"]

    return out


def _build_xml_section(ar: AgentResponse) -> str:
    """
    RCG: Wrap each agent output in structured XML tags.
    This makes large multi-agent inputs navigable for the synthesiser LLM.
    """
    ex = _extract(ar)

    structured = {}
    for k in ["forecast","itinerary","highlights","emergency_numbers","advisory_data"]:
        if ex.get(k):
            structured[k] = ex[k]

    return f"""<agent_output>
  <agent_name>{ar['agent']}</agent_name>
  <agent_role>{_agent_role(ar['agent'])}</agent_role>
  <retrieved_data>
{json.dumps(ex.get('raw', {}), indent=2)}
  </retrieved_data>
  <agent_reasoning>{ex['text']}</agent_reasoning>
  <structured_outputs>
{json.dumps(structured, indent=2)}
  </structured_outputs>
</agent_output>"""


async def synthesiser_node(state: TravelState) -> Dict[str, Any]:
    """
    LangGraph node: Synthesiser
    Merges all parallel agent outputs into the final structured response.
    Uses XML-tagged inputs for clear structure (RCG Goal 2).
    Uses gpt-4o for complex multi-source reasoning (RCG Goal 3).
    """
    agent_responses: List[AgentResponse] = state.get("agent_responses", [])
    destination = state.get("destination")
    logger.info(f"Synthesiser: merging {len(agent_responses)} agent outputs")

    if not agent_responses:
        final = _empty()
        return {"final_response": final, "messages": [], "agent_responses": []}

    # Build structured XML input — RCG Goal 2: structure extensive inputs clearly
    xml_sections = [_build_xml_section(ar) for ar in agent_responses]
    combined = "\n\n".join(xml_sections)

    # Use full gpt-4o — merging 5 agent outputs requires complex reasoning (RCG Goal 3)
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    response = await llm.ainvoke([
        SystemMessage(content=SYNTHESISER_SYSTEM),
        HumanMessage(content=f"Destination: {destination}\n\nAgent outputs:\n\n{combined}"),
    ])

    raw = response.content if isinstance(response.content, str) else ""

    try:
        final = json.loads(raw)
        final = _sanitise(final, agent_responses, destination)
    except json.JSONDecodeError as e:
        logger.warning(f"Synthesiser parse failed: {e}")
        final = _fallback(agent_responses, destination)

    msg = final.get("orchestrator_message", "Here is your travel information.")
    return {
        "final_response": final,
        "messages": [{"role": "assistant", "content": msg}],
        "agent_responses": [],
    }


def _ensure_list(val):
    if isinstance(val, list): return val
    if isinstance(val, dict):
        for v in val.values():
            if isinstance(v, list): return v
    return None


def _sanitise(final: Dict, responses: List[AgentResponse], destination: Optional[str]) -> Dict:
    ar = final.get("agent_responses", {})
    for name in ["planner","weather","activities","advisory","rescue"]:
        if name not in ar:
            ar[name] = {"active": False, "response": ""}

    if ar["weather"].get("active"):
        ar["weather"]["forecast"] = _ensure_list(ar["weather"].get("forecast"))
    if ar["planner"].get("active"):
        ar["planner"]["itinerary"] = _ensure_list(ar["planner"].get("itinerary"))
    if ar["activities"].get("active"):
        h = _ensure_list(ar["activities"].get("highlights"))
        ar["activities"]["highlights"] = [x["name"] if isinstance(x, dict) else str(x) for x in h] if h else None
    if ar["advisory"].get("active"):
        ar["advisory"]["hazards"]     = _ensure_list(ar["advisory"].get("hazards"))
        ar["advisory"]["vaccines"]    = _ensure_list(ar["advisory"].get("vaccines"))
        ar["advisory"]["local_rules"] = _ensure_list(ar["advisory"].get("local_rules"))
        ar["advisory"]["sources"]     = _ensure_list(ar["advisory"].get("sources")) or []
        if not ar["advisory"].get("risk_level"):
            ar["advisory"]["risk_level"] = "LOW"
    if ar["rescue"].get("active"):
        ar["rescue"]["emergency_numbers"] = _ensure_list(ar["rescue"].get("emergency_numbers"))

    final["agent_responses"] = ar
    if not final.get("destination"):
        final["destination"] = destination
    return final


def _empty() -> Dict:
    return {
        "orchestrator_message": "Hello! I am travelbuddy, your AI travel assistant. Ask me anything about your trip.",
        "destination": None, "agents_involved": ["orchestrator"],
        "agent_responses": {
            "planner":    {"active": False, "response": "", "itinerary": None},
            "weather":    {"active": False, "response": "", "forecast": None},
            "activities": {"active": False, "response": "", "highlights": None},
            "advisory":   {"active": False, "response": "", "risk_level": "LOW",
                           "hazards": None, "visa": None, "vaccines": None,
                           "local_rules": None, "sources": []},
            "rescue":     {"active": False, "response": "", "emergency_numbers": None},
        }
    }


def _fallback(responses: List[AgentResponse], destination: Optional[str]) -> Dict:
    base = _empty()
    base["destination"] = destination
    base["agents_involved"] = [r["agent"] for r in responses]
    base["orchestrator_message"] = (
        " ".join(r["response"] for r in responses if r.get("response"))
        or "Travel information gathered."
    )
    for r in responses:
        n = r["agent"]
        if n in base["agent_responses"]:
            base["agent_responses"][n]["active"] = True
            base["agent_responses"][n]["response"] = r.get("response", "")
    return base

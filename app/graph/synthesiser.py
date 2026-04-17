"""
Synthesiser — travelbuddy v4
--------------------------
Two modes depending on how many agents ran:

SINGLE AGENT (follow-up query):
  - Return only that agent's response
  - No itinerary generation
  - active=true only for that agent, false for all others
  - orchestrator_message is a short 1-sentence summary

MULTI AGENT (full planning query):
  - Generate complete day-by-day itinerary incorporating all agent data
  - active=true for every agent that ran
  - Full detailed response
"""

import json
import re
import logging
from typing import Dict, Any, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings
from app.graph.state import TravelState

logger = logging.getLogger("travelbuddy.synthesiser")


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE AGENT SYSTEM PROMPT
# Used when only one agent ran — just format its response cleanly
# ─────────────────────────────────────────────────────────────────────────────
SINGLE_AGENT_SYSTEM = """You are the synthesis engine for travelbuddy travel assistant.
One specialist agent ran to answer the user's question.
Format its output into a clean structured JSON response.

Return ONLY valid JSON — no markdown, no extra text:
{
  "orchestrator_message": "One sentence summarising what was found",
  "destination": "destination or null",
  "trip_duration": null,
  "travel_dates": null,
  "agents_involved": ["agent_name"],
  "itinerary": [],
  "agent_responses": {
    "transport":     {"active": false, "response": ""},
    "accommodation": {"active": false, "response": ""},
    "weather":       {"active": false, "response": ""},
    "activities":    {"active": false, "response": ""},
    "advisory":      {"active": false, "response": ""},
    "rescue":        {"active": false, "response": ""}
  }
}

Set active=true and populate the response fields ONLY for the agent that ran.
Set active=false and response="" for all other agents.
itinerary MUST always be [].
"""


# ─────────────────────────────────────────────────────────────────────────────
# MULTI AGENT SYSTEM PROMPT
# Used for full planning — generates detailed itinerary from all agent data
# ─────────────────────────────────────────────────────────────────────────────
MULTI_AGENT_SYSTEM = """You are the synthesis engine for travelbuddy travel assistant.
Multiple specialist agents ran to build a complete trip plan.
Your job: merge their data and generate a FULL day-by-day itinerary.

════════════════════════════════════════════════════════
ITINERARY RULES — most important part of your output
════════════════════════════════════════════════════════
- Produce EXACTLY the number of days requested
- 5-6 time-slotted items per day
- Use SPECIFIC named places from the activities data
- Include named breakfast, lunch, dinner at real restaurants
- Include local transport between locations (BTS, MRT, taxi, ferry + cost)
- Day 1: airport arrival → airport transfer → hotel area check-in
- Last day: hotel check-out → airport departure
- Factor in weather — suggest indoor alternatives if rain forecast

Activity detail level required:
  BAD:  {"time":"09:00","activity":"Visit a famous temple"}
  GOOD: {"time":"09:00","activity":"Wat Pho — see the 46m reclining Buddha, arrive before 9am, take BTS to Saphan Taksin then river taxi (4 THB)", "cost":"200 THB","duration":"2 hrs"}

COST field: include entry fees, transport costs, meal budgets. Use "Free" if no charge.
DURATION field: realistic time to spend. e.g. "2 hrs", "45 min", "~1 hr", "half day"
Always include cost and duration for every item.

Return ONLY valid JSON — no markdown, no extra text:
{
  "orchestrator_message": "2-3 sentence summary of what was found across all agents",
  "destination": "destination",
  "trip_duration": "N days",
  "travel_dates": "month/dates",
  "agents_involved": ["all agents that ran"],
  "itinerary": [
    {
      "day": 1,
      "title": "Arrival & Area Name",
      "items": [
        {"time": "10:00", "activity": "Arrive at airport — take [transport] to [hotel area]", "cost": "SGD XX", "duration": "45 min"},
        {"time": "12:00", "activity": "Check in at [hotel neighbourhood] — drop bags", "cost": "Free", "duration": "30 min"},
        {"time": "13:00", "activity": "Lunch at [Named Restaurant] — [dish]", "cost": "SGD XX", "duration": "~1 hr"},
        {"time": "15:00", "activity": "[Named Attraction] — [what to do, transport tip]", "cost": "Free or SGD XX", "duration": "2 hrs"},
        {"time": "18:00", "activity": "[Named Area] — [detail]", "cost": "Free", "duration": "1 hr"},
        {"time": "19:30", "activity": "Dinner at [Named Restaurant] — [dish]", "cost": "SGD XX", "duration": "~1 hr"}
      ]
    }
  ],
  "agent_responses": {
    "transport":     {"active": true,  "response": "2-3 plain sentences", "flights": [], "local_transport": [], "airport_transfer": []},
    "accommodation": {"active": true,  "response": "2-3 plain sentences", "hotels": [], "areas": []},
    "weather":       {"active": true,  "response": "2-3 plain sentences", "forecast": []},
    "activities":    {"active": true,  "response": "2-3 plain sentences", "highlights": [], "restaurants": []},
    "advisory":      {"active": true,  "response": "2-3 plain sentences", "risk_level": "LOW", "hazards": [], "visa": {}, "vaccines": [], "local_rules": [], "sources": []},
    "rescue":        {"active": false, "response": "", "emergency_numbers": null}
  }
}

Set active=true only for agents that actually ran.
Set active=false and response="" for agents that did not run.
All response text = plain text only, no markdown, no asterisks.
"""


def _extract(result: Dict) -> Dict:
    """Pull all structured data from a raw agent result."""
    out = {}
    text = result.get("response") or result.get("text") or ""
    if text:
        out["text"] = text

    field_map = {
        "flights":              ["flights", "options", "flight_options"],
        "local_transport":      ["local_transport", "local", "transit"],
        "airport_transfer":     ["airport_transfer", "transfer"],
        "trains_buses":         ["trains_buses"],
        "tourist_passes":       ["tourist_passes"],
        "apps":                 ["apps"],
        "hotels":               ["hotels", "hotel_options"],
        "areas":                ["areas", "best_areas"],
        "alternatives":         ["alternatives"],
        "forecast":             ["forecast", "daily"],
        "seasonal_summary":     ["seasonal_summary"],
        "packing_tips":         ["packing_tips"],
        "highlights":           ["highlights", "activities", "places"],
        "restaurants":          ["restaurants"],
        "risk_level":           ["risk_level"],
        "hazards":              ["hazards"],
        "visa":                 ["visa"],
        "vaccines":             ["vaccines"],
        "local_rules":          ["local_rules"],
        "sources":              ["sources"],
        "emergency_numbers":    ["emergency_numbers", "emergency_contacts", "contacts"],
        "disruption_solutions": ["solutions", "disruption_solutions"],
    }
    for out_key, candidates in field_map.items():
        for c in candidates:
            if result.get(c) is not None:
                out[out_key] = result[c]
                break
    return out


def _build_section(name: str, result: Dict) -> str:
    ex = _extract(result)
    text = ex.pop("text", "")
    return (
        f"<agent name='{name}'>\n"
        f"  <response>{text}</response>\n"
        f"  <data>{json.dumps(ex, ensure_ascii=False, indent=2)}</data>\n"
        f"</agent>"
    )


def _empty_ar() -> Dict:
    """Empty agent_responses scaffold."""
    def _e(**kw):
        return {"active": False, "response": "", **kw}
    return {
        "transport":     _e(flights=None, local_transport=None, airport_transfer=None),
        "accommodation": _e(hotels=None, areas=None),
        "weather":       _e(forecast=None),
        "activities":    _e(highlights=None, restaurants=None),
        "advisory":      _e(risk_level=None, hazards=None, visa=None,
                            vaccines=None, local_rules=None, sources=None),
        "rescue":        _e(emergency_numbers=None, disruption_solutions=None),
    }


def _empty_response() -> Dict:
    return {
        "orchestrator_message": "Something went wrong. Please try again.",
        "destination": None, "trip_duration": None, "travel_dates": None,
        "agents_involved": [], "itinerary": [],
        "agent_responses": _empty_ar(),
    }


async def _synthesise_single(
    agent_name: str,
    agent_result: Dict,
    destination: str,
    llm: ChatOpenAI,
) -> Dict:
    """
    Format a single agent's response — no itinerary, no other agents.
    Uses a lightweight prompt since there's only one agent to format.
    """
    section = _build_section(agent_name, agent_result)

    prompt = (
        f"Destination: {destination}\n"
        f"Agent that ran: {agent_name}\n\n"
        f"{section}\n\n"
        f"Format the above into the required JSON. "
        f"Set active=true only for {agent_name}. "
        f"Set active=false for all other agents. "
        f"itinerary must be []."
    )

    response = await llm.ainvoke([
        SystemMessage(content=SINGLE_AGENT_SYSTEM),
        HumanMessage(content=prompt),
    ])
    raw = response.content if isinstance(response.content, str) else "{}"

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Build response manually from agent data
        ex = _extract(agent_result)
        ar = _empty_ar()
        ar[agent_name] = {"active": True, "response": ex.get("text", ""), **{
            k: v for k, v in ex.items() if k != "text"
        }}
        return {
            "orchestrator_message": ex.get("text", "")[:200],
            "destination": destination,
            "trip_duration": None, "travel_dates": None,
            "agents_involved": [agent_name],
            "itinerary": [],
            "agent_responses": ar,
        }

    # Ensure scaffold is complete
    result.setdefault("itinerary", [])
    ar = result.setdefault("agent_responses", {})
    for key, default in _empty_ar().items():
        if key not in ar:
            ar[key] = default

    # Force: only the running agent should be active
    for key in ar:
        if key != agent_name:
            ar[key]["active"] = False
            ar[key]["response"] = ""

    return result


async def _synthesise_multi(
    active_agents: List[str],
    sections: List[str],
    destination: str,
    duration: str,
    travel_dates: str,
    num_days: int,
    llm: ChatOpenAI,
) -> Dict:
    """Full synthesis with itinerary generation for multi-agent planning queries."""

    itinerary_req = (
        f"\n\nITINERARY REQUIREMENT:\n"
        f"Build a COMPLETE {num_days}-day itinerary for {destination}"
        f"{f' in {travel_dates}' if travel_dates else ''}.\n"
        f"Output exactly {num_days} day objects — no fewer.\n"
        f"Use transport, accommodation, weather and activities data above.\n"
        f"Day 1: airport arrival and hotel check-in.\n"
        f"Day {num_days}: hotel check-out and airport departure."
    ) if num_days > 0 else (
        "\n\nBuild a day-by-day itinerary using the agent data. "
        "5-6 items per day with specific named places."
    )

    prompt = (
        f"Destination: {destination}\n"
        f"Duration: {duration or 'not specified'}\n"
        f"Travel dates: {travel_dates or 'not specified'}\n"
        f"Agents that ran: {', '.join(active_agents)}\n\n"
        f"Agent data:\n" + "\n\n".join(sections) + itinerary_req
    )

    response = await llm.ainvoke([
        SystemMessage(content=MULTI_AGENT_SYSTEM),
        HumanMessage(content=prompt),
    ])
    raw = response.content if isinstance(response.content, str) else "{}"

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Multi-agent JSON parse error: {e}")
        return _empty_response()

    result.setdefault("itinerary", [])
    result.setdefault("trip_duration", duration)
    result.setdefault("travel_dates", travel_dates)

    # Ensure scaffold
    ar = result.setdefault("agent_responses", {})
    for key, default in _empty_ar().items():
        if key not in ar:
            ar[key] = default

    # Pad missing itinerary days
    itinerary = result.get("itinerary", [])
    if num_days > 0 and len(itinerary) < num_days:
        logger.warning(f"Synthesiser: {len(itinerary)}/{num_days} days produced — padding")
        existing = {d["day"] for d in itinerary}
        for day_num in range(1, num_days + 1):
            if day_num not in existing:
                itinerary.append({
                    "day": day_num,
                    "title": f"Day {day_num} — {destination}",
                    "items": [
                        {"time": "09:00", "activity": f"Morning in {destination}"},
                        {"time": "12:00", "activity": "Lunch at local restaurant"},
                        {"time": "14:00", "activity": "Visit local attraction"},
                        {"time": "19:00", "activity": "Dinner and evening"},
                    ]
                })
        itinerary.sort(key=lambda d: d["day"])
        result["itinerary"] = itinerary

    return result


async def synthesiser_node(state: TravelState) -> Dict[str, Any]:
    """
    Route to single-agent or multi-agent synthesis based on how many agents ran.
    Single agent → quick format, no itinerary.
    Multiple agents → full itinerary generation.
    """
    agent_responses: List[Dict] = state.get("agent_responses", [])

    if not agent_responses:
        logger.warning("Synthesiser: no responses")
        return {"final_response": _empty_response()}

    # Collect active agents
    active = [(r.get("agent", "unknown"), r)
              for r in agent_responses
              if r.get("active") or r.get("response")]

    if not active:
        logger.warning("Synthesiser: all agents inactive")
        return {"final_response": _empty_response()}

    destination  = state.get("destination", "unknown")
    duration     = state.get("trip_duration", "")
    travel_dates = state.get("travel_dates", "")

    num_days = 0
    if duration:
        m = re.search(r'(\d+)', duration)
        if m:
            num_days = int(m.group(1))

    active_names = [name for name, _ in active]

    logger.info(
        f"\n{'='*60}\n"
        f"SYNTHESISER\n"
        f"  Destination  : {destination}\n"
        f"  Duration     : {duration} ({num_days}d)\n"
        f"  Active agents: {active_names}\n"
        f"  Mode         : {'SINGLE' if len(active) == 1 else 'MULTI'}\n"
        f"{'='*60}"
    )

    # Planning requires at least 2 of these data agents
    planning_set = {"transport", "accommodation", "activities"}
    is_planning  = (
        num_days > 0
        and len(active) >= 2
        and len(planning_set.intersection(set(active_names))) >= 2
    )

    # Choose gpt-4o-mini for single-agent (cheaper), gpt-4o for multi (needs quality)
    if len(active) == 1:
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_MINI,
            api_key=settings.OPENAI_API_KEY,
            temperature=0,
            model_kwargs={"response_format": {"type": "json_object"}},
            max_tokens=1500,
        )
        agent_name, agent_result = active[0]
        logger.info(f"Synthesiser: SINGLE mode → formatting {agent_name}")
        result = await _synthesise_single(agent_name, agent_result, destination, llm)
    else:
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.5,
            model_kwargs={"response_format": {"type": "json_object"}},
            max_tokens=6000,
        )
        sections = [_build_section(name, res) for name, res in active]
        logger.info(f"Synthesiser: MULTI mode → {active_names} | planning={is_planning}")
        result = await _synthesise_multi(
            active_names, sections, destination,
            duration, travel_dates, num_days if is_planning else 0, llm
        )

    ar = result.get("agent_responses", {})
    active_out = [k for k, v in ar.items() if v.get("active")]
    logger.info(
        f"\n{'='*60}\n"
        f"SYNTHESISER COMPLETE\n"
        f"  Active in output : {active_out}\n"
        f"  Itinerary days   : {len(result.get('itinerary', []))}\n"
        f"  Summary          : {result.get('orchestrator_message','')[:120]}\n"
        f"{'='*60}\n"
    )

    # ── Sanitise advisory fields before returning ─────────────────────────────
    ar  = result.get("agent_responses", {})
    adv = ar.get("advisory", {})
    if adv.get("active"):
        # risk_level must be one of the known values or None
        rl = adv.get("risk_level")
        adv["risk_level"] = (
            str(rl).upper()
            if rl and str(rl).lower() not in ("null","undefined","none","")
            else None
        )
        # visa.requirement must be a real string
        visa = adv.get("visa")
        if isinstance(visa, dict):
            req = visa.get("requirement","")
            if not req or str(req).lower() in ("null","undefined","none",""):
                adv["visa"] = None
        elif not isinstance(visa, dict):
            adv["visa"] = None
        # vaccines — drop invalid entries
        adv["vaccines"] = [
            v for v in (adv.get("vaccines") or [])
            if isinstance(v, dict) and v.get("name")
            and str(v.get("name","")).lower() not in ("null","undefined","")
        ]
        # local_rules — drop empty strings
        adv["local_rules"] = [
            r for r in (adv.get("local_rules") or [])
            if r and str(r).strip()
            and str(r).lower() not in ("null","undefined")
        ]
        ar["advisory"] = adv

    return {"final_response": result}

"""
Supervisor Node —  v4
Classifies current query → routes to correct agent(s).
Single-topic → one agent. Full trip → all agents in parallel.
"""

import re, json, logging
from typing import List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings
from app.graph.state import TravelState

logger = logging.getLogger("travelbuddy.supervisor")


def _msg_role(m) -> str:
    if isinstance(m, dict): return m.get("role", "")
    return getattr(m, "type", getattr(m, "role", ""))

def _msg_content(m) -> str:
    if isinstance(m, dict): return m.get("content", "")
    return getattr(m, "content", "")

def _match(q: str, patterns: list) -> bool:
    return any(p in q for p in patterns)

def _is_numbered_trip(q: str) -> bool:
    return bool(re.search(
        r'\d+[ -]?(day|days|night|nights)[ -]?(trip|holiday|vacation|itinerary|plan|in\b|at\b|visiting)',
        q.lower()
    ))


RESCUE = [
    "emergency contact","emergency number","emergency plan",
    "nearest hospital","find hospital","lost passport","stolen passport",
    "what if something goes wrong","flight cancel","flight delay",
    "typhoon warning","earthquake warning","police number",
    "ambulance","embassy address","consulate address",
]

SAFETY = [
    "is it safe","is it dangerous","how safe","how dangerous",
    "safe to travel","safe to visit","safe to go","safe for",
    " is safe","safe?"," dangerous","dangerous?",
    "crime rate","crime in","danger in","dangerous in",
    "travel advisory","travel warning","travel alert","travel ban",
    "visa requirement","need a visa","do i need visa","need visa for",
    "visa on arrival","entry requirement","evisa",
    "vaccine","vaccines","vaccination","vaccinations",
    "health requirement","health certificate",
    "local law","local laws","laws in","law in",
    "is it legal","dress code","can i drink","can i wear","can i smoke",
    "rules in","rules for","regulations in",
]

FULL_TRIP = [
    "plan a trip","plan my trip","plan the trip",
    "plan a holiday","plan my holiday","plan a vacation","plan my vacation",
    "full itinerary","complete itinerary","full trip","complete trip",
    "help me plan","please plan","can you plan",
    "make me an itinerary","create an itinerary","give me an itinerary",
    "give me a plan","give me a schedule","build me an itinerary",
]

WEATHER = [
    "weather in","weather for","weather during","weather when","weather like",
    "what is the weather","what's the weather",
    "climate in","climate of","how hot in","how cold in",
    "temperature in","best time to visit","best time to go",
    "rainy season","dry season","monsoon","typhoon season",
    "what to pack","packing list","packing for",
    "what to wear","what should i wear","forecast for",
]

ACTIVITIES = [
    "things to do","what to do in","what can i do in","what to do there",
    "places to visit","must see","top attractions","best attractions",
    "tourist spots","sightseeing","points of interest",
    "best restaurants","where to eat","best food",
    "street food","local food","local cuisine","food scene",
    "what to eat","must try food","must eat",
    "nightlife in","shopping in","markets in",
    "day trip from","excursion","things to see",
]

TRANSPORT = [
    "flight","flights","fly to","fly from",
    "how to get to","how to get there","how to reach","how do i get",
    "cheapest flight","cheap flight","best flight","book flight",
    "train","trains","bus to","ferry to","coach to",
    "getting around","local transport","public transport","transit",
    "airport transfer","from airport","to airport","airport shuttle",
    "jr pass","bullet train","shinkansen","subway","metro",
    "mrt","bts","skytrain",
]

ACCOMMODATION = [
    "hotel","hotels","motel","resort","inn","lodge",
    "airbnb","hostel","guesthouse","serviced apartment",
    "accommodation","accommodations","lodging","place to stay",
    "where to stay","where can i stay","best place to stay",
    "which area to stay","best area to stay","neighbourhood to stay",
    "4 star","4-star","five star","5 star","5-star","3 star","3-star",
    "budget stay","cheap stay","luxury stay",
    "budget accommodation","cheap accommodation",
    "affordable stay","affordable hotel","cheaper hotel",
    "cheapest hotel","cheap hotel","budget hotel","luxury hotel",
    "book a hotel","find a hotel","alternative accommodation","cheaper alternative",
]

CHANGE   = ["change","update","modify","edit","redo","different","instead",
            "replace","swap","can you change","please change","can you update"]
CONFIRM  = ["yes","yeah","yep","sure","ok","okay","go ahead",
            "please do","confirm","yes please","absolutely"]
REJECT   = ["no","nope","don't","do not","keep it","leave it",
            "never mind","cancel","ignore"]


def _classify(q: str) -> Optional[str]:
    if _match(q, RESCUE):        return "rescue"
    if _match(q, SAFETY):        return "advisory"
    if _match(q, FULL_TRIP):     return "full_trip"
    if _is_numbered_trip(q):     return "full_trip"
    if _match(q, WEATHER):       return "weather"
    if _match(q, ACTIVITIES):    return "activities"
    if _match(q, TRANSPORT):     return "transport"
    if _match(q, ACCOMMODATION): return "accommodation"
    return None


async def supervisor_node(state: TravelState) -> dict:
    messages          = state.get("messages", [])
    already_generated = state.get("already_generated", [])
    pending_agent     = state.get("pending_change_agent")

    # Extract latest user message — works for both plain dicts and LangChain objects
    latest = ""
    for m in reversed(messages):
        if _msg_role(m) == "user":
            latest = _msg_content(m)
            break

    q = latest.lower().strip()

    logger.info(
        f"\n{'─'*50}\n"
        f"SUPERVISOR\n"
        f"  Query      : {latest[:120]}\n"
        f"  Already gen: {already_generated}\n"
        f"  Pending    : {pending_agent}\n"
        f"{'─'*50}"
    )

    # ── Handle pending yes/no ─────────────────────────────────────────────────
    if pending_agent:
        if _match(q, CONFIRM):
            agents = (["transport","accommodation","weather","activities","advisory"]
                      if pending_agent == "full_trip" else [pending_agent])
            logger.info(f"Supervisor: confirmed → {agents}")
            return {"next_agents": agents, "pending_change_agent": None,
                    "pending_change_reason": None, "messages": [], "agent_responses": []}
        elif _match(q, REJECT):
            logger.info("Supervisor: rejected — no action")
            return {"next_agents": [], "pending_change_agent": None,
                    "pending_change_reason": None, "messages": [], "agent_responses": []}

    # ── Classify ──────────────────────────────────────────────────────────────
    classification = _classify(q)
    logger.info(f"Supervisor classification: {classification}")

    # ── Full trip replan guard ────────────────────────────────────────────────
    if classification == "full_trip" and already_generated and _match(q, CHANGE):
        confirm_q = "You already have a full trip plan. Would you like me to regenerate it? (yes / no)"
        return {
            "next_agents": [], "pending_change_agent": "full_trip",
            "pending_change_reason": latest, "clarification_needed": True,
            "clarification_question": confirm_q,
            "messages": [{"role": "assistant", "content": confirm_q}],
            "agent_responses": [],
        }

    # ── Direct routing ────────────────────────────────────────────────────────
    if classification == "rescue":        return _route(["rescue"])
    if classification == "advisory":      return _route(["advisory"])
    if classification == "weather":       return _route(["weather"])
    if classification == "activities":    return _route(["activities"])
    if classification == "transport":     return _route(["transport"])
    if classification == "accommodation": return _route(["accommodation"])
    if classification == "full_trip":
        return _route(["transport","accommodation","weather","activities","advisory"])

    # ── LLM fallback ─────────────────────────────────────────────────────────
    logger.info("Supervisor: ambiguous — LLM routing")
    ctx = " | ".join(filter(None,[
        state.get("destination"), state.get("trip_duration"), state.get("travel_dates")
    ]))
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL_ROUTER, api_key=settings.OPENAI_API_KEY,
        temperature=0, model_kwargs={"response_format": {"type": "json_object"}},
    )
    try:
        resp = await llm.ainvoke([
            SystemMessage(content=(
                "Route to ONE travel agent only.\n"
                "advisory=safety/visa/vaccine. accommodation=hotel/stay/4star.\n"
                "transport=flight/train. weather=forecast/climate.\n"
                "activities=food/attractions. rescue=emergency/hospital.\n"
                'Return JSON: {"next_agents":["agent"]}'
            )),
            HumanMessage(content=f"Context:{ctx}\nQuestion:{latest}"),
        ])
        agents = json.loads(resp.content or "{}").get("next_agents", [])
        agents = [a for a in agents
                  if a in {"transport","accommodation","weather","activities","advisory","rescue"}]
    except Exception as e:
        logger.warning(f"LLM routing failed: {e}")
        agents = []

    if "rescue" in agents and not _match(q, RESCUE):
        agents.remove("rescue")

    if not agents:
        # Never default to advisory — pick first not-yet-answered
        for a in ["accommodation","activities","transport","weather","advisory"]:
            if a not in already_generated:
                agents = [a]
                break
        if not agents:
            agents = ["activities"]

    logger.info(f"Supervisor LLM → {agents}")
    return _route(agents)


def _route(agents: list) -> dict:
    logger.info(f"Supervisor → {agents}")
    return {"next_agents": agents, "messages": [], "agent_responses": []}

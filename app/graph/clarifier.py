"""
Clarifier Node — travelbuddy v4
-----------------------------
Extracts travel context and decides whether to ask one clarifying question.

Clarification logic for planning queries:
  - destination missing                        → ask destination
  - destination known, both duration+dates missing → ask "how many days and which month?"
  - destination known, duration known, dates missing → ask "which month?"
  - destination known, dates known, duration missing → ask "how many days?"
  - destination + duration + dates all known   → proceed immediately
  - any follow-up query                        → proceed always
  - non-planning query (safety/weather/etc.)   → proceed always
"""

import json
import re
import logging
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings
from app.graph.state import TravelState

logger = logging.getLogger("travelbuddy.clarifier")


def _msg_role(msg) -> str:
    """Safe role extraction from dict or LangChain message object."""
    if isinstance(msg, dict):
        return msg.get("role", "user")
    t = getattr(msg, "type", "") or getattr(msg.__class__, "__name__", "")
    if "Human" in t or t == "human": return "user"
    if "AI" in t or t == "ai":       return "assistant"
    if "System" in t:                 return "system"
    return "user"


def _msg_content(msg) -> str:
    """Safe content extraction from dict or LangChain message object."""
    if isinstance(msg, dict):
        return msg.get("content", "")
    c = getattr(msg, "content", "")
    if isinstance(c, list):
        return " ".join(b.get("text","") if isinstance(b,dict) else str(b) for b in c)
    return str(c) if c else ""


# ── Python pre-extraction ─────────────────────────────────────────────────────

DURATION_PATTERNS = [
    r'(\d+)\s*-?\s*day',
    r'(\d+)\s*-?\s*night',
    r'(\d+)\s*-?\s*week',
    r'for\s+(\d+)\s*days?',
    r'(\d+)\s*days?\s+trip',
    r'(\d+)\s*days?\s+in',
    r'(\d+)\s*nights?\s+in',
]

MONTHS = [
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
    'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
]

SEASONS = ['spring', 'summer', 'autumn', 'fall', 'winter']

SAFETY_KEYWORDS       = ['is it safe', 'safe to travel', 'safe to visit',
                         'is safe', ' safe', 'dangerous', 'danger', 'risk',
                         'crime rate', 'travel advisory', 'travel warning',
                         'visa', 'vaccine', 'vaccination', 'local law']
WEATHER_KEYWORDS      = ['weather', 'climate', 'temperature', 'rain', 'forecast',
                         'packing', 'pack', 'best time to visit', 'season']
ACTIVITY_KEYWORDS     = ['things to do', 'activities', 'restaurant', 'food', 'eat',
                         'attraction', 'museum', 'beach', 'shopping', 'experience',
                         'things to see', 'places to visit', 'must see']
ACCOMMODATION_KEYWORDS= ['hotel', 'hotels', 'hostel', 'airbnb', 'accommodation',
                         'where to stay', 'place to stay', '4 star', '4-star',
                         '5 star', '5-star', 'budget hotel', 'cheap hotel',
                         'luxury hotel', 'resort', 'guesthouse']
TRANSPORT_KEYWORDS    = ['flight', 'flights', 'train', 'bus', 'ferry',
                         'how to get', 'getting around', 'airport transfer',
                         'local transport', 'public transport', 'transit']
EMERGENCY_KEYWORDS    = ['emergency', 'hospital', 'police', 'ambulance', 'help',
                         'lost passport', 'stolen passport', 'embassy', 'urgent']
PLANNING_KEYWORDS     = ['plan a trip', 'plan my trip', 'plan a holiday',
                         'itinerary', 'day trip', 'day tour', 'full trip']


def _pre_extract(messages: list) -> Dict[str, Any]:
    """Fast Python extraction before LLM call."""
    # Use only the latest USER message for query_type detection
    # Using full history causes query_type to match previous assistant responses
    latest_user = next(
        (_msg_content(m) for m in reversed(messages) if _msg_role(m) == "user"),
        ""
    ).lower()
    # Use ONLY the latest user message for duration/date extraction.
    # Scanning multiple messages pulls in values from old conversations
    # (e.g. "7 days Japan" would bleed into a new "3 day Bangkok" query).
    text = latest_user
    result = {}

    # Duration
    for pattern in DURATION_PATTERNS:
        match = re.search(pattern, text)
        if match:
            n = int(match.group(1))
            if 'week' in pattern:
                n = n * 7
            result["trip_duration"] = f"{n} days"
            break

    if 'long weekend' in text and "trip_duration" not in result:
        result["trip_duration"] = "3 days"
    elif 'weekend' in text and "trip_duration" not in result:
        result["trip_duration"] = "2 days"

    # Travel dates — month names
    for month in MONTHS:
        if re.search(r'\b' + month + r'\b', text):
            result["travel_dates"] = month.capitalize()
            break

    # Season
    if "travel_dates" not in result:
        for season in SEASONS:
            if re.search(r'\b' + season + r'\b', text):
                result["travel_dates"] = season.capitalize()
                break

    # Query type — detected from latest user message only, not full history
    # This prevents previous assistant responses from polluting the classification
    q = latest_user
    if any(kw in q for kw in EMERGENCY_KEYWORDS):
        result["query_type"] = "emergency"
    elif any(kw in q for kw in SAFETY_KEYWORDS):
        result["query_type"] = "safety"
    elif any(kw in q for kw in ACCOMMODATION_KEYWORDS):
        result["query_type"] = "accommodation"
    elif any(kw in q for kw in TRANSPORT_KEYWORDS):
        result["query_type"] = "transport"
    elif any(kw in q for kw in WEATHER_KEYWORDS):
        result["query_type"] = "weather"
    elif any(kw in q for kw in ACTIVITY_KEYWORDS):
        result["query_type"] = "activities"
    elif any(kw in q for kw in PLANNING_KEYWORDS):
        result["query_type"] = "planning"

    return result


CLARIFIER_SYSTEM = """You are a travel context extractor for an AI travel assistant.
Extract travel information from the conversation.

═══ EXTRACTION (works for ANY destination worldwide) ═══

DESTINATION — extract any place name mentioned:
  Pattern: "[verb] to [place]"  → extract [place] as destination
  Pattern: "[number] day trip to [place]" → extract [place]
  Pattern: "in [place]" / "visit [place]" / "explore [place]" → extract [place]

  Examples showing the PATTERN (not a fixed list of allowed countries):
    "trip to [any city]"          → destination: "[city], [country]"
    "visit [any country]"         → destination: "[country]"
    "plan [any destination] trip" → destination: "[destination]"
    "going to [any place]"        → destination: "[place]"

  This works for ANY destination worldwide — every city, country, region,
  landmark or territory is valid. America, India, Brazil, Nigeria, Iceland,
  anywhere — extract it as destination.

DURATION — any number + time unit:
  "3 day trip"     → trip_duration: "3 days"
  "5 nights"       → trip_duration: "5 days"
  "2 week holiday" → trip_duration: "14 days"
  "weekend trip"   → trip_duration: "2 days"

DATES — any time reference:
  "in april"       → travel_dates: "April"
  "next summer"    → travel_dates: "Summer"
  "december 2025"  → travel_dates: "December 2025"

LINKING — short answers link to the previous assistant question:
  ASSISTANT: "Which month are you thinking?"
  USER: "april"  → travel_dates: "April", proceed: true

  ASSISTANT: "How many days?"
  USER: "7"      → trip_duration: "7 days", proceed: true

═══ QUERY TYPE ═══
- planning      : wants itinerary, trip plan, full trip, day-by-day schedule
- safety        : is it safe, visa, vaccine, travel advisory, local laws
- accommodation : hotel, hostel, airbnb, where to stay, 4-star, cheap hotel
- transport     : flights, trains, how to get there, airport transfer
- weather       : weather, climate, forecast, packing, best time to visit
- activities    : restaurants, attractions, things to do, food, sightseeing
- emergency     : hospital, police, ambulance, emergency contacts
- general       : greetings, unclear

═══ PROCEED DECISION ═══

NON-PLANNING queries (safety/weather/activities/accommodation/transport/emergency/general):
  destination known → proceed=true always, no questions needed
  destination missing → ask once, then proceed

PLANNING queries — first query only:
  destination missing                                 → ask: "Where would you like to travel?"
  destination known, duration missing, dates missing  → ask: "How many days, and which month?"
  destination known, duration known, dates missing    → ask: "Which month are you planning to travel?"
  destination known, duration missing, dates known    → ask: "How many days are you planning?"
  destination known, duration known, dates known      → proceed=true

FOLLOW-UP queries (conversation already has 2+ messages):
  → proceed=true always, no questions

Rules:
- ONE question maximum per response
- question=null when proceed=true
- After 2 questions already asked → proceed=true always
- When in doubt → proceed=true

Respond ONLY with valid JSON:
{
  "extracted": {
    "destination":     "Full place name or null",
    "travel_dates":    "month/season or null",
    "traveler_origin": "home country or null",
    "trip_duration":   "N days or null",
    "travel_purpose":  "holiday/business/other or null"
  },
  "query_type": "planning|safety|weather|activities|emergency|general",
  "proceed": true|false,
  "question": "one friendly question, or null",
  "missing_field": "destination|duration|dates|null"
}
"""


async def clarifier_node(state: TravelState) -> Dict[str, Any]:
    """
    LangGraph node: Clarifier
    Extracts context and asks for missing planning info when needed.
    """
    messages  = state.get("messages", [])
    collected = state.get("collected_info", {})

    # Count clarification rounds
    clarification_rounds = sum(
        1 for m in messages
        if _msg_role(m) == "assistant" and "?" in _msg_content(m)
    )

    # Hard stop after 2 rounds
    if clarification_rounds >= 2:
        logger.info("Clarifier: 2+ rounds — forcing proceed")
        return {
            "clarification_needed":   False,
            "clarification_question": None,
            "clarification_field":    None,
            "messages":               [],
            "agent_responses":        [],
        }

    # ── Step 1: Python pre-extraction ─────────────────────────────────────────
    pre = _pre_extract(messages)
    logger.info(f"Clarifier pre-extract: {pre}")

    existing_dest     = collected.get("destination")     or state.get("destination")
    existing_duration = collected.get("trip_duration")   or state.get("trip_duration")
    existing_dates    = collected.get("travel_dates")    or state.get("travel_dates")

    # ── Step 2: LLM extraction ────────────────────────────────────────────────
    convo_text = "\n".join(
        f"{_msg_role(m).upper()}: {_msg_content(m)}"
        for m in messages[-20:]
    )

    # A follow-up means the clarifier already asked a question in THIS session
    # and the user is answering it. A long conversationHistory from a previous
    # trip does NOT make this a follow-up — that would skip destination extraction
    # and lock in the old destination (the Japan/Bangkok bug).
    is_follow_up = clarification_rounds > 0

    pre_context = json.dumps({k: v for k, v in {
        "already_collected":    collected,
        "python_duration":      pre.get("trip_duration"),
        "python_dates":         pre.get("travel_dates"),
        "python_query_type":    pre.get("query_type"),
        "existing_destination": existing_dest,
        "is_follow_up":         is_follow_up,
        "clarification_rounds": clarification_rounds,
    }.items() if v is not None})

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL_ROUTER,
        api_key=settings.OPENAI_API_KEY,
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    response = await llm.ainvoke([
        SystemMessage(content=CLARIFIER_SYSTEM),
        HumanMessage(content=(
            f"Conversation:\n{convo_text}\n\n"
            f"Context: {pre_context}\n\n"
            "Extract all travel context. "
            "If this is a planning query and month/dates are missing, ask for the month. "
            "If follow-up, always proceed=true."
        )),
    ])

    raw = response.content if isinstance(response.content, str) else "{}"

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Clarifier JSON parse failed — proceeding")
        result = {"proceed": True, "extracted": {}, "query_type": "planning"}

    extracted  = result.get("extracted", {})
    proceed    = result.get("proceed", True)
    question   = result.get("question")
    field      = result.get("missing_field")
    query_type = result.get("query_type", pre.get("query_type", "planning"))

    # ── Step 3: Merge Python + LLM results ───────────────────────────────────
    if pre.get("trip_duration") and not extracted.get("trip_duration"):
        extracted["trip_duration"] = pre["trip_duration"]
    if pre.get("travel_dates") and not extracted.get("travel_dates"):
        extracted["travel_dates"] = pre["travel_dates"]
    # Only inherit the old destination if this is a genuine follow-up
    # (clarifier already asked a question and user is answering).
    # For a fresh planning query with a new destination, existing_dest
    # from the old conversation must NOT override what the LLM extracted.
    if existing_dest and not extracted.get("destination") and is_follow_up:
        extracted["destination"] = existing_dest

    # Resolve final values
    dest     = extracted.get("destination")     or existing_dest
    duration = extracted.get("trip_duration")   or existing_duration or pre.get("trip_duration")
    dates    = extracted.get("travel_dates")    or existing_dates    or pre.get("travel_dates")

    # ── Step 4: Override logic ────────────────────────────────────────────────

    # Follow-up or non-planning → always proceed
    if is_follow_up:
        proceed  = True
        question = None
        logger.info("Clarifier: follow-up → proceed")

    elif query_type in ("safety", "weather", "activities", "emergency",
                        "accommodation", "transport", "general"):
        if dest:
            proceed  = True
            question = None

    elif query_type == "planning":
        if not dest:
            # No destination at all — ask for it
            proceed  = False
            question = "Where would you like to travel?"
            field    = "destination"

        elif dest and not duration and not dates:
            # Have destination, missing both duration and dates
            proceed  = False
            question = "How many days are you planning, and which month?"
            field    = "duration"

        elif dest and duration and not dates:
            # Have destination + duration, missing dates — THIS IS THE FIX
            proceed  = False
            question = f"Which month are you planning to travel to {dest.split(',')[0]}?"
            field    = "dates"

        elif dest and not duration and dates:
            # Have destination + dates, missing duration
            proceed  = False
            question = "How many days are you planning to stay?"
            field    = "duration"

        elif dest and duration and dates:
            # Have everything needed
            proceed  = True
            question = None

    # Final safety: if destination known and already asked once before, proceed
    if dest and clarification_rounds >= 1:
        proceed  = True
        question = None

    logger.info(
        f"Clarifier: type={query_type} proceed={proceed} "
        f"dest={dest} duration={duration} dates={dates} "
        f"question={question}"
    )

    # ── Step 5: Build state updates ───────────────────────────────────────────
    new_collected = {**collected}
    updates: Dict[str, Any] = {
        "messages":        [],
        "agent_responses": [],
        "collected_info":  new_collected,
    }

    for key in ["destination", "travel_dates", "traveler_origin",
                "trip_duration", "travel_purpose"]:
        val = extracted.get(key) or state.get(key)
        if val:
            updates[key] = val
            new_collected[key] = val

    if not proceed and question:
        logger.info(f"Clarifier: asking → '{question}'")
        updates.update({
            "clarification_needed":   True,
            "clarification_question": question,
            "clarification_field":    field,
            "messages": [{"role": "assistant", "content": question}],
        })
    else:
        updates.update({
            "clarification_needed":   False,
            "clarification_question": None,
            "clarification_field":    None,
        })

    return updates

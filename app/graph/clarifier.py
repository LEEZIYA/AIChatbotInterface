"""
Clarifier Node — RCG Edition
-----------------------------
Extracts travel context from conversation and decides whether to proceed
or ask one clarifying question.

Design principles:
- Pattern-based extraction rules, NOT destination-specific examples
- Any city, country or region in the world is valid — no hardcoding
- Bias strongly toward proceeding — interrogating users is bad UX
- Pre-extraction in Python catches obvious cases before calling the LLM
  (saves API cost and avoids LLM extraction failures on simple queries)
"""

import json
import re
import logging
from typing import Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import settings
from app.graph.state import TravelState

logger = logging.getLogger("travelbuddy.clarifier")


# ── Pre-extraction patterns ────────────────────────────────────────────────────
# Catch obvious cases in Python before calling the LLM.
# This handles the most common query shapes robustly.

DURATION_PATTERNS = [
    r'(\d+)\s*-?\s*day',          # "3 day", "3-day", "3 days"
    r'(\d+)\s*-?\s*night',        # "5 night", "5-night", "5 nights"
    r'(\d+)\s*-?\s*week',         # "2 week" → convert to days
    r'for\s+(\d+)\s*days?',       # "for 3 days"
    r'(\d+)\s*days?\s+trip',      # "3 days trip"
    r'(\d+)\s*days?\s+in',        # "5 days in"
]

TRAVEL_VERBS = [
    'plan', 'trip', 'travel', 'visit', 'go to', 'going to', 'fly to',
    'holiday', 'vacation', 'journey', 'tour', 'explore', 'itinerary',
    'book', 'flight', 'hotel', 'stay in', 'spend.*in',
]

SAFETY_KEYWORDS = [
    'safe', 'safety', 'dangerous', 'danger', 'risk', 'crime', 'protest',
    'war', 'conflict', 'unrest', 'advisory', 'warning', 'alert',
]

WEATHER_KEYWORDS = [
    'weather', 'climate', 'temperature', 'rain', 'sunny', 'forecast',
    'packing', 'pack', 'what to wear', 'best time', 'season',
]

ACTIVITY_KEYWORDS = [
    'things to do', 'activities', 'restaurant', 'food', 'eat', 'drink',
    'attraction', 'museum', 'beach', 'nightlife', 'shopping', 'experience',
]

EMERGENCY_KEYWORDS = [
    'emergency', 'hospital', 'police', 'ambulance', 'help', 'lost',
    'stolen', 'passport', 'embassy', 'consul', 'sos', 'urgent',
]

MONTHS = [
    'january','february','march','april','may','june',
    'july','august','september','october','november','december',
    'jan','feb','mar','apr','jun','jul','aug','sep','oct','nov','dec',
]


def _pre_extract(messages: list) -> Dict[str, Any]:
    """
    Fast Python-based extraction before calling the LLM.
    Handles the most common query patterns without an API call.
    Returns partial extracted dict — LLM fills in the rest.
    """
    # Combine last 5 messages into one text blob for pattern matching
    text = " ".join(
        m.get("content", "") for m in messages[-5:]
    ).lower()

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

    # Travel dates (month names)
    for month in MONTHS:
        if month in text:
            result["travel_dates"] = month.capitalize()
            break

    # Query type
    if any(kw in text for kw in EMERGENCY_KEYWORDS):
        result["query_type"] = "emergency"
    elif any(kw in text for kw in SAFETY_KEYWORDS):
        result["query_type"] = "safety"
    elif any(kw in text for kw in WEATHER_KEYWORDS):
        result["query_type"] = "weather"
    elif any(kw in text for kw in ACTIVITY_KEYWORDS):
        result["query_type"] = "activities"
    elif any(re.search(r'\b' + re.escape(v.replace('.*', r'\w*')), text) for v in TRAVEL_VERBS):
        result["query_type"] = "planning"

    return result


CLARIFIER_SYSTEM = """You are a travel context extractor for an AI travel assistant.

Your job: read the conversation and fill in a JSON object with travel context.
You work for travellers going ANYWHERE in the world — every city and country is valid.

═══ EXTRACTION RULES (apply to ANY destination) ═══

DESTINATION — extract any place name mentioned:
  Pattern: "[verb] to [place]", "in [place]", "[place] trip", "visit [place]"
  Examples of what to extract (the pattern matters, not the specific place):
    "trip to paris"           → destination: "Paris, France"
    "visit new york"          → destination: "New York, USA"
    "holiday in lisbon"       → destination: "Lisbon, Portugal"
    "plan dubai trip"         → destination: "Dubai, UAE"
    "going to cairo"          → destination: "Cairo, Egypt"
    "explore vietnam"         → destination: "Vietnam"
    "fly to sydney"           → destination: "Sydney, Australia"
  Rule: any recognisable city, country, region or landmark = destination

DURATION — extract any number + time unit:
  Pattern: [number] + day/days/night/nights/week/weeks
  Examples:
    "3 day trip"     → trip_duration: "3 days"
    "5 nights"       → trip_duration: "5 days"
    "2 week holiday" → trip_duration: "14 days"
    "weekend trip"   → trip_duration: "2 days"
    "long weekend"   → trip_duration: "3 days"
  Rule: extract the number, convert weeks to days

DATES — extract any time reference:
  Pattern: month names, "next [month/week]", "in [season]", "[month] [year]"
  Examples:
    "in april"          → travel_dates: "April"
    "next summer"       → travel_dates: "Summer"
    "december 2025"     → travel_dates: "December 2025"
    "during chinese new year" → travel_dates: "Chinese New Year"

LINKING — if the last assistant message asked a question, the user reply answers it:
  ASSISTANT: "Where would you like to travel?"
  USER: "rome"      → destination: "Rome, Italy"

  ASSISTANT: "How many days?"
  USER: "a week"    → trip_duration: "7 days"

═══ QUERY TYPE CLASSIFICATION ═══

- planning   : wants itinerary, trip plan, what to do, flights, hotels
- safety     : safety, visa, vaccine, law, advisory, risk
- weather    : weather, climate, forecast, packing
- activities : restaurants, things to do, attractions, food
- emergency  : hospital, police, emergency contacts, lost passport
- general    : greetings, off-topic, unclear

═══ PROCEED DECISION ═══

proceed = true when:
  - destination is known (for ANY query type)
  - user just answered a clarification question
  - query_type is emergency or general
  - you have been uncertain and already asked 1+ questions this session
  - the message seems like a travel query even if destination is unclear

proceed = false ONLY when:
  - query_type is planning/safety/weather/activities AND
    destination is genuinely impossible to infer from the entire conversation

IMPORTANT: When proceed=false, ask for destination ONLY.
Never ask for duration or dates — agents handle those.
Never ask more than one question.
When in doubt → set proceed=true.

═══ OUTPUT ═══

Respond ONLY with valid JSON:
{
  "extracted": {
    "destination":     "Full place name, country or null",
    "travel_dates":    "month/season/dates or null",
    "traveler_origin": "home country or null",
    "trip_duration":   "N days or null",
    "travel_purpose":  "holiday/business/other or null"
  },
  "query_type": "planning|safety|weather|activities|emergency|general",
  "missing_critical": true|false,
  "question": "one friendly question to ask, or null",
  "missing_field": "destination or null",
  "proceed": true|false
}
"""


async def clarifier_node(state: TravelState) -> Dict[str, Any]:
    """
    LangGraph node: Clarifier
    Extracts travel context and decides whether to proceed or ask one question.
    """
    messages   = state.get("messages", [])
    collected  = state.get("collected_info", {})

    # Hard stop after 2 clarification rounds — never interrogate the user further
    clarification_rounds = sum(
        1 for m in messages
        if m.get("role") == "assistant" and "?" in m.get("content", "")
    )
    if clarification_rounds >= 2:
        logger.info("Clarifier: 2+ rounds — forcing proceed")
        return {
            "clarification_needed":   False,
            "clarification_question": None,
            "clarification_field":    None,
            "messages":               [],
            "agent_responses":        [],
        }

    # ── Step 1: Python pre-extraction (fast, no API cost) ─────────────────────
    pre = _pre_extract(messages)
    logger.info(f"Clarifier pre-extract: {pre}")

    # If pre-extraction already found destination from state, we may not need LLM
    existing_dest = collected.get("destination") or state.get("destination")
    pre_duration  = pre.get("trip_duration") or collected.get("trip_duration") or state.get("trip_duration")
    pre_dates     = pre.get("travel_dates") or collected.get("travel_dates") or state.get("travel_dates")
    pre_qtype     = pre.get("query_type", "planning")

    # ── Step 2: LLM extraction for destination + full context ─────────────────
    convo_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in messages[-20:]
    )

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL_ROUTER,
        api_key=settings.OPENAI_API_KEY,
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    # Give the LLM what Python already found so it doesn't contradict it
    pre_context = json.dumps({k: v for k, v in {
        "already_extracted": collected,
        "python_pre_extraction": pre,
        "existing_destination": existing_dest,
    }.items() if v})

    response = await llm.ainvoke([
        SystemMessage(content=CLARIFIER_SYSTEM),
        HumanMessage(content=(
            f"Conversation:\n{convo_text}\n\n"
            f"Context already known: {pre_context}\n\n"
            f"Extract destination and all other travel context from the conversation above."
        )),
    ])

    raw = response.content if isinstance(response.content, str) else "{}"

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Clarifier JSON parse failed — proceeding")
        result = {
            "proceed": True,
            "missing_critical": False,
            "extracted": {},
            "query_type": pre_qtype,
        }

    extracted  = result.get("extracted", {})
    proceed    = result.get("proceed", True)
    question   = result.get("question")
    field      = result.get("missing_field")
    query_type = result.get("query_type", pre_qtype)

    # ── Step 3: Merge — Python pre-extraction wins on duration/dates ──────────
    # LLM is better at destination extraction; Python regex is better at numbers
    if pre_duration and not extracted.get("trip_duration"):
        extracted["trip_duration"] = pre_duration
        logger.info(f"Pre-extract duration override: {pre_duration}")
    if pre_dates and not extracted.get("travel_dates"):
        extracted["travel_dates"] = pre_dates
    if existing_dest and not extracted.get("destination"):
        extracted["destination"] = existing_dest
        # If we have a destination (from state or pre-extraction), always proceed
        proceed = True
        logger.info(f"Destination from state — forcing proceed: {existing_dest}")

    # ── Step 4: Safety override — if destination found anywhere, proceed ───────
    dest = extracted.get("destination") or existing_dest
    if dest and not proceed:
        logger.info(f"Destination known ({dest}) — overriding proceed to True")
        proceed = True
        question = None

    logger.info(
        f"Clarifier: type={query_type} proceed={proceed} "
        f"dest={dest} duration={extracted.get('trip_duration')} "
        f"dates={extracted.get('travel_dates')}"
    )

    # ── Step 5: Build state updates ───────────────────────────────────────────
    new_collected = {**collected}
    updates: Dict[str, Any] = {
        "messages":        [],
        "agent_responses": [],
        "collected_info":  new_collected,
    }

    for key in ["destination", "travel_dates", "traveler_origin", "trip_duration", "travel_purpose"]:
        val = extracted.get(key) or state.get(key)
        if val:
            updates[key] = val
            new_collected[key] = val

    if not proceed and question:
        logger.info(f"Clarifier: asking for '{field}' → '{question}'")
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
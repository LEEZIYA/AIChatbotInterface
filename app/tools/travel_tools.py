"""
Travel Tools — AI-powered with web search + microservice integration
---------------------------------------------------------------------
Three-tier tool architecture:

  Tier 1 — Microservice tools (best quality)
    Call a dedicated microservice that uses real APIs + MCP tools.
    Each microservice is independently deployable and scalable.
    Falls back to Tier 2 if unreachable.

  Tier 2 — Web search tools (good quality, always available)
    Call OpenAI with web_search_preview for live internet data.
    Used when microservice is unavailable or not configured.

  Tier 3 — Fallback (minimal, always works)
    Returns a safe minimal response if both tiers fail.
    Prevents agent crashes.

Current microservice integrations:
  RescueAgent  → rescue-agent-api (MCP-powered disruption handling)
  PlannerAgent → planned (real booking APIs)
  AdvisoryAgent → planned (real govt advisory feed)
"""

from langchain_core.tools import tool
from typing import Dict, Any, Optional
import logging
import json
import asyncio
import httpx
from openai import OpenAI
from app.config import settings

logger = logging.getLogger("travelbuddy.tools")

_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def _search_ai(prompt: str) -> str:
    """Tier 2: OpenAI call with web search. Returns response text."""
    client = get_client()
    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            tools=[{"type": "web_search_preview"}],
            input=prompt,
        )
        for block in response.output:
            if hasattr(block, "content"):
                for item in block.content:
                    if hasattr(item, "text"):
                        return item.text
        return ""
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return ""


def _parse_json(raw: str, fallback: Dict) -> Dict:
    """Extract JSON from AI response with aggressive recovery, return fallback only if all attempts fail."""
    if not raw or not raw.strip():
        logger.warning("_parse_json: empty response")
        return fallback

    attempts = [raw]

    # Strip markdown fences
    if "```json" in raw:
        attempts.append(raw.split("```json")[1].split("```")[0])
    if "```" in raw:
        attempts.append(raw.split("```")[1].split("```")[0])

    # Find outermost JSON object using brace matching
    start = raw.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(raw[start:], start):
            if ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    attempts.append(raw[start:i+1])
                    break

    for attempt in attempts:
        try:
            result = json.loads(attempt.strip())
            if isinstance(result, dict):
                return result
        except Exception:
            continue

    logger.warning(f"_parse_json: all attempts failed. Raw snippet: {raw[:200]}")
    return fallback


async def _call_microservice(
    url: str,
    payload: Dict,
    fallback: Dict,
    service_name: str = "microservice"
) -> Dict:
    """
    Generic microservice caller with fallback.
    Returns fallback dict if service is unreachable or returns an error.
    """
    if not url:
        logger.info(f"{service_name}: URL not configured — using web search fallback")
        return fallback

    try:
        async with httpx.AsyncClient(timeout=settings.MICROSERVICE_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info(f"{service_name}: success")
            return data
    except httpx.ConnectError:
        logger.warning(f"{service_name}: not reachable at {url} — falling back to web search")
        return fallback
    except httpx.TimeoutException:
        logger.warning(f"{service_name}: timeout after {settings.MICROSERVICE_TIMEOUT}s — falling back")
        return fallback
    except Exception as e:
        logger.error(f"{service_name}: error — {e}")
        return fallback


# ═══════════════════════════════════════════════════════════════════════════════
# PLANNER TOOLS
# Improvement: planner_agent_url reserved for real booking API integration
# Currently: web search via OpenAI
# Future: connect to Amadeus / Skyscanner / Booking.com API microservice
# ═══════════════════════════════════════════════════════════════════════════════

@tool
def build_itinerary(destination: str, duration_days: int, travel_dates: str = "", interests: str = "general") -> Dict[str, Any]:
    """Build a detailed day-by-day itinerary with specific named places using OpenAI."""
    logger.info(f"Tool: build_itinerary({destination}, {duration_days} days, {travel_dates})")
    date_ctx = f"in {travel_dates}" if travel_dates else ""
    client = get_client()

    # Build a rich prompt that forces ALL days and specific places
    system = (
        "You are a world-class travel planner. "
        "You know specific restaurants, temples, markets, and attractions in every city. "
        "Always name real, specific places — never generic descriptions. "
        "Respond ONLY with valid JSON, no markdown fences, no extra text."
    )

    user = f"""Create a detailed {duration_days}-day itinerary for {destination} {date_ctx}.

Return ONLY this JSON structure with ALL {duration_days} days filled in:
{{
  "destination": "{destination}",
  "duration_days": {duration_days},
  "itinerary": [
    {{
      "day": 1,
      "items": [
        {{"time": "08:30", "activity": "Specific named place — tip or detail"}},
        {{"time": "12:00", "activity": "Lunch at Specific Restaurant Name — dish to order"}},
        {{"time": "14:00", "activity": "Specific Attraction Name — what to do there"}},
        {{"time": "19:00", "activity": "Dinner area or restaurant — what to try"}}
      ]
    }},
    {{
      "day": 2,
      "items": [...]
    }}
    ... continue for ALL {duration_days} days
  ]
}}

CRITICAL RULES:
- You MUST include all {duration_days} days in the itinerary array
- Each day MUST have 4-6 specific activities with real place names
- NEVER use placeholder text like "Day X" or "Explore [destination]"
- Name specific temples, markets, restaurants, neighbourhoods
- Spread across different areas of {destination} across the days
- Include practical tips: opening hours, booking advice, transport
- For {destination} {date_ctx}, include seasonal events or festivals if relevant
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature=0.7,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        logger.info(f"build_itinerary: got {len(raw)} chars from gpt-4o")
    except Exception as e:
        logger.error(f"build_itinerary gpt-4o failed: {e} — trying web search")
        raw = _search_ai(f"Best {duration_days}-day itinerary for {destination} {date_ctx} with specific places and restaurants. Return as JSON.")

    fallback = {
        "destination": destination,
        "duration_days": duration_days,
        "itinerary": [
            {"day": i+1, "items": [
                {"time": "09:00", "activity": f"Morning exploration — Day {i+1}"},
                {"time": "12:00", "activity": "Lunch at local restaurant"},
                {"time": "14:00", "activity": "Afternoon sightseeing"},
                {"time": "19:00", "activity": "Dinner and evening"},
            ]} for i in range(duration_days)
        ]
    }

    result = _parse_json(raw, fallback)

    # Validate — ensure we have all requested days
    itinerary = result.get("itinerary", [])
    if len(itinerary) < duration_days:
        logger.warning(f"build_itinerary: only got {len(itinerary)} days, expected {duration_days}")
        # Pad missing days with reasonable placeholders
        existing_days = {d["day"] for d in itinerary}
        for day_num in range(1, duration_days + 1):
            if day_num not in existing_days:
                itinerary.append({"day": day_num, "items": [
                    {"time": "09:00", "activity": f"Free exploration of {destination} — Day {day_num}"},
                    {"time": "13:00", "activity": "Lunch at a local restaurant"},
                    {"time": "15:00", "activity": "Visit a local attraction"},
                    {"time": "19:00", "activity": "Dinner at a recommended spot"},
                ]})
        itinerary.sort(key=lambda d: d["day"])
        result["itinerary"] = itinerary

    logger.info(f"build_itinerary: returning {len(result.get('itinerary',[]))} days")
    return result


@tool
def search_flights(origin: str, destination: str, date: str) -> Dict[str, Any]:
    """Search for flight options and current prices between two cities."""
    logger.info(f"Tool: search_flights({origin} → {destination})")
    prompt = f"""Search the web for flights from {origin} to {destination} around {date}.
Return ONLY JSON:
{{
  "origin": "{origin}", "destination": "{destination}", "date": "{date}",
  "options": [
    {{"airline": "Name", "departure": "HH:MM", "arrival": "HH:MM", "price": "SGD XXX", "duration": "Xhr Xmin", "notes": "direct or stopover"}}
  ],
  "tips": "Current booking advice"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"origin": origin, "destination": destination, "date": date, "options": [], "tips": "Check Google Flights."})


@tool
def search_hotels(destination: str, checkin: str, checkout: str, budget: str = "mid-range") -> Dict[str, Any]:
    """Find recommended hotels with current prices and reviews."""
    logger.info(f"Tool: search_hotels({destination}, {budget})")
    prompt = f"""Search for best {budget} hotels in {destination} for {checkin} to {checkout}.
Return ONLY JSON:
{{
  "destination": "{destination}",
  "hotels": [
    {{"name": "Hotel", "stars": 4, "price_per_night": "SGD XXX", "area": "Neighbourhood", "rating": 8.9, "why": "What makes it special"}}
  ],
  "tip": "Booking advice"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "hotels": [], "tip": "Check Booking.com."})


# ═══════════════════════════════════════════════════════════════════════════════
# WEATHER TOOLS
# Improvement: could connect to OpenWeatherMap or WeatherAPI microservice
# for structured real-time forecast data with exact temperatures and alerts.
# Currently: web search provides good quality forecasts.
# Future enhancement: dedicated weather microservice with push alerts
# ═══════════════════════════════════════════════════════════════════════════════

@tool
def get_weather_forecast(city: str, travel_month: str = "") -> Dict[str, Any]:
    """Get weather forecast and seasonal information using live web search."""
    logger.info(f"Tool: get_weather_forecast({city}, {travel_month})")
    month_ctx = f"in {travel_month}" if travel_month else "currently"
    prompt = f"""Search for weather in {city} {month_ctx} for tourists.
Return ONLY JSON:
{{
  "city": "{city}",
  "forecast": [
    {{"day": "Mon", "icon": "sunny", "temp": "24C", "desc": "Partly cloudy"}},
    {{"day": "Tue", "icon": "rain", "temp": "21C", "desc": "Rain expected"}},
    {{"day": "Wed", "icon": "sunny", "temp": "26C", "desc": "Sunny"}},
    {{"day": "Thu", "icon": "cloudy", "temp": "25C", "desc": "Partly cloudy"}},
    {{"day": "Fri", "icon": "overcast", "temp": "23C", "desc": "Overcast"}}
  ],
  "seasonal_summary": "What weather is like this time of year",
  "packing_tips": ["tip 1", "tip 2", "tip 3"]
}}
CRITICAL: For the icon field use ONLY these exact plain text strings, no emoji, no symbols:
sunny, cloudy, overcast, rain, storm, snow
For temp use format like 24C or 24°C — no emoji, plain text only."""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"city": city, "forecast": [], "seasonal_summary": f"Check weather.com for {city}.", "packing_tips": []})


@tool
def get_seasonal_info(destination: str, month: str) -> Dict[str, Any]:
    """Get seasonal climate information and packing advice."""
    logger.info(f"Tool: get_seasonal_info({destination}, {month})")
    prompt = f"""Search for what {destination} is like for tourists in {month}.
Return ONLY JSON:
{{
  "destination": "{destination}", "month": "{month}",
  "climate": "Climate description",
  "avg_temp_high": "XX°C", "avg_temp_low": "XX°C",
  "packing_tips": ["tip 1", "tip 2", "tip 3"],
  "best_for": "Best activities this month",
  "avoid": "Risks or crowds to be aware of",
  "events": "Festivals or events this month"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "month": month, "climate": "Check local sources", "packing_tips": []})


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVITIES TOOLS
# Improvement: could integrate with TripAdvisor, Google Places, or Viator API
# for structured activity data with live availability and booking links.
# Currently: web search returns good quality recommendations.
# Future: dedicated experiences microservice with real-time availability
# ═══════════════════════════════════════════════════════════════════════════════

@tool
def search_activities(destination: str, duration_days: int = 3, interests: str = "general") -> Dict[str, Any]:
    """Find top-rated activities and attractions with current info."""
    logger.info(f"Tool: search_activities({destination})")
    prompt = f"""Search for the best things to do in {destination} right now.
Return ONLY JSON:
{{
  "destination": "{destination}",
  "highlights": [
    {{"name": "Place Name", "type": "Cultural/Food/Nature/Experience", "duration": "2-3 hrs", "cost": "Free or SGD XX", "rating": 4.8, "tip": "Insider tip"}}
  ]
}}
Include 6-8 specific real attractions. Mix must-sees with hidden gems."""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "highlights": []})


@tool
def search_restaurants(destination: str, cuisine: str = "local") -> Dict[str, Any]:
    """Find top restaurants with current recommendations."""
    logger.info(f"Tool: search_restaurants({destination})")
    prompt = f"""Search for the best {cuisine} restaurants in {destination} right now.
Return ONLY JSON:
{{
  "destination": "{destination}",
  "restaurants": [
    {{"name": "Name", "type": "Cuisine", "price": "$$$", "rating": 4.8, "must_try": "Specific dish", "area": "Neighbourhood", "tip": "Reservation needed?"}}
  ]
}}
Include 5 real restaurants from street food to fine dining."""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "restaurants": []})


# ═══════════════════════════════════════════════════════════════════════════════
# ADVISORY TOOLS
# Improvement: could connect to a govt advisory feed microservice that monitors
# US State Dept, UK FCO, DFAT in real-time with webhook push updates.
# Currently: web search with explicit source citations.
# Future: dedicated advisory microservice with structured govt data feeds
# ═══════════════════════════════════════════════════════════════════════════════

@tool
def get_travel_advisory(destination: str) -> Dict[str, Any]:
    """Get current official travel safety advisory from government sources."""
    logger.info(f"Tool: get_travel_advisory({destination})")
    prompt = f"""Search for current official travel advisory for {destination}.
Check: US State Dept (travel.state.gov), UK FCO (gov.uk/foreign-travel-advice), Australian DFAT (smartraveller.gov.au).
Return ONLY JSON:
{{
  "destination": "{destination}",
  "risk_level": "LOW or MEDIUM or HIGH or CRITICAL",
  "summary": "Current safety situation in 1-2 sentences",
  "hazards": [
    {{"type": "Natural Disaster or Political or Health or Crime", "level": "LOW or MEDIUM or HIGH", "detail": "Specific current risk"}}
  ],
  "sources": [
    {{"name": "US State Department", "type": "Government", "url": "travel.state.gov", "updated": "date"}},
    {{"name": "UK FCO", "type": "Government", "url": "gov.uk/foreign-travel-advice", "updated": "date"}}
  ]
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "risk_level": "LOW", "summary": "Check official travel advisories.", "hazards": [], "sources": []})


@tool
def get_visa_requirements(destination: str, passport_country: str = "Singapore") -> Dict[str, Any]:
    """Get current visa requirements from official immigration sources."""
    logger.info(f"Tool: get_visa_requirements({destination}, {passport_country})")
    prompt = f"""Search for current visa requirements for {passport_country} passport holders visiting {destination}.
Check official immigration or embassy website.
Return ONLY JSON:
{{
  "destination": "{destination}", "passport": "{passport_country}",
  "requirement": "Visa Free or Visa on Arrival or eVisa or Visa Required",
  "max_stay": "XX days", "details": "Requirements and how to apply",
  "fee": "Amount or Free", "source": "Official source", "source_url": "URL", "updated": "Date"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "passport": passport_country, "requirement": "Check embassy", "details": "Verify with official authority.", "source": "Embassy website", "updated": "Verify current"})


@tool
def get_vaccine_requirements(destination: str) -> Dict[str, Any]:
    """Get current vaccination requirements from WHO and CDC."""
    logger.info(f"Tool: get_vaccine_requirements({destination})")
    prompt = f"""Search for current vaccination requirements for {destination} from WHO and CDC.
Return ONLY JSON:
{{
  "destination": "{destination}",
  "mandatory": [{{"name": "Vaccine", "requirement": "Mandatory", "notes": "When required", "source": "WHO"}}],
  "recommended": [{{"name": "Vaccine", "requirement": "Recommended", "notes": "Why", "source": "CDC"}}],
  "sources": [
    {{"name": "WHO International Travel Health", "type": "WHO", "updated": "date"}},
    {{"name": "CDC Travelers Health", "type": "CDC", "updated": "date"}}
  ]
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "mandatory": [], "recommended": [], "sources": []})


@tool
def get_local_laws(destination: str) -> Dict[str, Any]:
    """Get important local laws and customs travellers must know."""
    logger.info(f"Tool: get_local_laws({destination})")
    prompt = f"""Search for local laws and customs tourists must know in {destination}.
Return ONLY JSON:
{{
  "destination": "{destination}",
  "rules": ["🚭 Specific law", "💊 Another rule", "📸 Photography rule"],
  "emergency_number": "local number",
  "source": "Source", "updated": "Date"
}}
Include 6-8 specific rules important for tourists."""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "rules": [], "emergency_number": "112", "source": "Embassy", "updated": "Verify"})


# ═══════════════════════════════════════════════════════════════════════════════
# RESCUE TOOLS — MCP MICROSERVICE INTEGRATION
#
# Primary:  rescue-agent-api microservice (MCP-powered, real flight/weather data)
#           From: github.com/LEEZIYA/AIChatbotInterface/tree/rescue_agent
#           Handles: FLIGHT_DELAY, FLIGHT_CANCELLATION, SEVERE_WEATHER,
#                    NATURAL_DISASTER, SECURITY_ALERT, TRANSPORT_STRIKE
#           Returns: ranked solutions (REBOOKING, ACCEPT_DELAY,
#                    ALTERNATIVE_ROUTE, MANUAL_ESCALATION)
#
# Fallback: web search (if microservice unreachable)
# ═══════════════════════════════════════════════════════════════════════════════

@tool
async def handle_disruption(
    destination: str,
    disruption_type: str = "FLIGHT_DELAY",
    flight_number: str = "",
    delay_duration: int = 60,
    description: str = ""
) -> Dict[str, Any]:
    """
    Handle a travel disruption using the MCP-powered Rescue Agent microservice.
    Detects disruption type, generates ranked solutions (rebooking, alternative routes, etc.)
    Falls back to web search if the microservice is unavailable.

    disruption_type options: FLIGHT_DELAY, FLIGHT_CANCELLATION, SEVERE_WEATHER,
                             NATURAL_DISASTER, SECURITY_ALERT, TRANSPORT_STRIKE
    """
    logger.info(f"Tool: handle_disruption({destination}, {disruption_type}) → rescue-agent-api")

    # Build the rescue agent API payload
    # Matches the API contract from rescue_agent branch README
    payload = {
        "event": {
            "id": f"evt_{destination[:3].lower()}_{disruption_type[:3].lower()}",
            "type": disruption_type,
            "flight_number": flight_number or "UNKNOWN",
            "delay_duration": delay_duration,
            "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
            "description": description or f"{disruption_type.replace('_',' ').title()} affecting travel in {destination}",
        },
        "itinerary": {
            "destination": destination,
            "origin": "Singapore",
        },
        "user_preferences": {
            "priority": "time",    # time | cost | convenience
            "budget": "medium"     # low | medium | high
        }
    }

    # Web search fallback response
    web_fallback = _get_disruption_web_fallback(destination, disruption_type)

    # Try microservice first (Tier 1)
    result = await _call_microservice(
        url=f"{settings.RESCUE_AGENT_URL}/api/handle-disruption",
        payload=payload,
        fallback=None,   # None signals to try web search next
        service_name="rescue-agent-api"
    )

    if result is not None:
        return result

    # Tier 2: web search fallback
    logger.info(f"handle_disruption: using web search fallback for {destination}")
    return web_fallback


def _get_disruption_web_fallback(destination: str, disruption_type: str) -> Dict[str, Any]:
    """Web search fallback when rescue microservice is unavailable."""
    prompt = f"""Search for how to handle a {disruption_type.replace('_',' ').lower()} in {destination}.
Return ONLY JSON:
{{
  "success": true,
  "solutions": [
    {{"strategy": "REBOOKING", "description": "Contact airline for next available flight", "cost_impact": 0, "time_impact": 120, "confidence": 0.8, "pros": ["Gets you moving"], "cons": ["May have wait time"]}},
    {{"strategy": "ACCEPT_DELAY", "description": "Wait at airport with compensation", "cost_impact": -50, "time_impact": 180, "confidence": 0.9, "pros": ["No extra cost", "Airline covers meals"], "cons": ["Long wait"]}},
    {{"strategy": "MANUAL_ESCALATION", "description": "Speak to airline desk supervisor", "cost_impact": 0, "time_impact": 60, "confidence": 0.7, "pros": ["Personal service"], "cons": ["Queue time"]}}
  ],
  "disruption_type": "{disruption_type}",
  "destination": "{destination}"
}}"""
    raw = _search_ai(prompt)
    fallback = {
        "success": True,
        "solutions": [
            {"strategy": "MANUAL_ESCALATION", "description": f"Contact airline or local authorities in {destination}",
             "cost_impact": 0, "time_impact": 60, "confidence": 0.7,
             "pros": ["Direct human assistance"], "cons": ["May involve queuing"]}
        ],
        "disruption_type": disruption_type,
        "destination": destination
    }
    return _parse_json(raw, fallback)


@tool
async def get_emergency_contacts(destination: str) -> Dict[str, Any]:
    """
    Get emergency contact numbers and hospitals.
    Tries rescue-agent-api first, falls back to web search.
    """
    logger.info(f"Tool: get_emergency_contacts({destination})")

    # Try microservice health endpoint to see if it's up
    fallback = _get_emergency_web_search(destination)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            health = await client.get(f"{settings.RESCUE_AGENT_URL}/health")
            if health.status_code == 200:
                # Microservice is up — use it for emergency data too
                # The rescue agent handles emergency queries via disruption endpoint
                logger.info("rescue-agent-api is healthy — using web search for emergency contacts")
    except Exception:
        logger.info("rescue-agent-api not available — using web search for emergency contacts")

    return _get_emergency_web_search(destination)


def _get_emergency_web_search(destination: str) -> Dict[str, Any]:
    """Web search for emergency contacts."""
    prompt = f"""Search for verified emergency contact numbers in {destination} for tourists.
Return ONLY JSON:
{{
  "destination": "{destination}",
  "emergency_numbers": [
    {{"service": "Police", "number": "XXX"}},
    {{"service": "Ambulance", "number": "XXX"}},
    {{"service": "Fire", "number": "XXX"}},
    {{"service": "Tourist Police", "number": "XXX"}},
    {{"service": "General Emergency", "number": "XXX"}}
  ],
  "hospitals": [
    {{"name": "Hospital Name", "type": "International/Private", "phone": "+XX", "address": "Area", "english_speaking": true}}
  ],
  "travel_insurance_tip": "Specific advice for {destination}"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {
        "destination": destination,
        "emergency_numbers": [{"service": "General Emergency", "number": "112"}],
        "hospitals": [],
        "travel_insurance_tip": "Always carry travel insurance."
    })


@tool
async def get_nearest_hospital(destination: str, area: str = "city centre") -> Dict[str, Any]:
    """Find hospitals and clinics in a specific area."""
    logger.info(f"Tool: get_nearest_hospital({destination}, {area})")
    prompt = f"""Search for hospitals and international clinics in {area}, {destination} for tourists.
Return ONLY JSON:
{{
  "destination": "{destination}", "area": "{area}",
  "facilities": [
    {{"name": "Name", "distance": "X km", "open": "24/7", "english_speaking": true, "phone": "+XX"}}
  ]
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "area": area, "facilities": []})


# ── Tool registries ────────────────────────────────────────────────────────────
# Each agent only has access to tools relevant to its role

PLANNER_TOOLS    = [search_flights, search_hotels, build_itinerary]
WEATHER_TOOLS    = [get_weather_forecast, get_seasonal_info]
ACTIVITIES_TOOLS = [search_activities, search_restaurants]
ADVISORY_TOOLS   = [get_travel_advisory, get_visa_requirements, get_vaccine_requirements, get_local_laws]
RESCUE_TOOLS     = [handle_disruption, get_emergency_contacts, get_nearest_hospital]
ALL_TOOLS        = PLANNER_TOOLS + WEATHER_TOOLS + ACTIVITIES_TOOLS + ADVISORY_TOOLS + RESCUE_TOOLS
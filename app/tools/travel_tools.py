"""
Travel Tools — travelbuddy v4
--------------------------
All tools use OpenAI web search (Responses API) with chat completions fallback.
build_itinerary removed — synthesiser generates itinerary from agent data.
"""

from langchain_core.tools import tool
from typing import Dict, Any
import logging
import json
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
    """Call OpenAI with web search. Falls back to chat completions on 429/error."""
    client = get_client()

    if settings.ENABLE_WEB_SEARCH:
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
        except Exception as e:
            logger.warning(f"Web search failed ({e}) — falling back to chat completions")

    # Fallback: standard chat completions (no web search, lower cost)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a travel expert. Answer based on your knowledge. Return JSON as instructed."},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1200,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"Chat completions fallback failed: {e}")
        return ""


def _parse_json(raw: str, fallback: Dict) -> Dict:
    """Extract JSON with aggressive recovery."""
    if not raw or not raw.strip():
        return fallback

    attempts = [raw]
    if "```json" in raw:
        attempts.append(raw.split("```json")[1].split("```")[0])
    if "```" in raw:
        attempts.append(raw.split("```")[1].split("```")[0])
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

    logger.warning(f"JSON parse failed. Snippet: {raw[:150]}")
    return fallback


# ── TRANSPORT TOOLS ────────────────────────────────────────────────────────────

@tool
def search_flights(origin: str, destination: str, date: str) -> Dict[str, Any]:
    """Search for flight options and current prices between two cities."""
    logger.info(f"Tool: search_flights({origin} → {destination})")
    prompt = f"""Search for flights from {origin} to {destination} around {date}.
Return ONLY JSON:
{{
  "origin": "{origin}", "destination": "{destination}", "date": "{date}",
  "options": [
    {{"airline": "Name", "departure": "HH:MM", "arrival": "HH:MM",
      "price": "SGD XXX", "duration": "Xhr Xmin", "notes": "direct or stopover"}}
  ],
  "tips": "Booking advice and cheapest days to fly"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"origin": origin, "destination": destination,
                             "date": date, "options": [], "tips": "Check Google Flights."})


@tool
def search_trains_buses(origin: str, destination: str) -> Dict[str, Any]:
    """Search for train and bus options between two places."""
    logger.info(f"Tool: search_trains_buses({origin} → {destination})")
    prompt = f"""Search for train and bus options from {origin} to {destination}.
Return ONLY JSON:
{{
  "options": [
    {{"type": "Train/Bus/Ferry", "operator": "Name", "duration": "Xhr",
      "price": "SGD XX", "frequency": "Every X hours", "notes": "booking tip"}}
  ],
  "recommended": "Best option and why",
  "tips": "Practical transport advice"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"options": [], "recommended": "", "tips": ""})


@tool
def get_local_transport(destination: str) -> Dict[str, Any]:
    """Get local transport options within a destination."""
    logger.info(f"Tool: get_local_transport({destination})")
    prompt = f"""Search for local transport in {destination} for tourists.
Return ONLY JSON:
{{
  "options": [
    {{"type": "Metro/Bus/Taxi/Rideshare", "name": "Service name",
      "cost": "Approx cost", "coverage": "Where it goes", "tip": "Practical tip"}}
  ],
  "best_for": "Which transport for which situation",
  "tourist_passes": "Any tourist transport passes",
  "apps": "Useful transport apps"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"options": [], "best_for": "", "tourist_passes": "", "apps": ""})


@tool
def get_airport_transfer(destination: str) -> Dict[str, Any]:
    """Get airport to city transfer options."""
    logger.info(f"Tool: get_airport_transfer({destination})")
    prompt = f"""Search for airport transfer options in {destination}.
Return ONLY JSON:
{{
  "options": [
    {{"type": "Train/Bus/Taxi/Private", "name": "Service",
      "duration": "Xmin", "price": "SGD XX", "tip": "Booking advice"}}
  ],
  "recommended": "Best option for most travellers"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"options": [], "recommended": ""})


# ── ACCOMMODATION TOOLS ────────────────────────────────────────────────────────

@tool
def search_hotels(destination: str, checkin: str, checkout: str,
                  budget: str = "mid-range") -> Dict[str, Any]:
    """Find recommended hotels with current prices and reviews."""
    logger.info(f"Tool: search_hotels({destination}, {budget})")
    prompt = f"""Search for {budget} hotels in {destination} for {checkin} to {checkout}.
Return ONLY JSON:
{{
  "destination": "{destination}",
  "hotels": [
    {{"name": "Hotel Name", "stars": 4, "price_per_night": "SGD XXX",
      "area": "Neighbourhood", "rating": 8.9,
      "why": "What makes it special", "near": "What it is close to"}}
  ],
  "best_areas": "Best neighbourhoods and why",
  "tip": "Booking advice"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "hotels": [],
                             "best_areas": "", "tip": "Check Booking.com."})


@tool
def get_best_areas_to_stay(destination: str, interests: str = "general") -> Dict[str, Any]:
    """Get neighbourhood guide for where to stay."""
    logger.info(f"Tool: get_best_areas_to_stay({destination})")
    prompt = f"""Search for best neighbourhoods to stay in {destination} for tourists.
Return ONLY JSON:
{{
  "areas": [
    {{"name": "Neighbourhood", "vibe": "Character", "best_for": "Type of traveller",
      "price_range": "Budget/Mid/Luxury", "pros": "Advantages",
      "cons": "Downsides", "transport": "Transport links"}}
  ],
  "summary": "Overall recommendation"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"areas": [], "summary": ""})


@tool
def search_alternative_accommodation(destination: str,
                                      budget: str = "mid-range") -> Dict[str, Any]:
    """Search for hostels, Airbnb and unique stays."""
    logger.info(f"Tool: search_alternative_accommodation({destination})")
    prompt = f"""Search for non-hotel accommodation in {destination} for {budget} budget.
Return ONLY JSON:
{{
  "options": [
    {{"type": "Hostel/Airbnb/Guesthouse", "name": "Example",
      "price_range": "SGD XX-XX per night", "area": "Location",
      "best_for": "Who this suits"}}
  ],
  "tip": "Booking advice"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"options": [], "tip": ""})


# ── WEATHER TOOLS ──────────────────────────────────────────────────────────────

@tool
def get_weather_forecast(city: str, travel_month: str = "") -> Dict[str, Any]:
    """Get weather forecast and seasonal information."""
    logger.info(f"Tool: get_weather_forecast({city}, {travel_month})")
    month_ctx = f"in {travel_month}" if travel_month else "currently"
    prompt = f"""Search for weather in {city} {month_ctx} for tourists.
Return ONLY JSON:
{{
  "city": "{city}",
  "forecast": [
    {{"day": "Mon", "icon": "sunny", "temp": "28C", "desc": "Hot and sunny"}},
    {{"day": "Tue", "icon": "rain",  "temp": "26C", "desc": "Afternoon showers"}},
    {{"day": "Wed", "icon": "cloudy","temp": "27C", "desc": "Partly cloudy"}},
    {{"day": "Thu", "icon": "sunny", "temp": "29C", "desc": "Hot and clear"}},
    {{"day": "Fri", "icon": "rain",  "temp": "25C", "desc": "Rainy"}}
  ],
  "seasonal_summary": "What weather is like this time of year",
  "packing_tips": ["tip 1", "tip 2", "tip 3"]
}}
For icon use only: sunny, cloudy, overcast, rain, storm, snow — plain text, no emoji.
For temp use: 28C format — plain text only."""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"city": city, "forecast": [],
                             "seasonal_summary": "", "packing_tips": []})


@tool
def get_seasonal_info(destination: str, month: str) -> Dict[str, Any]:
    """Get seasonal climate information and travel advice."""
    logger.info(f"Tool: get_seasonal_info({destination}, {month})")
    prompt = f"""Search for what {destination} is like for tourists in {month}.
Return ONLY JSON:
{{
  "destination": "{destination}", "month": "{month}",
  "climate": "Description",
  "avg_temp_high": "XXC", "avg_temp_low": "XXC",
  "packing_tips": ["tip 1", "tip 2"],
  "best_for": "Best activities this month",
  "events": "Festivals or events this month"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "month": month,
                             "climate": "", "packing_tips": []})


# ── ACTIVITIES TOOLS ───────────────────────────────────────────────────────────

@tool
def search_activities(destination: str, duration_days: int = 3,
                       interests: str = "general") -> Dict[str, Any]:
    """Find top-rated activities and attractions."""
    logger.info(f"Tool: search_activities({destination})")
    prompt = f"""Search for best things to do in {destination} for tourists.
Return ONLY JSON:
{{
  "destination": "{destination}",
  "highlights": [
    {{"name": "Place Name", "type": "Cultural/Food/Nature",
      "duration": "2-3 hrs", "cost": "Free or SGD XX",
      "rating": 4.8, "tip": "Insider tip", "area": "Neighbourhood"}}
  ]
}}
Include 6-8 specific real attractions mixing must-sees and hidden gems."""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "highlights": []})


@tool
def search_restaurants(destination: str, cuisine: str = "local") -> Dict[str, Any]:
    """Find top restaurants with current recommendations."""
    logger.info(f"Tool: search_restaurants({destination})")
    prompt = f"""Search for best {cuisine} restaurants in {destination} right now.
Return ONLY JSON:
{{
  "destination": "{destination}",
  "restaurants": [
    {{"name": "Name", "type": "Cuisine", "price": "$$",
      "rating": 4.8, "must_try": "Specific dish",
      "area": "Neighbourhood", "tip": "Reservation needed?"}}
  ]
}}
Include 5 real restaurants from street food to fine dining."""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "restaurants": []})


# ── ADVISORY TOOLS ─────────────────────────────────────────────────────────────

@tool
def get_travel_advisory(destination: str) -> Dict[str, Any]:
    """Get current official travel safety advisory."""
    logger.info(f"Tool: get_travel_advisory({destination})")
    prompt = f"""Search for current official travel advisory for {destination} from US State Dept, UK FCO, Australian DFAT.
Return ONLY JSON:
{{
  "destination": "{destination}",
  "risk_level": "LOW or MEDIUM or HIGH or CRITICAL",
  "summary": "Current safety situation",
  "hazards": [
    {{"type": "Natural/Political/Health/Crime", "level": "LOW/MEDIUM/HIGH", "detail": "Specific risk"}}
  ],
  "sources": [
    {{"name": "US State Department", "type": "Government", "updated": "date"}}
  ]
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "risk_level": "LOW",
                             "summary": "Check official advisories.", "hazards": [], "sources": []})


@tool
def get_visa_requirements(destination: str,
                           passport_country: str = "Singapore") -> Dict[str, Any]:
    """Get current visa requirements for a passport holder."""
    logger.info(f"Tool: get_visa_requirements({destination}, {passport_country})")
    prompt = f"""Search for current visa requirements for {passport_country} passport holders visiting {destination}.
Return ONLY JSON:
{{
  "destination": "{destination}", "passport": "{passport_country}",
  "requirement": "Visa Free or Visa on Arrival or eVisa or Visa Required",
  "max_stay": "XX days", "details": "How to apply",
  "fee": "Amount or Free", "source": "Official source", "updated": "Date"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "passport": passport_country,
                             "requirement": "Check embassy", "details": "", "source": ""})


@tool
def get_vaccine_requirements(destination: str) -> Dict[str, Any]:
    """Get current vaccination requirements from WHO and CDC."""
    logger.info(f"Tool: get_vaccine_requirements({destination})")
    prompt = f"""Search for vaccination requirements for {destination} from WHO and CDC.
Return ONLY JSON:
{{
  "destination": "{destination}",
  "mandatory": [{{"name": "Vaccine", "requirement": "Mandatory", "notes": "When required", "source": "WHO"}}],
  "recommended": [{{"name": "Vaccine", "requirement": "Recommended", "notes": "Why", "source": "CDC"}}],
  "sources": [{{"name": "WHO", "updated": "date"}}, {{"name": "CDC", "updated": "date"}}]
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "mandatory": [],
                             "recommended": [], "sources": []})


@tool
def get_local_laws(destination: str) -> Dict[str, Any]:
    """Get important local laws and customs for travellers."""
    logger.info(f"Tool: get_local_laws({destination})")
    prompt = f"""Search for local laws and customs tourists must know in {destination}.
Return ONLY JSON:
{{
  "destination": "{destination}",
  "rules": ["Specific law 1", "Specific law 2"],
  "emergency_number": "local number",
  "source": "Source", "updated": "Date"
}}
Include 5-6 specific rules important for tourists."""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "rules": [],
                             "emergency_number": "112", "source": ""})


# ── RESCUE TOOLS ───────────────────────────────────────────────────────────────

@tool
async def get_emergency_contacts(destination: str) -> Dict[str, Any]:
    """Get verified emergency contact numbers and hospitals."""
    logger.info(f"Tool: get_emergency_contacts({destination})")
    prompt = f"""Search for emergency contacts in {destination} for tourists.
Return ONLY JSON:
{{
  "destination": "{destination}",
  "emergency_numbers": [
    {{"service": "Police", "number": "XXX"}},
    {{"service": "Ambulance", "number": "XXX"}},
    {{"service": "Tourist Police", "number": "XXX"}},
    {{"service": "General Emergency", "number": "XXX"}}
  ],
  "hospitals": [
    {{"name": "Hospital Name", "type": "International/Private",
      "phone": "+XX", "address": "Area", "english_speaking": true}}
  ],
  "travel_insurance_tip": "Advice for {destination}"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {
        "destination": destination,
        "emergency_numbers": [{"service": "General Emergency", "number": "112"}],
        "hospitals": [],
        "travel_insurance_tip": "Always carry travel insurance.",
    })


@tool
async def get_nearest_hospital(destination: str, area: str = "city centre") -> Dict[str, Any]:
    """Find hospitals and clinics in a specific area."""
    logger.info(f"Tool: get_nearest_hospital({destination}, {area})")
    prompt = f"""Search for hospitals in {area}, {destination} for tourists.
Return ONLY JSON:
{{
  "destination": "{destination}", "area": "{area}",
  "facilities": [
    {{"name": "Name", "distance": "X km", "open": "24/7",
      "english_speaking": true, "phone": "+XX"}}
  ]
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "area": area, "facilities": []})


@tool
async def handle_disruption(destination: str, disruption_type: str = "FLIGHT_DELAY",
                              flight_number: str = "", delay_duration: int = 60,
                              description: str = "") -> Dict[str, Any]:
    """Handle a travel disruption — returns ranked solutions."""
    logger.info(f"Tool: handle_disruption({destination}, {disruption_type})")
    prompt = f"""Search for how to handle a {disruption_type.replace('_',' ').lower()} in {destination}.
Return ONLY JSON:
{{
  "success": true,
  "solutions": [
    {{"strategy": "REBOOKING", "description": "Contact airline for next flight",
      "cost_impact": 0, "time_impact": 120, "confidence": 0.8,
      "pros": ["Gets you moving"], "cons": ["Wait time"]}},
    {{"strategy": "ACCEPT_DELAY", "description": "Wait with compensation",
      "cost_impact": -50, "time_impact": 180, "confidence": 0.9,
      "pros": ["No cost"], "cons": ["Long wait"]}},
    {{"strategy": "MANUAL_ESCALATION", "description": "Speak to airline supervisor",
      "cost_impact": 0, "time_impact": 60, "confidence": 0.7,
      "pros": ["Personal help"], "cons": ["Queue time"]}}
  ],
  "disruption_type": "{disruption_type}",
  "destination": "{destination}"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"success": True, "solutions": [], "destination": destination})


# ── Tool registries ────────────────────────────────────────────────────────────

TRANSPORT_TOOLS     = [search_flights, search_trains_buses,
                        get_local_transport, get_airport_transfer]
ACCOMMODATION_TOOLS = [search_hotels, get_best_areas_to_stay,
                        search_alternative_accommodation]
WEATHER_TOOLS       = [get_weather_forecast, get_seasonal_info]
ACTIVITIES_TOOLS    = [search_activities, search_restaurants]
ADVISORY_TOOLS      = [get_travel_advisory, get_visa_requirements,
                        get_vaccine_requirements, get_local_laws]
RESCUE_TOOLS        = [handle_disruption, get_emergency_contacts, get_nearest_hospital]

ALL_TOOLS = (TRANSPORT_TOOLS + ACCOMMODATION_TOOLS + WEATHER_TOOLS +
             ACTIVITIES_TOOLS + ADVISORY_TOOLS + RESCUE_TOOLS)

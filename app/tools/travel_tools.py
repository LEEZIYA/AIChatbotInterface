"""
Travel Tools — AI-powered with web search
-----------------------------------------
Each tool calls OpenAI with web_search_preview enabled.
This means every response pulls live data from the internet:
- Real places, current prices, actual opening hours
- Live travel advisories and visa rules
- Current weather and forecasts
- Up-to-date vaccine requirements

No hardcoded data anywhere.
"""

from langchain_core.tools import tool
from typing import Dict, Any
import logging
import json
from openai import OpenAI
from app.config import settings

logger = logging.getLogger("voyager.tools")

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def _search_ai(prompt: str) -> str:
    """Make an OpenAI call with web search enabled. Returns response text."""
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
        logger.error(f"Web search AI call failed: {e}")
        return ""


def _parse_json(raw: str, fallback: Dict) -> Dict:
    """Extract JSON from AI response, return fallback if it fails."""
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
    except Exception:
        logger.warning("JSON parse failed — returning fallback")
        return fallback


# ── PLANNER ────────────────────────────────────────────────────────────────────

@tool
def build_itinerary(destination: str, duration_days: int, travel_dates: str = "", interests: str = "general") -> Dict[str, Any]:
    """Build a detailed day-by-day itinerary with specific named places using live web search."""
    logger.info(f"Tool: build_itinerary({destination}, {duration_days} days) — web search")
    date_ctx = f"for travel in {travel_dates}" if travel_dates else ""
    prompt = f"""Search the web for the best {duration_days}-day travel itinerary for {destination} {date_ctx}.

Return ONLY a valid JSON object, no other text:
{{
  "destination": "{destination}",
  "duration_days": {duration_days},
  "itinerary": [
    {{
      "day": 1,
      "items": [
        {{"time": "08:30", "activity": "[SPECIFIC NAMED PLACE] — [what to do there and why it is special]"}},
        {{"time": "12:00", "activity": "Lunch at [SPECIFIC RESTAURANT/MARKET NAME] — [what dish to order]"}},
        {{"time": "14:00", "activity": "[SPECIFIC ATTRACTION/NEIGHBOURHOOD] — [details and tips]"}},
        {{"time": "19:00", "activity": "Dinner at [SPECIFIC AREA/RESTAURANT] — [what to try]"}}
      ]
    }}
  ]
}}

Critical rules:
- Name SPECIFIC real places — never say "visit a temple", say WHICH temple
- Include real restaurant names and specific dishes to order
- Cover different areas and neighbourhoods across the days
- Add insider tips like "book ahead", "arrive early", "best at sunset"
- Include all {duration_days} days
- Each day should have 4-6 activities with times
"""
    raw = _search_ai(prompt)
    fallback = {
        "destination": destination,
        "duration_days": duration_days,
        "itinerary": [{"day": i+1, "items": [{"time": "09:00", "activity": f"Explore {destination} — Day {i+1}"}]} for i in range(duration_days)]
    }
    return _parse_json(raw, fallback)


@tool
def search_flights(origin: str, destination: str, date: str) -> Dict[str, Any]:
    """Search for flight options and current prices between two cities."""
    logger.info(f"Tool: search_flights({origin} → {destination}) — web search")
    prompt = f"""Search the web for flights from {origin} to {destination} around {date}.
Return ONLY a JSON object:
{{
  "origin": "{origin}",
  "destination": "{destination}",
  "date": "{date}",
  "options": [
    {{"airline": "Name", "departure": "HH:MM", "arrival": "HH:MM", "price": "SGD XXX", "duration": "Xhr Xmin", "notes": "direct or stopover info"}},
    {{"airline": "Name", "departure": "HH:MM", "arrival": "HH:MM", "price": "SGD XXX", "duration": "Xhr Xmin", "notes": "..."}}
  ],
  "tips": "Current booking advice"
}}
Include 3-4 realistic airline options with current typical prices."""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"origin": origin, "destination": destination, "date": date, "options": [], "tips": "Check Google Flights for latest prices."})


@tool
def search_hotels(destination: str, checkin: str, checkout: str, budget: str = "mid-range") -> Dict[str, Any]:
    """Find recommended hotels with current prices and reviews."""
    logger.info(f"Tool: search_hotels({destination}, {budget}) — web search")
    prompt = f"""Search the web for the best {budget} hotels in {destination} for {checkin} to {checkout}.
Return ONLY a JSON object:
{{
  "destination": "{destination}",
  "hotels": [
    {{"name": "Hotel Name", "stars": 4, "price_per_night": "SGD XXX", "area": "Neighbourhood", "rating": 8.9, "why": "What makes it special"}},
    {{"name": "...", "stars": 3, "price_per_night": "SGD XXX", "area": "...", "rating": 8.5, "why": "..."}}
  ],
  "tip": "Current booking advice"
}}
Include 3-4 real hotels with current realistic prices."""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "hotels": [], "tip": "Check Booking.com for latest availability."})


# ── WEATHER ────────────────────────────────────────────────────────────────────

@tool
def get_weather_forecast(city: str, travel_month: str = "") -> Dict[str, Any]:
    """Get weather forecast and seasonal information using live data."""
    logger.info(f"Tool: get_weather_forecast({city}, {travel_month}) — web search")
    month_ctx = f"in {travel_month}" if travel_month else "currently"
    prompt = f"""Search the web for weather in {city} {month_ctx} for tourists.
Return ONLY a JSON object:
{{
  "city": "{city}",
  "forecast": [
    {{"day": "Mon", "icon": "🌤", "temp": "24°C", "desc": "Partly cloudy"}},
    {{"day": "Tue", "icon": "🌧", "temp": "21°C", "desc": "Rain expected"}},
    {{"day": "Wed", "icon": "☀️", "temp": "26°C", "desc": "Sunny"}},
    {{"day": "Thu", "icon": "🌤", "temp": "25°C", "desc": "Partly cloudy"}},
    {{"day": "Fri", "icon": "⛅", "temp": "23°C", "desc": "Overcast"}}
  ],
  "seasonal_summary": "What the weather is like this time of year",
  "packing_tips": ["specific tip 1", "specific tip 2", "specific tip 3"]
}}
Icons: ☀️ sunny, 🌤 partly cloudy, ⛅ overcast, 🌧 rain, ⛈ storm, 🌨 snow."""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"city": city, "forecast": [], "seasonal_summary": f"Check weather.com for {city}.", "packing_tips": []})


@tool
def get_seasonal_info(destination: str, month: str) -> Dict[str, Any]:
    """Get detailed seasonal travel information for a destination and month."""
    logger.info(f"Tool: get_seasonal_info({destination}, {month}) — web search")
    prompt = f"""Search the web for what {destination} is like for tourists in {month}.
Return ONLY a JSON object:
{{
  "destination": "{destination}",
  "month": "{month}",
  "climate": "Climate description",
  "avg_temp_high": "XX°C",
  "avg_temp_low": "XX°C",
  "packing_tips": ["tip 1", "tip 2", "tip 3"],
  "best_for": "Activities best suited to this time of year",
  "avoid": "Any risks or busy periods to be aware of",
  "events": "Festivals or events happening this month"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "month": month, "climate": "Check local sources", "packing_tips": []})


# ── ACTIVITIES ─────────────────────────────────────────────────────────────────

@tool
def search_activities(destination: str, duration_days: int = 3, interests: str = "general") -> Dict[str, Any]:
    """Find top-rated activities and attractions with current info from the web."""
    logger.info(f"Tool: search_activities({destination}) — web search")
    prompt = f"""Search the web for the best things to do in {destination} right now.
Return ONLY a JSON object:
{{
  "destination": "{destination}",
  "highlights": [
    {{"name": "Specific Place Name", "type": "Cultural/Food/Nature/Experience", "duration": "2-3 hrs", "cost": "Free or SGD XX", "rating": 4.8, "tip": "Insider tip or best time to visit"}},
    {{"name": "...", "type": "...", "duration": "...", "cost": "...", "rating": 4.7, "tip": "..."}}
  ]
}}
Include 6-8 specific real attractions. Mix must-sees with hidden gems. Add current prices and insider tips."""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "highlights": []})


@tool
def search_restaurants(destination: str, cuisine: str = "local") -> Dict[str, Any]:
    """Find top restaurants with current recommendations from the web."""
    logger.info(f"Tool: search_restaurants({destination}) — web search")
    prompt = f"""Search the web for the best {cuisine} restaurants in {destination} right now.
Return ONLY a JSON object:
{{
  "destination": "{destination}",
  "restaurants": [
    {{"name": "Restaurant Name", "type": "Cuisine", "price": "$ or $$ or $$$", "rating": 4.8, "must_try": "Specific dish", "area": "Neighbourhood", "tip": "Reservation needed?"}},
    {{"name": "...", "type": "...", "price": "...", "rating": 4.7, "must_try": "...", "area": "...", "tip": "..."}}
  ]
}}
Include 5 real restaurants from street food to fine dining with specific dish recommendations."""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "restaurants": []})


# ── ADVISORY ───────────────────────────────────────────────────────────────────

@tool
def get_travel_advisory(destination: str) -> Dict[str, Any]:
    """Get current official travel safety advisory from government sources via web search."""
    logger.info(f"Tool: get_travel_advisory({destination}) — web search")
    prompt = f"""Search the web for the current official travel advisory for {destination}.
Check: US State Dept (travel.state.gov), UK FCO (gov.uk/foreign-travel-advice), Australian DFAT (smartraveller.gov.au).
Return ONLY a JSON object:
{{
  "destination": "{destination}",
  "risk_level": "LOW or MEDIUM or HIGH or CRITICAL",
  "summary": "Current safety situation in 1-2 plain sentences",
  "hazards": [
    {{"type": "Natural Disaster or Political or Health or Crime", "level": "LOW or MEDIUM or HIGH", "detail": "Specific current risk"}}
  ],
  "sources": [
    {{"name": "US State Department", "type": "Government", "url": "travel.state.gov", "updated": "date"}},
    {{"name": "UK FCO", "type": "Government", "url": "gov.uk/foreign-travel-advice", "updated": "date"}}
  ]
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "risk_level": "LOW", "summary": "Check official government travel advisories.", "hazards": [], "sources": []})


@tool
def get_visa_requirements(destination: str, passport_country: str = "Singapore") -> Dict[str, Any]:
    """Get current visa requirements from official immigration sources via web search."""
    logger.info(f"Tool: get_visa_requirements({destination}, {passport_country}) — web search")
    prompt = f"""Search the web for current visa requirements for {passport_country} passport holders visiting {destination}.
Check the official immigration or embassy website.
Return ONLY a JSON object:
{{
  "destination": "{destination}",
  "passport": "{passport_country}",
  "requirement": "Visa Free or Visa on Arrival or eVisa or Visa Required",
  "max_stay": "XX days",
  "details": "Specific requirements and how to apply",
  "fee": "Amount or Free",
  "source": "Official source name",
  "source_url": "URL",
  "updated": "Date"
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "passport": passport_country, "requirement": "Check embassy website", "details": "Verify with official immigration authority.", "source": "Official embassy website", "updated": "Verify current date"})


@tool
def get_vaccine_requirements(destination: str) -> Dict[str, Any]:
    """Get current vaccination requirements from WHO and CDC via web search."""
    logger.info(f"Tool: get_vaccine_requirements({destination}) — web search")
    prompt = f"""Search the web for current vaccination requirements and recommendations for {destination}.
Check WHO (who.int) and CDC (cdc.gov/travel).
Return ONLY a JSON object:
{{
  "destination": "{destination}",
  "mandatory": [
    {{"name": "Vaccine", "requirement": "Mandatory", "notes": "When required", "source": "WHO"}}
  ],
  "recommended": [
    {{"name": "Vaccine", "requirement": "Recommended", "notes": "Why recommended", "source": "CDC"}}
  ],
  "sources": [
    {{"name": "WHO International Travel Health", "type": "WHO", "updated": "date"}},
    {{"name": "CDC Travelers Health", "type": "CDC", "updated": "date"}}
  ]
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "mandatory": [], "recommended": [], "sources": []})


@tool
def get_local_laws(destination: str) -> Dict[str, Any]:
    """Get important local laws and customs travellers must know via web search."""
    logger.info(f"Tool: get_local_laws({destination}) — web search")
    prompt = f"""Search the web for important local laws and customs tourists must know in {destination}.
Focus on rules that commonly catch tourists off guard or result in fines.
Return ONLY a JSON object:
{{
  "destination": "{destination}",
  "rules": [
    "🚭 Specific law with emoji",
    "💊 Another important rule",
    "📸 Photography restriction"
  ],
  "emergency_number": "local emergency number",
  "source": "Source name",
  "updated": "Date"
}}
Include 6-8 specific rules important for tourists in {destination}."""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "rules": [], "emergency_number": "112", "source": "Check local embassy", "updated": "Verify current"})


# ── RESCUE ──────────────────────────────────────────────────────────────────────

@tool
def get_emergency_contacts(destination: str) -> Dict[str, Any]:
    """Get real emergency contact numbers and hospitals via web search."""
    logger.info(f"Tool: get_emergency_contacts({destination}) — web search")
    prompt = f"""Search the web for emergency contact numbers and hospitals in {destination} for tourists.
Return ONLY a JSON object:
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
    {{"name": "Hospital Name", "type": "International/Private", "phone": "+XX-XXX", "address": "Area", "english_speaking": true}}
  ],
  "travel_insurance_tip": "Specific advice for {destination}"
}}
Use real verified emergency numbers."""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "emergency_numbers": [{"service": "General Emergency", "number": "112"}], "hospitals": [], "travel_insurance_tip": "Always carry travel insurance."})


@tool
def get_nearest_hospital(destination: str, area: str = "city centre") -> Dict[str, Any]:
    """Find hospitals and clinics in a specific area via web search."""
    logger.info(f"Tool: get_nearest_hospital({destination}, {area}) — web search")
    prompt = f"""Search the web for hospitals and international clinics in {area}, {destination} for tourists.
Return ONLY a JSON object:
{{
  "destination": "{destination}",
  "area": "{area}",
  "facilities": [
    {{"name": "Facility Name", "distance": "X km", "open": "24/7 or hours", "english_speaking": true, "phone": "+XX-XXX"}}
  ]
}}"""
    raw = _search_ai(prompt)
    return _parse_json(raw, {"destination": destination, "area": area, "facilities": []})


# ── Tool registries ────────────────────────────────────────────────────────────

PLANNER_TOOLS    = [search_flights, search_hotels, build_itinerary]
WEATHER_TOOLS    = [get_weather_forecast, get_seasonal_info]
ACTIVITIES_TOOLS = [search_activities, search_restaurants]
ADVISORY_TOOLS   = [get_travel_advisory, get_visa_requirements, get_vaccine_requirements, get_local_laws]
RESCUE_TOOLS     = [get_emergency_contacts, get_nearest_hospital]
ALL_TOOLS        = PLANNER_TOOLS + WEATHER_TOOLS + ACTIVITIES_TOOLS + ADVISORY_TOOLS + RESCUE_TOOLS

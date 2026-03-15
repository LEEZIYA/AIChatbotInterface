"""
Travel Tools
------------
These are the real callable functions agents can invoke.
Each @tool decorated function is discoverable by the LLM via tool-calling.
The LLM decides WHEN and HOW to call them based on the user query.

In a production system these would call real APIs (OpenWeather, Skyscanner, etc.)
For now they return structured realistic data so the full graph works end-to-end.
"""

from langchain_core.tools import tool
from typing import Dict, Any
import logging

logger = logging.getLogger("TRAVELBUDDY.tools")


# ── PLANNER TOOLS ─────────────────────────────────────────────────────────────

@tool
def search_flights(origin: str, destination: str, date: str) -> Dict[str, Any]:
    """Search for available flights between two cities on a given date."""
    logger.info(f"Tool: search_flights({origin} → {destination}, {date})")
    return {
        "origin": origin,
        "destination": destination,
        "date": date,
        "options": [
            {"airline": "Singapore Airlines", "departure": "08:00", "arrival": "14:30", "price": "SGD 850", "duration": "6h 30m"},
            {"airline": "ANA",               "departure": "11:15", "arrival": "18:45", "price": "SGD 780", "duration": "7h 30m"},
            {"airline": "Cathay Pacific",    "departure": "22:00", "arrival": "05:30+1","price": "SGD 690", "duration": "7h 30m"},
        ]
    }


@tool
def search_hotels(destination: str, checkin: str, checkout: str, budget: str = "mid-range") -> Dict[str, Any]:
    """Search for hotels in a destination city for given dates and budget level."""
    logger.info(f"Tool: search_hotels({destination}, {checkin}–{checkout}, {budget})")
    return {
        "destination": destination,
        "checkin": checkin,
        "checkout": checkout,
        "hotels": [
            {"name": "Park Hyatt", "stars": 5, "price_per_night": "SGD 520", "area": "City Centre", "rating": 9.2},
            {"name": "Mercure Hotel", "stars": 4, "price_per_night": "SGD 180", "area": "Shinjuku", "rating": 8.7},
            {"name": "Dormy Inn", "stars": 3, "price_per_night": "SGD 95", "area": "Asakusa", "rating": 8.9},
        ]
    }


@tool
def build_itinerary(destination: str, duration_days: int, interests: str = "general") -> Dict[str, Any]:
    """Build a day-by-day travel itinerary for a destination."""
    logger.info(f"Tool: build_itinerary({destination}, {duration_days} days)")
    days = []
    sample_activities = {
        1: [("09:00","Arrive and check in to hotel"),("11:00","Explore city centre"),("14:00","Lunch at local restaurant"),("16:00","Visit main landmark"),("19:00","Dinner in food district")],
        2: [("08:00","Breakfast at hotel"),("09:30","Day trip to nearby attraction"),("13:00","Lunch"),("15:00","Museum or cultural site"),("18:00","Evening market or street food")],
        3: [("09:00","Morning temple or nature visit"),("12:00","Local neighbourhood exploration"),("15:00","Shopping or souvenir"),("18:00","Farewell dinner"),("21:00","Pack and rest")],
    }
    for d in range(1, min(duration_days + 1, 8)):
        items = sample_activities.get(d, sample_activities[3])
        days.append({"day": d, "items": [{"time": t, "activity": a} for t, a in items]})
    return {"destination": destination, "duration_days": duration_days, "itinerary": days}


# ── WEATHER TOOLS ─────────────────────────────────────────────────────────────

@tool
def get_weather_forecast(city: str, days: int = 5) -> Dict[str, Any]:
    """Get weather forecast for a city for the next N days."""
    logger.info(f"Tool: get_weather_forecast({city}, {days} days)")
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    forecasts = [
        {"day": day_names[i % 7], "icon": "🌤", "temp": f"{22 + i}°C", "desc": "Partly cloudy", "humidity": "65%", "rain_chance": "20%"}
        for i in range(days)
    ]
    forecasts[1]["icon"] = "🌧"
    forecasts[1]["desc"] = "Rain expected"
    forecasts[1]["rain_chance"] = "80%"
    return {"city": city, "forecast": forecasts, "source": "OpenWeatherMap"}


@tool
def get_seasonal_info(destination: str, month: str) -> Dict[str, Any]:
    """Get seasonal climate information and packing recommendations for a destination."""
    logger.info(f"Tool: get_seasonal_info({destination}, {month})")
    return {
        "destination": destination,
        "month": month,
        "climate": "Temperate with mild rainfall",
        "avg_temp_high": "24°C",
        "avg_temp_low": "16°C",
        "packing_tips": [
            "Light layers for temperature swings",
            "Compact umbrella or rain jacket",
            "Comfortable walking shoes",
            "Sunscreen SPF 30+"
        ],
        "best_for": "Sightseeing, outdoor activities",
        "avoid": "Heavy outdoor events may be rained out mid-week"
    }


# ── ACTIVITIES TOOLS ──────────────────────────────────────────────────────────

@tool
def search_activities(destination: str, category: str = "all") -> Dict[str, Any]:
    """Search for activities, attractions and experiences in a destination."""
    logger.info(f"Tool: search_activities({destination}, {category})")
    return {
        "destination": destination,
        "highlights": [
            {"name": "Historic Old Town", "type": "Cultural", "duration": "2-3 hrs", "cost": "Free", "rating": 4.8},
            {"name": "Street Food Night Market", "type": "Food", "duration": "2 hrs", "cost": "SGD 15-30", "rating": 4.9},
            {"name": "Guided Walking Tour", "type": "Tour", "duration": "3 hrs", "cost": "SGD 25", "rating": 4.7},
            {"name": "Local Cooking Class", "type": "Experience", "duration": "4 hrs", "cost": "SGD 80", "rating": 4.9},
            {"name": "National Museum", "type": "Museum", "duration": "2 hrs", "cost": "SGD 12", "rating": 4.6},
        ]
    }


@tool
def search_restaurants(destination: str, cuisine: str = "local") -> Dict[str, Any]:
    """Find top restaurants in a destination by cuisine type."""
    logger.info(f"Tool: search_restaurants({destination}, {cuisine})")
    return {
        "destination": destination,
        "cuisine": cuisine,
        "restaurants": [
            {"name": "The Local Table", "type": "Traditional", "price": "$$", "rating": 4.8, "must_try": "Chef's seasonal tasting menu"},
            {"name": "Night Bazaar Kitchen", "type": "Street Food", "price": "$", "rating": 4.9, "must_try": "Grilled skewers and noodles"},
            {"name": "Harbour View", "type": "Fine Dining", "price": "$$$$", "rating": 4.7, "must_try": "Seafood platter"},
        ]
    }


# ── ADVISORY TOOLS ────────────────────────────────────────────────────────────

@tool
def get_travel_advisory(destination: str) -> Dict[str, Any]:
    """
    Get official travel safety advisory for a destination.
    Sources: US State Dept, UK FCO, Australian DFAT.
    """
    logger.info(f"Tool: get_travel_advisory({destination})")
    return {
        "destination": destination,
        "risk_level": "LOW",
        "summary": f"{destination} is generally safe for tourists. Normal precautions apply.",
        "hazards": [
            {"type": "Natural Disaster", "level": "LOW", "detail": "Typhoon season July–October. Monitor local forecasts."},
            {"type": "Crime",            "level": "LOW", "detail": "Petty theft in crowded tourist areas. Keep valuables secure."},
        ],
        "sources": [
            {"name": "US State Department", "type": "Government", "url": "travel.state.gov", "updated": "2025-02-01"},
            {"name": "UK Foreign Commonwealth Office", "type": "Government", "url": "gov.uk/foreign-travel-advice", "updated": "2025-01-28"},
            {"name": "Australian DFAT Smartraveller", "type": "Government", "url": "smartraveller.gov.au", "updated": "2025-01-30"},
        ]
    }


@tool
def get_visa_requirements(destination: str, passport_country: str = "Singapore") -> Dict[str, Any]:
    """
    Get visa requirements for entering a destination with a specific passport.
    Source: Official immigration authority of the destination country.
    """
    logger.info(f"Tool: get_visa_requirements({destination}, passport={passport_country})")
    return {
        "destination": destination,
        "passport": passport_country,
        "requirement": "Visa on Arrival",
        "max_stay": "90 days",
        "details": "Singapore passport holders may enter visa-free for up to 90 days for tourism.",
        "fee": "No fee",
        "source": "Official Immigration Bureau",
        "source_url": "https://www.immigration.go.th",
        "updated": "2025-01-15"
    }


@tool
def get_vaccine_requirements(destination: str) -> Dict[str, Any]:
    """
    Get vaccination requirements and recommendations for a destination.
    Sources: WHO, CDC, destination country health ministry.
    """
    logger.info(f"Tool: get_vaccine_requirements({destination})")
    return {
        "destination": destination,
        "mandatory": [
            {"name": "Yellow Fever", "requirement": "Mandatory", "notes": "Required if arriving from endemic country", "source": "WHO"}
        ],
        "recommended": [
            {"name": "Hepatitis A",  "requirement": "Recommended", "notes": "Food and water precaution", "source": "CDC"},
            {"name": "Typhoid",      "requirement": "Recommended", "notes": "If eating street food",    "source": "CDC"},
            {"name": "COVID-19",     "requirement": "Recommended", "notes": "Up to date vaccination",   "source": "WHO"},
        ],
        "routine": ["MMR", "Tetanus", "Flu"],
        "sources": [
            {"name": "WHO International Travel Health", "type": "WHO",        "updated": "2025-01-10"},
            {"name": "CDC Travelers Health",            "type": "CDC",        "updated": "2025-01-20"},
        ]
    }


@tool
def get_local_laws(destination: str) -> Dict[str, Any]:
    """Get important local laws, customs and regulations for travelers."""
    logger.info(f"Tool: get_local_laws({destination})")
    return {
        "destination": destination,
        "rules": [
            "🚭 Smoking is prohibited in most public indoor spaces and near entrances",
            "🍺 Alcohol is restricted — check local rules for public consumption",
            "📸 Ask permission before photographing people or religious sites",
            "👗 Dress modestly when visiting temples or religious buildings",
            "🤝 Remove shoes before entering homes and many traditional establishments",
            "💴 Tipping is not customary and can sometimes be considered rude",
            "🚯 Littering carries heavy fines",
            "💊 Declare all medications at customs — carry original prescriptions",
        ],
        "emergency_number": "112",
        "source": "Local Tourism Authority & Embassy Guidelines",
        "updated": "2025-01-01"
    }


# ── RESCUE TOOLS ──────────────────────────────────────────────────────────────

@tool
def get_emergency_contacts(destination: str) -> Dict[str, Any]:
    """Get emergency contact numbers, hospitals and embassy information for a destination."""
    logger.info(f"Tool: get_emergency_contacts({destination})")
    return {
        "destination": destination,
        "emergency_numbers": [
            {"service": "Police",         "number": "191"},
            {"service": "Ambulance",      "number": "1669"},
            {"service": "Fire",           "number": "199"},
            {"service": "Tourist Police", "number": "1155"},
            {"service": "General Emergency", "number": "112"},
        ],
        "hospitals": [
            {"name": "Bumrungrad International Hospital", "type": "Private International", "phone": "+66-2-066-8888", "address": "City Centre"},
            {"name": "Bangkok Hospital",                  "type": "Private",               "phone": "+66-2-310-3000", "address": "New Phetchaburi Road"},
        ],
        "embassy": {
            "singapore": {"address": "129 South Sathorn Road", "phone": "+66-2-286-2111", "emergency": "+66-81-842-0041"}
        },
        "travel_insurance_tip": "Always carry your travel insurance policy number and 24hr assistance hotline."
    }


@tool
def get_nearest_hospital(destination: str, area: str = "city centre") -> Dict[str, Any]:
    """Find the nearest hospital or medical facility in a specific area."""
    logger.info(f"Tool: get_nearest_hospital({destination}, {area})")
    return {
        "destination": destination,
        "area": area,
        "facilities": [
            {"name": "International Medical Centre", "distance": "1.2 km", "open": "24/7", "english_speaking": True},
            {"name": "City General Hospital",        "distance": "2.8 km", "open": "24/7", "english_speaking": True},
            {"name": "Community Clinic",             "distance": "0.4 km", "open": "08:00-20:00", "english_speaking": False},
        ]
    }


# ── TOOL REGISTRIES ───────────────────────────────────────────────────────────
# Each agent gets its own subset of tools — principle of least privilege

PLANNER_TOOLS    = [search_flights, search_hotels, build_itinerary]
WEATHER_TOOLS    = [get_weather_forecast, get_seasonal_info]
ACTIVITIES_TOOLS = [search_activities, search_restaurants]
ADVISORY_TOOLS   = [get_travel_advisory, get_visa_requirements, get_vaccine_requirements, get_local_laws]
RESCUE_TOOLS     = [get_emergency_contacts, get_nearest_hospital]

ALL_TOOLS = PLANNER_TOOLS + WEATHER_TOOLS + ACTIVITIES_TOOLS + ADVISORY_TOOLS + RESCUE_TOOLS

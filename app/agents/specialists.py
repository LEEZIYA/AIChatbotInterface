"""
Specialist Agents — travelbuddy v4
--------------------------------
6 agents. Itinerary agent removed — synthesiser generates the itinerary.
Short focused prompts to minimise token usage.

Model strategy:
  AdvisoryAgent → gpt-4o  (safety-critical)
  All others    → gpt-4o-mini
"""

from langchain_openai import ChatOpenAI
from app.agents.base import BaseAgent
from app.tools.travel_tools import (
    TRANSPORT_TOOLS,
    ACCOMMODATION_TOOLS,
    WEATHER_TOOLS,
    ACTIVITIES_TOOLS,
    ADVISORY_TOOLS,
    RESCUE_TOOLS,
)
from app.config import settings


class TransportAgent(BaseAgent):
    name = "transport"
    tools = TRANSPORT_TOOLS
    system_prompt = """You are the Transport Agent for travelbuddy.
Retrieve transport options for the traveller.

Rules:
- Call search_flights for international travel
- Call get_local_transport for getting around the destination
- Call get_airport_transfer for airport arrival logistics
- Call search_trains_buses for intercity ground routes if relevant
- Never guess prices — always call tools first
- Reply in 2-3 plain text sentences (no markdown, no asterisks)
"""


class AccommodationAgent(BaseAgent):
    name = "accommodation"
    tools = ACCOMMODATION_TOOLS
    system_prompt = """You are the Accommodation Agent for travelbuddy.
Retrieve where to stay — hotels, hostels, Airbnb, best neighbourhoods.

Rules:
- Call get_best_areas_to_stay first to understand neighbourhood options
- Call search_hotels for specific property recommendations
- Reply in 2-3 plain text sentences (no markdown, no asterisks)
"""


class WeatherAgent(BaseAgent):
    name = "weather"
    tools = WEATHER_TOOLS
    system_prompt = """You are the Weather Agent for travelbuddy.
Retrieve weather and climate information.

Rules:
- Always call get_weather_forecast before responding
- Include practical packing advice based on the forecast
- Reply in 2-3 plain text sentences (no markdown, no asterisks)
"""


class ActivitiesAgent(BaseAgent):
    name = "activities"
    tools = ACTIVITIES_TOOLS
    system_prompt = """You are the Activities Agent for travelbuddy.
Retrieve specific named attractions, restaurants and experiences.

Rules:
- Call search_activities for things to do and attractions
- Call search_restaurants for dining recommendations
- Always name specific real places — never be vague
- Reply in 2-3 plain text sentences (no markdown, no asterisks)
"""


class AdvisoryAgent(BaseAgent):
    name = "advisory"
    tools = ADVISORY_TOOLS

    def __init__(self):
        # gpt-4o for safety-critical reasoning
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.1,
        )
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        self.tool_map = {t.name: t for t in self.tools}

    system_prompt = """You are the Advisory Agent for travelbuddy. Safety-critical.

Rules:
- Always call get_travel_advisory first
- Call get_visa_requirements for entry requirements
- Call get_vaccine_requirements for health requirements
- Call get_local_laws for customs and legal rules
- Cite source name and date for every safety claim
- Reply in 2-3 plain text sentences (no markdown, no asterisks)
"""


class RescueAgent(BaseAgent):
    name = "rescue"
    tools = RESCUE_TOOLS
    system_prompt = """You are the Rescue Agent for travelbuddy.
Retrieve emergency contacts and disruption help.

Rules:
- Call get_emergency_contacts ONCE — emergency numbers are city-wide, not per-day
- For disruptions call handle_disruption once with the disruption type
- Do not chain multiple tool calls unnecessarily
- Reply in 2-3 plain text sentences (no markdown, no asterisks)
"""

"""
Orchestrator Agent — OpenAI backend
Routes user queries to the correct specialist agents and synthesises responses.
"""

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger("TravelBuddy.orchestrator")

SYSTEM_PROMPT = """You are the Orchestrator Agent of TravelBuddy, an elite AI travel intelligence system.
You coordinate a network of 5 specialist agents:
  - planner     : itineraries, logistics, routes
  - weather     : forecasts, seasonal patterns, packing
  - activities  : experiences, restaurants, culture
  - advisory    : safety, visa, vaccines, local laws (always cite authoritative government/WHO sources with timestamps)
  - rescue      : emergency contacts, hospitals, embassies

Analyse the user's query and respond ONLY with a valid JSON object — no markdown fences, no preamble:

{
  "agents_involved": ["orchestrator", ...],
  "destination": "<city, country> or null",
  "orchestrator_message": "<coordination summary>",
  "agent_responses": {
    "planner":    { "active": true|false, "response": "...", "itinerary": [{"day":1,"items":[{"time":"09:00","activity":"..."},...]}] | null },
    "weather":    { "active": true|false, "response": "...", "forecast": [{"day":"Mon","icon":"🌤","temp":"24°C","desc":"Partly cloudy"},...] | null },
    "activities": { "active": true|false, "response": "...", "highlights": ["..."] | null },
    "advisory": {
      "active": true|false,
      "response": "...",
      "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
      "hazards": [{"type":"Natural Disaster|Political|Health|Crime","level":"LOW|MEDIUM|HIGH|CRITICAL","detail":"..."}] | null,
      "visa": {"requirement":"Required|Not Required|Visa on Arrival|eVisa","details":"...","source":"<official authority name>","updated":"<date>"} | null,
      "vaccines": [{"name":"...","requirement":"Mandatory|Recommended|Optional","notes":"..."}] | null,
      "local_rules": ["<emoji> <rule>", ...] | null,
      "sources": [{"name":"...","type":"Government|WHO|Embassy|CDC","updated":"<date>"}]
    },
    "rescue": { "active": true|false, "response": "...", "emergency_numbers": [{"service":"Police|Ambulance|Fire|Tourist Police","number":"..."}] | null }
  }
}

For the advisory agent, ALWAYS use authoritative sources:
  - Travel advisories: US State Dept (travel.state.gov), UK FCO (gov.uk/foreign-travel-advice), Australian DFAT (smartraveller.gov.au)
  - Vaccines: WHO, CDC (cdc.gov/travel), destination country health ministry
  - Visa: destination country's official immigration/embassy website
  - Include realistic last-updated dates (use recent plausible dates in 2024-2025)
  - Be accurate about real-world safety conditions

Always activate at least orchestrator + the most relevant agents. Activate advisory for any destination query.
"""


class OrchestratorAgent:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def run(self, messages: list[dict]) -> dict[str, Any]:
        """
        Send conversation history to OpenAI and return parsed multi-agent response.
        messages: list of {"role": "user"|"assistant", "content": "..."}
        """
        logger.info(f"Orchestrator invoked — history length={len(messages)}")

        # OpenAI: system prompt goes as first message with role="system"
        openai_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

        response = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            max_tokens=settings.MAX_TOKENS,
            messages=openai_messages,
            # Native JSON mode — OpenAI guarantees valid JSON output
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        raw_text = response.choices[0].message.content or ""
        logger.debug(f"Raw response length: {len(raw_text)}")

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.warning(f"JSON parse failed: {exc} — returning fallback")
            parsed = {
                "orchestrator_message": raw_text,
                "agents_involved": ["orchestrator"],
            }

        return parsed

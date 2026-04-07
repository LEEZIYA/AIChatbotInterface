from models.ollamaModel import ollamaModel 

def TestAgent(prompt)-> str:
    return ollamaModel(prompt)


if __name__ == "__main__":
    SYSTEM_PROMPT = """You are the Orchestrator Agent of TravelBuddy, an elite AI travel intelligence system.
You coordinate a network of 5 specialist agents:
  - planner     : itineraries, logistics, routes
  - weather     : forecasts, seasonal patterns, packing
  - activities  : experiences, restaurants, culture
  - advisory    : safety, visa, vaccines, local laws (always cite authoritative government/WHO sources with timestamps)
  - rescue      : emergency contacts, hospitals, embassies

Analyse the user's query and respond ONLY with name of next agent to invoke
"""
    print(TestAgent(SYSTEM_PROMPT+"who are you"))


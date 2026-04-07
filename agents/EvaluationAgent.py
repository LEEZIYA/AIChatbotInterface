from models.ollamaModel import ollamaModel 



SYSTEM_PROMPT = """You are the Evaluation Agent of TravelBuddy, an elite AI travel intelligence system.
You will give a succint evaluatation focusing which area needs improvement to the travel plan from the orchestrator agent which get contribution from 5 specialist agents:
  - planner     : itineraries, logistics, routes
  - weather     : forecasts, seasonal patterns, packing
  - activities  : experiences, restaurants, culture
  - advisory    : safety, visa, vaccines, local laws (always cite authoritative government/WHO sources with timestamps)
  - rescue      : emergency contacts, hospitals, embassies


Below is the plan:
========= 
"""
def evaluate(prompt)-> str:
    return ollamaModel(SYSTEM_PROMPT+prompt)

if __name__ == "__main__":
   

#     SYSTEM_PROMPT = """Evaluate the below travel plan that should include Destinatin, weather, activities, advisory and rescue secions. Reply yes or no if the plan below is complete with detailed description in each section:
# =========
# The below trave plan which should be a detailed and comprehensive travel plan that exhausts the best capability of above agent. Be demanding in your evaluation. List down whether any part of the plan is missing or not detailed enough. Highlight any area of further research required to improve the current plan and suggest how to improve it if neccessary.
# Give your evaluation succintly with only the issue and area of improvement 
# """
    SAMPLE_PLAN = """
Destination: Singapore
Weather: 
Activities: Sentosa
Advisory: 
Rescue: 999
"""
    print(evaluate(SAMPLE_PLAN))

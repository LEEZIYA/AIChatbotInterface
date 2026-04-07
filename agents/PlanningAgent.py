from models.ollamaModel import ollamaModel 



SYSTEM_PROMPT = """You are the Planning Agent of TravelBuddy, an elite AI travel intelligence system.
Given the discussion between the various agents below, generate a day by day travel plan including the location, weather, transport plan and activities for each day of the trip. Use only the info from the transript and leave it blank if the info is not available
"""
def planTravel(prompt)-> str:
    return ollamaModel(SYSTEM_PROMPT+prompt)

if __name__ == "__main__":
   

#     SYSTEM_PROMPT = """Evaluate the below travel plan that should include Destinatin, weather, activities, advisory and rescue secions. Reply yes or no if the plan below is complete with detailed description in each section:
# =========
# The below trave plan which should be a detailed and comprehensive travel plan that exhausts the best capability of above agent. Be demanding in your evaluation. List down whether any part of the plan is missing or not detailed enough. Highlight any area of further research required to improve the current plan and suggest how to improve it if neccessary.
# Give your evaluation succintly with only the issue and area of improvement 
# """
    SAMPLE_PLAN = """
User: i want to go Japan for 4 days
Weather: it is cold, with some rain
activity: can go tokyo for shopping, osaka have food
transport:  can take flight sq1234 to tokyo, can take train abcd to osaka, can take train in city

"""
    print(planTravel(SAMPLE_PLAN))

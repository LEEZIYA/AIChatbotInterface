# from models.ollamaModel import ollamaModel 
from models.ollamaLLM import getOllamaLLM

import os
import yaml
# from pathlib import Path
from dotenv import load_dotenv
from typing import Any, Type, Optional
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv(override=True)

# Import CrewAI components
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool
from crewai.tools import BaseTool



## What We're Building

##Transport Planning Team** — three agents (LandTransport, AirTransport, LocalTransport) collaborating to produce a blog post about AI-powered content marketing.

#llm = LLM(model="gpt-4o", temperature=0.7)

llm = getOllamaLLM()
#     model="ollama/llama3:70b",
#     base_url="http://localhost:11434"
# )

web_search_tool = None
try:
    if os.getenv('SERPER_API_KEY'):
        web_search_tool = SerperDevTool()
        print("Web Search Tool (SerperDev) initialized")
    else:
        print("No SERPER_API_KEY found — agents will use LLM knowledge only")
except Exception as e:
    print(f"Web Search Tool error: {e}")

SYSTEM_PROMPT = """You are the Transport Agent of TravelBuddy, an elite AI travel intelligence system.
You will give a list of transportation bookings required with details based on the planned location and activities listed below: 
"""

landTravelAgent = Agent(
    role="Land Transport Specialist",
    goal="Plan and recommend land transportation options",
    backstory="Expert in ground transportation including trains, buses, and car rentals",
    llm=llm,
    tools=[web_search_tool] if web_search_tool else [],
    verbose=True
)

airtravelAgent = Agent(
    role="Air Travel Specialist",
    goal="Plan and recommend flight options",
    backstory="Expert in air travel, flight bookings, and airport logistics",
    llm=llm,
    tools=[web_search_tool] if web_search_tool else [],
    verbose=True
)

TravelPlanaggregator = Agent(
    role="Travel Plan Aggregator",
    goal="Compile and synthesize all transportation recommendations",
    backstory="Expert in creating comprehensive travel plans from multiple sources",
    llm=llm,
    verbose=True
)




crew = create_travel_crew(
    location="Bali, Indonesia",
    start_date="2024-12-20",
    end_date="2024-12-27",
    activities="Beach resorts, Temple tours, Rice terraces, Surfing",
    budget="low"
)

# Execute with custom inputs if needed
result = crew.kickoff()
print(result)

def planTravel(prompt)-> str:
    content_crew = Crew(
    agents=[landTravelAgent, airtravelAgent, TravelPlanaggregator],
    tasks=[landTravel_task, airTravel_task, aggregator_task],
    process=Process.sequential,
    verbose=True,
    memory=False,
    max_iter=10
)
    
    result = content_crew.kickoff()


    
    # return ollamaModel(SYSTEM_PROMPT+prompt)

if __name__ == "__main__":
   

#     SYSTEM_PROMPT = """Evaluate the below travel plan that should include Destinatin, weather, activities, advisory and rescue secions. Reply yes or no if the plan below is complete with detailed description in each section:
# =========
# The below trave plan which should be a detailed and comprehensive travel plan that exhausts the best capability of above agent. Be demanding in your evaluation. List down whether any part of the plan is missing or not detailed enough. Highlight any area of further research required to improve the current plan and suggest how to improve it if neccessary.
# Give your evaluation succintly with only the issue and area of improvement 
# """
    SAMPLE_REQUIREMENT = """
Destination: Singapore
Weather: 
Activities: Sentosa
Advisory: 
Rescue: 999
"""
    print(evaluate(SAMPLE_PLAN))

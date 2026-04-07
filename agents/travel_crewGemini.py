"""
Travel Planning Crew Module
Defines agents, tasks, and crew for travel planning
"""

import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool
from models.geminiLLM import getGeminiLLM  # ✅ Fixed import
###------------
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set environment variable
os.environ['HTTPX_VERIFY'] = 'false'
os.environ['PYTHONHTTPSVERIFY'] = '0'
###----------------------------------------------
# Load environment variables
load_dotenv(override=True)

# Initialize LLM
llm = getGeminiLLM()

# Initialize web search tool
web_search_tool = None
try:
    if os.getenv('SERPER_API_KEY'):
        web_search_tool = SerperDevTool()
        print("✓ Web Search Tool (SerperDev) initialized")
    else:
        print("⚠ No SERPER_API_KEY found — agents will use LLM knowledge only")
except Exception as e:
    print(f"✗ Web Search Tool error: {e}")


# Define Agents
land_travel_agent = Agent(
    role="Land Transport Specialist",
    goal="Plan and recommend optimal land transportation options including trains, buses, taxis, and car rentals",
    backstory="""You are an expert in ground transportation with 15 years of experience. 
    You know the best routes, most reliable services, and cost-effective options for land travel.
    You consider factors like traffic patterns, local customs, and accessibility.""",
    llm=llm,
    tools=[web_search_tool] if web_search_tool else [],
    verbose=True
)

air_travel_agent = Agent(
    role="Air Travel Specialist",
    goal="Plan and recommend optimal flight options with best routes and pricing",
    backstory="""You are an aviation expert with deep knowledge of airlines, routes, and airport logistics.
    You excel at finding the best flight deals, optimal layovers, and seamless connections.
    You stay updated on airline policies, baggage rules, and travel restrictions.""",
    llm=llm,
    tools=[web_search_tool] if web_search_tool else [],
    verbose=True
)

travel_plan_aggregator = Agent(
    role="Travel Plan Aggregator & Coordinator",
    goal="Synthesize all transportation recommendations into a cohesive, actionable travel plan",
    backstory="""You are a master travel coordinator who excels at creating comprehensive itineraries.
    You combine inputs from various specialists to create seamless travel experiences.
    You ensure all connections are logical, timings are realistic, and contingencies are planned.""",
    llm=llm,
    verbose=True
)


def create_travel_crew(location: str, start_date: str, end_date: str, activities: str = "", budget: str = "moderate") -> Crew:
    """
    Create a travel planning crew with specific parameters
    
    Args:
        location: Destination location
        start_date: Travel start date (format: YYYY-MM-DD)
        end_date: Travel end date (format: YYYY-MM-DD)
        activities: Planned activities at destination
        budget: Budget level (low/moderate/high)
    
    Returns:
        Configured Crew instance
    """
    
    period = f"{start_date} to {end_date}"  # ✅ Create period string
    
    # Define Tasks with dynamic inputs
    land_travel_task = Task(
        description=f"""Research and recommend land transportation options for {location}.
        
        Travel Period: {period}
        Planned Activities: {activities}
        Budget Level: {budget}
        
        Consider:
        - Local public transport (trains, buses, metro)
        - Taxi and ride-sharing services
        - Car rental options
        - Inter-city transportation if needed
        - Accessibility and convenience
        - Cost estimates and booking information
        """,
        expected_output="""Detailed land transportation plan including:
        - Recommended transport modes with reasons
        - Estimated costs and booking links
        - Schedules and routes
        - Tips for local navigation
        - Alternative options""",
        agent=land_travel_agent
    )
    
    air_travel_task = Task(
        description=f"""Research and recommend flight options to {location}.
        
        Travel Period: {period}
        Budget Level: {budget}
        
        Consider:
        - Direct vs connecting flights
        - Best airlines for this route
        - Optimal departure/arrival times
        - Baggage policies
        - Airport transfer options
        - Price comparisons
        """,
        expected_output="""Detailed flight recommendations including:
        - Top 3 flight options with pros/cons
        - Pricing and booking information
        - Departure and arrival details
        - Layover information if applicable
        - Airport transfer suggestions
        - Travel time comparisons""",
        agent=air_travel_agent
    )
    
    aggregator_task = Task(
        description=f"""Compile all transportation recommendations into a comprehensive travel plan for {location}.
        
        Travel Period: {period}
        Activities: {activities}
        Budget: {budget}
        
        Create a cohesive plan that:
        - Integrates air and land travel seamlessly
        - Provides a day-by-day transportation overview
        - Includes total cost estimates
        - Highlights booking priorities
        - Suggests optimal timing for bookings
        - Includes backup options
        """,
        expected_output="""Complete transportation plan with:
        - Executive summary
        - Detailed itinerary with all transport modes
        - Total cost breakdown
        - Booking checklist with priorities
        - Important tips and considerations
        - Emergency contact information
        - Alternative options for flexibility""",
        agent=travel_plan_aggregator,
        context=[land_travel_task, air_travel_task]
    )
    
    # Create and return the crew
    crew = Crew(
        agents=[land_travel_agent, air_travel_agent, travel_plan_aggregator],
        tasks=[land_travel_task, air_travel_task, aggregator_task],
        process=Process.sequential,
        verbose=True,
        memory=False,
        max_iter=15
    )
    
    return crew


def plan_travel(location: str, start_date: str, end_date: str, activities: str = "", budget: str = "moderate") -> str:
    """
    Execute travel planning crew and return comprehensive plan
    
    Args:
        location: Destination location
        start_date: Travel start date (format: YYYY-MM-DD)
        end_date: Travel end date (format: YYYY-MM-DD)
        activities: Planned activities at destination
        budget: Budget level (low/moderate/high)
    
    Returns:
        Comprehensive travel plan as string
    """
    print(f"""{'='*60}
🌍 Planning Travel to: {location}
📅 Period: {start_date} to {end_date}
🎯 Activities: {activities or 'General sightseeing'}
💰 Budget: {budget}
{'='*60}""")
    
    crew = create_travel_crew(
        location=location,
        start_date=start_date,
        end_date=end_date,
        activities=activities,
        budget=budget
    )
    
    result = crew.kickoff()
    
    return str(result)


if __name__ == "__main__":
    # Test the travel crew
    test_result = plan_travel(
        location="Paris",
        start_date="2024-07-01",
        end_date="2024-07-07",
        activities="museums, cafes, Eiffel Tower",
        budget="moderate"
    )
    print("" + "="*60)
    print("TRAVEL PLAN RESULT:")
    print("="*60)
    print(test_result)
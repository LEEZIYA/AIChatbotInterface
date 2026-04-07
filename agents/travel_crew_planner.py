"""
Travel Planning Crew Module
Defines agents, tasks, and crew for travel planning
"""

import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool
from models.ollamaLLM import getOllamaLLM

# Load environment variables
load_dotenv(override=True)

# Initialize LLM
llm = getOllamaLLM()

# Initialize web search tool
web_search_tool = None
# try:
#     if os.getenv('SERPER_API_KEY'):
#         web_search_tool = SerperDevTool()
#         print("✓ Web Search Tool (SerperDev) initialized")
#     else:
#         print("⚠ No SERPER_API_KEY found — agents will use LLM knowledge only")
# except Exception as e:
#     print(f"✗ Web Search Tool error: {e}")


# Define Agents
planner_agent = Agent(
    role="Travel Requirements Planner",
    goal="Interpret natural language travel requirements and convert them into a short, structured execution brief with only essential points",
    backstory="""You are an expert travel planner who translates broad travel requests into a structured plan.
    Keep all outputs concise, practical, and focused on only the most important details.
    Use short bullet points. Avoid long paragraphs and repetition.""",
    llm=llm,
    verbose=True,
    allow_delegation=False
)

land_travel_agent = Agent(
    role="Land Transport Specialist",
    goal="Plan and recommend optimal land transportation options including trains, buses, taxis, and car rentals",
    backstory="""You are an expert in ground transportation with 15 years of experience.
    You know the best routes, most reliable services, and cost-effective options for land travel.
    You consider factors like traffic patterns, local customs, and accessibility.
    Keep all outputs concise, practical, and focused on only the most important details.
    Use short bullet points. Avoid long paragraphs and repetition.""",
    llm=llm,
    tools=[web_search_tool] if web_search_tool else [],
    verbose=True,
    allow_delegation=False
)

air_travel_agent = Agent(
    role="Air Travel Specialist",
    goal="Plan and recommend optimal flight options with best routes and pricing",
    backstory="""You are an aviation expert with deep knowledge of airlines, routes, and airport logistics.
    You excel at finding the best flight deals, optimal layovers, and seamless connections.
    You stay updated on airline policies, baggage rules, and travel restrictions.
    Keep all outputs concise, practical, and focused on only the most important details.
    Use short bullet points. Avoid long paragraphs and repetition.""",
    llm=llm,
    tools=[web_search_tool] if web_search_tool else [],
    verbose=True,
    allow_delegation=False
)

accommodation_agent = Agent(
    role="Accommodation Specialist",
    goal="Plan and recommend the best accommodation options based on location, budget, convenience, and travel activities",
    backstory="""You are a travel accommodation expert with strong knowledge of hotels, hostels, serviced apartments,
    and vacation rentals. You help travellers choose where to stay based on budget, safety, proximity to attractions,
    transport access, and overall value.
    Keep all outputs concise, practical, and focused on only the most important details.
    Use short bullet points. Avoid long paragraphs and repetition.""",
    llm=llm,
    tools=[web_search_tool] if web_search_tool else [],
    verbose=True,
    allow_delegation=False
)

travel_plan_aggregator = Agent(
    role="Travel Plan Aggregator & Coordinator",
    goal="Synthesize planning, transportation, and accommodation recommendations into a cohesive, actionable travel plan",
    backstory="""You are a master travel coordinator who excels at creating comprehensive itineraries.
    You combine inputs from various specialists to create seamless travel experiences.
    You ensure all connections are logical, timings are realistic, accommodation is well-located,
    and contingencies are planned.
    Keep all outputs concise, practical, and focused on only the most important details.
    Use short bullet points. Avoid long paragraphs and repetition.""",
    llm=llm,
    verbose=True,
    allow_delegation=False
)


def create_travel_crew(TravelContext: str) -> Crew:
    """
    Create a travel planning crew using a single natural-language travel context.

    Args:
        TravelContext: Natural language prompt describing the travel requirement

    Returns:
        Configured Crew instance
    """

    planner_task = Task(
    description=f"""Read the travel request and convert it into a short structured brief.

    Travel Context:
    {TravelContext}

    Keep the output concise.
    Use bullet points only.
    Include only information needed by the specialist agents.
    Avoid long explanations and repetition.
    """,
    expected_output="""Concise planning brief with:
    - Destination
    - Dates or duration
    - Budget
    - Main activities
    - Key preferences or constraints
    - Research priorities for flight, land transport, and accommodation
    - Assumptions or missing details (max 3 points)""",
    agent=planner_agent
    )

    air_travel_task = Task(
    description="""Using the planner's brief, recommend the best flight options.

    Keep the output concise.
    Return only the most relevant options.
    Use bullet points only.
    Avoid long explanations.
    """,
    expected_output="""Concise flight recommendation with:
    - Best 1-2 flight options
    - Estimated price range
    - Key timing details
    - Main trade-off for each option
    - Final recommended option""",
    agent=air_travel_agent,
    context=[planner_task]
    )
    land_travel_task = Task(
        description="""Using the planner's brief, recommend the most practical land transport options.

        Keep the output concise.
        Focus only on the most useful options.
        Use bullet points only.
        """,
        expected_output="""Concise land transport plan with:
        - Best local transport mode(s)
        - Estimated cost range
        - Key usage tips
        - One backup option""",
        agent=land_travel_agent,
        context=[planner_task]
    )

    accommodation_task = Task(
        description="""Using the planner's brief, recommend the most suitable accommodation options.

        Keep the output concise.
        Focus on the best-fit stay options only.
        Use bullet points only.
        """,
        expected_output="""Concise accommodation recommendation with:
        - Best area(s) to stay
        - Top 1-2 accommodation options
        - Estimated nightly price range
        - Key reason for recommendation
        - One backup option""",
        agent=accommodation_agent,
        context=[planner_task]
    )
    aggregator_task = Task(
        description="""Combine all outputs into one short final travel plan.

        Keep the final answer very concise.
        Use bullet points only.
        Include only crucial decision-making information.
        Do not repeat details already implied.
        Avoid long paragraphs.
        """,
        expected_output="""Short final travel plan with:
        - Trip summary
        - Best flight option
        - Best accommodation option
        - Best local transport option
        - Estimated total budget
        - Top 3 booking priorities
        - Key assumptions or risks""",
        agent=travel_plan_aggregator,
        context=[planner_task, air_travel_task, land_travel_task, accommodation_task]
    )
    crew = Crew(
        agents=[
            planner_agent,
            air_travel_agent,
            land_travel_agent,
            accommodation_agent,
            travel_plan_aggregator
        ],
        tasks=[
            planner_task,
            air_travel_task,
            land_travel_task,
            accommodation_task,
            aggregator_task
        ],
        process=Process.sequential,
        verbose=True,
        memory=False,
        max_iter=5
    )

    return crew


def plan_travel(TravelContext: str) -> str:
    """
    Execute travel planning crew using a single natural-language travel request.

    Args:
        TravelContext: Natural language prompt describing the overall travel requirement

    Returns:
        Comprehensive travel plan as string
    """
    print(f"""{'='*60}
🌍 Travel Planning Request
📝 Context: {TravelContext}
{'='*60}""")

    crew = create_travel_crew(TravelContext=TravelContext)
    result = crew.kickoff()

    return str(result)


if __name__ == "__main__":
    # Test the travel crew
    test_result = plan_travel(
        TravelContext="""
        I want to plan a 6-day trip to Paris in early July.
        My budget is moderate.
        I want to visit museums, cafes, and the Eiffel Tower.
        Please suggest flights, local transport, and a convenient place to stay near major attractions.
        """
    )
    print("" + "="*60)
    print("TRAVEL PLAN RESULT:")
    print("="*60)
    print(test_result)
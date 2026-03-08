"""
MCP-Enhanced Rescue Agent Demo

This demo shows the agent using REAL-TIME data through MCP servers!
"""
import asyncio
from uuid import uuid4
from datetime import datetime, timedelta
from loguru import logger

from src import (
    RescueAgentMCP,
    Itinerary, FlightLeg,
    DisruptionEvent, DisruptionType,
    UserPreferences
)


def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(title)
    print("="*60 + "\n")


def print_section(title: str):
    """Print section divider"""
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}\n")


async def demo_mcp_enhanced_rescue():
    """
    Demo: MCP-Enhanced Real-Time Analysis
    
    This shows how the agent uses MCP tools to get REAL data!
    """
    print_header("🚀 MCP-ENHANCED RESCUE AGENT DEMO")
    
    print("📋 Creating sample itinerary...")
    
    # Create itinerary
    itinerary = Itinerary(
        user_id="user_mcp_demo",
        trip_id="trip_mcp_demo_001",
        legs=[
            FlightLeg(
                id="leg1",
                origin="JFK",
                destination="LHR",
                departure_time=datetime.now() + timedelta(hours=6),
                arrival_time=datetime.now() + timedelta(hours=13),
                airline="BA",
                flight_number="BA001",
                cost=450.00
            ),
            FlightLeg(
                id="leg2",
                origin="LHR",
                destination="CDG",
                departure_time=datetime.now() + timedelta(hours=15),
                arrival_time=datetime.now() + timedelta(hours=16),
                airline="AF",
                flight_number="AF1234",
                cost=180.00
            )
        ]
    )
    
    print(f"✅ Created itinerary: {itinerary.trip_id}")
    for i, leg in enumerate(itinerary.legs, 1):
        print(f"   - Leg {i}: {leg.origin} → {leg.destination} ({leg.flight_number})")
    
    print("\n🚨 Initializing MCP-Enhanced Rescue Agent...")
    
    # Initialize agent
    agent = RescueAgentMCP(use_mock_apis=True)
    
    # IMPORTANT: Start MCP connections
    await agent.start()
    
    print("✅ Agent initialized with MCP servers connected!\n")
    
    # Simulate disruption
    print_section("⚠️ SIMULATING FLIGHT DISRUPTION")
    
    disruption = DisruptionEvent(
    id=str(uuid4()),  # Add this line!
    type=DisruptionType.FLIGHT_DELAY,
    flight_number="BA001",
    delay_duration=180,
    timestamp=datetime.now(),
    description="BA001 delayed by 180 minutes due to weather"
    )
    
    print(f"   Type: {disruption.type.value}")
    print(f"   Flight: {disruption.flight_number}")
    print(f"   Delay: {disruption.delay_duration} minutes")
    
    print("\n🔧 Agent will now:")
    print("   1️⃣  Call MCP tool: get_flight_status (real-time status)")
    print("   2️⃣  Call MCP tool: search_alternative_flights (actual availability)")
    print("   3️⃣  Call MCP tool: check_weather (weather conditions)")
    print("   4️⃣  Generate solutions based on REAL data")
    
    # User preferences
    preferences = UserPreferences(
        priority="time",
        budget="medium",
        max_acceptable_delay=120
    )
    
    # Handle disruption (will use MCP tools!)
    print("\n🤖 LLM analyzing with MCP tools...\n")
    
    solutions = await agent.handle_disruption(
        event=disruption,
        itinerary=itinerary,
        user_preferences=preferences
    )
    
    print(f"\n✅ Generated {len(solutions)} solution(s) using MCP data\n")
    
    # Display solutions
    print_section("💡 DATA-DRIVEN SOLUTION OPTIONS")
    
    for i, solution in enumerate(solutions, 1):
        print(f"\nOption {i}: {solution.strategy}")
        print(f"{'─'*60}")
        print(f"Description: {solution.description}")
        print(f"Score: {solution.score:.2f} | Confidence: {solution.confidence:.0%}")
        print(f"Cost Impact: ${solution.cost_impact:+.2f}")
        print(f"Time Impact: {solution.time_impact:+} minutes")
        
        if hasattr(solution, 'data_verified'):
            print(f"✅ Data Verified: {solution.data_verified}")
        
        print(f"\n✅ Pros:")
        for pro in solution.pros:
            print(f"   • {pro}")
        
        print(f"\n❌ Cons:")
        for con in solution.cons:
            print(f"   • {con}")
        
        if solution.requires_user_action:
            print(f"\n📋 Required Actions:")
            for action in solution.requires_user_action:
                print(f"   • {action}")
        
        print(f"\n⏰ Urgency: {solution.urgency}")
    
    # Simulate user selection
    if solutions:
        print("\n" + "="*60)
        print("👤 User selects Option 1...")
        
        attempt_id = agent.rescue_attempts[-1].id
        await agent.approve_solution(attempt_id, solutions[0].strategy)
        
        print("✅ Solution approved and recorded")
    
    # Shutdown MCP connections
    await agent.shutdown()
    
    print("\n" + "="*60)
    print("Demo completed successfully!")
    print("="*60 + "\n")


async def demo_mcp_tools_direct():
    """
    Demo: Direct MCP Tool Usage
    
    Shows what happens when LLM calls MCP tools
    """
    print_header("🛠️ MCP TOOLS DEMONSTRATION")
    
    print("This shows what the LLM sees when it calls MCP tools:\n")
    
    # Initialize agent to get MCP client
    agent = RescueAgentMCP(use_mock_apis=True)
    await agent.start()
    
    print_section("Available MCP Tools")
    
    for tool in agent.llm.mcp_tools:
        tool_func = tool['function']
        print(f"\n📦 Tool: {tool_func['name']}")
        print(f"   Description: {tool_func['description']}")
        print(f"   Parameters: {list(tool_func['parameters']['properties'].keys())}")
    
    print_section("Example: Calling get_flight_status")
    
    print("LLM calls: get_flight_status(flight_number='BA001')\n")
    
    try:
        result = await agent.llm._execute_mcp_tool(
            "get_flight_status",
            {"flight_number": "BA001"}
        )
        
        print("📊 MCP Tool Response:")
        print(result)
    except Exception as e:
        print(f"⚠️  {e}")
    
    print_section("Example: Searching Alternative Flights")
    
    print("LLM calls: search_alternative_flights(origin='JFK', destination='LHR', date='2026-03-15')\n")
    
    try:
        result = await agent.llm._execute_mcp_tool(
            "search_alternative_flights",
            {
                "origin": "JFK",
                "destination": "LHR", 
                "departure_date": "2026-03-15"
            }
        )
        
        print("📊 MCP Tool Response:")
        print(result)
    except Exception as e:
        print(f"⚠️  {e}")
    
    await agent.shutdown()


async def demo_comparison():
    """
    Demo: MCP vs Non-MCP Comparison
    """
    print_header("⚖️ MCP vs TRADITIONAL COMPARISON")
    
    print_section("WITHOUT MCP (Traditional)")
    
    print("""
    Agent Flow:
    1. User reports delay
    2. Agent uses MOCK/CACHED data
    3. Generates solutions from assumptions
    4. Solutions may be outdated
    
    Example Solution:
    - "Rebook on UA123" 
    - ❌ But UA123 might be full!
    - ❌ Price might be different!
    - ❌ Flight might not exist!
    """)
    
    print_section("WITH MCP (Real-Time)")
    
    print("""
    Agent Flow:
    1. User reports delay
    2. LLM calls get_flight_status MCP tool → REAL status
    3. LLM calls search_alternative_flights → ACTUAL availability
    4. LLM calls check_weather → CURRENT conditions
    5. Generates solutions from VERIFIED data
    
    Example Solution:
    - "Rebook on UA123"
    - ✅ Verified: 8 seats available
    - ✅ Current price: $523
    - ✅ Flight status: On-time
    - ✅ Weather: Clear conditions
    """)
    
    print_section("The Difference")
    
    print("""
    Traditional:  🎲 Guessing based on old data
    MCP-Enhanced: ✅ Acting on real-time facts
    
    Result:
    - Higher success rate
    - Accurate pricing
    - Better user experience
    - Fewer failed rebookings
    """)


async def main():
     
    try:
        # Main demo
        await demo_mcp_enhanced_rescue()
        
        # Tool demonstration
        await demo_mcp_tools_direct()
        
        
        print("\n✅ All demos completed!")
        print("\nNext steps:")
        print("1. Review mcp_servers/flight_server.py to see how tools are defined")
        print("2. Check src/llm_client.py to see MCP integration")
        print("3. Add your OpenAI API key to .env")
        print("4. Connect real APIs (FlightAware, OpenWeather) for production use")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

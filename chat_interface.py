"""
TravelBuddy Rescue Agent - Interactive Chat Interface

Run with: streamlit run chat_interface.py
"""
import streamlit as st
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

# Import your agent
from src import (
    RescueAgentMCP,
    Itinerary, FlightLeg,
    DisruptionEvent, DisruptionType,
    UserPreferences
)

# Page config
st.set_page_config(
    page_title="TravelBuddy - Rescue Agent",
    page_icon="🚨",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main {
        background-color: #0a0e27;
    }
    .stChatMessage {
        background-color: #1a1f2e;
        border-radius: 10px;
        padding: 15px;
    }
    .agent-status {
        padding: 10px;
        background: #1a1f2e;
        border-radius: 5px;
        margin: 5px 0;
    }
    .active {
        border-left: 3px solid #00ff88;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.messages = []
    st.session_state.agent = None
    st.session_state.itinerary = None
    st.session_state.agent_status = "IDLE"

# Sidebar
with st.sidebar:
    st.title("🌍 TravelBuddy")
    st.markdown("### AI TRAVEL INTELLIGENCE")
    
    st.markdown("---")
    st.markdown("### 🤖 Agents")
    
    agents = {
        "Orchestrator": "ACTIVE",
        "Planner Agent": "IDLE",
        "Weather Agent": "IDLE",
        "Activities Agent": "IDLE",
        "Advisory Agent": "IDLE",
        "Rescue Agent": st.session_state.agent_status
    }
    
    for agent_name, status in agents.items():
        if status == "ACTIVE":
            st.markdown(f'<div class="agent-status active">🟢 <b>{agent_name}</b><br><small>{status}</small></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="agent-status">⚪ <b>{agent_name}</b><br><small>{status}</small></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Trip info
    if st.session_state.itinerary:
        st.markdown("### ✈️ Current Trip")
        st.markdown(f"**Trip ID:** {st.session_state.itinerary.trip_id}")
        st.markdown(f"**Legs:** {len(st.session_state.itinerary.legs)}")
        
        for i, leg in enumerate(st.session_state.itinerary.legs, 1):
            st.markdown(f"**Leg {i}:** {leg.origin} → {leg.destination}")
            st.markdown(f"*{leg.flight_number}*")
    
    st.markdown("---")
    
    if st.button("🔄 Reset Conversation"):
        st.session_state.messages = []
        st.session_state.initialized = False
        st.session_state.agent_status = "IDLE"
        st.rerun()

# Main chat area
st.title("Rescue Agent Chat")
st.markdown("Ask me about flight disruptions, delays, or cancellations!")

# Initialize agent
async def init_agent():
    if not st.session_state.initialized:
        with st.spinner("🚨 Initializing Rescue Agent..."):
            st.session_state.agent = RescueAgentMCP(use_mock_apis=True)
            await st.session_state.agent.start()
            
            # Create sample itinerary
            st.session_state.itinerary = Itinerary(
                user_id="user_chat_demo",
                trip_id="trip_chat_001",
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
            
            st.session_state.initialized = True
            
            # Welcome message
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"👋 **Rescue Agent ready!**\n\nI'm monitoring your trip: **{st.session_state.itinerary.trip_id}**\n\n"
                          f"**Your flights:**\n"
                          f"- {st.session_state.itinerary.legs[0].flight_number}: {st.session_state.itinerary.legs[0].origin} → {st.session_state.itinerary.legs[0].destination}\n"
                          f"- {st.session_state.itinerary.legs[1].flight_number}: {st.session_state.itinerary.legs[1].origin} → {st.session_state.itinerary.legs[1].destination}\n\n"
                          f"💬 Try saying:\n"
                          f"- 'My flight BA001 is delayed 3 hours'\n"
                          f"- 'Flight AF1234 was cancelled'\n"
                          f"- 'What should I do about the delay?'"
            })

# Run initialization
if not st.session_state.initialized:
    asyncio.run(init_agent())

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle user input
async def process_user_message(user_message):
    """Process user message and get agent response"""
    
    # Check if we have pending solutions (from previous message)
    if 'pending_solutions' in st.session_state and st.session_state.pending_solutions:
        user_lower = user_message.lower()
        
        # Check for approval/selection
        if any(word in user_lower for word in ['yes', 'proceed', 'approve', 'ok', 'confirm']):
            # User wants option 1
            st.session_state.agent_status = "ACTIVE"
            
            solution = st.session_state.pending_solutions[0]
            await st.session_state.agent.approve_solution(solution)
            
            st.session_state.agent_status = "IDLE"
            st.session_state.pending_solutions = None
            
            return (f"✅ **Solution Approved!**\n\n"
                   f"I've recorded your approval for:\n"
                   f"**{solution.strategy}** - {solution.description}\n\n"
                   f"💰 Cost Impact: ${solution.cost_impact:+.2f}\n"
                   f"⏱️ Time Impact: {solution.time_impact:+} minutes\n\n"
                   f"In a production system, I would now:\n"
                   f"1. Process the rebooking\n"
                   f"2. Send confirmation email\n"
                   f"3. Update your itinerary\n"
                   f"4. Notify other agents\n\n"
                   f"Is there anything else I can help with?")
        
        # Check for option selection
        elif 'option 2' in user_lower or 'second option' in user_lower:
            if len(st.session_state.pending_solutions) > 1:
                solution = st.session_state.pending_solutions[1]
                
                return (f"📋 **Option 2 Details:**\n\n"
                       f"**Strategy:** {solution.strategy}\n"
                       f"**Description:** {solution.description}\n\n"
                       f"💰 Cost Impact: ${solution.cost_impact:+.2f}\n"
                       f"⏱️ Time Impact: {solution.time_impact:+} minutes\n"
                       f"⭐ Confidence: {solution.confidence:.0%}\n\n"
                       f"**Pros:**\n" + "\n".join(f"  • {pro}" for pro in solution.pros[:3]) + "\n\n"
                       f"**Cons:**\n" + "\n".join(f"  • {con}" for con in solution.cons[:3]) + "\n\n"
                       f"Would you like to proceed with Option 2?")
            else:
                return "I only found 1 solution. Would you like to proceed with Option 1?"
        
        elif 'no' in user_lower or 'cancel' in user_lower:
            st.session_state.pending_solutions = None
            return ("Understood. I won't proceed with any solution.\n\n"
                   "Would you like me to look for different solutions?")
    
    # Detect disruption keywords
    disruption_detected = False
    disruption_type = None
    flight_number = None
    delay_minutes = 0
    
    user_lower = user_message.lower()
    
    # Check for disruption
    if "delayed" in user_lower or "delay" in user_lower:
        disruption_detected = True
        disruption_type = DisruptionType.FLIGHT_DELAY
        
        # Extract delay duration
        import re
        hours = re.search(r'(\d+)\s*hour', user_lower)
        minutes = re.search(r'(\d+)\s*minute', user_lower)
        
        if hours:
            delay_minutes = int(hours.group(1)) * 60
        elif minutes:
            delay_minutes = int(minutes.group(1))
        else:
            delay_minutes = 180  # Default 3 hours
    
    elif "cancelled" in user_lower or "canceled" in user_lower:
        disruption_detected = True
        disruption_type = DisruptionType.FLIGHT_CANCELLATION
    
    # Extract flight number
    for leg in st.session_state.itinerary.legs:
        if leg.flight_number.lower() in user_lower:
            flight_number = leg.flight_number
            break
    
    if not flight_number and disruption_detected:
        flight_number = st.session_state.itinerary.legs[0].flight_number
    
    if disruption_detected:
        # Activate Rescue Agent
        st.session_state.agent_status = "ACTIVE"
        
        # Create disruption event
        disruption = DisruptionEvent(
            id=str(uuid4()),
            type=disruption_type,
            flight_number=flight_number,
            delay_duration=delay_minutes,
            timestamp=datetime.now(),
            description=user_message
        )
        
        # Get user preferences
        preferences = UserPreferences(
            priority="time",
            budget="medium",
            max_acceptable_delay=120
        )
        
        # Handle disruption
        with st.spinner("🚨 Analyzing disruption and finding solutions..."):
            solutions = await st.session_state.agent.handle_disruption(
                event=disruption,
                itinerary=st.session_state.itinerary,
                user_preferences=preferences
            )
        
        st.session_state.agent_status = "IDLE"
        
        # Store solutions for follow-up
        st.session_state.pending_solutions = solutions
        
        # Format response
        if solutions:
            response = f"🚨 **DISRUPTION DETECTED**\n\n"
            response += f"**Flight:** {flight_number}\n"
            response += f"**Issue:** {disruption_type.value}\n"
            
            if delay_minutes > 0:
                response += f"**Delay:** {delay_minutes} minutes\n"
            
            response += f"\n💡 **I found {len(solutions)} solution(s):**\n\n"
            
            for i, solution in enumerate(solutions[:3], 1):
                response += f"**Option {i}: {solution.strategy}**\n"
                response += f"📝 {solution.description}\n"
                response += f"💰 Cost: ${solution.cost_impact:+.2f}\n"
                response += f"⏱️ Time: {solution.time_impact:+} minutes\n"
                response += f"⭐ Confidence: {solution.confidence:.0%}\n\n"
                
                if solution.pros:
                    response += "✅ **Pros:**\n"
                    for pro in solution.pros[:3]:
                        response += f"  • {pro}\n"
                
                if solution.cons:
                    response += "\n❌ **Cons:**\n"
                    for con in solution.cons[:3]:
                        response += f"  • {con}\n"
                
                response += "\n---\n\n"
            
            response += "💬 **What would you like to do?**\n"
            response += "- Say 'yes' to proceed with Option 1\n"
            response += "- Say 'no' if you'd like different solutions"
        else:
            response = "😟 I couldn't generate solutions. Let me connect you to customer support."
            st.session_state.pending_solutions = None
        
        return response
    
    else:
        # General conversation
        return ("I'm your Rescue Agent! 🚨\n\n"
                "I specialize in handling flight disruptions. "
                "Try telling me about a delay or cancellation, and I'll help you find solutions!\n\n"
                "For example: 'My flight BA001 is delayed 3 hours'")

# Chat input
if prompt := st.chat_input("Type your message..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Get agent response
    response = asyncio.run(process_user_message(prompt))
    
    # Add assistant response
    st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Rerun to update chat
    st.rerun()

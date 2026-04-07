"""
TravelAgent.py
Wrapper for the travel planning crew functionality
"""

import logging
from typing import Optional
from agents.travel_crew_planner import plan_travel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TravelAgent:
    """
    Travel Agent wrapper class for planning travel using AI agents
    """
    
    def __init__(self):
        """Initialize the Travel Agent"""
        logger.info("TravelAgent initialized")
    
    def plan_trip(self, travel_context: str) -> dict:
        """
        Plan a trip based on natural language travel context
        
        Args:
            travel_context: Natural language description of travel requirements
            
        Returns:
            dict with:
                - success: bool
                - travel_plan: str (if successful)
                - error: str (if failed)
        """
        try:
            logger.info(f"Planning trip with context: {travel_context[:100]}...")
            
            # Validate input
            if not travel_context or not travel_context.strip():
                logger.warning("Empty travel context provided")
                return {
                    "success": False,
                    "error": "Travel context cannot be empty"
                }
            
            # Call the crew-based planner
            travel_plan = plan_travel(TravelContext=travel_context)
            
            logger.info("Travel plan generated successfully")
            
            return {
                "success": True,
                "travel_plan": travel_plan
            }
            
        except Exception as e:
            logger.error(f"Error planning trip: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to generate travel plan: {str(e)}"
            }
    
    def validate_context(self, travel_context: str) -> tuple[bool, Optional[str]]:
        """
        Validate travel context before processing
        
        Args:
            travel_context: Travel request string
            
        Returns:
            tuple of (is_valid: bool, error_message: Optional[str])
        """
        if not travel_context:
            return False, "Travel context is required"
        
        if len(travel_context.strip()) < 10:
            return False, "Travel context is too short. Please provide more details."
        
        if len(travel_context) > 5000:
            return False, "Travel context is too long. Please keep it under 5000 characters."
        
        return True, None


# Singleton instance
_travel_agent_instance = None


def get_travel_agent() -> TravelAgent:
    """
    Get or create singleton TravelAgent instance
    
    Returns:
        TravelAgent instance
    """
    global _travel_agent_instance
    if _travel_agent_instance is None:
        _travel_agent_instance = TravelAgent()
    return _travel_agent_instance


# For direct testing
if __name__ == "__main__":
    agent = get_travel_agent()
    
    test_context = """
    I want to plan a 6-day trip to Paris in early July.
    My budget is moderate.
    I want to visit museums, cafes, and the Eiffel Tower.
    Please suggest flights, local transport, and a convenient place to stay near major attractions.
    """
    
    result = agent.plan_trip(test_context)
    
    if result["success"]:
        print("=" * 60)
        print("TRAVEL PLAN:")
        print("=" * 60)
        print(result["travel_plan"])
    else:
        print("=" * 60)
        print("ERROR:")
        print("=" * 60)
        print(result["error"])
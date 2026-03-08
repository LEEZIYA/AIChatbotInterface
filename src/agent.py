"""
MCP-Enhanced Rescue Agent

This version uses Model Context Protocol (MCP) to access real-time data
through specialized servers for flights, weather, and more.
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import uuid4
from loguru import logger

from .models import (
    Itinerary, DisruptionEvent, DisruptionDetection,
    Solution, UserPreferences, RescueAttempt, Severity
)
from .detector import DisruptionDetector
from .evaluator import SolutionEvaluator
from .llm_client import MCPLLMClient
from .external_apis import ExternalAPIClient
from .config import Config


class RescueAgentMCP:
    """
    MCP-Enhanced Rescue Agent
    
    Key Differences from v1:
    - Uses MCP servers for real-time flight data
    - Uses MCP servers for weather information
    - LLM can call MCP tools directly for current data
    - More accurate solutions based on actual availability
    """
    
    def __init__(self, use_mock_apis: bool = None):
        """Initialize the MCP-Enhanced Rescue Agent"""
        
        if use_mock_apis is None:
            use_mock_apis = Config.USE_MOCK_APIS
        
        logger.info(f"Initializing MCP-Enhanced Rescue Agent v{Config.AGENT_VERSION}")
        logger.info(f"Mock APIs: {use_mock_apis} | MCP Enabled: {Config.USE_MCP}")
        
        # Initialize components
        self.llm = MCPLLMClient()
        self.api = ExternalAPIClient(use_mock=use_mock_apis)
        self.detector = DisruptionDetector(self.llm)
        self.evaluator = SolutionEvaluator(self.llm, self.api)
        
        # State
        self.active_itineraries: Dict[str, Itinerary] = {}
        self.rescue_attempts: List[RescueAttempt] = []
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        
        # MCP initialization flag
        self.mcp_initialized = False
        
        logger.info("Rescue Agent MCP initialized successfully")
    
    async def start(self):
        """
        Start the agent and initialize MCP connections
        
        Call this before using the agent!
        """
        if Config.USE_MCP and not self.mcp_initialized:
            logger.info("Initializing MCP servers...")
            try:
                await self.llm.initialize_mcp_servers()
                self.mcp_initialized = True
                logger.info("✅ MCP servers connected and ready")
            except Exception as e:
                logger.error(f"MCP initialization failed: {e}")
                logger.warning("Continuing without MCP - will use fallback data")
        else:
            logger.info("MCP disabled - using standard mode")
    
    async def register_itinerary(self, itinerary: Itinerary) -> str:
        """
        Register an itinerary for monitoring
        
        Args:
            itinerary: The itinerary to monitor
            
        Returns:
            Monitoring ID
        """
        itinerary_id = itinerary.trip_id
        self.active_itineraries[itinerary_id] = itinerary
        
        logger.info(f"Registered itinerary {itinerary_id} with {len(itinerary.legs)} legs")
        
        # Start monitoring
        task = asyncio.create_task(self._monitor_itinerary(itinerary))
        self.monitoring_tasks[itinerary_id] = task
        
        return itinerary_id
    
    async def _monitor_itinerary(self, itinerary: Itinerary):
        """Monitor an itinerary for disruptions"""
        logger.info(f"Started monitoring itinerary {itinerary.trip_id}")
        
        try:
            while True:
                # Determine polling interval
                first_leg = itinerary.legs[0]
                time_until_trip = (first_leg.departure_time - datetime.now()).total_seconds()
                
                if time_until_trip < 7200:
                    interval = Config.POLLING_INTERVAL_CRITICAL
                elif time_until_trip < 172800:
                    interval = Config.POLLING_INTERVAL_UPCOMING
                else:
                    interval = Config.POLLING_INTERVAL_FUTURE
                
                # Check each flight
                for leg in itinerary.legs:
                    if leg.departure_time > datetime.now():
                        disruption = await self.api.monitor_flight(leg.flight_number)
                        
                        if disruption:
                            logger.warning(f"Disruption detected: {disruption.description}")
                            await self.handle_disruption(disruption, itinerary)
                
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            logger.info(f"Monitoring cancelled for {itinerary.trip_id}")
        except Exception as e:
            logger.error(f"Error monitoring itinerary {itinerary.trip_id}: {e}")
    
    async def handle_disruption(
        self,
        event: DisruptionEvent,
        itinerary: Itinerary,
        user_preferences: Optional[UserPreferences] = None
    ) -> List[Solution]:
        """
        Handle a detected disruption using MCP-enhanced analysis
        
        The LLM will use MCP tools to:
        - Get real-time flight status
        - Search for actual alternative flights
        - Check weather conditions
        - Verify availability
        
        Args:
            event: The disruption event
            itinerary: The affected itinerary
            user_preferences: User preferences for solutions
            
        Returns:
            List of ranked solutions based on REAL data
        """
        logger.info(f"Handling disruption: {event.type.value}")
        
        if user_preferences is None:
            user_preferences = UserPreferences()
        
        # Step 1: Detect and classify
        detection = self.detector.detect_flight_delay(event, itinerary)
        
        if not detection:
            logger.info("No significant disruption detected")
            return []
        
        if not self.detector.validate_disruption(detection):
            logger.info("Disruption did not pass validation threshold")
            return []
        
        logger.info(f"Disruption classified as {detection.severity.value}")
        
        # Check for cascading effects
        if detection.cascading:
            cascading = self.detector.detect_cascading_effect(detection, itinerary)
            if cascading:
                detection = cascading
                logger.warning(f"Cascading disruption affecting {len(detection.affected_legs)} legs")
        
        # Step 2: Generate solutions using MCP-enhanced LLM
        logger.info("🔧 Using MCP-enhanced analysis for REAL-TIME data")
        
        solutions = await self.evaluator.generate_solutions(
            disruption=detection,
            itinerary=itinerary,
            user_preferences=user_preferences
        )
        
        if not solutions:
            logger.error("No solutions generated - escalating")
            solutions = [self._create_manual_escalation_solution()]
        
        logger.info(f"Generated {len(solutions)} solution(s) using real-time data")
        
        # Step 3: Record rescue attempt
        attempt = RescueAttempt(
            id=str(uuid4()),
            disruption_id=event.id,
            itinerary_id=itinerary.trip_id,
            timestamp=datetime.now(),
            solutions_generated=solutions
        )
        self.rescue_attempts.append(attempt)
        
        return solutions
    
    def _create_manual_escalation_solution(self) -> Solution:
        """Fallback solution for manual escalation"""
        return Solution(
            strategy="MANUAL_ESCALATION",
            description="Contact customer support for personalized assistance",
            cost_impact=0.0,
            time_impact=0,
            pros=["Expert human assistance", "Personalized solution"],
            cons=["Requires phone/email contact", "May take longer"],
            confidence=1.0,
            requires_user_action=[
                "Contact support at 1-800-TRAVEL",
                "Provide trip ID and disruption details"
            ],
            urgency="immediate"
        )
    
    async def approve_solution(self, attempt_id: str, solution_strategy: str) -> bool:
        """Record user approval of a solution"""
        attempt = None
        for a in self.rescue_attempts:
            if a.id == attempt_id:
                attempt = a
                break
        
        if not attempt:
            logger.error(f"Rescue attempt {attempt_id} not found")
            return False
        
        attempt.user_selected_solution = solution_strategy
        attempt.outcome = "resolved"
        
        logger.info(f"User approved solution: {solution_strategy}")
        return True
    
    async def shutdown(self):
        """Gracefully shutdown the agent and MCP connections"""
        logger.info("Shutting down MCP-Enhanced Rescue Agent")
        
        # Cancel monitoring tasks
        for task in self.monitoring_tasks.values():
            task.cancel()
        
        await asyncio.gather(*self.monitoring_tasks.values(), return_exceptions=True)
        
        # Close MCP connections
        if self.mcp_initialized:
            await self.llm.shutdown()
        
        logger.info("Shutdown complete")

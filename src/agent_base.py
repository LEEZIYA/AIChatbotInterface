"""
Main Rescue Agent implementation
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
from .llm_client import LLMClient
from .external_apis import ExternalAPIClient
from .config import Config


class RescueAgent:
    """
    Main Rescue Agent class
    
    Coordinates disruption detection, solution generation,
    and user notification for travel disruptions.
    """
    
    def __init__(self, use_mock_apis: bool = None):
        """Initialize the Rescue Agent"""
        
        if use_mock_apis is None:
            use_mock_apis = Config.USE_MOCK_APIS
        
        logger.info(f"Initializing Rescue Agent (mock APIs: {use_mock_apis})")
        
        # Initialize components
        self.llm = LLMClient()
        self.api = ExternalAPIClient(use_mock=use_mock_apis)
        self.detector = DisruptionDetector(self.llm)
        self.evaluator = SolutionEvaluator(self.llm, self.api)
        
        # State
        self.active_itineraries: Dict[str, Itinerary] = {}
        self.rescue_attempts: List[RescueAttempt] = []
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        
        logger.info("Rescue Agent initialized successfully")
    
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
        """
        Monitor an itinerary for disruptions
        
        This runs continuously until the trip is complete or cancelled.
        """
        logger.info(f"Started monitoring itinerary {itinerary.trip_id}")
        
        try:
            while True:
                # Determine polling interval based on trip proximity
                first_leg = itinerary.legs[0]
                time_until_trip = (first_leg.departure_time - datetime.now()).total_seconds()
                
                if time_until_trip < 7200:  # Within 2 hours
                    interval = Config.POLLING_INTERVAL_CRITICAL
                elif time_until_trip < 172800:  # Within 2 days
                    interval = Config.POLLING_INTERVAL_UPCOMING
                else:
                    interval = Config.POLLING_INTERVAL_FUTURE
                
                # Check each flight
                for leg in itinerary.legs:
                    # Only monitor upcoming flights
                    if leg.departure_time > datetime.now():
                        disruption = await self.api.monitor_flight(leg.flight_number)
                        
                        if disruption:
                            logger.warning(f"Disruption detected: {disruption.description}")
                            await self.handle_disruption(disruption, itinerary)
                
                # Wait before next check
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
        Handle a detected disruption
        
        This is the main rescue workflow:
        1. Detect and classify the disruption
        2. Generate solution alternatives
        3. Rank solutions
        4. Return for user approval
        
        Args:
            event: The disruption event
            itinerary: The affected itinerary
            user_preferences: User preferences for solutions
            
        Returns:
            List of ranked solutions
        """
        logger.info(f"Handling disruption: {event.type.value}")
        
        # Use default preferences if not provided
        if user_preferences is None:
            user_preferences = UserPreferences()
        
        # Step 1: Detect and classify
        detection = self.detector.detect_flight_delay(event, itinerary)
        
        if not detection:
            logger.info("No significant disruption detected")
            return []
        
        # Validate disruption
        if not self.detector.validate_disruption(detection):
            logger.info("Disruption did not pass validation threshold")
            return []
        
        logger.info(f"Disruption classified as {detection.severity.value}")
        
        # Check for cascading effects
        if detection.cascading:
            cascading = self.detector.detect_cascading_effect(detection, itinerary)
            if cascading:
                detection = cascading
                logger.warning(f"Cascading disruption detected affecting {len(detection.affected_legs)} legs")
        
        # Step 2: Generate solutions
        solutions = await self.evaluator.generate_solutions(
            disruption=detection,
            itinerary=itinerary,
            user_preferences=user_preferences
        )
        
        if not solutions:
            logger.error("No solutions generated - escalating to manual handling")
            solutions = [self._create_manual_escalation_solution()]
        
        logger.info(f"Generated {len(solutions)} solution(s)")
        
        # Step 3: Record rescue attempt
        attempt = RescueAttempt(
            id=str(uuid4()),
            disruption_id=event.id,
            itinerary_id=itinerary.trip_id,
            timestamp=datetime.now(),
            solutions_generated=solutions
        )
        self.rescue_attempts.append(attempt)
        
        # Step 4: Return solutions for user approval
        return solutions
    
    async def handle_disruption_with_llm(
        self,
        events: List[DisruptionEvent],
        itinerary: Itinerary,
        user_preferences: Optional[UserPreferences] = None
    ) -> List[Solution]:
        """
        Handle complex disruptions using LLM reasoning
        
        Use this for:
        - Multiple simultaneous disruptions
        - Unclear patterns
        - Edge cases
        """
        logger.info("Using LLM for complex disruption handling")
        
        if user_preferences is None:
            user_preferences = UserPreferences()
        
        # Use LLM for detection
        detections = await self.detector.detect_with_llm(events, itinerary)
        
        if not detections:
            return []
        
        # Pick highest severity detection
        detection = max(detections, key=lambda d: ["low", "medium", "high", "critical"].index(d.severity.value))
        
        # Generate solutions
        solutions = await self.evaluator.generate_solutions(
            disruption=detection,
            itinerary=itinerary,
            user_preferences=user_preferences
        )
        
        return solutions
    
    def _create_manual_escalation_solution(self) -> Solution:
        """Create a fallback solution for manual escalation"""
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
    
    async def approve_solution(
        self,
        attempt_id: str,
        solution_strategy: str
    ) -> bool:
        """
        Record user approval of a solution
        
        Args:
            attempt_id: The rescue attempt ID
            solution_strategy: The strategy name that was approved
            
        Returns:
            Success status
        """
        # Find the attempt
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
        
        # In a real system, this would trigger booking actions
        # For now, just log
        logger.info("Solution approved - in production, would execute booking")
        
        return True
    
    async def reject_all_solutions(self, attempt_id: str) -> bool:
        """
        Record user rejection of all solutions
        
        This typically results in manual escalation.
        """
        attempt = None
        for a in self.rescue_attempts:
            if a.id == attempt_id:
                attempt = a
                break
        
        if not attempt:
            return False
        
        attempt.outcome = "escalated"
        attempt.notes = "User rejected all automated solutions"
        
        logger.info(f"User rejected all solutions for attempt {attempt_id} - escalating")
        
        return True
    
    def get_rescue_history(self, itinerary_id: str) -> List[RescueAttempt]:
        """Get all rescue attempts for an itinerary"""
        return [a for a in self.rescue_attempts if a.itinerary_id == itinerary_id]
    
    async def stop_monitoring(self, itinerary_id: str):
        """Stop monitoring an itinerary"""
        if itinerary_id in self.monitoring_tasks:
            task = self.monitoring_tasks[itinerary_id]
            task.cancel()
            await task
            del self.monitoring_tasks[itinerary_id]
            logger.info(f"Stopped monitoring {itinerary_id}")
    
    async def shutdown(self):
        """Gracefully shutdown the agent"""
        logger.info("Shutting down Rescue Agent")
        
        # Cancel all monitoring tasks
        for task in self.monitoring_tasks.values():
            task.cancel()
        
        # Wait for all tasks to complete
        await asyncio.gather(*self.monitoring_tasks.values(), return_exceptions=True)
        
        logger.info("Rescue Agent shut down complete")

"""
Disruption detection service
"""
from datetime import datetime, timedelta
from typing import Optional, List
from loguru import logger
from .models import (
    DisruptionEvent, DisruptionDetection, Itinerary,
    FlightLeg, Severity, DisruptionType
)
from .llm_client import MCPLLMClient as LLMClient

class DisruptionDetector:
    """Detects and classifies travel disruptions"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.rules = {
            "flight_delay": self.detect_flight_delay,
            "cascading_delays": self.detect_cascading_effect,
        }
    
    def detect_flight_delay(
        self,
        event: DisruptionEvent,
        itinerary: Itinerary
    ) -> Optional[DisruptionDetection]:
        """Detect if a flight delay causes missed connections"""
        
        if event.type != DisruptionType.FLIGHT_DELAY:
            return None
        
        affected_flight = event.flight_number
        delay_minutes = event.delay_duration or 0
        
        # Find this flight in itinerary
        flight_leg = itinerary.get_flight(affected_flight)
        if not flight_leg:
            logger.debug(f"Flight {affected_flight} not in itinerary")
            return None
        
        # Check if there's a connection
        next_leg = itinerary.get_next_leg(flight_leg)
        if not next_leg:
            # Last leg - delay doesn't affect connections
            return DisruptionDetection(
                type=DisruptionType.FLIGHT_DELAY,
                severity=Severity.LOW,
                affected_legs=[flight_leg.id],
                reasoning="Delay on final leg - no connections affected",
                cascading=False,
                user_action_required=False,
                confidence=1.0
            )
        
        # Calculate new arrival time
        new_arrival = flight_leg.arrival_time + timedelta(minutes=delay_minutes)
        connection_time = (next_leg.departure_time - new_arrival).total_seconds() / 60
        
        # Minimum connection time
        min_connection = next_leg.minimum_connection_time
        
        if connection_time < min_connection:
            # Connection at risk or missed
            severity = Severity.CRITICAL if connection_time < 0 else Severity.HIGH
            
            return DisruptionDetection(
                type=DisruptionType.FLIGHT_DELAY,
                severity=severity,
                affected_legs=[flight_leg.id, next_leg.id],
                reasoning=f"Delay of {delay_minutes}min leaves only {int(connection_time)}min "
                         f"connection time (minimum: {min_connection}min)",
                cascading=True,
                user_action_required=True,
                confidence=0.95
            )
        
        # Delay but adequate buffer
        return DisruptionDetection(
            type=DisruptionType.FLIGHT_DELAY,
            severity=Severity.LOW,
            affected_legs=[flight_leg.id],
            reasoning=f"Delay within acceptable range ({int(connection_time)}min buffer remaining)",
            cascading=False,
            user_action_required=False,
            confidence=0.9
        )
    
    def detect_cascading_effect(
        self,
        initial_detection: DisruptionDetection,
        itinerary: Itinerary
    ) -> Optional[DisruptionDetection]:
        """
        Detect if one disruption triggers cascading failures
        
        This walks through subsequent legs to see if the initial disruption
        creates a domino effect.
        """
        if not initial_detection.cascading:
            return None
        
        affected_legs = []
        current_delay = 0
        
        # Find the first affected leg
        first_leg_id = initial_detection.affected_legs[0]
        start_idx = None
        for i, leg in enumerate(itinerary.legs):
            if leg.id == first_leg_id:
                start_idx = i
                break
        
        if start_idx is None:
            return None
        
        # Simulate delay propagation
        for i in range(start_idx, len(itinerary.legs)):
            leg = itinerary.legs[i]
            
            if i == start_idx:
                # Initial disrupted leg
                affected_legs.append(leg.id)
                # Extract delay from detection reasoning or assume worst case
                current_delay = 180  # Default assumption
                continue
            
            # Calculate if this leg is affected
            prev_leg = itinerary.legs[i-1]
            
            # Adjusted arrival time of previous leg
            adjusted_arrival = prev_leg.arrival_time + timedelta(minutes=current_delay)
            
            # Connection time
            connection_time = (leg.departure_time - adjusted_arrival).total_seconds() / 60
            
            if connection_time < leg.minimum_connection_time:
                # This leg is now affected
                affected_legs.append(leg.id)
                
                # Delay propagates
                shortfall = leg.minimum_connection_time - connection_time
                current_delay += shortfall
            else:
                # Chain breaks - sufficient buffer
                break
        
        if len(affected_legs) > 1:
            return DisruptionDetection(
                type=DisruptionType.FLIGHT_DELAY,
                severity=Severity.CRITICAL,
                affected_legs=affected_legs,
                reasoning=f"Cascading disruption affects {len(affected_legs)} legs",
                cascading=True,
                user_action_required=True,
                confidence=0.85
            )
        
        return None
    
    async def detect_with_llm(
        self,
        events: List[DisruptionEvent],
        itinerary: Itinerary
    ) -> List[DisruptionDetection]:
        """Use LLM for complex pattern detection"""
        
        logger.info("Using LLM for complex disruption detection")
        
        # Convert to dict for JSON serialization
        events_dict = [
            {
                "type": e.type.value,
                "flight_number": e.flight_number,
                "delay_minutes": e.delay_duration,
                "description": e.description,
                "timestamp": e.timestamp.isoformat()
            }
            for e in events
        ]
        
        result = await self.llm.detect_complex_disruption(
            events=events_dict,
            itinerary=itinerary.to_summary()
        )
        
        # Convert LLM response to DisruptionDetection objects
        detections = []
        for d in result.get("disruptions_detected", []):
            try:
                detection = DisruptionDetection(
                    type=DisruptionType(d["type"]),
                    severity=Severity(d["severity"]),
                    affected_legs=d.get("affected_legs", []),
                    reasoning=d.get("reasoning", ""),
                    cascading=d.get("cascading", False),
                    user_action_required=True,
                    confidence=d.get("confidence", 0.7)
                )
                detections.append(detection)
            except Exception as e:
                logger.error(f"Failed to parse LLM detection: {e}")
                continue
        
        return detections
    
    def validate_disruption(self, detection: DisruptionDetection) -> bool:
        """Validate if disruption should trigger user notification"""
        
        # Low confidence + low severity = skip
        if detection.confidence < 0.7 and detection.severity in [Severity.LOW, Severity.MEDIUM]:
            logger.info(f"Skipping low-confidence disruption: {detection.reasoning}")
            return False
        
        # Very low confidence = flag for review
        if detection.confidence < 0.5:
            logger.warning(f"Very low confidence disruption flagged for review: {detection.reasoning}")
            return False
        
        return True

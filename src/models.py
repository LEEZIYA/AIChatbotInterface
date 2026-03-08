"""
Data models for the Rescue Agent
"""
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum


class DisruptionType(str, Enum):
    FLIGHT_DELAY = "FLIGHT_DELAY"
    FLIGHT_CANCELLATION = "FLIGHT_CANCELLATION"
    WEATHER_SEVERE = "WEATHER_SEVERE"
    NATURAL_DISASTER = "NATURAL_DISASTER"
    SECURITY_ALERT = "SECURITY_ALERT"
    TRANSPORT_STRIKE = "TRANSPORT_STRIKE"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FlightLeg(BaseModel):
    """Represents a single flight segment"""
    id: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    airline: str
    flight_number: str
    cost: float = 0.0
    international: bool = False
    minimum_connection_time: int = 90  # minutes


class Itinerary(BaseModel):
    """User's complete travel itinerary"""
    user_id: str
    trip_id: str
    legs: List[FlightLeg]
    version: int = 1
    
    def get_flight(self, flight_number: str) -> Optional[FlightLeg]:
        """Find a flight leg by flight number"""
        for leg in self.legs:
            if leg.flight_number == flight_number:
                return leg
        return None
    
    def get_next_leg(self, current_leg: FlightLeg) -> Optional[FlightLeg]:
        """Get the next leg after the current one"""
        try:
            idx = self.legs.index(current_leg)
            if idx < len(self.legs) - 1:
                return self.legs[idx + 1]
        except ValueError:
            pass
        return None
    
    def to_summary(self) -> str:
        """Generate human-readable summary"""
        summary = f"Trip ID: {self.trip_id}\n"
        for i, leg in enumerate(self.legs, 1):
            summary += f"Leg {i}: {leg.origin} → {leg.destination} "
            summary += f"({leg.airline} {leg.flight_number}) "
            summary += f"Departs: {leg.departure_time.strftime('%Y-%m-%d %H:%M')}\n"
        return summary


class DisruptionEvent(BaseModel):
    """Represents a detected disruption"""
    id: str
    type: DisruptionType
    timestamp: datetime
    flight_number: Optional[str] = None
    location: Optional[str] = None
    delay_duration: Optional[int] = None  # minutes
    description: str
    source: str = "unknown"
    raw_data: Dict[str, Any] = {}


class DisruptionDetection(BaseModel):
    """Result of disruption detection"""
    type: DisruptionType
    severity: Severity
    affected_legs: List[str]
    reasoning: str
    cascading: bool = False
    user_action_required: bool = True
    confidence: float = Field(ge=0.0, le=1.0)


class AlternativeFlight(BaseModel):
    """Alternative flight option"""
    origin: str
    destination: str
    airline: str
    flight_number: str
    departure_time: datetime
    arrival_time: datetime
    cost: float
    availability: Literal["available", "limited", "waitlist"] = "available"
    stops: int = 0
    duration_minutes: int


class Solution(BaseModel):
    """A proposed solution to a disruption"""
    strategy: str
    description: str
    cost_impact: float  # Delta from original
    time_impact: int  # Minutes delta from original
    pros: List[str]
    cons: List[str]
    preserves_itinerary: bool = False
    booking_details: Optional[Dict[str, Any]] = None
    confidence: float = Field(ge=0.0, le=1.0)
    requires_user_action: List[str] = []
    urgency: Literal["immediate", "within_hour", "within_day", "low"] = "within_hour"
    score: float = 0.0  # Ranking score


class UserPreferences(BaseModel):
    """User preferences for solution generation"""
    priority: Literal["cost", "time", "convenience", "balanced"] = "balanced"
    budget: Literal["low", "medium", "high", "unlimited"] = "medium"
    risk_tolerance: Literal["low", "medium", "high"] = "medium"
    companions: str = "solo"
    max_acceptable_delay: int = 180  # minutes
    

class RescueAttempt(BaseModel):
    """Record of a rescue attempt"""
    id: str
    disruption_id: str
    itinerary_id: str
    timestamp: datetime
    solutions_generated: List[Solution]
    user_selected_solution: Optional[str] = None
    outcome: Optional[Literal["resolved", "escalated", "cancelled"]] = None
    notes: str = ""

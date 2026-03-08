"""
Solution evaluation and generation service
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from loguru import logger
from .models import (
    Solution, DisruptionDetection, Itinerary,
    UserPreferences, AlternativeFlight
)
from .llm_client import MCPLLMClient as LLMClient
from .external_apis import ExternalAPIClient


class SolutionEvaluator:
    """Generates and ranks solution alternatives"""
    
    def __init__(self, llm_client: LLMClient, api_client: ExternalAPIClient):
        self.llm = llm_client
        self.api = api_client
        self.strategies = [
            self.strategy_rebooking,
            self.strategy_accept_delay,
        ]
   
    def _safe_float(self, value, default=0.0):
        """Safely convert value to float, handling strings like 'TBD'"""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Handle common non-numeric strings
            if value.lower() in ['tbd', 'to be determined', 'n/a', 'unknown', '']:
                return default
            try:
                return float(value)
            except ValueError:
                return default
        return default
    
    def _safe_int(self, value, default=0):
        """Safely convert value to int, handling strings like 'TBD'"""
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            # Handle common non-numeric strings
            if value.lower() in ['tbd', 'to be determined', 'n/a', 'unknown', '']:
                return default
            try:
                return int(float(value))  # Handle "123.5" strings
            except ValueError:
                return default
        return default
    
    async def generate_solutions(
        self,
        disruption: DisruptionDetection,
        itinerary: Itinerary,
        user_preferences: UserPreferences
    ) -> List[Solution]:
        """
        Generate multiple solution options
        
        This is the main entry point for solution generation.
        """
        logger.info(f"Generating solutions for {disruption.type.value} disruption")
        
        solutions = []
        
        # Try rule-based strategies first
        for strategy in self.strategies:
            try:
                solution = await strategy(disruption, itinerary, user_preferences)
                if solution:
                    solutions.append(solution)
            except Exception as e:
                logger.error(f"Strategy {strategy.__name__} failed: {e}")
        
        # If we have good solutions, skip LLM to save cost
        if len(solutions) >= 2 and all(s.confidence > 0.8 for s in solutions):
            logger.info("Using rule-based solutions only")
        else:
            # Use LLM for complex reasoning
            logger.info("Calling LLM for additional solution analysis")
            llm_solution = await self.generate_with_llm(
                disruption, itinerary, user_preferences
            )
            if llm_solution:
                solutions.extend(llm_solution)
        
        # Rank all solutions
        ranked = self.rank_solutions(solutions, user_preferences)
        
        # Return top 3
        return ranked[:3]
    
    async def strategy_rebooking(
        self,
        disruption: DisruptionDetection,
        itinerary: Itinerary,
        prefs: UserPreferences
    ) -> Optional[Solution]:
        """Find alternative flights on same route"""
        
        # Get the affected leg
        if not disruption.affected_legs:
            return None
        
        affected_leg_id = disruption.affected_legs[0]
        affected_leg = None
        for leg in itinerary.legs:
            if leg.id == affected_leg_id:
                affected_leg = leg
                break
        
        if not affected_leg:
            return None
        
        logger.debug(f"Finding rebooking options for {affected_leg.origin} -> {affected_leg.destination}")
        
        # Search for alternatives
        alternatives = await self.api.search_alternative_flights(
            origin=affected_leg.origin,
            destination=affected_leg.destination,
            departure_after=datetime.now() + timedelta(hours=1),
            max_results=3
        )
        
        if not alternatives:
            return None
        
        # Pick best alternative
        best = alternatives[0]
        
        # Calculate impacts
        cost_delta = best.cost - affected_leg.cost
        time_delta = int((best.arrival_time - affected_leg.arrival_time).total_seconds() / 60)
        
        # Check if it preserves rest of itinerary
        next_leg = itinerary.get_next_leg(affected_leg)
        preserves = True
        if next_leg:
            connection_time = (next_leg.departure_time - best.arrival_time).total_seconds() / 60
            preserves = connection_time >= next_leg.minimum_connection_time
        
        pros = [
            "Same route - direct flight" if best.stops == 0 else "Minimal stops",
            f"Arrives at {best.arrival_time.strftime('%H:%M')}",
        ]
        
        if preserves:
            pros.append("Preserves rest of itinerary")
        
        cons = []
        if cost_delta > 0:
            cons.append(f"Additional cost: ${cost_delta:.2f}")
        if time_delta > 0:
            cons.append(f"Arrives {time_delta} minutes later")
        if best.availability != "available":
            cons.append(f"Limited availability")
        
        return Solution(
            strategy="REBOOKING",
            description=f"Rebook on {best.airline} flight {best.flight_number}",
            cost_impact=cost_delta,
            time_impact=time_delta,
            pros=pros,
            cons=cons if cons else ["None identified"],
            preserves_itinerary=preserves,
            booking_details={
                "flight_number": best.flight_number,
                "airline": best.airline,
                "departure": best.departure_time.isoformat(),
                "arrival": best.arrival_time.isoformat(),
                "cost": best.cost
            },
            confidence=0.9,
            requires_user_action=[
                "Approve rebooking",
                "Provide payment confirmation"
            ],
            urgency="within_hour"
        )
    
    async def strategy_accept_delay(
        self,
        disruption: DisruptionDetection,
        itinerary: Itinerary,
        prefs: UserPreferences
    ) -> Optional[Solution]:
        """Accept the delay and adjust itinerary accordingly"""
        
        # Don't suggest for critical disruptions
        if disruption.severity.value == "critical":
            return None
        
        # Don't suggest for cancellations
        if "cancell" in disruption.reasoning.lower():
            return None
        
        # Extract delay duration from reasoning (simplified)
        # In production, this should be more robust
        delay = 60  # Default assumption
        if "delay" in disruption.reasoning.lower():
            # Try to extract number
            import re
            match = re.search(r'(\d+)\s*min', disruption.reasoning)
            if match:
                delay = int(match.group(1))
        
        # Check if delay exceeds user's tolerance
        if delay > prefs.max_acceptable_delay:
            return None
        
        adjustments = []
        
        # Simple adjustments
        if delay > 90:
            adjustments.append("Contact hotel for late check-in")
        if delay > 120:
            adjustments.append("Reschedule or cancel evening activities")
        
        pros = [
            "No additional cost",
            "No need to rebook",
            "Stay on same airline",
            "Keep existing seat/preferences"
        ]
        
        cons = [
            f"{delay} minute delay",
            f"{len(adjustments)} adjustments needed" if adjustments else "Minor inconvenience"
        ]
        
        return Solution(
            strategy="ACCEPT_DELAY",
            description=f"Wait for delayed flight (estimated {delay} min delay)",
            cost_impact=0.0,
            time_impact=delay,
            pros=pros,
            cons=cons,
            preserves_itinerary=True,
            confidence=0.8 if len(adjustments) < 2 else 0.6,
            requires_user_action=adjustments if adjustments else ["Monitor flight status"],
            urgency="within_day" if delay < 120 else "within_hour"
        )
    
    async def generate_with_llm(
        self,
        disruption: DisruptionDetection,
        itinerary: Itinerary,
        prefs: UserPreferences
    ) -> List[Solution]:
        """Use LLM for sophisticated solution generation"""
        
        # Prepare disruption dict
        disruption_dict = {
            "type": disruption.type.value,
            "severity": disruption.severity.value,
            "affected_legs": disruption.affected_legs,
            "reasoning": disruption.reasoning,
            "cascading": disruption.cascading
        }
        
        # Prepare preferences dict
        prefs_dict = {
            "priority": prefs.priority,
            "budget": prefs.budget,
            "risk_tolerance": prefs.risk_tolerance,
            "companions": prefs.companions,
            "max_acceptable_delay": prefs.max_acceptable_delay
        }
        
        result = await self.llm.analyze_disruption(
            disruption=disruption_dict,
            itinerary=itinerary.to_summary(),
            user_preferences=prefs_dict
        )
        
        # Convert LLM alternatives to Solution objects
        solutions = []
        for alt in result.get("alternatives", []):
            try:
                solution = Solution(
                    strategy=alt.get("strategy", "LLM_GENERATED"),
    description=alt.get("description", ""),
    cost_impact=self._safe_float(alt.get("cost_delta", 0)),
    time_impact=self._safe_int(alt.get("time_delta", 0)),
    pros=alt.get("pros", []),
    cons=alt.get("cons", []),
    confidence=self._safe_float(alt.get("confidence", 0.7), default=0.7),
    requires_user_action=alt.get("requires_user_action", []),
    urgency=result.get("urgency", "within_hour")
                )
                solutions.append(solution)
            except Exception as e:
                logger.error(f"Failed to parse LLM solution: {e}")
                continue
        
        return solutions
    
    def rank_solutions(
        self,
        solutions: List[Solution],
        user_preferences: UserPreferences
    ) -> List[Solution]:
        """Rank solutions based on user preferences"""
        
        # Define weights based on priority
        if user_preferences.priority == "cost":
            weights = {"cost": 0.5, "time": 0.2, "convenience": 0.15, "confidence": 0.15}
        elif user_preferences.priority == "time":
            weights = {"cost": 0.2, "time": 0.5, "convenience": 0.15, "confidence": 0.15}
        elif user_preferences.priority == "convenience":
            weights = {"cost": 0.2, "time": 0.2, "convenience": 0.4, "confidence": 0.2}
        else:  # balanced
            weights = {"cost": 0.3, "time": 0.3, "convenience": 0.2, "confidence": 0.2}
        
        # Score each solution
        for solution in solutions:
            score = 0
            
            # Cost score (lower is better, normalize to 0-1)
            cost_impact = abs(solution.cost_impact)
            cost_score = 1.0 / (1.0 + cost_impact / 100)
            score += weights["cost"] * cost_score
            
            # Time score (lower is better, normalize to 0-1)
            time_impact = abs(solution.time_impact)
            time_score = 1.0 / (1.0 + time_impact / 60)
            score += weights["time"] * time_score
            
            # Convenience score
            convenience = 1.0 if solution.preserves_itinerary else 0.5
            score += weights["convenience"] * convenience
            
            # Confidence score
            score += weights["confidence"] * solution.confidence
            
            solution.score = score
        
        # Sort by score descending
        return sorted(solutions, key=lambda s: s.score, reverse=True)

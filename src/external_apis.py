"""
Mock external API clients for development and testing
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
import random
from loguru import logger
from .models import AlternativeFlight, DisruptionEvent, DisruptionType


class MockFlightAPI:
    """Mock flight status and search API"""
    
    async def get_flight_status(self, flight_number: str) -> dict:
        """Get current status of a flight"""
        await asyncio.sleep(0.1)  # Simulate network delay
        
        # Randomly generate delays or cancellations
        status_options = [
            {"status": "on_time", "delay": 0},
            {"status": "delayed", "delay": random.randint(30, 180)},
            {"status": "delayed", "delay": random.randint(30, 60)},
            {"status": "on_time", "delay": 0},
            {"status": "cancelled", "delay": None},
        ]
        
        status = random.choice(status_options)
        
        logger.debug(f"Mock flight status for {flight_number}: {status}")
        
        return {
            "flight_number": flight_number,
            "status": status["status"],
            "delay_minutes": status["delay"],
            "timestamp": datetime.now().isoformat()
        }
    
    async def search_alternatives(
        self,
        origin: str,
        destination: str,
        departure_after: datetime,
        max_results: int = 5
    ) -> List[AlternativeFlight]:
        """Search for alternative flights"""
        await asyncio.sleep(0.2)  # Simulate network delay
        
        alternatives = []
        base_time = departure_after
        
        airlines = ["BA", "AA", "DL", "UA", "AF", "LH", "KLM"]
        
        for i in range(max_results):
            # Generate flight departing 1-6 hours after requested time
            hours_offset = random.randint(1, 6)
            dept_time = base_time + timedelta(hours=hours_offset)
            
            # Flight duration between 1-8 hours
            duration = random.randint(60, 480)
            arr_time = dept_time + timedelta(minutes=duration)
            
            # Random pricing
            base_cost = random.randint(200, 800)
            
            airline = random.choice(airlines)
            flight_num = f"{airline}{random.randint(100, 999)}"
            
            alternatives.append(AlternativeFlight(
                origin=origin,
                destination=destination,
                airline=airline,
                flight_number=flight_num,
                departure_time=dept_time,
                arrival_time=arr_time,
                cost=base_cost,
                availability="available" if i < 3 else "limited",
                stops=0 if random.random() > 0.3 else 1,
                duration_minutes=duration
            ))
        
        logger.info(f"Found {len(alternatives)} mock alternative flights")
        return alternatives


class MockWeatherAPI:
    """Mock weather forecast API"""
    
    async def get_forecast(self, location: str, date: datetime) -> dict:
        """Get weather forecast for a location"""
        await asyncio.sleep(0.1)
        
        conditions = ["clear", "cloudy", "rain", "storm", "snow"]
        severities = ["low", "medium", "high"]
        
        condition = random.choice(conditions)
        severity = "low" if condition in ["clear", "cloudy"] else random.choice(severities)
        
        return {
            "location": location,
            "date": date.isoformat(),
            "condition": condition,
            "temperature": random.randint(-10, 35),
            "precipitation_chance": random.randint(0, 100),
            "severity": severity,
            "alerts": ["Severe weather warning"] if severity == "high" else []
        }


class MockDisasterAPI:
    """Mock natural disaster monitoring API"""
    
    async def check_alerts(self, location: str) -> List[dict]:
        """Check for natural disaster alerts"""
        await asyncio.sleep(0.1)
        
        # Mostly no alerts, occasionally generate one
        if random.random() < 0.1:  # 10% chance
            alert_types = ["earthquake", "hurricane", "flood", "wildfire"]
            return [{
                "type": random.choice(alert_types),
                "severity": random.choice(["medium", "high", "critical"]),
                "location": location,
                "issued": datetime.now().isoformat(),
                "description": "Mock disaster alert for testing"
            }]
        
        return []


class MockNewsAPI:
    """Mock news API for strike/protest monitoring"""
    
    async def search_travel_disruptions(self, location: str, date: datetime) -> List[dict]:
        """Search for news about travel disruptions"""
        await asyncio.sleep(0.15)
        
        # Occasionally return a strike notice
        if random.random() < 0.05:  # 5% chance
            return [{
                "headline": f"Transportation strike announced in {location}",
                "published": datetime.now().isoformat(),
                "source": "Mock News",
                "summary": "Workers union announced a 24-hour strike affecting public transport",
                "relevance": 0.9
            }]
        
        return []


class ExternalAPIClient:
    """Unified client for all external APIs"""
    
    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock
        
        if use_mock:
            self.flight_api = MockFlightAPI()
            self.weather_api = MockWeatherAPI()
            self.disaster_api = MockDisasterAPI()
            self.news_api = MockNewsAPI()
            logger.info("Using mock external APIs")
        else:
            # TODO: Initialize real API clients here
            logger.warning("Real API clients not implemented yet - falling back to mocks")
            self.flight_api = MockFlightAPI()
            self.weather_api = MockWeatherAPI()
            self.disaster_api = MockDisasterAPI()
            self.news_api = MockNewsAPI()
    
    async def monitor_flight(self, flight_number: str) -> Optional[DisruptionEvent]:
        """Monitor a flight and return disruption if detected"""
        status = await self.flight_api.get_flight_status(flight_number)
        
        if status["status"] == "cancelled":
            return DisruptionEvent(
                id=f"disruption_{datetime.now().timestamp()}",
                type=DisruptionType.FLIGHT_CANCELLATION,
                timestamp=datetime.now(),
                flight_number=flight_number,
                description=f"Flight {flight_number} has been cancelled",
                source="flight_api"
            )
        
        if status["status"] == "delayed" and status["delay_minutes"] >= 30:
            return DisruptionEvent(
                id=f"disruption_{datetime.now().timestamp()}",
                type=DisruptionType.FLIGHT_DELAY,
                timestamp=datetime.now(),
                flight_number=flight_number,
                delay_duration=status["delay_minutes"],
                description=f"Flight {flight_number} delayed by {status['delay_minutes']} minutes",
                source="flight_api"
            )
        
        return None
    
    async def search_alternative_flights(
        self,
        origin: str,
        destination: str,
        departure_after: datetime,
        max_results: int = 5
    ) -> List[AlternativeFlight]:
        """Search for alternative flight options"""
        return await self.flight_api.search_alternatives(
            origin, destination, departure_after, max_results
        )
    
    async def check_weather(self, location: str, date: datetime) -> dict:
        """Check weather forecast"""
        return await self.weather_api.get_forecast(location, date)
    
    async def check_disasters(self, location: str) -> List[dict]:
        """Check for natural disasters"""
        return await self.disaster_api.check_alerts(location)
    
    async def check_news(self, location: str, date: datetime) -> List[dict]:
        """Check news for disruptions"""
        return await self.news_api.search_travel_disruptions(location, date)

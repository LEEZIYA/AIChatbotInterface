import os
import json
import requests
from typing import Optional
from dataclasses import dataclass, asdict
from openai import OpenAI


@dataclass
class Activity:
    name: str
    kind: str
    description: str
    address: Optional[str]
    latitude: float
    longitude: float
    rating: Optional[float]
    xid: str


class ActivityFetcher:
    
    BASE_URL = "https://api.opentripmap.com/0.1/en/places"
    
    def __init__(self, api_key: str, debug: bool = True):
        self.api_key = api_key
        self.debug = debug
    
    def _log(self, message: str):
        if self.debug:
            print(f"[DEBUG] {message}")
    
    def get_activities(
        self,
        destination: str,
        radius: int = 20000,
        limit: int = 15,
        kinds: Optional[str] = None
    ) -> list[Activity]:
        self._log(f"Searching for activities in: {destination}")
        
        coords = self._get_coordinates(destination)
        if not coords:
            self._log(f"Could not find coordinates for: {destination}")
            return []
        
        lat, lon = coords
        self._log(f"Found coordinates: {lat}, {lon}")
        
        places = self._get_places_by_radius(lat, lon, radius, limit, kinds)
        self._log(f"Found {len(places)} places from API")
        
        activities = []
        for place in places:
            activity = self._get_place_details(place.get("xid"))
            if activity:
                if activity.name and activity.name != "Unknown":
                    activities.append(activity)
                    self._log(f"  - {activity.name} ({activity.kind})")
                else:
                    self._log(f"  - Skipped unnamed place: {place.get('xid')}")
        
        self._log(f"Returning {len(activities)} activities with details")
        return activities
    
    def _get_coordinates(self, place_name: str) -> Optional[tuple[float, float]]:
        url = f"{self.BASE_URL}/geoname"
        params = {"name": place_name, "apikey": self.api_key}
        
        try:
            response = requests.get(url, params=params, timeout=10)
            self._log(f"Geoname API status: {response.status_code}")
            
            if response.status_code != 200:
                self._log(f"Geoname API error: {response.text}")
                return None
                
            data = response.json()
            
            if "error" in data:
                self._log(f"API returned error: {data['error']}")
                return None
                
            if "lat" in data and "lon" in data:
                return (data["lat"], data["lon"])
            
            self._log(f"No coordinates in response: {data}")
            return None
        except requests.RequestException as e:
            self._log(f"Request error: {e}")
            return None
    
    def _get_places_by_radius(
        self, lat: float, lon: float, radius: int, limit: int, kinds: Optional[str]
    ) -> list[dict]:
        url = f"{self.BASE_URL}/radius"
        params = {
            "lat": lat, "lon": lon, "radius": radius,
            "limit": limit, "apikey": self.api_key,
            "rate": "1",
            "format": "json"
        }
        if kinds:
            params["kinds"] = kinds
            self._log(f"Filtering by category: {kinds}")
        
        try:
            response = requests.get(url, params=params, timeout=10)
            self._log(f"Radius API status: {response.status_code}")
            
            if response.status_code != 200:
                self._log(f"Radius API error: {response.text}")
                return []
            
            data = response.json()
            
            if isinstance(data, dict) and "error" in data:
                self._log(f"API returned error: {data['error']}")
                return []
            
            return data if isinstance(data, list) else []
        except requests.RequestException as e:
            self._log(f"Request error: {e}")
            return []
    
    def _get_place_details(self, xid: str) -> Optional[Activity]:
        if not xid:
            return None
            
        url = f"{self.BASE_URL}/xid/{xid}"
        params = {"apikey": self.api_key}
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return None
                
            data = response.json()
            
            address = None
            if "address" in data:
                addr_parts = [str(data["address"].get(k, "")) for k in ["road", "city", "country"] if data["address"].get(k)]
                address = ", ".join(addr_parts) if addr_parts else None
            
            description = ""
            if "wikipedia_extracts" in data:
                description = data["wikipedia_extracts"].get("text", "")
            elif "info" in data:
                description = data["info"].get("descr", "")
            
            return Activity(
                name=data.get("name", "Unknown"),
                kind=data.get("kinds", "").replace(",", ", "),
                description=description[:300] if description else "No description available",
                address=address,
                latitude=data.get("point", {}).get("lat", 0),
                longitude=data.get("point", {}).get("lon", 0),
                rating=data.get("rate"),
                xid=xid
            )
        except requests.RequestException:
            return None


class ActivityAgent:
    
    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "search_activities",
                "description": "Search for activities, attractions, and things to do at a travel destination. Use this when the user asks about what to do, places to visit, attractions, or activities at a location.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "destination": {
                            "type": "string",
                            "description": "The city or place to search, e.g., 'Paris, France' or 'Tokyo, Japan'"
                        },
                        "category": {
                            "type": "string",
                            "enum": ["museums", "historic", "natural", "architecture", "cultural", "amusements", "sport", "beaches", "restaurants", "cafes", "shops"],
                            "description": "Optional category to filter results. Note: restaurants/cafes may have limited data in some locations."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of results to return (default 5)",
                            "default": 5
                        }
                    },
                    "required": ["destination"]
                }
            }
        }
    ]
    
    SYSTEM_PROMPT = """You are a helpful travel activity assistant. Your job is to help users discover activities, attractions, and things to do at their travel destinations.

When users ask about activities or things to do at a location, use the search_activities function to fetch real data. Then present the results in a friendly, helpful way with:
- Activity name and type
- Brief description
- Location/address if available
- Your personalized recommendation or tip

Be conversational and enthusiastic about travel! If users ask follow-up questions, help them narrow down options based on their interests.

Available activity categories: museums, historic, natural, architecture, cultural, amusements, sport, beaches, restaurants, cafes, shops.

IMPORTANT: 
- If the search returns results, present them even if they're not an exact match. For example, if someone asks for "beach clubs" and you find beaches, present the beaches and explain that beach clubs (commercial venues) aren't in the database but here are nearby beaches they might enjoy.
- The database contains tourist attractions, landmarks, and natural sites - NOT commercial venues like beach clubs, nightclubs, specific restaurants, or bars.
- Always present the results you DO find rather than saying you couldn't find anything."""

    def __init__(self, openai_api_key: str, opentripmap_api_key: str):
        """
        Initialize the Activity Agent.
        
        Args:
            openai_api_key: Your OpenAI API key
            opentripmap_api_key: Your OpenTripMap API key (free at opentripmap.io)
        """
        self.client = OpenAI(api_key=openai_api_key)
        self.fetcher = ActivityFetcher(api_key=opentripmap_api_key)
        self.conversation_history = [
            {"role": "system", "content": self.SYSTEM_PROMPT}
        ]
    
    def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool and return results as string."""
        if tool_name == "search_activities":
            activities = self.fetcher.get_activities(
                destination=arguments["destination"],
                limit=arguments.get("limit", 5),
                kinds=arguments.get("category")
            )
            
            if not activities:
                return json.dumps({"error": f"No activities found for {arguments['destination']}"})
            
            return json.dumps([asdict(a) for a in activities], indent=2)
        
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    
    def _message_to_dict(self, message) -> dict:
        
        msg_dict = {"role": message.role, "content": message.content}
        
        if message.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in message.tool_calls
            ]
        
        return msg_dict
    
    def chat(self, user_message: str) -> str:
        
        self.conversation_history.append({"role": "user", "content": user_message})
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=self.conversation_history,
            tools=self.TOOLS,
            tool_choice="auto"
        )
        
        assistant_message = response.choices[0].message
        
        while assistant_message.tool_calls:
            self.conversation_history.append(self._message_to_dict(assistant_message))
            
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                
                print(f"Searching activities in {arguments.get('destination', 'destination')}...")
                
                result = self._execute_tool(tool_name, arguments)
                
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.conversation_history,
                tools=self.TOOLS,
                tool_choice="auto"
            )
            assistant_message = response.choices[0].message
        
        self.conversation_history.append(self._message_to_dict(assistant_message))
        return assistant_message.content
    


def main():
    
    openai_key = "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"
    opentripmap_key = "5ae2e3f221c38a28845f05b62d9587e658f99c85a01b435568bf721e"

    agent = ActivityAgent(
        openai_api_key=openai_key,
        opentripmap_api_key=opentripmap_key
    )
    
    print("  - What can I do in Paris?")
    print("  - Find me museums in Rome")
    print("  - What are the best beaches in Bali?")
    print("  - I want outdoor activities in Tokyo")
    print("\nType 'quit' to exit\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == "quit":
                print("\nBYE")
                break
            
            
            response = agent.chat(user_input)
            print(f"\nAgent: {response}\n")
            
        except KeyboardInterrupt:
            print("\n\nBYE")
            break


if __name__ == "__main__":
    main()

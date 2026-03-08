"""
Simplified MCP-Enhanced LLM Client for Windows

This version uses a simpler approach that works reliably on Windows.
"""
import json
import asyncio
from typing import Optional, Dict, Any, List
from loguru import logger
from openai import AsyncOpenAI

from .config import Config


RESCUE_AGENT_SYSTEM_PROMPT = """
You are a Rescue Agent for TravelBuddy with access to REAL-TIME data tools.

YOUR CAPABILITIES:
- Access real flight status data
- Search for alternative flights with actual availability
- Check weather conditions and forecasts
- Get severe weather alerts
- Provide data-driven recommendations

OUTPUT FORMAT:
Respond in JSON format:
{
    "analysis": "Data-driven assessment",
    "severity": "low|medium|high|critical",
    "data_sources_used": ["list of tools called"],
    "alternatives": [
        {
            "strategy": "REBOOKING|ALTERNATIVE_ROUTE|etc",
            "description": "Specific solution with flight numbers",
            "data_verified": true,
            "pros": ["based on actual data"],
            "cons": ["based on actual constraints"],
            "cost_delta": 100.50,
            "time_delta": 120,
            "confidence": 0.9
        }
    ],
    "recommendation": "Top pick with reasoning",
    "urgency": "immediate|within_hour|within_day|low"
}
"""


class MCPLLMClient:
    """LLM Client with simplified MCP integration for Windows"""
    
    def __init__(self):
        self.openai_client = None
        self.mcp_tools = []
        self.mcp_enabled = Config.USE_MCP
        
        # Initialize OpenAI
        if Config.OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
            logger.info("OpenAI client initialized")
        
        if self.mcp_enabled:
            logger.info("MCP support enabled (simplified mode for Windows)")
            self._register_mcp_tools()
        else:
            logger.warning("MCP disabled - using mock responses")
    
    def _register_mcp_tools(self):
        """Register MCP tools for OpenAI function calling"""
        self.mcp_tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_flight_status",
                    "description": "Get real-time flight status including delays, cancellations, gate info",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "flight_number": {
                                "type": "string",
                                "description": "Flight number (e.g., BA001, UA500)"
                            },
                            "date": {
                                "type": "string",
                                "description": "Flight date in YYYY-MM-DD format (optional)"
                            }
                        },
                        "required": ["flight_number"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_alternative_flights",
                    "description": "Search for alternative flights between two cities with actual availability",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "origin": {
                                "type": "string",
                                "description": "Origin airport code (e.g., JFK, LAX)"
                            },
                            "destination": {
                                "type": "string",
                                "description": "Destination airport code (e.g., LHR, CDG)"
                            },
                            "departure_date": {
                                "type": "string",
                                "description": "Desired departure date YYYY-MM-DD"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 5
                            }
                        },
                        "required": ["origin", "destination", "departure_date"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_weather",
                    "description": "Check weather conditions and forecasts for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name or airport code"
                            },
                            "date": {
                                "type": "string",
                                "description": "Date for forecast YYYY-MM-DD"
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ]
        logger.info(f"Registered {len(self.mcp_tools)} MCP tools")
    
    async def _execute_mcp_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute an MCP tool (simplified - uses mocks for now)"""
        logger.info(f"Executing MCP tool: {tool_name}")
        
        if tool_name == "get_flight_status":
            return await self._get_flight_status(arguments)
        elif tool_name == "search_alternative_flights":
            return await self._search_alternative_flights(arguments)
        elif tool_name == "check_weather":
            return await self._check_weather(arguments)
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
    
    async def _get_flight_status(self, args: dict) -> str:
        """Get flight status (mock implementation)"""
        flight_number = args["flight_number"]
        
        # In production: Call real FlightAware API here
        result = {
            "flight_number": flight_number,
            "status": "delayed",
            "delay_minutes": 180,
            "departure_gate": "B12",
            "scheduled_departure": "2026-03-08T15:00:00",
            "estimated_departure": "2026-03-08T18:00:00",
            "data_source": "mock_flightaware",
            "verified": True
        }
        
        return json.dumps(result)
    
    async def _search_alternative_flights(self, args: dict) -> str:
        """Search for alternative flights (mock implementation)"""
        origin = args["origin"]
        destination = args["destination"]
        
        # In production: Call real flight search API
        result = {
            "origin": origin,
            "destination": destination,
            "alternatives": [
                {
                    "flight_number": "UA123",
                    "airline": "United",
                    "departure": "2026-03-08T14:00:00",
                    "arrival": "2026-03-09T02:00:00",
                    "seats_available": 8,
                    "price_usd": 523,
                    "verified": True
                },
                {
                    "flight_number": "AA456",
                    "airline": "American",
                    "departure": "2026-03-08T16:00:00",
                    "arrival": "2026-03-09T04:00:00",
                    "seats_available": 3,
                    "price_usd": 487,
                    "verified": True
                }
            ],
            "data_source": "mock_amadeus",
            "search_timestamp": "2026-03-08T09:00:00"
        }
        
        return json.dumps(result)
    
    async def _check_weather(self, args: dict) -> str:
        """Check weather (mock implementation)"""
        location = args["location"]
        
        # In production: Call real OpenWeather API
        result = {
            "location": location,
            "temperature_f": 72,
            "conditions": "Partly Cloudy",
            "precipitation_chance": 20,
            "wind_mph": 8,
            "severe_alerts": False,
            "data_source": "mock_openweather",
            "verified": True
        }
        
        return json.dumps(result)
    
    async def analyze_disruption(
        self,
        disruption: Dict[str, Any],
        itinerary: str,
        user_preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze disruption using LLM with MCP tools
        """
        if not self.openai_client:
            return self._mock_analysis()
        
        prompt = f"""
DISRUPTION DETECTED:
{json.dumps(disruption, indent=2, default=str)}

CURRENT ITINERARY:
{itinerary}

USER PREFERENCES:
{json.dumps(user_preferences, indent=2)}

IMPORTANT: Use the available tools to get REAL data:
1. Check flight status with get_flight_status
2. Search for alternatives with search_alternative_flights  
3. Check weather conditions with check_weather
4. Base recommendations on ACTUAL data

Provide a data-driven analysis with concrete alternatives.
"""
        
        messages = [
            {"role": "system", "content": RESCUE_AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        tools = self.mcp_tools if self.mcp_enabled else None
        
        try:
            logger.info(f"Calling GPT-4 with {len(self.mcp_tools)} MCP tools available")
            
            # Initial LLM call
            response = await self.openai_client.chat.completions.create(
                model=Config.LLM_MODEL,
                messages=messages,
                tools=tools,
                temperature=Config.LLM_TEMPERATURE,
                max_tokens=Config.LLM_MAX_TOKENS
            )
            
            message = response.choices[0].message
            
            # Handle tool calls if any
            if message.tool_calls:
                logger.info(f"✅ LLM requesting {len(message.tool_calls)} tool calls")
                
                # Add assistant's message to conversation
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
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
                })
                
                # Execute each tool call
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"🔧 Executing: {tool_name}({tool_args})")
                    
                    try:
                        result = await self._execute_mcp_tool(tool_name, tool_args)
                        
                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result
                        })
                        
                        logger.info(f"✅ Tool {tool_name} executed successfully")
                        
                    except Exception as e:
                        logger.error(f"Tool execution failed: {e}")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps({"error": str(e)})
                        })
                
                # Get final response with tool results
                final_response = await self.openai_client.chat.completions.create(
                    model=Config.LLM_MODEL,
                    messages=messages,
                    temperature=Config.LLM_TEMPERATURE,
                    max_tokens=Config.LLM_MAX_TOKENS
                )
                
                response_text = final_response.choices[0].message.content
            else:
                response_text = message.content
            
            # Parse JSON response
# Parse JSON response
            try:
                # Clean up markdown formatting if present
                cleaned_text = response_text.strip()
                
                # Remove markdown code blocks if present
                if cleaned_text.startswith("```"):
                    # Extract JSON from markdown
                    lines = cleaned_text.split('\n')
                    cleaned_text = '\n'.join(lines[1:-1])  # Remove first and last line
                
                result = json.loads(cleaned_text)
                logger.info("✅ Successfully analyzed with MCP tools")
                
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response: {e}")
                logger.debug(f"Response was: {response_text[:200]}...")
                return self._mock_analysis()
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return self._mock_analysis()
            logger.info("✅ Successfully analyzed with MCP tools")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return self._mock_analysis()
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return self._mock_analysis()
    
    def _mock_analysis(self) -> Dict[str, Any]:
        """Fallback mock response"""
        return {
            "analysis": "Using mock data - MCP not available",
            "severity": "high",
            "data_sources_used": ["mock"],
            "alternatives": [
                {
                    "strategy": "REBOOKING",
                    "description": "Rebook on next available flight (mock data)",
                    "data_verified": False,
                    "pros": ["Same airline"],
                    "cons": ["Based on mock data"],
                    "cost_delta": 50.00,
                    "time_delta": 240,
                    "confidence": 0.5
                }
            ],
            "recommendation": "Enable MCP for real-time data",
            "urgency": "within_hour"
        }
    
    async def initialize_mcp_servers(self):
        """Initialize MCP (simplified - no external servers needed)"""
        if self.mcp_enabled:
            logger.info("✅ MCP tools registered and ready (simplified mode)")
        else:
            logger.info("MCP disabled")
    
    async def shutdown(self):
        """Clean shutdown"""
        logger.info("MCP client shutdown")

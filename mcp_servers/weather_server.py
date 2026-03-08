"""
MCP Server for Weather Data

Provides tools for:
- Weather forecasts
- Severe weather alerts
- Travel weather advisories
"""
import asyncio
import json
import os
from datetime import datetime, timedelta
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


server = Server("weather-server")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available weather tools"""
    return [
        Tool(
            name="get_weather_forecast",
            description="Get weather forecast for a location and date",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or airport code"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date for forecast YYYY-MM-DD"
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Number of hours to forecast",
                        "default": 24,
                        "minimum": 1,
                        "maximum": 168
                    }
                },
                "required": ["location", "date"]
            }
        ),
        Tool(
            name="check_severe_weather",
            description="Check for severe weather alerts at a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or airport code"
                    }
                },
                "required": ["location"]
            }
        ),
        Tool(
            name="get_travel_weather_advice",
            description="Get weather-based travel recommendations",
            inputSchema={
                "type": "object",
                "properties": {
                    "origin": {"type": "string"},
                    "destination": {"type": "string"},
                    "travel_date": {"type": "string"}
                },
                "required": ["origin", "destination", "travel_date"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    """Handle tool calls"""
    if name == "get_weather_forecast":
        return await get_weather_forecast(arguments or {})
    elif name == "check_severe_weather":
        return await check_severe_weather(arguments or {})
    elif name == "get_travel_weather_advice":
        return await get_travel_weather_advice(arguments or {})
    else:
        raise ValueError(f"Unknown tool: {name}")


async def get_weather_forecast(args: dict) -> list[TextContent]:
    """Get weather forecast"""
    location = args["location"]
    date = args["date"]
    hours = args.get("hours", 24)
    
    # Mock weather data
    # In production: Call OpenWeather, Weather.gov, etc.
    result = {
        "location": location,
        "date": date,
        "forecast_hours": hours,
        "current_conditions": {
            "temperature_f": 72,
            "temperature_c": 22,
            "conditions": "Partly Cloudy",
            "humidity": 65,
            "wind_mph": 8,
            "precipitation_chance": 20
        },
        "hourly_forecast": [
            {
                "time": f"{i:02d}:00",
                "temp_f": 70 + (i % 5),
                "conditions": "Clear" if i < 12 else "Cloudy",
                "precipitation_chance": 10 + (i % 20)
            }
            for i in range(min(hours, 24))
        ],
        "alerts": [],
        "data_source": "mock_weather_api",
        "timestamp": datetime.now().isoformat()
    }
    
    return [TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def check_severe_weather(args: dict) -> list[TextContent]:
    """Check for severe weather alerts"""
    location = args["location"]
    
    # Mock severe weather check
    result = {
        "location": location,
        "alerts_active": False,
        "alerts": [],
        "risk_level": "low",
        "safe_to_travel": True,
        "advisory": "No severe weather expected in the area",
        "last_updated": datetime.now().isoformat()
    }
    
    # Simulate severe weather for specific locations (for testing)
    if location.upper() in ["ORD", "CHICAGO"]:
        result.update({
            "alerts_active": True,
            "alerts": [{
                "type": "THUNDERSTORM WARNING",
                "severity": "moderate",
                "start_time": datetime.now().isoformat(),
                "end_time": (datetime.now() + timedelta(hours=6)).isoformat(),
                "description": "Severe thunderstorms expected with heavy rain and possible flight delays"
            }],
            "risk_level": "moderate",
            "safe_to_travel": True,
            "advisory": "Monitor conditions closely. Flight delays possible."
        })
    
    return [TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def get_travel_weather_advice(args: dict) -> list[TextContent]:
    """Get travel weather recommendations"""
    origin = args["origin"]
    destination = args["destination"]
    travel_date = args["travel_date"]
    
    result = {
        "route": f"{origin} → {destination}",
        "travel_date": travel_date,
        "origin_weather": {
            "conditions": "Clear",
            "temperature_f": 68,
            "flight_impact": "none"
        },
        "destination_weather": {
            "conditions": "Partly Cloudy",
            "temperature_f": 55,
            "flight_impact": "none"
        },
        "enroute_weather": {
            "turbulence_risk": "low",
            "delays_expected": False
        },
        "recommendations": [
            "Weather is favorable for travel",
            "Pack a light jacket for destination",
            "No significant delays expected"
        ],
        "timestamp": datetime.now().isoformat()
    }
    
    return [TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def main():
    """Run the weather MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="weather",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())

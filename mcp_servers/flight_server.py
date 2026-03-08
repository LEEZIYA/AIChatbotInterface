"""
MCP Server for Real-Time Flight Data

This server provides tools for:
- Getting flight status
- Searching alternative flights
- Checking flight availability
"""
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
import httpx


# Initialize the MCP server
server = Server("flight-data-server")


# Mock flight database (in production, this would be real API calls)
MOCK_FLIGHTS = {
    "BA001": {
        "airline": "British Airways",
        "origin": "JFK",
        "destination": "LHR", 
        "status": "delayed",
        "delay_minutes": 180,
        "departure": "2026-03-15T18:00:00",
        "arrival": "2026-03-16T09:00:00"
    },
    "UA500": {
        "airline": "United",
        "origin": "SFO",
        "destination": "ORD",
        "status": "on_time",
        "delay_minutes": 0,
        "departure": "2026-03-15T14:00:00",
        "arrival": "2026-03-15T20:00:00"
    }
}


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """
    List available tools for flight data operations.
    """
    return [
        Tool(
            name="get_flight_status",
            description="Get real-time status of a flight including delays, cancellations, gate info",
            inputSchema={
                "type": "object",
                "properties": {
                    "flight_number": {
                        "type": "string",
                        "description": "Flight number (e.g., BA001, UA500)"
                    },
                    "date": {
                        "type": "string",
                        "description": "Flight date in YYYY-MM-DD format (optional)",
                        "default": datetime.now().strftime("%Y-%m-%d")
                    }
                },
                "required": ["flight_number"]
            }
        ),
        Tool(
            name="search_alternative_flights",
            description="Search for alternative flights between two cities",
            inputSchema={
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
                    "departure_time": {
                        "type": "string",
                        "description": "Earliest departure time HH:MM (24hr format)",
                        "default": "00:00"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20
                    }
                },
                "required": ["origin", "destination", "departure_date"]
            }
        ),
        Tool(
            name="check_flight_availability",
            description="Check if seats are available on a specific flight",
            inputSchema={
                "type": "object",
                "properties": {
                    "flight_number": {
                        "type": "string",
                        "description": "Flight number to check"
                    },
                    "date": {
                        "type": "string",
                        "description": "Flight date YYYY-MM-DD"
                    },
                    "cabin_class": {
                        "type": "string",
                        "description": "Cabin class to check",
                        "enum": ["economy", "premium_economy", "business", "first"],
                        "default": "economy"
                    }
                },
                "required": ["flight_number", "date"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    """
    Handle tool execution requests.
    """
    
    if name == "get_flight_status":
        return await get_flight_status(arguments or {})
    elif name == "search_alternative_flights":
        return await search_alternative_flights(arguments or {})
    elif name == "check_flight_availability":
        return await check_flight_availability(arguments or {})
    else:
        raise ValueError(f"Unknown tool: {name}")


async def get_flight_status(args: dict) -> list[TextContent]:
    """Get real-time flight status"""
    flight_number = args["flight_number"].upper()
    date = args.get("date", datetime.now().strftime("%Y-%m-%d"))
    
    # In production: Call real FlightAware or similar API
    # For now: Use mock data
    
    if flight_number in MOCK_FLIGHTS:
        flight_data = MOCK_FLIGHTS[flight_number]
        
        result = {
            "flight_number": flight_number,
            "date": date,
            "airline": flight_data["airline"],
            "route": f"{flight_data['origin']} → {flight_data['destination']}",
            "status": flight_data["status"],
            "delay_minutes": flight_data["delay_minutes"],
            "scheduled_departure": flight_data["departure"],
            "scheduled_arrival": flight_data["arrival"],
            "data_source": "mock_api",
            "last_updated": datetime.now().isoformat()
        }
        
        if flight_data["status"] == "delayed":
            result["estimated_departure"] = (
                datetime.fromisoformat(flight_data["departure"]) + 
                timedelta(minutes=flight_data["delay_minutes"])
            ).isoformat()
    else:
        result = {
            "flight_number": flight_number,
            "date": date,
            "status": "not_found",
            "message": "Flight not found in database"
        }
    
    return [TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def search_alternative_flights(args: dict) -> list[TextContent]:
    """Search for alternative flights"""
    origin = args["origin"].upper()
    destination = args["destination"].upper()
    date = args["departure_date"]
    departure_time = args.get("departure_time", "00:00")
    max_results = args.get("max_results", 5)
    
    # In production: Call real flight search API (Amadeus, Skyscanner, etc.)
    # For now: Generate mock alternatives
    
    alternatives = []
    airlines = ["BA", "UA", "AA", "DL", "LH", "AF", "KLM"]
    base_date = datetime.fromisoformat(date)
    
    for i in range(min(max_results, 5)):
        hours_offset = i * 2 + 2  # Flights every 2 hours
        dept_time = base_date + timedelta(hours=hours_offset)
        arr_time = dept_time + timedelta(hours=7)  # 7 hour flight
        
        airline = airlines[i % len(airlines)]
        flight_num = f"{airline}{100 + i * 100}"
        
        alternatives.append({
            "flight_number": flight_num,
            "airline": airline,
            "origin": origin,
            "destination": destination,
            "departure_time": dept_time.isoformat(),
            "arrival_time": arr_time.isoformat(),
            "duration_minutes": 420,
            "stops": 0 if i < 3 else 1,
            "price_usd": 450 + (i * 50),
            "seats_available": 15 - i if i < 10 else 2,
            "cabin_class": "economy"
        })
    
    result = {
        "route": f"{origin} → {destination}",
        "date": date,
        "alternatives_found": len(alternatives),
        "flights": alternatives,
        "data_source": "mock_api",
        "search_timestamp": datetime.now().isoformat()
    }
    
    return [TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def check_flight_availability(args: dict) -> list[TextContent]:
    """Check seat availability"""
    flight_number = args["flight_number"].upper()
    date = args["date"]
    cabin_class = args.get("cabin_class", "economy")
    
    # Mock availability check
    result = {
        "flight_number": flight_number,
        "date": date,
        "cabin_class": cabin_class,
        "seats_available": 12,
        "availability_status": "available",
        "price_usd": 580.00,
        "can_book": True,
        "last_updated": datetime.now().isoformat()
    }
    
    return [TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="flight-data",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())

"""
Rescue Agent MCP - Enhanced with Model Context Protocol

This version uses MCP servers to access real-time data.
"""
from .agent import RescueAgentMCP
from .models import (
    Itinerary, FlightLeg, DisruptionEvent, Solution,
    UserPreferences, DisruptionType, Severity
)
from .config import Config

__version__ = "2.0.0-mcp"

__all__ = [
    "RescueAgentMCP",
    "Itinerary",
    "FlightLeg",
    "DisruptionEvent",
    "Solution",
    "UserPreferences",
    "DisruptionType",
    "Severity",
    "Config"
]

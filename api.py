"""
FastAPI wrapper for Rescue Agent
Exposes REST API endpoints for orchestrator to call
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from src import RescueAgentMCP
from src.models import (
    DisruptionEvent, DisruptionType, 
    UserPreferences, Itinerary, FlightLeg,
    Solution
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RescueAgentAPI")

# Create FastAPI app
app = FastAPI(
    title="Rescue Agent API",
    version="1.0.0",
    description="AI-powered travel disruption management"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance
rescue_agent: Optional[RescueAgentMCP] = None


# ============ Request/Response Models ============

class DisruptionRequest(BaseModel):
    """Request to handle a disruption"""
    event: Dict[str, Any] = Field(..., description="Disruption event details")
    itinerary: Dict[str, Any] = Field(..., description="User's trip itinerary")
    user_preferences: Dict[str, Any] = Field(..., description="User preferences")

class SolutionResponse(BaseModel):
    """Solution returned by agent"""
    strategy: str
    description: str
    cost_impact: float
    time_impact: int
    confidence: float
    pros: List[str]
    cons: List[str]

class DisruptionResponse(BaseModel):
    """Response from handle_disruption endpoint"""
    success: bool
    solutions: List[SolutionResponse]
    message: str

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    agent_ready: bool
    timestamp: str


# ============ Lifecycle Events ============

@app.on_event("startup")
async def startup_event():
    """Initialize rescue agent on startup"""
    global rescue_agent
    logger.info("🚀 Starting Rescue Agent API...")
    
    try:
        rescue_agent = RescueAgentMCP(use_mock_apis=True)
        await rescue_agent.start()
        logger.info("✅ Rescue Agent initialized successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to initialize agent: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global rescue_agent
    logger.info("Shutting down Rescue Agent API...")
    
    if rescue_agent:
        await rescue_agent.shutdown()
    
    logger.info("✅ Shutdown complete")


# ============ API Endpoints ============

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "service": "Rescue Agent API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "handle_disruption": "/api/handle-disruption"
        }
    }

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent_ready": rescue_agent is not None,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/handle-disruption", response_model=DisruptionResponse, tags=["Disruption"])
async def handle_disruption(request: DisruptionRequest):
    """
    Handle a travel disruption and generate solutions
    
    This is the main endpoint the orchestrator will call!
    """
    if not rescue_agent:
        raise HTTPException(
            status_code=503,
            detail="Rescue agent not initialized"
        )
    
    try:
        logger.info(f"Handling disruption: {request.event.get('type', 'unknown')}")
        
        # Convert dicts to Pydantic models
        event = DisruptionEvent(**request.event)
        itinerary = Itinerary(**request.itinerary)
        preferences = UserPreferences(**request.user_preferences)
        
        # Call the agent!
        solutions = await rescue_agent.handle_disruption(
            event=event,
            itinerary=itinerary,
            user_preferences=preferences
        )
        
        logger.info(f"✅ Generated {len(solutions)} solutions")
        
        # Convert solutions to response format
        solution_responses = [
            SolutionResponse(
                strategy=sol.strategy,
                description=sol.description,
                cost_impact=sol.cost_impact,
                time_impact=sol.time_impact,
                confidence=sol.confidence,
                pros=sol.pros,
                cons=sol.cons
            )
            for sol in solutions
        ]
        
        return DisruptionResponse(
            success=True,
            solutions=solution_responses,
            message=f"Generated {len(solutions)} solution(s)"
        )
        
    except Exception as e:
        logger.error(f"❌ Error handling disruption: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process disruption: {str(e)}"
        )


# ============ Simple Test Endpoint ============

@app.post("/api/test-disruption", tags=["Testing"])
async def test_disruption():
    """
    Test endpoint with hardcoded example
    Use this to verify the agent works!
    """
    if not rescue_agent:
        raise HTTPException(status_code=503, detail="Agent not ready")
    
    # Sample disruption
    event = DisruptionEvent(
        id="test_001",
        type=DisruptionType.FLIGHT_DELAY,
        flight_number="BA001",
        delay_duration=180,  # 3 hours
        timestamp=datetime.now(),
        description="Test flight delay"
    )
    
    # Sample itinerary
    from datetime import timedelta
    itinerary = Itinerary(
        user_id="test_user",
        trip_id="test_trip",
        legs=[
            FlightLeg(
                id="leg1",
                origin="JFK",
                destination="LHR",
                departure_time=datetime.now() + timedelta(hours=6),
                arrival_time=datetime.now() + timedelta(hours=13),
                airline="BA",
                flight_number="BA001",
                cost=450.00
            )
        ]
    )
    
    # Sample preferences
    preferences = UserPreferences(
        priority="time",
        budget="medium",
        max_acceptable_delay=120
    )
    
    # Call agent
    solutions = await rescue_agent.handle_disruption(
        event=event,
        itinerary=itinerary,
        user_preferences=preferences
    )
    
    return {
        "test": "success",
        "solutions_count": len(solutions),
        "solutions": [
            {
                "strategy": s.strategy,
                "description": s.description,
                "cost": s.cost_impact,
                "time": s.time_impact
            }
            for s in solutions
        ]
    }


# ============ Run with Uvicorn ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

"""
APIAgent.py
FastAPI server for Travel Planning API
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional
import logging
import uvicorn
from datetime import datetime, timezone

from TravelPlanAgent import get_travel_agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Utility function for UTC timestamps
def utc_now_iso() -> str:
    """Get current UTC time in ISO format with Z suffix"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# Initialize FastAPI app
app = FastAPI(
    title="TravelBuddy Travel Planning API",
    description="AI-powered travel planning service using multi-agent system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Travel Agent
travel_agent = get_travel_agent()


# Request/Response Models
class TravelPlanRequest(BaseModel):
    """Request model for travel planning"""
    travel_context: str = Field(
        ...,
        description="Natural language description of travel requirements",
        min_length=10,
        max_length=5000,
        example="""I want to plan a 6-day trip to Paris in early July.
        My budget is moderate. I want to visit museums, cafes, and the Eiffel Tower.
        Please suggest flights, local transport, and accommodation."""
    )
    
    @validator('travel_context')
    def validate_context(cls, v):
        """Validate travel context"""
        if not v or not v.strip():
            raise ValueError('Travel context cannot be empty')
        return v.strip()


class TravelPlanResponse(BaseModel):
    """Response model for successful travel planning"""
    success: bool = True
    travel_plan: str = Field(..., description="Generated travel plan")
    timestamp: str = Field(default_factory=utc_now_iso)


class ErrorResponse(BaseModel):
    """Response model for errors"""
    success: bool = False
    error: str = Field(..., description="Error message")
    timestamp: str = Field(default_factory=utc_now_iso)


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    timestamp: str


class ValidationResponse(BaseModel):
    """Context validation response"""
    valid: bool
    message: str
    timestamp: str = Field(default_factory=utc_now_iso)


# API Endpoints

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "message": "TravelBuddy Travel Planning API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "timestamp": utc_now_iso()
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint
    """
    return HealthResponse(
        status="healthy",
        service="Travel Planning API",
        timestamp=utc_now_iso()
    )


@app.post(
    "/api/v1/plan-travel",
    response_model=TravelPlanResponse,
    responses={
        200: {"description": "Travel plan generated successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    tags=["Travel Planning"]
)
async def plan_travel_endpoint(request: TravelPlanRequest):
    """
    Generate a comprehensive travel plan based on natural language input
    
    **Request Body:**
    - `travel_context`: Natural language description of your travel needs
    
    **Example:**
    ```json
    {
        "travel_context": "I want to visit Tokyo for 5 days in September. Budget is around \$3000. I love food and culture."
    }
    ```
    
    **Returns:**
    - Comprehensive travel plan including flights, accommodation, and local transport
    """
    try:
        logger.info(f"Received travel planning request: {request.travel_context[:100]}...")
        
        # Validate context
        is_valid, error_msg = travel_agent.validate_context(request.travel_context)
        if not is_valid:
            logger.warning(f"Invalid travel context: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Plan the trip
        result = travel_agent.plan_trip(request.travel_context)
        
        if result["success"]:
            logger.info("Travel plan generated successfully")
            return TravelPlanResponse(
                success=True,
                travel_plan=result["travel_plan"]
            )
        else:
            logger.error(f"Travel planning failed: {result['error']}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in plan_travel_endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@app.post(
    "/api/v1/validate-context",
    response_model=ValidationResponse,
    tags=["Travel Planning"]
)
async def validate_context_endpoint(request: TravelPlanRequest):
    """
    Validate travel context without generating a plan
    
    Useful for checking if the input is valid before submitting
    
    **Example:**
    ```json
    {
        "travel_context": "I want to visit Paris next month"
    }
    ```
    """
    try:
        is_valid, error_msg = travel_agent.validate_context(request.travel_context)
        
        if is_valid:
            return ValidationResponse(
                valid=True,
                message="Travel context is valid"
            )
        else:
            return ValidationResponse(
                valid=False,
                message=error_msg
            )
            
    except Exception as e:
        logger.error(f"Error validating context: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation error: {str(e)}"
        )


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}")
    return ErrorResponse(
        success=False,
        error=exc.detail
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return ErrorResponse(
        success=False,
        error="An unexpected error occurred. Please try again later."
    )


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info("=" * 60)
    logger.info("TravelBuddy Travel Planning API Starting")
    logger.info("=" * 60)
    logger.info(f"Startup time: {utc_now_iso()}")
    logger.info("Initializing Travel Agent...")
    
    try:
        # Pre-initialize the travel agent
        agent = get_travel_agent()
        logger.info("✓ Travel Agent initialized successfully")
    except Exception as e:
        logger.error(f"✗ Failed to initialize Travel Agent: {str(e)}")
        raise
    
    logger.info("=" * 60)
    logger.info("API Ready")
    logger.info("Docs available at: http://localhost:8000/docs")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    logger.info("=" * 60)
    logger.info("TravelBuddy Travel Planning API Shutting Down")
    logger.info(f"Shutdown time: {utc_now_iso()}")
    logger.info("=" * 60)


# Run server
if __name__ == "__main__":
    uvicorn.run(
        "APIAgent:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
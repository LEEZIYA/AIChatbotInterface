from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from app.config import settings

router = APIRouter(tags=["health"])

class HealthResponse(BaseModel):
    status: str; version: str; env: str; timestamp: str

@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", version=settings.APP_VERSION,
                          env=settings.ENV, timestamp=datetime.now(timezone.utc).isoformat())

@router.get("/ready", response_model=HealthResponse)
async def ready():
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured")
    return await health()

"""
TravelBuddy — AI Travel Intelligence
FastAPI Multi-Agent Backend
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging

from app.routers import chat, health
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger("TravelBuddy")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 TravelBuddy starting — env={settings.ENV}")
    yield
    logger.info("TravelBuddy shutting down")


app = FastAPI(
    title="TravelBuddy Travel Intelligence API",
    version="1.0.0",
    description="Multi-agent AI travel assistant",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

# Serve static frontend
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse("app/static/index.html")

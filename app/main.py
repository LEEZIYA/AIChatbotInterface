"""
TRAVELBUDDY — AI Travel Intelligence (LangGraph Edition)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging

from app.routers import chat, health
from app.graph.builder import get_graph
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger("TRAVELBUDDY")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-build the graph at startup so first request isn't slow
    logger.info(f"🚀 TRAVELBUDDY LangGraph starting — env={settings.ENV}")
    get_graph()
    logger.info("✅ LangGraph compiled and ready")
    yield
    logger.info("TRAVELBUDDY shutting down")


app = FastAPI(
    title="TRAVELBUDDY Travel Intelligence API",
    version=settings.APP_VERSION,
    description="Multi-agent AI travel assistant powered by LangGraph",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(chat.router,  prefix="/api")

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse("app/static/index.html")

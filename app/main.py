"""travelbuddy v4 — FastAPI main application."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import chat, health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("travelbuddy")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"travelbuddy v{settings.APP_VERSION} starting — ENV={settings.ENV}")
    from app.graph.builder import get_graph
    get_graph()
    logger.info("LangGraph ready ✅")
    yield
    logger.info("travelbuddy shutting down")


app = FastAPI(title="travelbuddy", version=settings.APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router,   prefix="/api")
app.include_router(health.router, prefix="/api")
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")

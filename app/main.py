"""VOYAGER v4 — RCG Multi-Agent Travel Intelligence"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging

from app.routers import chat, health
from app.graph.builder import get_graph
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger("voyager")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 VOYAGER v4 starting — env={settings.ENV}")
    get_graph()
    logger.info("✅ LangGraph ready")
    yield
    logger.info("VOYAGER shutting down")


app = FastAPI(title="VOYAGER Travel Intelligence", version=settings.APP_VERSION, lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=settings.ALLOWED_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(health.router, prefix="/api")
app.include_router(chat.router,  prefix="/api")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse("app/static/index.html")

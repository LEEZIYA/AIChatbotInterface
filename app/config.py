"""
Configuration — reads from .env file

RCG Model Strategy:
  OPENAI_MODEL_ROUTER → gpt-4o-mini  : routing (clarifier, supervisor)
  OPENAI_MODEL_MINI   → gpt-4o-mini  : simple agents (planner, weather, activities, rescue)
  OPENAI_MODEL        → gpt-4o       : complex reasoning (advisory, synthesiser)

Microservice URLs:
  Each specialist agent can optionally delegate to a dedicated microservice.
  If the microservice is unreachable, the agent falls back to web search tools.
  Set to empty string "" to disable a microservice and always use web search.
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    ENV: str = "development"
    APP_VERSION: str = "4.1.0"

    # ── OpenAI ────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"             # advisory, synthesiser
    OPENAI_MODEL_MINI: str = "gpt-4o-mini"   # planner, weather, activities, rescue
    OPENAI_MODEL_ROUTER: str = "gpt-4o-mini" # clarifier, supervisor

    # ── Microservice URLs ─────────────────────────────────────────────────────
    # Rescue Agent — MCP-powered flight disruption handling
    # Docker internal: http://rescue-agent-api:8000
    # Local dev:       http://localhost:8001
    # Disabled:        "" (falls back to web search)
    RESCUE_AGENT_URL: str = "http://rescue-agent-api:8000"

    # Planner Agent — real booking API microservice (future)
    PLANNER_AGENT_URL: str = ""

    # Advisory Agent — real govt advisory API microservice (future)
    ADVISORY_AGENT_URL: str = ""

    # ── Memory ────────────────────────────────────────────────────────────────
    SQLITE_DB_PATH: str = "travelbuddy_memory.db"

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["*"]

    # ── Rate limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_RPM: int = 30

    # ── Microservice timeouts (seconds) ───────────────────────────────────────
    MICROSERVICE_TIMEOUT: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

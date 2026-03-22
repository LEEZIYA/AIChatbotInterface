"""
Configuration — reads from .env file

RCG Model Strategy:
  OPENAI_MODEL_ROUTER → gpt-4o-mini  : routing decisions (clarifier, supervisor)
  OPENAI_MODEL_MINI   → gpt-4o-mini  : simple specialist agents (planner, weather, activities, rescue)
  OPENAI_MODEL        → gpt-4o       : complex reasoning (advisory, synthesiser)
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    ENV: str = "development"
    APP_VERSION: str = "4.0.0"

    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"            # complex reasoning: advisory, synthesiser
    OPENAI_MODEL_MINI: str = "gpt-4o-mini"  # simple agents: planner, weather, activities, rescue
    OPENAI_MODEL_ROUTER: str = "gpt-4o-mini" # routing only: clarifier, supervisor

    # Memory
    SQLITE_DB_PATH: str = "voyager_memory.db"

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

    # Rate limiting
    RATE_LIMIT_RPM: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

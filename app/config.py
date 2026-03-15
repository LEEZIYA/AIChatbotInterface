"""
Configuration — reads from .env file
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    ENV: str = "development"
    APP_VERSION: str = "2.0.0"

    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MODEL_MINI: str = "gpt-4o-mini"  # used by sub-agents to save cost

    # Memory
    SQLITE_DB_PATH: str = "TRAVELBUDDY_memory.db"

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

    # Rate limiting
    RATE_LIMIT_RPM: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

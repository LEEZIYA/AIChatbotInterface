"""
Configuration — loads from environment variables / .env
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    ENV: str = "production"
    APP_VERSION: str = "1.0.0"

    # OpenAI
    OPENAI_API_KEY: str

    # CORS — comma-separated origins
    ALLOWED_ORIGINS: List[str] = ["*"]

    # Model — gpt-4o for best quality, gpt-4o-mini for lower cost
    OPENAI_MODEL: str = "gpt-4o"
    MAX_TOKENS: int = 2500

    # Rate limiting (requests per minute per IP)
    RATE_LIMIT_RPM: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

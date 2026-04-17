"""
Configuration — reads from .env

Model strategy (RCG — align complexity with model strength):
  OPENAI_MODEL        → gpt-4o       : advisory + synthesiser (complex reasoning)
  OPENAI_MODEL_MINI   → gpt-4o-mini  : transport, weather, activities, accommodation, rescue
  OPENAI_MODEL_ROUTER → gpt-4o-mini  : clarifier + supervisor (classification only)
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    ENV: str = "development"
    APP_VERSION: str = "4.2.0"

    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MODEL_MINI: str = "gpt-4o-mini"
    OPENAI_MODEL_ROUTER: str = "gpt-4o-mini"

    # Microservices (leave empty to use web search fallback)
    RESCUE_AGENT_URL: str = ""
    PLANNER_AGENT_URL: str = ""
    ADVISORY_AGENT_URL: str = ""

    # Web search (set False in dev to save costs)
    ENABLE_WEB_SEARCH: bool = True

    # Timeouts
    MICROSERVICE_TIMEOUT: int = 30

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

    # Rate limiting
    RATE_LIMIT_RPM: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

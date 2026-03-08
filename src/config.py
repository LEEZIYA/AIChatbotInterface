"""
Configuration for MCP-Enhanced Rescue Agent
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


class Config:
    """Application configuration with MCP support"""
    
    # API Keys
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    
    # MCP Configuration
    USE_MCP = os.getenv('USE_MCP', 'true').lower() == 'true'
    
    # Optional: Real API keys for MCP servers
    FLIGHTAWARE_API_KEY = os.getenv('FLIGHTAWARE_API_KEY', '')
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '')
    
    # Agent Configuration
    AGENT_NAME = os.getenv('AGENT_NAME', 'RescueAgent')
    AGENT_VERSION = os.getenv('AGENT_VERSION', '2.0.0-mcp')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # LLM Configuration
    LLM_MODEL = os.getenv('LLM_MODEL', 'gpt-4-turbo-preview')
    LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', '2000'))
    LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.3'))
    
    # Monitoring intervals (seconds)
    POLLING_INTERVAL_CRITICAL = int(os.getenv('POLLING_INTERVAL_CRITICAL', '60'))
    POLLING_INTERVAL_UPCOMING = int(os.getenv('POLLING_INTERVAL_UPCOMING', '1800'))
    POLLING_INTERVAL_FUTURE = int(os.getenv('POLLING_INTERVAL_FUTURE', '21600'))
    
    # Cache Configuration
    CACHE_TTL = int(os.getenv('CACHE_TTL', '300'))
    CACHE_MAX_SIZE = int(os.getenv('CACHE_MAX_SIZE', '1000'))
    
    # Development
    USE_MOCK_APIS = os.getenv('USE_MOCK_APIS', 'true').lower() == 'true'
    
    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        if not cls.OPENAI_API_KEY and not cls.USE_MOCK_APIS:
            logger.warning("OPENAI_API_KEY not set. Using mock mode.")
            cls.USE_MOCK_APIS = True
        
        logger.info(f"Configuration loaded: {cls.AGENT_NAME} v{cls.AGENT_VERSION}")
        logger.info(f"LLM Model: {cls.LLM_MODEL}")
        logger.info(f"MCP Enabled: {cls.USE_MCP}")
        logger.info(f"Mock APIs: {cls.USE_MOCK_APIS}")


# Validate on import
Config.validate()

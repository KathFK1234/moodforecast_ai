"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App settings loaded from .env file."""
    
    weatherai_api_key: str
    database_url: str = "sqlite:///./test.db"
    redis_url: str | None = None
    cache_ttl_seconds: int = 600
    environment: str = "development"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

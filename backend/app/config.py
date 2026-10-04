"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings loaded from .env file."""
    
    # extra="ignore" so leftover keys (e.g. the old WEATHERAI_API_KEY) don't break startup
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )
    
    weather_api_url: str = "https://api.open-meteo.com/v1"
    database_url: str = "sqlite:///./moodforecast.db"
    cache_ttl_seconds: int = 600
    environment: str = "development"


settings = Settings()

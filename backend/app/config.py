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
    marine_api_url: str = "https://marine-api.open-meteo.com/v1"
    database_url: str = "sqlite:///./moodforecast.db"
    cache_ttl_seconds: int = 600
    environment: str = "development"
    
    # Email (SMTP). Nothing is sent until smtp_host and mail_from are set.
    smtp_host: str = ""
    smtp_port: int = 587        # 465 connects over TLS; any other port upgrades with STARTTLS
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    mail_from: str = ""         # e.g. MoodForecast <alerts@example.com>
    
    # Where the site is reachable, for the links in emails
    public_url: str = "http://localhost:8000"
    
    # Local hour (0-23) at the subscriber's location when the daily alert goes out
    alert_hour: int = 7


settings = Settings()

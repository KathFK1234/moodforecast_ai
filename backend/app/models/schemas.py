"""Pydantic request and response models."""

from pydantic import BaseModel, Field, field_validator


# Request Models

class SubscribeRequest(BaseModel):
    """SMS subscriber registration request."""
    phone: str = Field(..., description="E.164 format, e.g. +254712345678")
    location: str = Field(..., description="City name or lat/lon coordinates")
    crop: str | None = Field(None, description="Crop type (optional)")
    language: str = Field("en", description="en or sw")
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate E.164 format."""
        if not v.startswith("+") or len(v) < 10:
            raise ValueError("Phone must be in E.164 format (e.g., +254712345678)")
        return v


# Response Models

class WeatherData(BaseModel):
    """Current weather conditions."""
    temp_c: float
    condition: str
    humidity: float
    wind_kph: float


class ForecastResponse(BaseModel):
    """Forecast endpoint response."""
    location: str
    weather: WeatherData
    forecast_days: int
    ai_summary: str | None = None


class WellbeingResponse(BaseModel):
    """Wellbeing endpoint response."""
    location: str
    weather: WeatherData
    mood_score: int
    energy_level: str
    risk_level: str
    ai_summary: str | None = None
    recommendations: list[str]


class SubscribeResponse(BaseModel):
    """Subscription response."""
    subscriber_id: str
    phone: str
    location: str
    status: str = "subscribed"


class HealthResponse(BaseModel):
    """Health check response."""
    status: str

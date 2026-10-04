"""Pydantic request and response models."""

import re
from pydantic import BaseModel, Field, field_validator


E164_PATTERN = re.compile(r"\+[1-9]\d{7,14}")


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
        """Validate E.164 format: '+', then 8-15 digits, not starting with 0."""
        v = v.strip().replace(" ", "")
        if not E164_PATTERN.fullmatch(v):
            raise ValueError("Phone must be in E.164 format (e.g., +254712345678)")
        return v
    
    @field_validator("location")
    @classmethod
    def validate_location(cls, v: str) -> str:
        """Location must not be blank."""
        v = v.strip()
        if not v:
            raise ValueError("Location is required")
        return v


# Response Models

class WeatherData(BaseModel):
    """Current weather conditions."""
    temp_c: float
    feels_like_c: float | None = None
    condition: str
    humidity: float
    wind_kph: float
    is_day: bool = True


class DailyForecast(BaseModel):
    """Forecast for a single day."""
    date: str = Field(..., description="Local date, YYYY-MM-DD")
    condition: str
    temp_max_c: float
    temp_min_c: float
    precipitation_chance: float | None = Field(None, description="Highest chance of precipitation, %")
    uv_index: float | None = None
    sunrise: str | None = Field(None, description="Local time, HH:MM")
    sunset: str | None = Field(None, description="Local time, HH:MM")
    mood_score: int = Field(..., description="Expected mood score for the day, 0-100")
    mood_label: str


class ForecastResponse(BaseModel):
    """Forecast endpoint response."""
    location: str
    weather: WeatherData
    forecast_days: int
    daily: list[DailyForecast]
    ai_summary: str | None = None


class MoodFactor(BaseModel):
    """One contribution to the mood score."""
    label: str
    delta: int


class WellbeingResponse(BaseModel):
    """Wellbeing endpoint response."""
    location: str
    weather: WeatherData
    mood_score: int
    mood_label: str
    baseline_score: int
    factors: list[MoodFactor]
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

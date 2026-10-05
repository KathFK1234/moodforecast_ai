"""Pydantic request and response models."""

import re
from pydantic import BaseModel, Field, field_validator
from app.services.activity_advisor import find_activity


EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def normalise_email(value: str) -> str:
    """Trim and lowercase an email address, rejecting anything that isn't one."""
    value = value.strip().lower()
    if len(value) > 254 or not EMAIL_PATTERN.fullmatch(value):
        raise ValueError("Enter a valid email address")
    return value


# Request Models

class SubscribeRequest(BaseModel):
    """Daily alert subscription request."""
    email: str = Field(..., description="Where to send the daily alert")
    location: str = Field(..., description="City name or lat/lon coordinates")
    activity: str | None = Field(None, description="Activity to report on each day; omit for a random pick")
    language: str = Field("en", description="en or sw")
    
    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Email is stored trimmed and lowercase."""
        return normalise_email(v)
    
    @field_validator("activity")
    @classmethod
    def validate_activity(cls, v: str | None) -> str | None:
        """Activity must be one the advisor knows; blank means a random pick."""
        if v is None or not v.strip():
            return None
        activity = find_activity(v)
        if activity is None:
            raise ValueError(f"Unknown activity '{v.strip()}'")
        return activity.name
    
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


class LocationSuggestion(BaseModel):
    """A place offered while the user is typing a location."""
    name: str
    region: str | None = None
    country: str | None = None
    label: str = Field(..., description="Text to search for, e.g. 'Kisumu, Kisumu County, Kenya'")


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


class CuriosityPrompt(BaseModel):
    """A question about another place, and the place to search for the answer."""
    question: str
    location: str


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
    curiosity: list[CuriosityPrompt] = Field(
        default_factory=list, description="Other places worth looking up"
    )


class ActivityChoice(BaseModel):
    """An activity that is practical at a location."""
    name: str
    prompt: str = Field(..., description="How someone would ask about it, e.g. 'Go for a run'")


class ActivityCuriosity(BaseModel):
    """Other places to check the same activity."""
    question: str
    places: list[str]


class ActivityResponse(BaseModel):
    """Activity endpoint response."""
    location: str
    weather: WeatherData
    activity: str = Field(..., description="The activity the question was understood to be about")
    recognised: bool = Field(..., description="False if the answer is for general time outdoors")
    verdict: str = Field(..., description="go, maybe or skip")
    headline: str
    reasons: list[str]
    suggestion: str | None = Field(None, description="Something to do instead, when the verdict is skip")
    curiosity: ActivityCuriosity


class SubscribeResponse(BaseModel):
    """Subscription response."""
    subscriber_id: str
    email: str
    location: str = Field(..., description="Resolved display name")
    activity: str | None = None
    status: str = Field("subscribed", description="subscribed, or updated if the email was already subscribed")
    unsubscribe_token: str = Field(..., description="Pass to POST /api/unsubscribe/{token} to stop the alerts")
    confirmation_sent: bool = Field(False, description="Whether a confirmation email went out")


class UnsubscribeLinkRequest(BaseModel):
    """Request for an unsubscribe link by email."""
    email: str
    
    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Email is matched trimmed and lowercase."""
        return normalise_email(v)


class UnsubscribeLinkResponse(BaseModel):
    """Unsubscribe link response. The same whether or not the address is subscribed."""
    status: str = "sent_if_subscribed"


class UnsubscribeResponse(BaseModel):
    """Unsubscribe response."""
    email: str
    status: str = "unsubscribed"


class HealthResponse(BaseModel):
    """Health check response."""
    status: str

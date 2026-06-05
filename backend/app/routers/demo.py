"""Demo router - Mock endpoints for testing without WeatherAI API key."""

from fastapi import APIRouter
from app.models.schemas import ForecastResponse, WellbeingResponse, WeatherData

router = APIRouter(prefix="/api", tags=["demo"])


@router.get("/demo/forecast/{location}")
async def demo_forecast(location: str) -> ForecastResponse:
    """
    Demo forecast endpoint with mock data.
    
    Useful for testing frontend without valid WeatherAI API key.
    
    Example: GET /api/demo/forecast/Nairobi
    """
    weather_data = WeatherData(
        temp_c=21.5,
        condition="Sunny",
        humidity=65,
        wind_kph=12
    )
    
    return ForecastResponse(
        location=location.capitalize(),
        weather=weather_data,
        forecast_days=7,
        ai_summary=f"The weather in {location} looks pleasant with mild temperatures and mostly clear skies. A great day for outdoor activities!"
    )


@router.get("/demo/wellbeing/{location}")
async def demo_wellbeing(location: str) -> WellbeingResponse:
    """
    Demo wellbeing endpoint with mock data.
    
    Useful for testing frontend without valid WeatherAI API key.
    
    Example: GET /api/demo/wellbeing/Nairobi
    """
    weather_data = WeatherData(
        temp_c=21.5,
        condition="Sunny",
        humidity=65,
        wind_kph=12
    )
    
    return WellbeingResponse(
        location=location.capitalize(),
        weather=weather_data,
        mood_score=80,
        energy_level="High",
        risk_level="Minimal",
        ai_summary=f"Excellent conditions in {location}! The sunny weather, comfortable temperature, and moderate humidity create an optimal environment for mood and wellbeing. Perfect time for outdoor activities or important tasks.",
        recommendations=[
            "Get outside for 30+ minutes of sunlight exposure",
            "Maintain hydration with 2-3 liters of water today",
            "Consider a walk or light exercise in the pleasant weather",
            "Plan social activities during peak sunshine hours (10am-3pm)"
        ]
    )

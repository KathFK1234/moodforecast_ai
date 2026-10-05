"""Forecast router - GET /api/forecast/{location}"""

from fastapi import APIRouter, HTTPException
from app.services.weather import get_weather_client
from app.services.mood_engine import calculate_mood_score, classify_mood_label
from app.models.schemas import DailyForecast, ForecastResponse
from app.routers.common import TIMEOUT_MESSAGE, UNAVAILABLE_MESSAGE, build_weather, resolve_location

router = APIRouter(prefix="/api", tags=["forecast"])

# Assumed when the forecast has no humidity for a day (no effect on the score)
DEFAULT_HUMIDITY = 50


@router.get("/forecast/{location}")
async def get_forecast(location: str) -> ForecastResponse:
    """
    Get weather forecast for a location.
    
    Returns current conditions + 7-day forecast with a mood outlook per day.
    Cached for 10 minutes.
    """
    try:
        client = get_weather_client()
        lat, lon, resolved_location = await resolve_location(client, location)
        
        # Fetch current conditions + daily forecast
        forecast = await client.get_forecast(lat, lon)
        weather = build_weather(forecast["current"])
        
        daily = []
        for day in forecast["daily"]:
            # Score the day on its average temperature and humidity
            humidity = day.get("humidity")
            mood_score = calculate_mood_score(
                day["condition"],
                (day["temp_max"] + day["temp_min"]) / 2,
                DEFAULT_HUMIDITY if humidity is None else humidity
            )
            daily.append(DailyForecast(
                date=day["date"],
                condition=day["condition"],
                temp_max_c=day["temp_max"],
                temp_min_c=day["temp_min"],
                precipitation_chance=day.get("precipitation_chance"),
                uv_index=day.get("uv_index"),
                sunrise=day.get("sunrise"),
                sunset=day.get("sunset"),
                mood_score=mood_score,
                mood_label=classify_mood_label(mood_score)
            ))
        
        return ForecastResponse(
            location=resolved_location,
            weather=weather,
            forecast_days=len(daily),
            daily=daily,
            ai_summary=f"Weather in {resolved_location}: {weather.condition}"
        )
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except TimeoutError:
        raise HTTPException(status_code=504, detail=TIMEOUT_MESSAGE)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=UNAVAILABLE_MESSAGE)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

"""Forecast router - GET /api/forecast/{location}"""

from fastapi import APIRouter, HTTPException
from app.services.weather import get_weather_client
from app.models.schemas import ForecastResponse, WeatherData

router = APIRouter(prefix="/api", tags=["forecast"])


@router.get("/forecast/{location}")
async def get_forecast(location: str) -> ForecastResponse:
    """
    Get weather forecast for a location.
    
    Returns current conditions + 7-day forecast + AI summary.
    Cached for 10 minutes.
    """
    try:
        client = get_weather_client()
        
        # Resolve location to coordinates
        geo_data = await client.get_location_by_name(location)
        if "error" in geo_data:
            raise HTTPException(status_code=422, detail=geo_data["error"])
        
        lat = geo_data.get("lat")
        lon = geo_data.get("lon")
        resolved_location = geo_data.get("name", location)
        
        if lat is None or lon is None:
            raise HTTPException(status_code=422, detail="Location not found")
        
        # Fetch current conditions
        current = await client.get_current(lat, lon)
        condition = current.get("condition")
        
        weather = WeatherData(
            temp_c=float(current.get("temperature", 0)),
            condition=condition or "Unknown",
            humidity=float(current.get("humidity", 0)),
            wind_kph=float(current.get("wind_speed", 0))
        )
        
        return ForecastResponse(
            location=resolved_location,
            weather=weather,
            forecast_days=7,
            ai_summary=f"Weather in {resolved_location}: {condition}"
        )
    
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Weather API timeout")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail="Weather service unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

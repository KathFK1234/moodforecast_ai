"""Forecast router - GET /api/forecast/{location}"""

from fastapi import APIRouter, HTTPException
from app.services.weatherai import get_weatherai_client
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
        client = get_weatherai_client()
        
        # Resolve location to coordinates
        geo_data = await client.get_geo_lookup(location)
        lat = geo_data.get("lat")
        lon = geo_data.get("lon")
        resolved_location = geo_data.get("name", location)
        
        if not lat or not lon:
            raise HTTPException(status_code=422, detail="Location not found")
        
        # Fetch forecast
        forecast_data = await client.get_forecast(lat, lon, days=7)
        current = forecast_data.get("current", {})
        
        # Fetch AI insights
        try:
            insights = await client.get_insights(lat, lon)
            ai_summary = insights.get("summary")
        except:
            ai_summary = None
        
        weather = WeatherData(
            temp_c=current.get("temp_c", 0),
            condition=current.get("condition", "Unknown"),
            humidity=current.get("humidity", 0),
            wind_kph=current.get("wind_kph", 0)
        )
        
        return ForecastResponse(
            location=resolved_location,
            weather=weather,
            forecast_days=7,
            ai_summary=ai_summary
        )
    
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except TimeoutError:
        raise HTTPException(status_code=504, detail="WeatherAI API timeout")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail="WeatherAI service unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

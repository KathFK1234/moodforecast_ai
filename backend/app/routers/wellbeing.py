"""Wellbeing router - GET /api/wellbeing/{location}"""

from fastapi import APIRouter, HTTPException
from app.services.weatherai import get_weatherai_client
from app.services.mood_engine import score_mood
from app.models.schemas import WellbeingResponse, WeatherData

router = APIRouter(prefix="/api", tags=["wellbeing"])


@router.get("/wellbeing/{location}")
async def get_wellbeing(location: str) -> WellbeingResponse:
    """
    Get mood and wellbeing score for a location.
    
    Returns mood score, energy level, risk rating, recommendations, and AI summary.
    Cached for 10 minutes.
    """
    try:
        client = get_weatherai_client()
        
        # Resolve location to coordinates
        geo_data = await client.get_location_by_name(location)
        if "error" in geo_data:
            raise HTTPException(status_code=422, detail=geo_data["error"])
        
        lat = geo_data.get("lat")
        lon = geo_data.get("lon")
        resolved_location = geo_data.get("name", location)
        
        if lat is None or lon is None:
            raise HTTPException(status_code=422, detail="Location not found")
        
        # Fetch weather
        weather_data = await client.get_weather(lat, lon, ai=False)
        current = weather_data.get("current", {})
        
        temp_c = float(current.get("temperature", 0))
        
        # Extract condition text using condition code
        condition_code = current.get("condition_code")
        condition = client._get_condition_text(condition_code)
        
        humidity = float(current.get("humidity", 0))
        wind_kph = float(current.get("wind_speed", 0))
        
        # Calculate mood
        mood_result = score_mood(condition, temp_c, humidity)
        
        weather = WeatherData(
            temp_c=temp_c,
            condition=condition or "Unknown",
            humidity=humidity,
            wind_kph=wind_kph
        )
        
        return WellbeingResponse(
            location=resolved_location,
            weather=weather,
            mood_score=mood_result["mood_score"],
            energy_level=mood_result["energy_level"],
            risk_level=mood_result["risk_level"],
            ai_summary=f"Weather analysis for {resolved_location}: {condition}. Your mood is affected by these conditions.",
            recommendations=mood_result["recommendations"]
        )
    
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Weather-AI API timeout")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail="WeatherAI service unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

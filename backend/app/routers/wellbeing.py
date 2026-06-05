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
        geo_data = await client.get_geo_lookup(location)
        lat = geo_data.get("lat")
        lon = geo_data.get("lon")
        resolved_location = geo_data.get("name", location)
        
        if not lat or not lon:
            raise HTTPException(status_code=422, detail="Location not found")
        
        # Fetch weather
        weather_data = await client.get_weather(lat, lon, ai=False)
        current = weather_data.get("current", {})
        
        temp_c = current.get("temp_c", 0)
        condition = current.get("condition", "Unknown")
        humidity = current.get("humidity", 0)
        wind_kph = current.get("wind_kph", 0)
        
        # Calculate mood
        mood_result = score_mood(condition, temp_c, humidity)
        
        # Fetch AI insights
        try:
            insights = await client.get_insights(lat, lon)
            ai_summary = insights.get("summary")
        except:
            ai_summary = None
        
        weather = WeatherData(
            temp_c=temp_c,
            condition=condition,
            humidity=humidity,
            wind_kph=wind_kph
        )
        
        return WellbeingResponse(
            location=resolved_location,
            weather=weather,
            mood_score=mood_result["mood_score"],
            energy_level=mood_result["energy_level"],
            risk_level=mood_result["risk_level"],
            ai_summary=ai_summary,
            recommendations=mood_result["recommendations"]
        )
    
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except TimeoutError:
        raise HTTPException(status_code=504, detail="WeatherAI API timeout")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail="WeatherAI service unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

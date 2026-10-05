"""Wellbeing router - GET /api/wellbeing/{location}"""

import logging
from fastapi import APIRouter, HTTPException
from app.services.weather import get_weather_client
from app.services.mood_engine import BASELINE_SCORE, build_summary, score_mood
from app.services.curiosity import curiosity_prompts
from app.models.schemas import WellbeingResponse
from app.routers.common import TIMEOUT_MESSAGE, UNAVAILABLE_MESSAGE, UNEXPECTED_MESSAGE, build_weather, resolve_location

router = APIRouter(prefix="/api", tags=["wellbeing"])
logger = logging.getLogger(__name__)


@router.get("/wellbeing/{location}")
async def get_wellbeing(location: str) -> WellbeingResponse:
    """
    Get mood and wellbeing score for a location.
    
    Returns mood score with the factors behind it, energy level, risk rating,
    recommendations, a summary, and questions about other places to look up.
    Cached for 10 minutes.
    """
    try:
        client = get_weather_client()
        lat, lon, resolved_location = await resolve_location(client, location)
        
        # Fetch weather
        weather = build_weather(await client.get_current(lat, lon))
        
        # Calculate mood
        mood_result = score_mood(
            weather.condition, weather.temp_c, weather.humidity, weather.is_day
        )
        
        return WellbeingResponse(
            location=resolved_location,
            weather=weather,
            mood_score=mood_result["mood_score"],
            mood_label=mood_result["mood_label"],
            baseline_score=BASELINE_SCORE,
            factors=mood_result["factors"],
            energy_level=mood_result["energy_level"],
            risk_level=mood_result["risk_level"],
            ai_summary=build_summary(
                resolved_location,
                weather.condition,
                weather.temp_c,
                mood_result["mood_score"],
                mood_result["factors"],
                weather.is_day
            ),
            recommendations=mood_result["recommendations"],
            curiosity=curiosity_prompts(
                resolved_location, weather.condition, weather.temp_c, weather.is_day,
                searched_as=location
            )
        )
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except TimeoutError:
        raise HTTPException(status_code=504, detail=TIMEOUT_MESSAGE)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=UNAVAILABLE_MESSAGE)
    except Exception:
        logger.exception("Unexpected error")
        raise HTTPException(status_code=500, detail=UNEXPECTED_MESSAGE)

"""Activity router - GET /api/activity/{location} and /api/random-activity/{location}"""

from fastapi import APIRouter, HTTPException, Query
from app.services.weather import get_weather_client
from app.services.activity_advisor import check_activity, random_activity
from app.models.schemas import ActivityResponse
from app.routers.common import build_weather, resolve_location

router = APIRouter(prefix="/api", tags=["activity"])


@router.get("/activity/{location}")
async def get_activity_advice(
    location: str,
    activity: str = Query(
        ..., min_length=1, max_length=120,
        description="What you would like to do, e.g. 'run' or 'Can I have a picnic?'"
    )
) -> ActivityResponse:
    """
    Check whether the current weather at a location suits an activity.
    
    Returns a verdict (go, maybe or skip) with the reasons behind it, something
    to do instead when the answer is no, and other places to compare.
    """
    try:
        client = get_weather_client()
        lat, lon, resolved_location = await resolve_location(client, location)
        
        # Fetch weather
        weather = build_weather(await client.get_current(lat, lon))
        
        advice = check_activity(
            activity,
            resolved_location,
            weather.condition,
            weather.temp_c,
            weather.humidity,
            weather.wind_kph,
            weather.is_day,
            searched_as=location
        )
        
        return ActivityResponse(location=resolved_location, weather=weather, **advice)
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Weather API timeout")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail="Weather service unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/random-activity/{location}")
async def get_random_activity(
    location: str,
    exclude: str = Query("", max_length=40, description="An activity name to leave out, to get a different pick")
) -> ActivityResponse:
    """
    Pick a random activity that the current weather at a location suits.
    
    Returns the same shape as the activity check, with the verdict always "go".
    """
    try:
        client = get_weather_client()
        lat, lon, resolved_location = await resolve_location(client, location)
        
        # Fetch weather
        weather = build_weather(await client.get_current(lat, lon))
        
        advice = random_activity(
            resolved_location,
            weather.condition,
            weather.temp_c,
            weather.humidity,
            weather.wind_kph,
            weather.is_day,
            searched_as=location,
            exclude=exclude
        )
        
        return ActivityResponse(location=resolved_location, weather=weather, **advice)
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Weather API timeout")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail="Weather service unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

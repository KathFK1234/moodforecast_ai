"""Activity router - GET /api/activity, /api/random-activity and /api/activities"""

from fastapi import APIRouter, HTTPException, Query
from app.services.weather import get_weather_client
from app.services.activity_advisor import ACTIVITIES, check_activity, local_activities, random_activity
from app.models.schemas import ActivityChoice, ActivityResponse
from app.routers.common import local_weather

router = APIRouter(prefix="/api", tags=["activity"])


@router.get("/activities")
async def list_activities() -> list[str]:
    """Names of the activities the advisor knows, e.g. for a subscription form."""
    return [activity.name for activity in ACTIVITIES]


@router.get("/activities/{location}")
async def list_local_activities(location: str) -> list[ActivityChoice]:
    """
    The activities that are practical at a location, local favourites first.
    
    Leaves out what the place can't offer (sea activities inland, snow sports
    away from snow country) and sports that aren't commonly played there.
    """
    try:
        client = get_weather_client()
        _, weather, place = await local_weather(client, location)
        return [
            ActivityChoice(name=activity.name, prompt=activity.prompt)
            for activity in local_activities(place, weather.condition)
        ]
    
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


@router.get("/activity/{location}")
async def get_activity_advice(
    location: str,
    activity: str = Query(
        ..., min_length=1, max_length=120,
        description="What you would like to do, e.g. 'run' or 'Can I have a picnic?'"
    )
) -> ActivityResponse:
    """
    Check whether an activity suits a location and its current weather.
    
    An activity the place can't offer (surfing far from the sea, skiing where
    there are no slopes) is a skip whatever the weather; one that isn't
    commonly done there gets a caveat.
    
    Returns a verdict (go, maybe or skip) with the reasons behind it, something
    to do instead when the answer is no, and other places to compare.
    """
    try:
        client = get_weather_client()
        resolved_location, weather, place = await local_weather(client, location)
        
        advice = check_activity(
            activity,
            resolved_location,
            weather.condition,
            weather.temp_c,
            weather.humidity,
            weather.wind_kph,
            weather.is_day,
            searched_as=location,
            place=place
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
    Pick a random activity that suits a location and its current weather.
    
    Only activities that are practical at the location are picked, and ones
    that are popular in its country come up more often.
    
    Returns the same shape as the activity check, with the verdict always "go".
    """
    try:
        client = get_weather_client()
        resolved_location, weather, place = await local_weather(client, location)
        
        advice = random_activity(
            resolved_location,
            weather.condition,
            weather.temp_c,
            weather.humidity,
            weather.wind_kph,
            weather.is_day,
            searched_as=location,
            exclude=exclude,
            place=place
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

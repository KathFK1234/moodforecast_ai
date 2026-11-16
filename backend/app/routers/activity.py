"""Activity router - GET /api/activity, /api/random-activity and /api/activities"""

from fastapi import APIRouter, Query
from app.services.weather import get_weather_client
from app.services.activity_advisor import (
    ACTIVITIES, check_activity, family_of, group_of, local_activities, random_activity, suited_activities
)
from app.services.locality import LOCAL_FAVOURITES
from app.models.schemas import ActivityChoice, ActivityResponse
from app.routers.common import friendly_errors, local_weather, LocationPath

router = APIRouter(prefix="/api", tags=["activity"])


@router.get("/activities")
async def list_activities() -> list[str]:
    """Names of the activities the advisor knows, e.g. for a subscription form."""
    return [activity.name for activity in ACTIVITIES]


@router.get("/activities/{location}")
@friendly_errors
async def list_local_activities(location: LocationPath) -> list[ActivityChoice]:
    """
    The activities that are practical at a location, local favourites first.
    
    Each comes with its group (Sport and exercise, Out and about, On the water,
    Snow or Indoors), its family of closely related activities, whether it is
    a local favourite, and whether it suits the weather right now (`suited`:
    the activities a random pick may choose).
    
    Leaves out what the place can't offer (sea activities inland, snow sports
    away from snow country) and sports that aren't commonly played there.
    """
    client = get_weather_client()
    _, weather, place = await local_weather(client, location)
    favourites = LOCAL_FAVOURITES.get(place.country, ())
    suited = {
        activity.name for activity in suited_activities(
            weather.condition, weather.temp_c, weather.humidity, weather.wind_kph, weather.is_day, place
        )
    }
    return [
        ActivityChoice(
            name=activity.name,
            prompt=activity.prompt,
            group=group_of(activity),
            favourite=activity.name in favourites,
            family=family_of(activity),
            suited=activity.name in suited,
        )
        for activity in local_activities(place, weather.condition)
    ]


@router.get("/activity/{location}")
@friendly_errors
async def get_activity_advice(
    location: LocationPath,
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


@router.get("/random-activity/{location}")
@friendly_errors
async def get_random_activity(
    location: LocationPath,
    exclude: str = Query("", max_length=40, description="An activity name to leave out, to get a different pick"),
    choose: str = Query(
        "", max_length=40,
        description="An activity name to pick, if it suits the place and the weather right now; otherwise ignored"
    )
) -> ActivityResponse:
    """
    Pick a random activity that suits a location and its current weather.
    
    Only activities that are practical at the location are picked, and ones
    that are popular in its country come up more often.
    
    The page learns which activities its visitor likes, in the browser, and can
    ask for one with `choose`. It is picked only when the same rules as a random
    pick allow it (`suited` in /api/activities/{location}); otherwise the pick
    is made as if it hadn't been asked for.
    
    Returns the same shape as the activity check, with the verdict always "go".
    """
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
        place=place,
        choose=choose
    )
    
    return ActivityResponse(location=resolved_location, weather=weather, **advice)

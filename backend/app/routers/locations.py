"""Locations router - GET /api/locations, POST /api/place"""

from fastapi import APIRouter, HTTPException, Query
from app.services.geocoding import place_at, suggest_locations
from app.models.schemas import LocationSuggestion, PlaceAtPoint, PointRequest
from app.routers.common import friendly_errors

router = APIRouter(prefix="/api", tags=["locations"])


@router.get("/locations")
async def get_location_suggestions(
    q: str = Query(..., max_length=80, description="What the user has typed so far")
) -> list[LocationSuggestion]:
    """
    Suggest locations matching the start of a place name.
    
    Returns an empty list for fewer than two characters, or if the lookup fails.
    """
    return [LocationSuggestion(**suggestion) for suggestion in await suggest_locations(q)]


@router.post("/place")
@friendly_errors
async def get_place_at(point: PointRequest) -> PlaceAtPoint:
    """
    The town or city at a point: for "Use my location" and choosing on the map.
    
    A POST, so the coordinates travel in the body and never appear in an
    address, the browser's history or any request log. They are rounded to
    about 1 km before use and are not stored; the answer is cached by the
    rounded point for the cache lifetime, as any search is.
    
    Returns the place's name and label (search for the label to get its
    weather) and the place's own coordinates. 422 if there is no named place
    there, such as out at sea.
    """
    place = await place_at(point.lat, point.lon)
    if "error" in place:
        raise HTTPException(status_code=422, detail=place["error"])
    return PlaceAtPoint(**place)

"""Locations router - GET /api/locations"""

from fastapi import APIRouter, Query
from app.services.geocoding import suggest_locations
from app.models.schemas import LocationSuggestion

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

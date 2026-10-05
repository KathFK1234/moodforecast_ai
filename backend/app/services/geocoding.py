"""Geocoding service - Convert location names to coordinates."""

import httpx
from app.services.cache import cache


# Popular locations with their coordinates for offline fallback
POPULAR_LOCATIONS = {
    "nairobi": {"lat": -1.2921, "lon": 36.8219, "country": "KE", "timezone": "Africa/Nairobi"},
    "london": {"lat": 51.5074, "lon": -0.1278, "country": "GB", "timezone": "Europe/London"},
    "paris": {"lat": 48.8566, "lon": 2.3522, "country": "FR", "timezone": "Europe/Paris"},
    "tokyo": {"lat": 35.6762, "lon": 139.6503, "country": "JP", "timezone": "Asia/Tokyo"},
    "new york": {"lat": 40.7128, "lon": -74.0060, "country": "US", "timezone": "America/New_York"},
    "sydney": {"lat": -33.8688, "lon": 151.2093, "country": "AU", "timezone": "Australia/Sydney"},
    "dubai": {"lat": 25.2048, "lon": 55.2708, "country": "AE", "timezone": "Asia/Dubai"},
    "singapore": {"lat": 1.3521, "lon": 103.8198, "country": "SG", "timezone": "Asia/Singapore"},
    "bangkok": {"lat": 13.7563, "lon": 100.5018, "country": "TH", "timezone": "Asia/Bangkok"},
    "mumbai": {"lat": 19.0760, "lon": 72.8777, "country": "IN", "timezone": "Asia/Kolkata"},
    "delhi": {"lat": 28.7041, "lon": 77.1025, "country": "IN", "timezone": "Asia/Kolkata"},
    "moscow": {"lat": 55.7558, "lon": 37.6173, "country": "RU", "timezone": "Europe/Moscow"},
    "berlin": {"lat": 52.5200, "lon": 13.4050, "country": "DE", "timezone": "Europe/Berlin"},
    "toronto": {"lat": 43.6629, "lon": -79.3957, "country": "CA", "timezone": "America/Toronto"},
    "mexico city": {"lat": 19.4326, "lon": -99.1332, "country": "MX", "timezone": "America/Mexico_City"},
    "johannesburg": {"lat": -26.2023, "lon": 28.0436, "country": "ZA", "timezone": "Africa/Johannesburg"},
    "cairo": {"lat": 30.0444, "lon": 31.2357, "country": "EG", "timezone": "Africa/Cairo"},
    "lagos": {"lat": 6.5244, "lon": 3.3792, "country": "NG", "timezone": "Africa/Lagos"},
    "accra": {"lat": 5.6037, "lon": -0.1870, "country": "GH", "timezone": "Africa/Accra"},
    "dakar": {"lat": 14.6928, "lon": -17.0467, "country": "SN", "timezone": "Africa/Dakar"},
}


# Coordinates of places offered as suggestions, keyed by lowercase label, so
# picking one finds exactly that place without a second lookup.
_suggested: dict[str, dict] = {}
MAX_SUGGESTED = 2000


async def get_coordinates(location: str) -> dict:
    """
    Convert location name to coordinates.
    
    Checks the hardcoded popular locations and places recently offered as
    suggestions first, then Nominatim (OpenStreetMap).
    Cache key: geo:{location_name}
    
    Raises TimeoutError / RuntimeError if the online lookup fails.
    
    Returns: {
        "lat": float,
        "lon": float,
        "name": str,
        "country": str,
        "timezone": str
    }
    """
    location = location.strip()
    location_lower = location.lower()
    cache_key = f"geo:{location_lower}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    # Try hardcoded popular locations first (no API call, instant)
    if location_lower in POPULAR_LOCATIONS:
        result = POPULAR_LOCATIONS[location_lower].copy()
        result["name"] = location.title()
        cache.set(cache_key, result)
        return result
    
    # A suggestion the user picked
    if location_lower in _suggested:
        result = _suggested[location_lower].copy()
        cache.set(cache_key, result)
        return result
    
    # Try online geocoding via Nominatim (free, no API key needed)
    matches = await _search_nominatim(location)
    
    # "Town, Region, Country" can fail on the region's spelling - retry without it
    parts = [part.strip() for part in location.split(",")]
    if not matches and len(parts) >= 3:
        matches = await _search_nominatim(f"{parts[0]}, {parts[-1]}")
    
    if matches:
        data = matches[0]
        result = {
            "lat": float(data["lat"]),
            "lon": float(data["lon"]),
            # Prefer the place's proper name over what the user typed
            "name": data.get("name") or location,
            "country": data.get("address", {}).get("country_code", "").upper(),
            "timezone": "",  # Nominatim doesn't provide timezone
        }
        cache.set(cache_key, result)
        return result
    
    # Location not found
    return {
        "error": f"Location '{location}' not found",
        "lat": None,
        "lon": None
    }


async def _search_nominatim(query: str) -> list[dict]:
    """
    Look a place up on Nominatim. Returns the best match, or an empty list.
    
    Raises TimeoutError / RuntimeError if the lookup fails.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": query,
                    "format": "json",
                    "limit": 1,
                    "addressdetails": 1,
                },
                headers={"User-Agent": "MoodForecastAI/1.0"},
                timeout=5.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise TimeoutError("Geocoding request timed out")
    except (httpx.HTTPError, ValueError) as e:
        # Don't report "not found" (or guess a city) when the lookup itself failed
        raise RuntimeError(f"Geocoding service unavailable: {e}")


async def suggest_locations(query: str, limit: int = 5) -> list[dict]:
    """
    Suggest places whose names start with what the user has typed so far.
    
    Uses Open-Meteo's geocoding API, which is built for search-as-you-type
    (Nominatim's usage policy does not allow autocomplete).
    Cache key: suggest:{query}
    
    Suggestions are a convenience, so any failure returns an empty list.
    
    Returns: [{"name": str, "region": str | None, "country": str | None, "label": str}, ...]
    with the closest names and largest places first. `label` is the text to search for.
    """
    query = query.strip()
    if len(query) < 2:
        return []
    
    cache_key = f"suggest:{query.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": query, "count": 10, "language": "en", "format": "json"},
                timeout=3.0
            )
            response.raise_for_status()
            matches = response.json().get("results") or []
    except (httpx.HTTPError, ValueError):
        return []
    
    # Names that start with the query first (the API also matches alternate
    # names), then the largest places
    query_lower = query.lower()
    matches.sort(
        key=lambda match: (
            str(match.get("name", "")).lower().startswith(query_lower),
            match.get("population") or 0,
        ),
        reverse=True
    )
    
    suggestions = []
    seen = set()
    for match in matches:
        name = match.get("name")
        if not name:
            continue
        region = match.get("admin1")
        country = match.get("country")
        # "Nairobi, Nairobi County, Kenya" - skip a region that only repeats the name
        parts = [name, region if region != name else None, country]
        label = ", ".join(part for part in parts if part)
        if label in seen:
            continue
        seen.add(label)
        suggestions.append({"name": name, "region": region, "country": country, "label": label})
        if match.get("latitude") is not None and match.get("longitude") is not None:
            if len(_suggested) >= MAX_SUGGESTED:
                _suggested.clear()
            _suggested[label.lower()] = {
                "lat": float(match["latitude"]),
                "lon": float(match["longitude"]),
                "name": name,
                "country": match.get("country_code", ""),
                "timezone": match.get("timezone", ""),
            }
        if len(suggestions) == limit:
            break
    
    cache.set(cache_key, suggestions)
    return suggestions

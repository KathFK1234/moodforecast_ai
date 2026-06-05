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


async def get_coordinates(location: str) -> dict:
    """
    Convert location name to coordinates.
    
    Uses Nominatim (OpenStreetMap) for online lookup, falls back to hardcoded list.
    Cache key: geo:{location_name}
    
    Returns: {
        "lat": float,
        "lon": float,
        "name": str,
        "country": str,
        "timezone": str
    }
    """
    cache_key = f"geo:{location.lower()}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    # Try hardcoded popular locations first (no API call, instant)
    location_lower = location.lower()
    if location_lower in POPULAR_LOCATIONS:
        result = POPULAR_LOCATIONS[location_lower].copy()
        result["name"] = location
        cache.set(cache_key, result)
        return result
    
    # Try online geocoding via Nominatim (free, no API key needed)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": location,
                    "format": "json",
                    "limit": 1,
                },
                headers={"User-Agent": "MoodForecastAI/1.0"},
                timeout=5.0
            )
            
            if response.status_code == 200 and response.json():
                data = response.json()[0]
                result = {
                    "lat": float(data["lat"]),
                    "lon": float(data["lon"]),
                    "name": location,
                    "country": data.get("address", {}).get("country", ""),
                    "timezone": "",  # Nominatim doesn't provide timezone
                }
                cache.set(cache_key, result)
                return result
    except Exception:
        pass  # Fall through to error response
    
    # If online lookup fails, check if it's close to a known location
    # (typo tolerance)
    for known_loc, coords in POPULAR_LOCATIONS.items():
        if location_lower.startswith(known_loc[:3]):  # Match first 3 chars
            result = coords.copy()
            result["name"] = location
            cache.set(cache_key, result)
            return result
    
    # Location not found
    return {
        "error": f"Location '{location}' not found",
        "lat": None,
        "lon": None
    }

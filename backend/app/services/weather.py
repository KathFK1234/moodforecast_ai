"""Async HTTP client for the Open-Meteo weather API (https://open-meteo.com)."""

import httpx
from typing import Any
from app.config import settings
from app.services.cache import cache


# Mapping of WMO weather interpretation codes (used by Open-Meteo) to readable descriptions
CONDITION_MAP = {
    0: "Clear",
    1: "Mainly Clear",
    2: "Partly Cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Foggy",
    51: "Light Drizzle",
    53: "Drizzle",
    55: "Heavy Drizzle",
    56: "Freezing Drizzle",
    57: "Freezing Drizzle",
    61: "Light Rain",
    63: "Rain",
    65: "Heavy Rain",
    66: "Freezing Rain",
    67: "Freezing Rain",
    71: "Light Snow",
    73: "Snow",
    75: "Heavy Snow",
    77: "Snow Grains",
    80: "Light Rain Showers",
    81: "Rain Showers",
    82: "Heavy Rain Showers",
    85: "Snow Showers",
    86: "Heavy Snow Showers",
    95: "Thunderstorm",
    96: "Thunderstorm with Hail",
    99: "Thunderstorm with Heavy Hail",
}

# Current-conditions variables requested from Open-Meteo
CURRENT_VARIABLES = "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"


class WeatherClient:
    """Async client for Open-Meteo with caching and error handling."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client. Open-Meteo needs no API key."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=10.0
            )
        return self._client
    
    async def close(self):
        """Close the async client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request with error handling."""
        client = await self._get_client()
        try:
            response = await client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            status = e.response.status_code
            # 429 = rate limited, which is the service being unavailable to us
            if 400 <= status < 500 and status != 429:
                raise ValueError(f"Bad request: {error_text}")
            else:
                raise RuntimeError(f"Server error: {error_text}")
        except httpx.TimeoutException:
            raise TimeoutError("Weather API request timed out")
        except httpx.RequestError as e:
            raise RuntimeError(f"Weather API unreachable: {e}")
    
    def _get_condition_text(self, condition_code: str | int | None) -> str:
        """Convert WMO weather code to readable text."""
        try:
            return CONDITION_MAP[int(condition_code)]
        except (KeyError, TypeError, ValueError):
            return "Unknown"
    
    async def get_current(self, lat: float, lon: float) -> dict[str, Any]:
        """
        GET /forecast - Current conditions for a set of coordinates.
        
        Cache key: weather:{lat}:{lon}
        
        Returns: {
            "temperature": float (°C),
            "humidity": float (%),
            "wind_speed": float (km/h),
            "condition_code": int (WMO code),
            "condition": str
        }
        """
        cache_key = f"weather:{lat}:{lon}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": CURRENT_VARIABLES,
            "timezone": "auto",
        }
        
        data = await self._request("GET", "/forecast", params=params)
        current = data.get("current")
        if not current:
            raise RuntimeError("Weather API returned no current conditions")
        
        condition_code = current.get("weather_code")
        result = {
            "temperature": float(current.get("temperature_2m", 0)),
            "humidity": float(current.get("relative_humidity_2m", 0)),
            "wind_speed": float(current.get("wind_speed_10m", 0)),
            "condition_code": condition_code,
            "condition": self._get_condition_text(condition_code),
        }
        cache.set(cache_key, result)
        return result
    
    async def get_location_by_name(self, location: str) -> dict[str, Any]:
        """
        Resolve location name to lat/lon using geocoding service.
        
        Uses Nominatim (OpenStreetMap) for online lookup, falls back to hardcoded list.
        Cache key: geo:{location}
        """
        from app.services.geocoding import get_coordinates
        
        result = await get_coordinates(location)
        return result


# Global client instance
_client: WeatherClient | None = None


def get_weather_client() -> WeatherClient:
    """Get or create global weather client."""
    global _client
    if _client is None:
        _client = WeatherClient(settings.weather_api_url)
    return _client

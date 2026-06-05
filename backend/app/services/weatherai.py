"""Async HTTP client for Weather-AI API integration."""

import httpx
from typing import Any
from app.config import settings
from app.services.cache import cache


# Mapping of weather-ai.co condition codes to readable descriptions
CONDITION_MAP = {
    "0": "Clear",
    "1": "Mainly Clear",
    "2": "Partly Cloudy",
    "3": "Overcast",
    "4": "Foggy",
    "5": "Drizzle",
    "6": "Rain",
    "7": "Snow",
    "8": "Rain and Snow",
    "9": "Thunderstorm",
    "10": "Thunderstorm with Hail",
    "11": "Thunderstorm with Heavy Hail",
}


class WeatherAIClient:
    """Async client for weather-ai.co with caching and error handling."""
    
    BASE_URL = "https://api.weather-ai.co/v1"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client with bearer token auth."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10.0
            )
        return self._client
    
    async def close(self):
        """Close the async client."""
        if self._client is not None:
            await self._client.aclose()
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request with error handling."""
        client = await self._get_client()
        try:
            response = await client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            if 400 <= e.response.status_code < 500:
                raise ValueError(f"Bad request: {error_text}")
            else:
                raise RuntimeError(f"Server error: {error_text}")
        except httpx.TimeoutException:
            raise TimeoutError("Weather-AI API request timed out")
    
    def _get_condition_text(self, condition_code: str | int) -> str:
        """Convert weather-ai.co condition code to readable text."""
        code_str = str(condition_code)
        return CONDITION_MAP.get(code_str, f"Condition {code_str}")
    
    async def get_weather(
        self,
        lat: float,
        lon: float,
        days: int = 7,
        ai: bool = True,
        units: str = "metric",
        lang: str = "en"
    ) -> dict[str, Any]:
        """
        GET /current - Current conditions + forecast.
        
        Supports location name, coordinates, or IP address.
        Cache key: weather:{lat}:{lon}
        """
        cache_key = f"weather:{lat}:{lon}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        params = {
            "lat": lat,
            "lon": lon,
        }
        
        data = await self._request("GET", "/current", params=params)
        cache.set(cache_key, data)
        return data
    
    async def get_forecast(
        self,
        lat: float,
        lon: float,
        days: int = 7,
        units: str = "metric"
    ) -> dict[str, Any]:
        """
        GET /current - Forecast data.
        
        Cache key: forecast:{lat}:{lon}
        """
        cache_key = f"forecast:{lat}:{lon}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        params = {
            "lat": lat,
            "lon": lon,
        }
        data = await self._request("GET", "/current", params=params)
        cache.set(cache_key, data)
        return data
    
    async def get_current(
        self,
        lat: float,
        lon: float,
        units: str = "metric"
    ) -> dict[str, Any]:
        """GET /current - Current conditions only."""
        params = {"lat": lat, "lon": lon}
        return await self._request("GET", "/current", params=params)
    
    async def get_insights(
        self,
        lat: float,
        lon: float,
        lang: str = "en"
    ) -> dict[str, Any]:
        """
        GET /current - Get weather data with insights.
        
        Cache key: insights:{lat}:{lon}
        """
        cache_key = f"insights:{lat}:{lon}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        params = {"lat": lat, "lon": lon}
        data = await self._request("GET", "/current", params=params)
        cache.set(cache_key, data)
        return data
    
    async def get_location_by_name(self, location: str) -> dict[str, Any]:
        """
        Resolve location name to lat/lon using current endpoint.
        
        The weather-ai.co API resolves location names automatically.
        Cache key: geo:{location}
        """
        cache_key = f"geo:{location}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        params = {"location": location}
        try:
            data = await self._request("GET", "/current", params=params)
            # Extract location info from the response
            loc_info = data.get("location", {})
            result = {
                "name": location,
                "lat": loc_info.get("lat"),
                "lon": loc_info.get("lon"),
                "timezone": loc_info.get("timezone", ""),
                "country": loc_info.get("country", ""),
            }
            cache.set(cache_key, result)
            return result
        except (ValueError, RuntimeError):
            # Return error if location not found
            result = {"error": f"Location '{location}' not found"}
            cache.set(cache_key, result)
            return result
    
    async def get_ip_lookup(self, ip: str) -> dict[str, Any]:
        """Resolve IP address to weather data."""
        params = {"ip": ip}
        return await self._request("GET", "/current", params=params)


# Global client instance
_client: WeatherAIClient | None = None


def get_weatherai_client() -> WeatherAIClient:
    """Get or create global WeatherAI client."""
    global _client
    if _client is None:
        _client = WeatherAIClient(settings.weatherai_api_key)
    return _client

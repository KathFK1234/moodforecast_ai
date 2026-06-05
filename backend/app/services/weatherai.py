"""Async HTTP client for WeatherAI API integration."""

import httpx
from typing import Any
from app.config import settings
from app.services.cache import cache


class WeatherAIClient:
    """Async client for WeatherAI API with caching."""
    
    BASE_URL = "https://api.weather-ai.co"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5.0
            )
        return self._client
    
    async def close(self):
        """Close the async client."""
        if self._client is not None:
            await self._client.aclose()
    
    async def _request(self, method: str, url: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request with error handling."""
        client = await self._get_client()
        try:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if 400 <= e.response.status_code < 500:
                raise ValueError(f"Bad request: {e.response.text}")
            else:
                raise RuntimeError(f"Server error: {e.response.text}")
        except httpx.TimeoutException:
            raise TimeoutError("WeatherAI API request timed out")
    
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
        GET /v1/weather - Current conditions + forecast.
        
        Cache key: weather:{lat}:{lon}
        """
        cache_key = f"weather:{lat}:{lon}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        params = {
            "lat": lat,
            "lon": lon,
            "days": days,
            "ai": ai,
            "units": units,
            "lang": lang,
        }
        
        data = await self._request("GET", "/v1/weather", params=params)
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
        GET /v1/forecast - Alias of /v1/weather.
        
        Cache key: forecast:{lat}:{lon}
        """
        cache_key = f"forecast:{lat}:{lon}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        params = {"lat": lat, "lon": lon, "days": days, "units": units}
        data = await self._request("GET", "/v1/forecast", params=params)
        cache.set(cache_key, data)
        return data
    
    async def get_current(
        self,
        lat: float,
        lon: float,
        units: str = "metric"
    ) -> dict[str, Any]:
        """GET /v1/current - Current conditions only."""
        params = {"lat": lat, "lon": lon, "units": units}
        return await self._request("GET", "/v1/current", params=params)
    
    async def get_insights(
        self,
        lat: float,
        lon: float,
        lang: str = "en"
    ) -> dict[str, Any]:
        """
        GET /v1/insights - AI-powered weather insights.
        
        Cache key: insights:{lat}:{lon}
        """
        cache_key = f"insights:{lat}:{lon}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        params = {"lat": lat, "lon": lon, "lang": lang}
        data = await self._request("GET", "/v1/insights", params=params)
        cache.set(cache_key, data)
        return data
    
    async def get_geo_lookup(self, location: str) -> dict[str, Any]:
        """
        GET /v1/geo/lookup - Resolve location string to lat/lon.
        
        Cache key: geo:{location}
        """
        cache_key = f"geo:{location}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        params = {"location": location}
        data = await self._request("GET", "/v1/geo/lookup", params=params)
        cache.set(cache_key, data)
        return data
    
    async def get_ip_lookup(self, ip: str) -> dict[str, Any]:
        """GET /v1/ip-lookup - Resolve IP address to geo coordinates."""
        params = {"ip": ip}
        return await self._request("GET", "/v1/ip-lookup", params=params)


# Global client instance
_client: WeatherAIClient | None = None


def get_weatherai_client() -> WeatherAIClient:
    """Get or create global WeatherAI client."""
    global _client
    if _client is None:
        _client = WeatherAIClient(settings.weatherai_api_key)
    return _client

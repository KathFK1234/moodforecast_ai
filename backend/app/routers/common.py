"""Helpers shared by the forecast and wellbeing routers."""

from typing import Any
from fastapi import HTTPException
from app.models.schemas import WeatherData
from app.services.locality import Place, build_place
from app.services.weather import WeatherClient


async def resolve_location(client: WeatherClient, location: str) -> tuple[float, float, str]:
    """
    Resolve a location name to (lat, lon, display name).
    
    Raises HTTPException 422 if the location cannot be found.
    """
    geo_data = await client.get_location_by_name(location)
    if "error" in geo_data:
        raise HTTPException(status_code=422, detail=geo_data["error"])
    
    lat = geo_data.get("lat")
    lon = geo_data.get("lon")
    if lat is None or lon is None:
        raise HTTPException(status_code=422, detail="Location not found")
    
    name = geo_data.get("name", location)
    country = geo_data.get("country")
    return lat, lon, f"{name}, {country}" if country else name


def build_weather(current: dict[str, Any]) -> WeatherData:
    """Convert the weather client's current conditions into the response model."""
    return WeatherData(
        temp_c=float(current.get("temperature", 0)),
        feels_like_c=current.get("feels_like"),
        condition=current.get("condition") or "Unknown",
        humidity=float(current.get("humidity", 0)),
        wind_kph=float(current.get("wind_speed", 0)),
        is_day=current.get("is_day", True)
    )


async def local_weather(client: WeatherClient, location: str) -> tuple[str, WeatherData, Place]:
    """
    Look a location up and return (display name, current weather, local facts).
    
    Raises HTTPException 422 if the location cannot be found.
    """
    lat, lon, resolved_location = await resolve_location(client, location)
    forecast = await client.get_forecast(lat, lon)
    sea = await client.get_sea(lat, lon)
    place = build_place(resolved_location, lat, forecast, sea)
    return resolved_location, build_weather(forecast["current"]), place

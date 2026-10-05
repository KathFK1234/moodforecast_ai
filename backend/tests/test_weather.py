"""Unit tests for the Open-Meteo weather client - HTTP layer is mocked."""

import httpx
import pytest
from app.services.cache import cache
from app.services.weather import WeatherClient


OPEN_METEO_RESPONSE = {
    "latitude": -1.3,
    "longitude": 36.82,
    "timezone": "Africa/Nairobi",
    "current": {
        "time": "2026-10-05T00:00",
        "temperature_2m": 18.8,
        "relative_humidity_2m": 61,
        "apparent_temperature": 17.3,
        "is_day": 0,
        "weather_code": 2,
        "wind_speed_10m": 12.0,
    },
    "daily": {
        "time": ["2026-10-05", "2026-10-06", "2026-10-07"],
        "weather_code": [53, 80, 3],
        "temperature_2m_max": [28.3, 27.6, 25.4],
        "temperature_2m_min": [16.0, 16.1, 15.6],
        "relative_humidity_2m_mean": [61, 72, 83],
        "precipitation_probability_max": [45, 97, 100],
        "uv_index_max": [9.8, 9.4, 8.9],
        "sunrise": ["2026-10-05T06:17", "2026-10-06T06:17", "2026-10-07T06:16"],
        "sunset": ["2026-10-05T18:24", "2026-10-06T18:24", "2026-10-07T18:24"],
    },
}


def make_client(handler) -> WeatherClient:
    """Build a WeatherClient whose HTTP calls are answered by handler."""
    client = WeatherClient("https://api.open-meteo.com/v1")
    client._client = httpx.AsyncClient(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler)
    )
    return client


@pytest.fixture(autouse=True)
def clear_cache():
    """Start every test with an empty cache."""
    cache.clear()
    yield
    cache.clear()


class TestConditionText:
    """Test WMO weather code mapping."""
    
    def test_known_codes(self):
        client = WeatherClient("https://api.open-meteo.com/v1")
        assert client._get_condition_text(0) == "Clear"
        assert client._get_condition_text(3) == "Overcast"
        assert client._get_condition_text("63") == "Rain"
        assert client._get_condition_text(95) == "Thunderstorm"
    
    def test_unknown_code(self):
        client = WeatherClient("https://api.open-meteo.com/v1")
        assert client._get_condition_text(1234) == "Unknown"
        assert client._get_condition_text(None) == "Unknown"


class TestGetCurrent:
    """Test fetching current conditions."""
    
    @pytest.mark.asyncio
    async def test_parses_open_meteo_response(self):
        requests = []
        
        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=OPEN_METEO_RESPONSE)
        
        client = make_client(handler)
        result = await client.get_current(-1.2921, 36.8219)
        
        assert result == {
            "temperature": 18.8,
            "feels_like": 17.3,
            "humidity": 61.0,
            "wind_speed": 12.0,
            "is_day": False,
            "condition_code": 2,
            "condition": "Partly Cloudy",
        }
        assert requests[0].url.path == "/v1/forecast"
        assert requests[0].url.params["latitude"] == "-1.2921"
        assert requests[0].url.params["longitude"] == "36.8219"
    
    @pytest.mark.asyncio
    async def test_forecast_includes_daily(self):
        requests = []
        
        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=OPEN_METEO_RESPONSE)
        
        client = make_client(handler)
        result = await client.get_forecast(-1.2921, 36.8219)
        
        assert result["current"]["condition"] == "Partly Cloudy"
        assert len(result["daily"]) == 3
        assert result["daily"][0] == {
            "date": "2026-10-05",
            "condition": "Drizzle",
            "temp_max": 28.3,
            "temp_min": 16.0,
            "humidity": 61,
            "precipitation_chance": 45,
            "uv_index": 9.8,
            "sunrise": "06:17",
            "sunset": "18:24",
        }
        assert [day["condition"] for day in result["daily"]] == [
            "Drizzle", "Light Rain Showers", "Overcast"
        ]
        assert requests[0].url.params["forecast_days"] == "7"
    
    @pytest.mark.asyncio
    async def test_forecast_tolerates_missing_optional_variables(self):
        response = {
            **OPEN_METEO_RESPONSE,
            "daily": {
                "time": ["2026-10-05"],
                "weather_code": [53],
                "temperature_2m_max": [28.3],
                "temperature_2m_min": [16.0],
            },
        }
        
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=response)
        
        client = make_client(handler)
        result = await client.get_forecast(-1.2921, 36.8219)
        assert len(result["daily"]) == 1
        assert result["daily"][0]["uv_index"] is None
        assert result["daily"][0]["sunrise"] is None
    
    @pytest.mark.asyncio
    async def test_forecast_skips_days_without_data(self):
        response = {
            **OPEN_METEO_RESPONSE,
            "daily": {
                "time": ["2026-10-05", "2026-10-06"],
                "weather_code": [53, None],
                "temperature_2m_max": [28.3, None],
                "temperature_2m_min": [16.0, None],
            },
        }
        
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=response)
        
        client = make_client(handler)
        result = await client.get_forecast(-1.2921, 36.8219)
        assert [day["date"] for day in result["daily"]] == ["2026-10-05"]
    
    @pytest.mark.asyncio
    async def test_current_and_forecast_share_one_request(self):
        calls = 0
        
        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json=OPEN_METEO_RESPONSE)
        
        client = make_client(handler)
        await client.get_forecast(-1.2921, 36.8219)
        await client.get_current(-1.2921, 36.8219)
        assert calls == 1
    
    @pytest.mark.asyncio
    async def test_second_call_is_cached(self):
        calls = 0
        
        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json=OPEN_METEO_RESPONSE)
        
        client = make_client(handler)
        await client.get_current(-1.2921, 36.8219)
        await client.get_current(-1.2921, 36.8219)
        assert calls == 1
    
    @pytest.mark.asyncio
    async def test_bad_request_raises_value_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": True, "reason": "Latitude must be in range"})
        
        client = make_client(handler)
        with pytest.raises(ValueError):
            await client.get_current(999, 0)
    
    @pytest.mark.asyncio
    async def test_server_error_raises_runtime_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="unavailable")
        
        client = make_client(handler)
        with pytest.raises(RuntimeError):
            await client.get_current(-1.2921, 36.8219)
    
    @pytest.mark.asyncio
    async def test_rate_limit_raises_runtime_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": True, "reason": "Too many requests"})
        
        client = make_client(handler)
        with pytest.raises(RuntimeError):
            await client.get_current(-1.2921, 36.8219)
    
    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=request)
        
        client = make_client(handler)
        with pytest.raises(TimeoutError):
            await client.get_current(-1.2921, 36.8219)


class TestGetSea:
    """Test the nearby-sea lookup."""
    
    @pytest.mark.asyncio
    async def test_coastal_when_any_nearby_point_is_at_sea(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.host == "marine-api.open-meteo.com"
            assert len(request.url.params["latitude"].split(",")) == 9
            return httpx.Response(200, json=[
                {"current": {"wave_height": None, "sea_surface_temperature": None}},
                {"current": {"wave_height": None, "sea_surface_temperature": None}},
                {"current": {"wave_height": 1.4, "sea_surface_temperature": 27.6}},
                {"current": {"wave_height": 1.2, "sea_surface_temperature": 27.1}},
                {"current": {"wave_height": None, "sea_surface_temperature": None}},
            ] + [{"current": {"wave_height": None, "sea_surface_temperature": None}}] * 4)
        
        client = make_client(handler)
        assert await client.get_sea(-4.05, 39.67) == {"coastal": True, "sea_temp_c": 27.6}
    
    @pytest.mark.asyncio
    async def test_inland_when_no_point_is_at_sea(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[
                {"current": {"wave_height": None, "sea_surface_temperature": None}}
            ] * 9)
        
        client = make_client(handler)
        assert await client.get_sea(-1.29, 36.82) == {"coastal": False, "sea_temp_c": None}
    
    @pytest.mark.asyncio
    async def test_unknown_when_the_lookup_fails(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="unavailable")
        
        client = make_client(handler)
        assert await client.get_sea(-1.29, 36.82) is None
    
    @pytest.mark.asyncio
    async def test_points_stay_in_range_near_the_date_line(self):
        def handler(request: httpx.Request) -> httpx.Response:
            longitudes = [float(v) for v in request.url.params["longitude"].split(",")]
            assert all(-180 <= lon <= 180 for lon in longitudes)
            return httpx.Response(200, json={"current": {"wave_height": 2.0, "sea_surface_temperature": 24.0}})
        
        client = make_client(handler)
        assert (await client.get_sea(-17.7, 179.95))["coastal"] is True

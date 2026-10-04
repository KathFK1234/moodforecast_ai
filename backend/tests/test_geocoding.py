"""Unit tests for the geocoding service - HTTP layer is mocked."""

import httpx
import pytest
from app.services import geocoding
from app.services.cache import cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Start every test with an empty cache."""
    cache.clear()
    yield
    cache.clear()


def mock_nominatim(monkeypatch, handler):
    """Answer the geocoder's HTTP calls with handler."""
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        geocoding.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)
    )


@pytest.mark.asyncio
async def test_popular_location_needs_no_request(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Nominatim should not be called")
    
    mock_nominatim(monkeypatch, handler)
    result = await geocoding.get_coordinates(" Nairobi ")
    assert result["lat"] == -1.2921
    assert result["lon"] == 36.8219
    assert result["name"] == "Nairobi"


@pytest.mark.asyncio
async def test_online_lookup(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{
            "lat": "-0.1029109",
            "lon": "34.7541761",
            "address": {"country": "Kenya", "country_code": "ke"}
        }])
    
    mock_nominatim(monkeypatch, handler)
    result = await geocoding.get_coordinates("Kisumu")
    assert result["lat"] == pytest.approx(-0.1029109)
    assert result["lon"] == pytest.approx(34.7541761)
    assert result["country"] == "KE"


@pytest.mark.asyncio
async def test_unknown_location_returns_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])
    
    mock_nominatim(monkeypatch, handler)
    # "Torino" shares a prefix with "toronto" but must not resolve to it
    result = await geocoding.get_coordinates("Torino")
    assert "error" in result
    assert result["lat"] is None


@pytest.mark.asyncio
async def test_lookup_failure_raises(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")
    
    mock_nominatim(monkeypatch, handler)
    with pytest.raises(RuntimeError):
        await geocoding.get_coordinates("Kisumu")

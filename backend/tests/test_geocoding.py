"""Unit tests for the geocoding service - HTTP layer is mocked."""

import httpx
import pytest
from app.services import geocoding
from app.services.cache import cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Start every test with an empty cache."""
    cache.clear()
    geocoding._suggested.clear()
    yield
    cache.clear()
    geocoding._suggested.clear()


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


OPEN_METEO_MATCHES = {"results": [
    {"name": "Kiş", "country": "Azerbaijan", "admin1": "Khojavend"},
    {"name": "Kisumu", "country": "Kenya", "admin1": "Kisumu County", "population": 397957},
    {"name": "Kisii", "country": "Kenya", "admin1": "Kisii County", "population": 28547},
    {"name": "Singapore", "country": "Singapore", "admin1": "Singapore", "population": 3547809},
]}


@pytest.mark.asyncio
async def test_suggestions_put_matching_names_then_the_largest_places_first(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "geocoding-api.open-meteo.com"
        assert request.url.params["name"] == "kis"
        return httpx.Response(200, json=OPEN_METEO_MATCHES)
    
    mock_nominatim(monkeypatch, handler)
    suggestions = await geocoding.suggest_locations(" kis ", limit=3)
    assert [s["label"] for s in suggestions] == [
        "Kisumu, Kisumu County, Kenya",
        "Kisii, Kisii County, Kenya",
        "Singapore, Singapore",
    ]
    assert suggestions[0] == {
        "name": "Kisumu", "region": "Kisumu County", "country": "Kenya",
        "label": "Kisumu, Kisumu County, Kenya",
    }


@pytest.mark.asyncio
async def test_suggestions_need_two_characters(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No lookup for a single character")
    
    mock_nominatim(monkeypatch, handler)
    assert await geocoding.suggest_locations("k") == []


@pytest.mark.asyncio
async def test_suggestions_are_empty_when_the_lookup_fails(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")
    
    mock_nominatim(monkeypatch, handler)
    assert await geocoding.suggest_locations("kis") == []


@pytest.mark.asyncio
async def test_suggestions_with_no_matches(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"generationtime_ms": 0.5})
    
    mock_nominatim(monkeypatch, handler)
    assert await geocoding.suggest_locations("zzzzzz") == []


@pytest.mark.asyncio
async def test_picked_suggestion_resolves_without_another_lookup(monkeypatch):
    def suggest(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{
            "name": "Kisumu", "country": "Kenya", "country_code": "KE", "admin1": "Kisumu County",
            "latitude": -0.10221, "longitude": 34.76171, "timezone": "Africa/Nairobi",
        }]})
    
    mock_nominatim(monkeypatch, suggest)
    suggestions = await geocoding.suggest_locations("kis")
    
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("A picked suggestion should not be looked up again")
    
    mock_nominatim(monkeypatch, handler)
    result = await geocoding.get_coordinates(suggestions[0]["label"])
    assert result == {
        "lat": -0.10221, "lon": 34.76171, "name": "Kisumu",
        "country": "KE", "timezone": "Africa/Nairobi",
    }


@pytest.mark.asyncio
async def test_lookup_retries_without_the_region(monkeypatch):
    queries = []
    
    def handler(request: httpx.Request) -> httpx.Response:
        queries.append(request.url.params["q"])
        if "Lunda Sul" in request.url.params["q"]:
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[{
            "lat": "-9.9", "lon": "20.4", "name": "Mombo", "address": {"country_code": "ao"}
        }])
    
    mock_nominatim(monkeypatch, handler)
    result = await geocoding.get_coordinates("Mombo, Lunda Sul Province, Angola")
    assert queries == ["Mombo, Lunda Sul Province, Angola", "Mombo, Angola"]
    assert result["name"] == "Mombo"
    assert result["country"] == "AO"


@pytest.mark.asyncio
async def test_unknown_location_says_what_to_try(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])
    
    mock_nominatim(monkeypatch, handler)
    result = await geocoding.get_coordinates("Zzyzx")
    assert result["error"] == (
        "We couldn't find 'Zzyzx'. Check the spelling, or add the country (for example 'Kisumu, Kenya')."
    )

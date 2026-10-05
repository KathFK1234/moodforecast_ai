"""Unit tests for the geocoding service - HTTP layer is mocked."""

import asyncio

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


@pytest.mark.asyncio
async def test_lookup_asks_for_english_names_and_drops_city_of(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["accept-language"] == "en"
        return httpx.Response(200, json=[{
            "lat": "-1.95", "lon": "30.06", "name": "City of Kigali", "address": {"country_code": "rw"}
        }])
    
    mock_nominatim(monkeypatch, handler)
    result = await geocoding.get_coordinates("Kigali")
    assert result["name"] == "Kigali"


@pytest.mark.asyncio
async def test_simultaneous_lookups_share_one_request(monkeypatch):
    """A search looks the same place up twice at once; Nominatim should hear about it once."""
    calls = 0
    
    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return httpx.Response(200, json=[{
            "lat": "-4.05", "lon": "39.67", "name": "Mombasa", "address": {"country_code": "ke"}
        }])
    
    mock_nominatim(monkeypatch, handler)
    first, second = await asyncio.gather(
        geocoding.get_coordinates("Mombasa"), geocoding.get_coordinates("mombasa")
    )
    assert first == second
    assert calls == 1


@pytest.mark.asyncio
async def test_a_place_is_only_looked_up_once_even_after_the_cache_expires(monkeypatch):
    calls = 0
    
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=[{
            "lat": "-4.05", "lon": "39.67", "name": "Mombasa", "address": {"country_code": "ke"}
        }])
    
    mock_nominatim(monkeypatch, handler)
    first = await geocoding.get_coordinates("Mombasa")
    cache.clear()
    assert await geocoding.get_coordinates("Mombasa") == first
    assert calls == 1


@pytest.mark.asyncio
async def test_falls_back_to_open_meteo_when_nominatim_is_down(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "nominatim.openstreetmap.org":
            raise httpx.ReadTimeout("timed out", request=request)
        assert request.url.params["name"] == "kisumu"
        return httpx.Response(200, json={"results": [
            {"name": "Kisumu", "country": "Uganda", "country_code": "UG", "latitude": 1.0, "longitude": 33.0},
            {"name": "Kisumu", "country": "Kenya", "country_code": "KE", "admin1": "Kisumu County",
             "latitude": -0.10221, "longitude": 34.76171, "timezone": "Africa/Nairobi"},
        ]})
    
    mock_nominatim(monkeypatch, handler)
    result = await geocoding.get_coordinates("Kisumu, Kenya")
    assert result == {
        "lat": -0.10221, "lon": 34.76171, "name": "Kisumu", "country": "KE", "timezone": "Africa/Nairobi",
    }


@pytest.mark.asyncio
async def test_lookup_fails_when_both_geocoders_are_down(monkeypatch):
    down = True
    
    def handler(request: httpx.Request) -> httpx.Response:
        if not down:
            return httpx.Response(200, json=[{
                "lat": "-0.10", "lon": "34.75", "name": "Kisumu", "address": {"country_code": "ke"}
            }])
        if request.url.host == "nominatim.openstreetmap.org":
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(503, text="unavailable")
    
    mock_nominatim(monkeypatch, handler)
    with pytest.raises(TimeoutError):
        await geocoding.get_coordinates("Kisumu")
    
    # A failure is not remembered: the next search tries again
    down = False
    assert (await geocoding.get_coordinates("Kisumu"))["country"] == "KE"


@pytest.mark.asyncio
async def test_unknown_places_are_not_remembered(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])
    
    mock_nominatim(monkeypatch, handler)
    assert "error" in await geocoding.get_coordinates("Zzyzx")
    assert "zzyzx" not in geocoding._suggested

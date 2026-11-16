"""Unit tests for the geocoding service - HTTP layer is mocked."""

import asyncio
import time

import httpx
import pytest
from app.services import geocoding
from app.services.cache import cache


@pytest.fixture(autouse=True)
def clear_cache(monkeypatch):
    """Start every test with an empty cache and no wait for Nominatim."""
    cache.clear()
    geocoding._points.clear()
    geocoding._suggested.clear()
    monkeypatch.setattr(geocoding, "NOMINATIM_INTERVAL", 0.0)
    monkeypatch.setattr(geocoding, "_next_nominatim_slot", 0.0)
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


@pytest.mark.asyncio
async def test_nominatim_gets_at_most_one_request_per_interval(monkeypatch):
    """Nominatim's usage policy: one request per second from the whole app."""
    monkeypatch.setattr(geocoding, "NOMINATIM_INTERVAL", 0.05)
    started = []
    
    def handler(request: httpx.Request) -> httpx.Response:
        assert "github.com/KathFK1234/moodforecast_ai" in request.headers["User-Agent"]
        started.append(asyncio.get_running_loop().time())
        return httpx.Response(200, json=[{"lat": "1", "lon": "2", "address": {"country_code": "ke"}}])
    
    mock_nominatim(monkeypatch, handler)
    await asyncio.gather(*(geocoding.get_coordinates(f"Town {n}") for n in range(4)))
    started.sort()
    assert len(started) == 4
    assert all(later - earlier >= 0.045 for earlier, later in zip(started, started[1:]))


@pytest.mark.asyncio
async def test_lookups_that_would_wait_too_long_use_the_fallback(monkeypatch):
    monkeypatch.setattr(geocoding, "NOMINATIM_INTERVAL", 10.0)
    hosts = []
    
    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        if request.url.host == "nominatim.openstreetmap.org":
            return httpx.Response(200, json=[{"lat": "1", "lon": "2", "address": {"country_code": "ke"}}])
        return httpx.Response(200, json={"results": [
            {"name": "Eldoret", "latitude": 0.52, "longitude": 35.27, "country_code": "KE"}
        ]})
    
    mock_nominatim(monkeypatch, handler)
    await geocoding.get_coordinates("Kisumu")
    result = await geocoding.get_coordinates("Eldoret")
    assert hosts == ["nominatim.openstreetmap.org", "geocoding-api.open-meteo.com"]
    assert result["lat"] == pytest.approx(0.52)


@pytest.mark.asyncio
async def test_a_location_of_only_commas_is_no_match_for_the_fallback_geocoder():
    assert await geocoding._search_open_meteo(" , ,") is None


@pytest.mark.parametrize("reply", [
    {"error": "x"}, "text", None, [1], [{"name": "x"}], [{"lat": "x", "lon": "1"}],
    [{"lat": "1", "lon": "2", "address": None}], [{"lat": "1", "lon": "2", "name": 5}],
])
@pytest.mark.asyncio
async def test_a_nominatim_reply_of_the_wrong_shape_counts_as_unavailable(monkeypatch, reply):
    mock_nominatim(monkeypatch, lambda request: httpx.Response(200, json=reply if "nominatim" in request.url.host else None))
    with pytest.raises(RuntimeError):
        await geocoding.get_coordinates("Somewhere Odd")


@pytest.mark.parametrize("reply", [
    None, "text", [1], {"results": "text"}, {"results": [1]},
    {"results": [{"name": "x", "latitude": "a", "longitude": 1}]},
    {"results": [{"name": "x", "population": "a"}, {"name": "y", "population": 3}]},
])
@pytest.mark.asyncio
async def test_a_suggestion_reply_of_the_wrong_shape_means_no_suggestions(monkeypatch, reply):
    mock_nominatim(monkeypatch, lambda request: httpx.Response(200, json=reply))
    assert await geocoding.suggest_locations("somewhere") == []


@pytest.mark.asyncio
async def test_line_breaks_in_a_found_places_name_are_cleaned_out(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{
            "lat": "-0.1", "lon": "34.75", "name": "Kisumu\r\nBcc: someone@example.com",
            "address": {"country_code": "k\ne"}
        }])
    
    mock_nominatim(monkeypatch, handler)
    result = await geocoding.get_coordinates("Kisumu")
    assert result["name"] == "Kisumu Bcc: someone@example.com"
    assert result["country"] == "K E"


@pytest.mark.asyncio
async def test_line_breaks_in_suggestions_are_cleaned_out(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{
            "name": "Kisumu\n", "admin1": "Kisumu\tCounty", "country": "Ken\x00ya",
            "country_code": "KE", "latitude": -0.1, "longitude": 34.75,
        }]})
    
    mock_nominatim(monkeypatch, handler)
    suggestions = await geocoding.suggest_locations("kis")
    assert suggestions == [{
        "name": "Kisumu", "region": "Kisumu County", "country": "Ken ya",
        "label": "Kisumu, Kisumu County, Ken ya",
    }]
    # Picking it finds the same clean name
    assert (await geocoding.get_coordinates("Kisumu, Kisumu County, Ken ya"))["name"] == "Kisumu"


@pytest.mark.asyncio
async def test_the_fallback_geocoders_names_are_cleaned_too(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "nominatim.openstreetmap.org":
            return httpx.Response(503)
        return httpx.Response(200, json={"results": [{
            "name": "Kisumu\r\n", "country_code": "KE", "latitude": -0.1, "longitude": 34.75,
        }]})
    
    mock_nominatim(monkeypatch, handler)
    assert (await geocoding.get_coordinates("Kisumu"))["name"] == "Kisumu"


@pytest.mark.parametrize("value, cleaned", [(None, None), ("Nairobi", "Nairobi"), (" Dar  es\x7fSalaam ", "Dar es Salaam")])
def test_clean_name(value, cleaned):
    assert geocoding.clean_name(value) == cleaned


def test_a_name_that_isnt_text_is_unusable():
    with pytest.raises(TypeError):
        geocoding.clean_name(5)


NAIVASHA_REVERSE = {
    "lat": "-0.7167", "lon": "36.4333", "name": "Naivasha",
    "address": {"town": "Naivasha", "county": "Nakuru County", "state": "Nakuru County", "country": "Kenya", "country_code": "ke"},
}


@pytest.mark.asyncio
async def test_place_at_a_point_rounds_it_and_remembers_the_place(monkeypatch):
    asked = []
    
    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(request)
        return httpx.Response(200, json=NAIVASHA_REVERSE)
    
    mock_nominatim(monkeypatch, handler)
    place = await geocoding.place_at(-0.712345678, 36.431111111)
    assert place["label"] == "Naivasha, Nakuru County, Kenya"
    assert (place["lat"], place["lon"]) == (-0.7167, 36.4333)
    # The exact point never leaves the server: only the rounded one, at town level
    params = asked[0].url.params
    assert asked[0].url.path == "/reverse"
    assert (params["lat"], params["lon"], params["zoom"]) == ("-0.71", "36.43", "10")
    assert asked[0].headers["User-Agent"] == geocoding.NOMINATIM_USER_AGENT
    
    # A point nearby is answered from the cache, and searching for the label needs no lookup
    assert (await geocoding.place_at(-0.7149, 36.4321))["label"] == place["label"]
    found = await geocoding.get_coordinates("Naivasha, Nakuru County, Kenya")
    assert (found["lat"], found["lon"], found["country"]) == (-0.7167, 36.4333, "KE")
    assert len(asked) == 1


@pytest.mark.asyncio
async def test_no_place_at_sea_is_cached_too(monkeypatch):
    asked = []
    
    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(request)
        return httpx.Response(200, json={"error": "Unable to geocode"})
    
    mock_nominatim(monkeypatch, handler)
    assert (await geocoding.place_at(0, -30))["error"] == geocoding.NO_PLACE_THERE
    assert (await geocoding.place_at(0.001, -30.001))["error"] == geocoding.NO_PLACE_THERE
    assert len(asked) == 1


@pytest.mark.asyncio
async def test_place_at_a_point_uses_the_address_when_unnamed_and_skips_repeats(monkeypatch):
    reply = {"lat": "1.3", "lon": "103.8", "address": {"city": "Singapore", "country": "Singapore", "country_code": "sg"}}
    mock_nominatim(monkeypatch, lambda request: httpx.Response(200, json=reply))
    place = await geocoding.place_at(1.3, 103.8)
    assert place["label"] == "Singapore"
    assert place["region"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("reply", [[], {"lat": "x", "lon": "1", "name": "Somewhere"}, {"name": 5}])
async def test_an_odd_reverse_reply_counts_as_unavailable(monkeypatch, reply):
    mock_nominatim(monkeypatch, lambda request: httpx.Response(200, json=reply))
    with pytest.raises(RuntimeError):
        await geocoding.place_at(10, 10)


@pytest.mark.asyncio
async def test_reverse_lookup_failures_raise(monkeypatch):
    def handler(request):
        if request.url.params["lat"] == "10.0":
            raise httpx.ReadTimeout("slow")
        return httpx.Response(500)
    mock_nominatim(monkeypatch, handler)
    with pytest.raises(TimeoutError):
        await geocoding.place_at(10, 10)
    with pytest.raises(RuntimeError):
        await geocoding.place_at(11, 11)


@pytest.mark.asyncio
async def test_simultaneous_reverse_lookups_share_one_request(monkeypatch):
    asked = []
    
    async def handler(request: httpx.Request) -> httpx.Response:
        asked.append(request)
        await asyncio.sleep(0.01)
        return httpx.Response(200, json=NAIVASHA_REVERSE)
    
    mock_nominatim(monkeypatch, handler)
    first, second = await asyncio.gather(geocoding.place_at(-0.71, 36.43), geocoding.place_at(-0.711, 36.431))
    assert first == second
    assert len(asked) == 1


@pytest.mark.asyncio
async def test_a_search_that_looks_like_a_point_key_does_not_share_its_lookup(monkeypatch):
    mock_nominatim(monkeypatch, lambda request: httpx.Response(200, json=[]))
    result = await geocoding.get_coordinates("rev:-0.71:36.43")
    assert "error" in result


@pytest.mark.asyncio
async def test_a_kenyan_ward_is_named_after_its_neighbourhood(monkeypatch):
    reply = {
        "lat": "-4.05", "lon": "39.67", "name": "Tudor ward",
        "address": {"city": "Tudor ward", "county": "Mvita", "state": "Mombasa County", "country": "Kenya", "country_code": "ke"},
    }
    mock_nominatim(monkeypatch, lambda request: httpx.Response(200, json=reply))
    assert (await geocoding.place_at(-4.04, 39.67))["label"] == "Tudor, Mombasa County, Kenya"


@pytest.mark.asyncio
async def test_a_refused_reverse_lookup_is_logged_without_the_point(monkeypatch, caplog):
    mock_nominatim(monkeypatch, lambda request: httpx.Response(403))
    with pytest.raises(RuntimeError):
        await geocoding.place_at(-0.7123, 36.4311)
    assert "Nominatim reverse lookup failed: 403" in caplog.text
    assert "36.43" not in caplog.text and "-0.71" not in caplog.text


@pytest.mark.asyncio
async def test_a_point_is_forgotten_once_past_the_cache_lifetime(monkeypatch):
    mock_nominatim(monkeypatch, lambda request: httpx.Response(200, json=NAIVASHA_REVERSE))
    await geocoding.place_at(-0.71, 36.43)
    assert len(geocoding._points) == 1
    # Not in the main cache, whose expired entries stay until pushed out
    assert not any(key.startswith("rev:") for key in cache._cache)
    clock = time.time() + geocoding._points.ttl_seconds + 1
    monkeypatch.setattr("app.services.cache.time.time", lambda: clock)
    geocoding.forget_old_points()
    assert len(geocoding._points) == 0

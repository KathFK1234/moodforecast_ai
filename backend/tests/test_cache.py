"""Unit tests for the in-memory TTL cache."""

from app.services.cache import TTLCache


def test_values_expire_after_the_ttl(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("app.services.cache.time.time", lambda: now[0])
    cache = TTLCache(ttl_seconds=60)
    cache.set("a", 1)
    now[0] += 59
    assert cache.get("a") == 1
    now[0] += 2
    assert cache.get("a") is None
    # Still there for a caller that accepts an older value
    assert cache.get_stale("a", 3600) == 1


def test_cache_never_holds_more_than_its_limit():
    cache = TTLCache(max_entries=3)
    for key in "abcdef":
        cache.set(key, key)
    assert len(cache) == 3
    assert [cache.get(key) for key in "abcdef"] == [None, None, None, "d", "e", "f"]


def test_setting_a_key_again_makes_it_the_newest():
    cache = TTLCache(max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("a", 3)
    cache.set("c", 4)
    assert cache.get("a") == 3
    assert cache.get("b") is None
    assert cache.get("c") == 4

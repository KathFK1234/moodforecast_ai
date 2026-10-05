"""Unit tests for the local facts about a place - no I/O dependencies."""

from datetime import datetime, timezone

from app.services.locality import build_place, country_of, is_late_night


def test_country_comes_from_the_display_name():
    assert country_of("Nairobi, KE") == "KE"
    assert country_of("Kisumu, Kisumu County, ke") == "KE"
    assert country_of("Nairobi") == ""
    assert country_of("Somewhere, Far Away") == ""


def test_build_place_gathers_what_is_known():
    place = build_place(
        "Mombasa, KE", -4.05,
        {"elevation": 19.0, "utc_offset_seconds": 10800},
        {"coastal": True, "sea_temp_c": 27.6},
        now_utc=datetime(2026, 10, 5, 22, 30, tzinfo=timezone.utc)
    )
    assert place.name == "Mombasa"
    assert place.country == "KE"
    assert place.elevation == 19.0
    assert place.coastal is True
    assert place.sea_temp_c == 27.6
    # 22:30 UTC is 01:30 the next day at UTC+3
    assert place.local_hour == 1
    assert is_late_night(place) is True


def test_build_place_leaves_the_unknown_unknown():
    place = build_place("Somewhere", 10.0)
    assert place.country == ""
    assert place.coastal is None
    assert place.elevation is None
    assert place.local_hour is None
    assert is_late_night(place) is False


def test_late_night_is_eleven_to_five():
    def at(hour):
        return is_late_night(build_place("X, KE", 0)._replace(local_hour=hour))
    
    assert [hour for hour in range(24) if at(hour)] == [0, 1, 2, 3, 4, 23]

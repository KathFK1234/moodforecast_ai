"""Integration tests for API endpoints with mocked weather client."""

import asyncio
import json
import logging
import re
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from app.main import HideTokens, api_limiter, app, form_limiter
from app.models.db import PendingSubscription, Subscriber
from app.services import alerts, mailer
from app.services.cache import cache


client = TestClient(app)


def memory_engine():
    """A fresh in-memory database with the tables created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def mock_weather():
    """Mock weather client for all tests."""
    with patch('app.routers.forecast.get_weather_client') as mock_forecast, \
         patch('app.routers.wellbeing.get_weather_client') as mock_wellbeing, \
         patch('app.routers.activity.get_weather_client') as mock_activity, \
         patch('app.routers.subscribe.get_weather_client') as mock_subscribe, \
         patch('app.routers.subscribe.get_engine', return_value=memory_engine()):
        
        mock_client = AsyncMock()
        
        # Mock location lookup
        mock_client.get_location_by_name = AsyncMock(return_value={
            "lat": -1.2921,
            "lon": 36.8219,
            "name": "Nairobi",
            "timezone": "Africa/Nairobi",
            "country": "KE"
        })
        
        # Mock weather in the weather client's normalised format
        current = {
            "temperature": 18,
            "feels_like": 16.5,
            "humidity": 74,
            "wind_speed": 12,
            "is_day": True,
            "condition_code": 2,
            "condition": "Partly Cloudy"
        }
        mock_client.get_current = AsyncMock(return_value=current)
        mock_client.get_forecast = AsyncMock(return_value={
            "current": current,
            "daily": [
                {
                    "date": "2026-10-05", "condition": "Clear", "temp_max": 26.0, "temp_min": 16.0,
                    "humidity": 60, "precipitation_chance": 5, "uv_index": 9.8,
                    "sunrise": "06:17", "sunset": "18:24"
                },
                {
                    "date": "2026-10-06", "condition": "Thunderstorm", "temp_max": 12.0, "temp_min": 6.0,
                    "humidity": 90, "precipitation_chance": 100, "uv_index": 2.0,
                    "sunrise": "06:17", "sunset": "18:24"
                },
            ],
            "utc_offset_seconds": 10800,
            "elevation": 1668.0
        })
        mock_client.get_sea = AsyncMock(return_value={"coastal": False, "sea_temp_c": None})
        
        mock_forecast.return_value = mock_client
        mock_wellbeing.return_value = mock_client
        mock_activity.return_value = mock_client
        mock_subscribe.return_value = mock_client
        
        yield mock_client


def test_health_check():
    """GET /health should return ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def confirm_token(outbox):
    """The token in the last confirmation link emailed."""
    text = outbox[-1][1].get_body(("plain",)).get_content()
    return re.search(r"\?confirm=([\w-]+)", text).group(1)


def subscribe_and_confirm(outbox, **request):
    """Ask for alerts, then follow the emailed link, as a subscriber would."""
    alerts._recently_sent.clear()  # Each request in a test gets its own email
    response = client.post("/api/subscribe", json=request)
    assert response.status_code == 202
    return client.post(f"/api/confirm/{confirm_token(outbox)}")


def test_subscribe_asks_for_confirmation_first(mock_weather, outbox):
    """Nothing is subscribed until the emailed link is followed."""
    engine = memory_engine()
    with patch('app.routers.subscribe.get_engine', return_value=engine):
        response = client.post("/api/subscribe", json={
            "email": "amina@example.com", "location": "Nairobi", "activity": "running"
        })
    assert response.status_code == 202
    assert response.json() == {
        "email": "amina@example.com", "location": "Nairobi, KE", "activity": "running",
        "status": "pending", "confirmation_sent": True,
    }
    with Session(engine) as session:
        assert session.exec(select(Subscriber)).all() == []
        assert len(session.exec(select(PendingSubscription)).all()) == 1
    
    assert len(outbox) == 1
    message = outbox[0][1]
    assert message["To"] == "amina@example.com"
    assert message["Subject"] == "Confirm your MoodForecast alerts for Nairobi, KE"
    link = f"https://moodforecast.test/?confirm={confirm_token(outbox)}"
    text = message.get_body(("plain",)).get_content()
    assert link in text
    assert link in message.get_body(("html",)).get_content()
    assert "how the weather suits running" in text
    assert "48 hours" in text
    # Not subscribed yet, so nothing to unsubscribe from
    assert "unsubscribe" not in text.lower()
    assert message["List-Unsubscribe"] is None


def test_subscribe_never_reveals_a_subscribers_token(mock_weather, outbox):
    """Typing someone's address in must not hand over their unsubscribe link."""
    subscribe_and_confirm(outbox, email="amina@example.com", location="Nairobi")
    response = client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
    assert set(response.json()) == {"email", "location", "activity", "status", "confirmation_sent"}


def test_confirming_starts_the_alerts(mock_weather, outbox):
    engine = memory_engine()
    with patch('app.routers.subscribe.get_engine', return_value=engine):
        response = subscribe_and_confirm(outbox, email="amina@example.com", location="nairobi", language="sw")
    assert response.status_code == 200
    assert response.json() == {
        "email": "amina@example.com", "location": "Nairobi, KE", "activity": None, "status": "subscribed"
    }
    
    with Session(engine) as session:
        subscriber = session.exec(select(Subscriber)).one()
        assert session.exec(select(PendingSubscription)).all() == []
    assert subscriber.email == "amina@example.com"
    assert subscriber.location == "nairobi"
    assert subscriber.place == "Nairobi, KE"
    assert (subscriber.lat, subscriber.lon) == (-1.2921, 36.8219)
    assert subscriber.utc_offset_seconds == 10800
    assert subscriber.activity is None
    assert subscriber.language == "sw"
    assert subscriber.active is True
    assert subscriber.confirmed is True
    assert subscriber.token
    
    # Then the welcome email, with the unsubscribe link
    message = outbox[-1][1]
    assert message["Subject"] == "You're subscribed to MoodForecast for Nairobi, KE"
    link = f"https://moodforecast.test/?unsubscribe={subscriber.token}"
    text = message.get_body(("plain",)).get_content()
    assert "a new activity to try" in text
    assert "around 07:00" in text
    assert link in text
    assert link in message.get_body(("html",)).get_content()
    assert message["List-Unsubscribe"] == f"<https://moodforecast.test/api/unsubscribe/{subscriber.token}>"
    assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_confirmation_through_brevo(mock_weather, brevo):
    """The whole flow works when email goes through Brevo's API instead of SMTP."""
    sent, _ = brevo
    assert client.get("/api/alerts").json() == {"available": True}
    response = client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
    assert response.json()["confirmation_sent"] is True
    request = json.loads(sent[-1].content)
    assert request["to"] == [{"email": "amina@example.com"}]
    assert request["subject"] == "Confirm your MoodForecast alerts for Nairobi, KE"
    token = re.search(r"\?confirm=([\w-]+)", request["textContent"]).group(1)
    
    assert client.post(f"/api/confirm/{token}").status_code == 200
    welcome = json.loads(sent[-1].content)
    assert welcome["subject"] == "You're subscribed to MoodForecast for Nairobi, KE"
    assert welcome["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_a_confirmation_link_works_once(mock_weather, outbox):
    client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
    token = confirm_token(outbox)
    assert client.post(f"/api/confirm/{token}").status_code == 200
    again = client.post(f"/api/confirm/{token}")
    assert again.status_code == 404
    assert "expired or has already been used" in again.json()["detail"]


def test_a_confirmation_link_expires(mock_weather, outbox):
    engine = memory_engine()
    with patch('app.routers.subscribe.get_engine', return_value=engine):
        client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
        with Session(engine) as session:
            pending = session.exec(select(PendingSubscription)).one()
            pending.created_at -= timedelta(hours=49)
            session.add(pending)
            session.commit()
        assert client.post(f"/api/confirm/{confirm_token(outbox)}").status_code == 404


def test_an_earlier_subscriber_confirms_from_the_emailed_link(mock_weather, outbox):
    """A subscriber from before confirmation keeps their subscription and token once they confirm."""
    engine = memory_engine()
    with Session(engine) as session:
        session.add(Subscriber(
            id="old-1", email="amina@example.com", token="old-token", location="nairobi",
            place="Nairobi, KE", lat=-1.2921, lon=36.8219, activity="running", confirmed=False,
        ))
        session.commit()
    with patch('app.services.alerts.get_engine', return_value=engine), \
         patch('app.routers.subscribe.get_engine', return_value=engine):
        asyncio.run(alerts.request_confirmations())
        response = client.post(f"/api/confirm/{confirm_token(outbox)}")
    assert response.status_code == 200
    assert response.json()["activity"] == "running"
    with Session(engine) as session:
        subscriber = session.exec(select(Subscriber)).one()
    assert subscriber.confirmed is True
    assert subscriber.token == "old-token"


def test_unknown_confirmation_token(mock_weather):
    assert client.post("/api/confirm/not-a-real-token").status_code == 404


def test_changes_need_confirming_too(mock_weather, outbox):
    """Nobody can change someone else's alerts by typing their address in."""
    engine = memory_engine()
    with patch('app.routers.subscribe.get_engine', return_value=engine):
        subscribe_and_confirm(outbox, email="amina@example.com", location="Nairobi")
        with Session(engine) as session:
            token = session.exec(select(Subscriber)).one().token
        
        alerts._recently_sent.clear()
        client.post("/api/subscribe", json={
            "email": " Amina@Example.com ", "location": "Nairobi", "activity": "a picnic"
        })
        with Session(engine) as session:
            assert session.exec(select(Subscriber)).one().activity is None
        
        response = client.post(f"/api/confirm/{confirm_token(outbox)}")
    assert response.json()["status"] == "updated"
    assert response.json()["activity"] == "a picnic"
    with Session(engine) as session:
        subscriber = session.exec(select(Subscriber)).one()
    assert subscriber.activity == "a picnic"
    assert subscriber.token == token


@pytest.mark.parametrize("email", ["invalid", "amina@", "@example.com", "amina@example", "a b@example.com", ""])
def test_subscribe_rejects_malformed_email(mock_weather, email):
    """Emails need a name, an @ and a domain with a dot."""
    response = client.post("/api/subscribe", json={"email": email, "location": "Nairobi"})
    assert response.status_code == 422


def test_subscribe_understands_activities_in_free_text(mock_weather, outbox):
    """The activity is stored under the advisor's name for it."""
    response = client.post("/api/subscribe", json={
        "email": "amina@example.com", "location": "Nairobi", "activity": "Go for a run"
    })
    assert response.status_code == 202
    assert response.json()["activity"] == "running"


def test_subscribe_rejects_unknown_activity(mock_weather):
    response = client.post("/api/subscribe", json={
        "email": "amina@example.com", "location": "Nairobi", "activity": "underwater basket weaving"
    })
    assert response.status_code == 422


def test_subscribe_rejects_blank_location(mock_weather):
    """Location is required, not just present."""
    response = client.post("/api/subscribe", json={"email": "amina@example.com", "location": "   "})
    assert response.status_code == 422


def test_subscribe_rejects_unknown_location(mock_weather, outbox):
    """An alert can't be sent for a place the geocoder can't find."""
    mock_weather.get_location_by_name.return_value = {
        "error": "Location 'UnknownPlace123' not found",
        "lat": None,
        "lon": None
    }
    response = client.post("/api/subscribe", json={"email": "amina@example.com", "location": "UnknownPlace123"})
    assert response.status_code == 422
    assert "not found" in response.json()["detail"]
    assert outbox == []


def test_unsubscribe_deletes_the_subscriber(mock_weather, outbox):
    """POST /api/unsubscribe/{token} should delete their details; subscribing again starts afresh."""
    engine = memory_engine()
    
    with patch('app.routers.subscribe.get_engine', return_value=engine):
        subscribe_and_confirm(outbox, email="amina@example.com", location="Nairobi")
        alerts._recently_sent.clear()
        assert client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"}).status_code == 202
        with Session(engine) as session:
            token = session.exec(select(Subscriber)).one().token
        
        response = client.post(f"/api/unsubscribe/{token}")
        assert response.status_code == 200
        assert response.json() == {"email": "amina@example.com", "status": "unsubscribed"}
        with Session(engine) as session:
            assert session.exec(select(Subscriber)).all() == []
            assert session.exec(select(PendingSubscription)).all() == []
        
        # Using the link twice says so
        repeat = client.post(f"/api/unsubscribe/{token}")
        assert repeat.status_code == 404
        assert "already unsubscribed" in repeat.json()["detail"]
        
        alerts._recently_sent.clear()
        again = subscribe_and_confirm(outbox, email="amina@example.com", location="Nairobi")
        assert again.json()["status"] == "subscribed"
        with Session(engine) as session:
            subscriber = session.exec(select(Subscriber)).one()
            assert subscriber.active is True
            assert subscriber.token != token


@pytest.mark.parametrize("path", ["/api/confirm/abc%00def", "/api/unsubscribe/abc%00def"])
def test_a_token_with_a_nul_byte_is_just_an_unknown_token(path):
    """PostgreSQL raises on these rather than finding nothing."""
    assert client.post(path).status_code == 404


def test_nul_bytes_are_refused_before_they_reach_the_database():
    email = client.post("/api/unsubscribe-link", json={"email": "a\x00b@example.com"})
    location = client.post("/api/subscribe", json={"email": "a@example.com", "location": "Nai\x00robi"})
    assert email.status_code == 422
    assert location.status_code == 422


def test_unsubscribe_unknown_token(mock_weather):
    response = client.post("/api/unsubscribe/not-a-real-token")
    assert response.status_code == 404


def test_first_daily_alert_waits_for_the_next_morning(mock_weather, outbox):
    """Confirming after the alert hour should not trigger an alert the same day."""
    engine = memory_engine()
    # The mocked location is UTC+3: 12:00 UTC is 15:00 there, 02:00 UTC is 05:00
    afternoon = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    before_dawn = datetime(2026, 10, 5, 2, 0, tzinfo=timezone.utc)
    
    with patch('app.routers.subscribe.get_engine', return_value=engine), \
         patch('app.routers.subscribe.datetime') as clock:
        clock.now.return_value = afternoon
        subscribe_and_confirm(outbox, email="amina@example.com", location="Nairobi")
        clock.now.return_value = before_dawn
        subscribe_and_confirm(outbox, email="ben@example.com", location="Nairobi")
    
    with Session(engine) as session:
        by_email = {s.email: s for s in session.exec(select(Subscriber)).all()}
    assert by_email["amina@example.com"].last_sent_on == "2026-10-05"
    # Confirmed before the alert hour, so today's alert is still to come
    assert by_email["ben@example.com"].last_sent_on is None


def test_alerts_status_says_whether_email_is_configured(outbox):
    assert client.get("/api/alerts").json() == {"available": True}


def test_alerts_status_without_email():
    assert client.get("/api/alerts").json() == {"available": False}


def test_subscribe_needs_email_configured(mock_weather):
    """Without email the request could never be confirmed, so say so instead of storing it."""
    engine = memory_engine()
    with patch('app.routers.subscribe.get_engine', return_value=engine):
        response = client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Email alerts aren't available right now. Please try again later."
    with Session(engine) as session:
        assert session.exec(select(PendingSubscription)).all() == []


def test_subscribe_survives_a_mail_failure(mock_weather, outbox, monkeypatch):
    def unreachable(host, port, **kwargs):
        raise ConnectionRefusedError("nothing listening")
    
    monkeypatch.setattr(mailer.smtplib, "SMTP", unreachable)
    response = client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
    assert response.status_code == 202
    assert response.json()["confirmation_sent"] is False


def test_unsubscribe_link_is_emailed_to_subscribers_only(mock_weather, outbox):
    engine = memory_engine()
    
    with patch('app.routers.subscribe.get_engine', return_value=engine):
        subscribe_and_confirm(outbox, email="amina@example.com", location="Nairobi")
        # Asked for, but never confirmed
        client.post("/api/subscribe", json={"email": "ben@example.com", "location": "Nairobi"})
        with Session(engine) as session:
            token = session.exec(select(Subscriber)).one().token
        outbox.clear()
        
        subscribed = client.post("/api/unsubscribe-link", json={"email": "Amina@example.com"})
        stranger = client.post("/api/unsubscribe-link", json={"email": "nobody@example.com"})
        pending = client.post("/api/unsubscribe-link", json={"email": "ben@example.com"})
    
    # Same answer for all, so the endpoint doesn't reveal who is subscribed
    assert subscribed.status_code == stranger.status_code == pending.status_code == 202
    assert subscribed.json() == stranger.json() == pending.json() == {"status": "sent_if_subscribed"}
    
    assert len(outbox) == 1
    message = outbox[0][1]
    assert message["To"] == "amina@example.com"
    assert f"https://moodforecast.test/?unsubscribe={token}" in message.get_body(("plain",)).get_content()


def test_repeat_requests_do_not_flood_an_inbox(mock_weather, outbox):
    """Typing someone's address into the forms again and again sends each email once."""
    statuses = []
    for _ in range(5):
        response = client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
        assert response.status_code == 202
        assert response.json()["confirmation_sent"] is True
        statuses.append(response.json()["status"])
    assert statuses == ["pending"] + ["already_sent"] * 4
    assert [message["Subject"] for _, message in outbox] == ["Confirm your MoodForecast alerts for Nairobi, KE"]
    
    client.post(f"/api/confirm/{confirm_token(outbox)}")
    outbox.clear()
    for _ in range(5):
        assert client.post("/api/unsubscribe-link", json={"email": "amina@example.com"}).status_code == 202
    assert [message["Subject"] for _, message in outbox] == ["Your MoodForecast unsubscribe link"]
    
    # A different address is not held back
    client.post("/api/subscribe", json={"email": "ben@example.com", "location": "Nairobi"})
    assert outbox[-1][1]["To"] == "ben@example.com"


def test_a_quick_second_request_does_not_replace_the_emailed_one(mock_weather, outbox):
    """The link already sent applies the details it was sent for; a change has to wait for a new link."""
    engine = memory_engine()
    with patch('app.routers.subscribe.get_engine', return_value=engine):
        client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
        second = client.post("/api/subscribe", json={
            "email": "amina@example.com", "location": "Nairobi", "activity": "a picnic"
        })
        assert second.json()["status"] == "already_sent"
        with Session(engine) as session:
            assert [p.activity for p in session.exec(select(PendingSubscription))] == [None]
        assert client.post(f"/api/confirm/{confirm_token(outbox)}").json()["activity"] is None


def test_a_burst_of_searches_does_not_lift_the_inbox_guard(mock_weather, outbox):
    """Filling the shared cache must not let the same email be sent again early."""
    client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
    for n in range(cache.max_entries + 10):
        cache.set(f"suggest:place {n}", [])
    client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
    assert len(outbox) == 1


def test_unsubscribe_link_needs_email_configured(mock_weather):
    response = client.post("/api/unsubscribe-link", json={"email": "amina@example.com"})
    assert response.status_code == 503


def test_subscribe_endpoint_missing_email(mock_weather):
    """POST /api/subscribe without email should return 422."""
    response = client.post("/api/subscribe", json={
        "location": "Nairobi"
    })
    assert response.status_code == 422


def test_activities_endpoint():
    """GET /api/activities should list the activities a subscriber can choose."""
    response = client.get("/api/activities")
    assert response.status_code == 200
    assert "running" in response.json()
    assert "stargazing" in response.json()


def test_forecast_endpoint(mock_weather):
    """GET /api/forecast should return current weather for the location."""
    response = client.get("/api/forecast/Nairobi")
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "Nairobi, KE"
    assert data["weather"] == {
        "temp_c": 18,
        "feels_like_c": 16.5,
        "condition": "Partly Cloudy",
        "humidity": 74,
        "wind_kph": 12,
        "is_day": True
    }
    assert data["forecast_days"] == 2
    assert data["daily"][0] == {
        "date": "2026-10-05",
        "condition": "Clear",
        "temp_max_c": 26.0,
        "temp_min_c": 16.0,
        "precipitation_chance": 5,
        "uv_index": 9.8,
        "sunrise": "06:17",
        "sunset": "18:24",
        # 65 baseline + 15 clear + 10 comfortable (21°C average)
        "mood_score": 90,
        "mood_label": "Radiant"
    }
    # 65 baseline - 20 storm - 15 cold (9°C average) - 8 humid
    assert data["daily"][1]["mood_score"] == 22
    assert data["daily"][1]["mood_label"] == "Heavy"


def test_wellbeing_endpoint(mock_weather):
    """GET /api/wellbeing should return weather plus mood scoring."""
    response = client.get("/api/wellbeing/Nairobi")
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "Nairobi, KE"
    assert data["weather"]["condition"] == "Partly Cloudy"
    # 65 baseline - 5 cloud cover + 10 comfortable temperature
    assert data["mood_score"] == 70
    assert data["mood_label"] == "Steady"
    assert data["baseline_score"] == 65
    assert data["factors"] == [
        {"label": "Cloud cover", "delta": -5},
        {"label": "Comfortable temperature", "delta": 10}
    ]
    assert data["ai_summary"] == (
        "Partly cloudy and 18°C in Nairobi, KE. Comfortable temperature helps, "
        "while cloud cover pulls the score down."
    )
    assert data["energy_level"] in ["High", "Medium", "Low", "Very Low"]
    assert data["risk_level"] in ["Minimal", "Low", "Moderate", "High"]
    assert len(data["recommendations"]) > 0
    assert len(data["curiosity"]) == 3
    for prompt in data["curiosity"]:
        assert prompt["location"] in prompt["question"]
        assert prompt["location"] != "Nairobi"


def test_activity_endpoint(mock_weather):
    """GET /api/activity should judge an activity against the current weather."""
    response = client.get("/api/activity/Nairobi", params={"activity": "Can I go for a run?"})
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "Nairobi, KE"
    assert data["weather"]["condition"] == "Partly Cloudy"
    assert data["activity"] == "running"
    assert data["recognised"] is True
    # Partly cloudy, 18°C, 12 km/h wind, daytime: nothing in the way
    assert data["verdict"] == "go"
    assert data["reasons"] == ["Partly cloudy and 18°C with 12 km/h of wind — hard to ask for more."]
    assert data["suggestion"] is None
    assert len(data["curiosity"]["places"]) == 3


def test_activity_endpoint_says_no_when_the_weather_rules_it_out(mock_weather):
    """18°C is too cold for skiing and there is no snow."""
    response = client.get("/api/activity/Nairobi", params={"activity": "skiing"})
    assert response.status_code == 200
    data = response.json()
    assert data["activity"] == "snow sports"
    assert data["verdict"] == "skip"
    assert data["suggestion"]


def test_activity_endpoint_requires_an_activity(mock_weather):
    assert client.get("/api/activity/Nairobi").status_code == 422
    assert client.get("/api/activity/Nairobi", params={"activity": ""}).status_code == 422


def test_random_activity_endpoint(mock_weather):
    """GET /api/random-activity should pick something the weather suits."""
    response = client.get("/api/random-activity/Nairobi")
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "Nairobi, KE"
    assert data["verdict"] == "go"
    assert data["activity"] in data["headline"]
    assert len(data["reasons"]) == 2
    
    again = client.get("/api/random-activity/Nairobi", params={"exclude": data["activity"]})
    assert again.json()["activity"] != data["activity"]


def test_activity_endpoint_rules_out_what_the_place_cannot_offer(mock_weather):
    """The mocked Nairobi is inland, so the sea is out whatever the weather."""
    response = client.get("/api/activity/Nairobi", params={"activity": "Go surfing"})
    data = response.json()
    assert data["verdict"] == "skip"
    assert data["reasons"] == ["Nairobi isn't on the coast, so surfing would mean a trip to the sea first."]
    assert data["suggestion"].startswith("Something that does work in Nairobi right now: ")


def test_random_activity_fits_the_place(mock_weather):
    not_in_nairobi = {"a beach day", "surfing", "snorkelling", "sailing", "snow sports", "cricket", "baseball", "golf"}
    for _ in range(40):
        assert client.get("/api/random-activity/Nairobi").json()["activity"] not in not_in_nairobi


def test_local_activities_endpoint(mock_weather):
    """GET /api/activities/{location} should list what is practical there."""
    response = client.get("/api/activities/Nairobi")
    assert response.status_code == 200
    choices = response.json()
    assert choices[0] == {
        "name": "running", "prompt": "Go for a run", "group": "Sport and exercise", "favourite": True
    }
    # Kenya's favourites come first and are flagged; the rest are not
    favourites = [choice["name"] for choice in choices if choice["favourite"]]
    assert favourites == [choice["name"] for choice in choices[:len(favourites)]]
    assert "a safari" in favourites
    assert {choice["group"] for choice in choices} == {
        "Sport and exercise", "Out and about", "On the water", "Indoors"
    }
    names = [choice["name"] for choice in choices]
    assert "surfing" not in names
    assert "snow sports" not in names
    
    mock_weather.get_sea.return_value = {"coastal": True, "sea_temp_c": 27.6}
    names = [choice["name"] for choice in client.get("/api/activities/Mombasa").json()]
    assert "a beach day" in names


def test_local_checks_survive_a_failed_sea_lookup(mock_weather):
    """Without the sea lookup, asking is given the benefit of the doubt and picks stay cautious."""
    mock_weather.get_sea.return_value = None
    asked = client.get("/api/activity/Nairobi", params={"activity": "beach"}).json()
    # 18°C is brisk for the beach, but nothing claims Nairobi is inland
    assert asked["verdict"] == "maybe"
    assert not any("coast" in reason for reason in asked["reasons"])
    names = [choice["name"] for choice in client.get("/api/activities/Nairobi").json()]
    assert "a beach day" not in names


def test_subscribe_rejects_an_activity_the_place_cannot_offer(mock_weather, outbox):
    response = client.post("/api/subscribe", json={
        "email": "amina@example.com", "location": "Nairobi", "activity": "surfing"
    })
    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Nairobi isn't on the coast, so surfing would mean a trip to the sea first. Pick another activity."
    )
    # Uncommon is allowed - it's still possible
    response = client.post("/api/subscribe", json={
        "email": "amina@example.com", "location": "Nairobi", "activity": "cricket"
    })
    assert response.status_code == 202


def test_locations_endpoint():
    """GET /api/locations should return suggestions for what has been typed."""
    suggestion = {
        "name": "Kisumu", "region": "Kisumu County", "country": "Kenya",
        "label": "Kisumu, Kisumu County, Kenya",
    }
    with patch('app.routers.locations.suggest_locations', AsyncMock(return_value=[suggestion])) as suggest:
        response = client.get("/api/locations", params={"q": "kis"})
    assert response.status_code == 200
    assert response.json() == [suggestion]
    suggest.assert_awaited_once_with("kis")
    assert client.get("/api/locations").status_code == 422


def test_forecast_unknown_location(mock_weather):
    """GET /api/forecast with unknown location should return 422."""
    mock_weather.get_location_by_name.return_value = {
        "error": "Location 'UnknownPlace123' not found",
        "lat": None,
        "lon": None
    }
    response = client.get("/api/forecast/UnknownPlace123")
    assert response.status_code == 422
    assert "not found" in response.json()["detail"]


def test_wellbeing_unknown_location(mock_weather):
    """GET /api/wellbeing with unknown location should return 422."""
    mock_weather.get_location_by_name.return_value = {
        "error": "Location 'UnknownPlace123' not found",
        "lat": None,
        "lon": None
    }
    response = client.get("/api/wellbeing/UnknownPlace123")
    assert response.status_code == 422
    assert "not found" in response.json()["detail"]


def test_forecast_weather_service_down(mock_weather):
    """GET /api/forecast should return 503 when the weather API fails."""
    mock_weather.get_forecast.side_effect = RuntimeError("Server error")
    response = client.get("/api/forecast/Nairobi")
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "The weather service can't be reached right now. Please try again in a moment."
    )


def test_unexpected_errors_do_not_leak_details(mock_weather):
    mock_weather.get_forecast.side_effect = KeyError("secret_internal_name")
    response = client.get("/api/forecast/Nairobi")
    assert response.status_code == 500
    assert response.json()["detail"] == "Something went wrong on our side. Please try again."
    assert "secret_internal_name" not in response.text


def test_slow_weather_service_says_to_try_again(mock_weather):
    mock_weather.get_forecast.side_effect = TimeoutError("slow")
    mock_weather.get_current.side_effect = TimeoutError("slow")
    for path in ["/api/wellbeing/Nairobi", "/api/random-activity/Nairobi"]:
        response = client.get(path)
        assert response.status_code == 504
        assert response.json()["detail"] == (
            "The weather service is taking too long to answer. Please try again in a moment."
        )


def test_docs_available():
    """OpenAPI docs should be available at /docs."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "openapi" in response.json()


def test_frontend_served():
    """GET / should serve the frontend and the assets it links to."""
    response = client.get("/")
    assert response.status_code == 200
    assert "MoodForecast AI" in response.text
    for asset in ["app.js", "styles.css", "favicon.ico"]:
        assert f'"{asset}' in response.text
        assert client.get(f"/{asset}").status_code == 200


def test_frontend_is_revalidated_not_blindly_cached():
    """A cached app.js must never be paired with a newer index.html."""
    for path in ["/", "/app.js", "/styles.css"]:
        response = client.get(path)
        assert response.headers["cache-control"] == "no-cache"
        
        # An unchanged file is still cheap: the browser gets a 304, with the same instruction
        unchanged = client.get(path, headers={"If-None-Match": response.headers["etag"]})
        assert unchanged.status_code == 304
        assert unchanged.headers["cache-control"] == "no-cache"


def test_cors_lets_other_sites_read_but_not_write():
    """Other sites can read the public GET endpoints, without credentials, and can't POST."""
    response = client.get("/health", headers={"Origin": "https://other.example"})
    assert response.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in response.headers
    
    preflight = client.options("/api/subscribe", headers={
        "Origin": "https://other.example",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    # A failed preflight stops the browser sending the POST
    assert preflight.status_code == 400
    assert "POST" not in preflight.headers["access-control-allow-methods"]


@pytest.mark.parametrize("path", [
    "/api/forecast/{}", "/api/wellbeing/{}", "/api/activities/{}",
    "/api/random-activity/{}", "/api/activity/{}?activity=run",
])
def test_overlong_locations_are_refused(mock_weather, path):
    assert client.get(path.format("x" * 121)).status_code == 422
    assert client.get(path.format("Nairobi")).status_code == 200


def test_subscribe_refuses_an_overlong_location_or_unknown_language(mock_weather):
    long = client.post("/api/subscribe", json={"email": "amina@example.com", "location": "x" * 121})
    assert long.status_code == 422
    odd = client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi", "language": "xx"})
    assert odd.status_code == 422


class TestSecurityHeaders:
    """Test the headers that protect the page and the tokens in email links."""
    
    @pytest.mark.parametrize("path", ["/", "/health", "/api/alerts"])
    def test_every_response_has_them(self, path):
        response = client.get(path)
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["strict-transport-security"] == "max-age=31536000"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    
    def test_the_api_docs_keep_working_without_the_content_policy(self):
        response = client.get("/docs")
        assert response.status_code == 200
        assert "content-security-policy" not in response.headers


class TestAccessLog:
    """Test that tokens stay out of the access log."""
    
    @pytest.mark.parametrize("path, logged", [
        ("/api/unsubscribe/abc-123", "/api/unsubscribe/[token]"),
        ("/api/confirm/abc-123", "/api/confirm/[token]"),
        ("/?unsubscribe=abc-123", "/?unsubscribe=[token]"),
        ("/?confirm=abc-123&x=1", "/?confirm=[token]&x=1"),
        ("/api/unsubscribe-link", "/api/unsubscribe-link"),
        ("/api/forecast/Nairobi", "/api/forecast/Nairobi"),
    ])
    def test_tokens_are_hidden(self, path, logged):
        record = logging.LogRecord(
            "uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
            ("100.64.0.5:1", "POST", path, "1.1", 200), None
        )
        assert HideTokens().filter(record) is True
        assert record.getMessage() == f'100.64.0.5:1 - "POST {logged} HTTP/1.1" 200'


class TestLinkPreview:
    """Test the preview card shown when a link to the site is shared."""
    
    def test_the_page_carries_the_tags_and_the_image_is_served(self):
        page = client.get("/?unsubscribe=abc-123").text
        for tag in ("og:title", "og:description", "og:url", "og:type", "og:site_name"):
            assert f'property="{tag}"' in page
        assert '<meta name="twitter:card" content="summary_large_image">' in page
        assert 'name="twitter:image:alt"' in page
        assert "abc-123" not in page
        
        image_url = re.search(r'property="og:image" content="(https://[^"]+)"', page).group(1)
        image = client.get(image_url.split(".app", 1)[1])
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/png"
        assert len(image.content) < 1_000_000
    
    def test_the_privacy_page_has_its_own_card(self):
        page = client.get("/privacy.html").text
        address = re.search(r'property="og:url" content="([^"]+)"', page).group(1)
        assert address.endswith("/privacy.html")
        assert f'<link rel="canonical" href="{address}">' in page
        assert 'property="og:title" content="Privacy - MoodForecast AI"' in page
        assert 'property="og:image" content="https://' in page
        assert '<meta name="twitter:card" content="summary_large_image">' in page


class TestRateLimits:
    """Test the limits on how often one visitor can use the site."""
    
    def test_the_form_limit_stops_one_visitor_only(self, monkeypatch):
        monkeypatch.setattr(form_limiter, "limit", 1)
        body = {"email": "amina@example.com"}
        first = client.post("/api/unsubscribe-link", json=body, headers={"x-real-ip": "1.1.1.1"})
        second = client.post("/api/unsubscribe-link", json=body, headers={"x-real-ip": "1.1.1.1"})
        other = client.post("/api/unsubscribe-link", json=body, headers={"x-real-ip": "2.2.2.2"})
        
        assert first.status_code == 503  # Email isn't configured here, so it got through to the route
        assert second.status_code == 429
        assert "wait a few minutes" in second.json()["detail"]
        assert second.headers["retry-after"] == "3600"
        assert second.headers["x-content-type-options"] == "nosniff"
        assert other.status_code == 503
    
    def test_the_general_limit_covers_the_api_but_not_the_page(self, monkeypatch):
        monkeypatch.setattr(api_limiter, "limit", 1)
        assert client.get("/api/activities").status_code == 200
        assert client.get("/api/activities").status_code == 429
        assert client.get("/").status_code == 200
        assert client.get("/health").status_code == 200
    
    def test_an_oversized_request_is_refused_unread(self):
        response = client.post("/api/subscribe", content=b"x" * 5000, headers={"content-type": "application/json"})
        assert response.status_code == 413


def test_the_apps_info_lines_are_logged_and_httpx_is_quiet():
    assert logging.getLogger("app.services.alerts").getEffectiveLevel() <= logging.INFO
    assert logging.getLogger("httpx").getEffectiveLevel() == logging.WARNING


@pytest.mark.parametrize("path", [
    "/api/forecast/Nairobi",
    "/api/wellbeing/Nairobi",
    "/api/activities/Nairobi",
    "/api/activity/Nairobi?activity=run",
    "/api/random-activity/Nairobi",
])
@pytest.mark.parametrize("failure, status, words", [
    (TimeoutError("slow"), 504, "taking too long"),
    (RuntimeError("down"), 503, "can't be reached"),
    (ValueError("Not usable"), 422, "Not usable"),
    (KeyError("surprise"), 500, "went wrong on our side"),
])
def test_every_weather_route_explains_its_failures(mock_weather, path, failure, status, words):
    mock_weather.get_forecast.side_effect = failure
    mock_weather.get_current.side_effect = failure
    response = client.get(path)
    assert response.status_code == status
    assert words in response.json()["detail"]


def test_the_page_scripts_are_compressed():
    response = client.get("/app.js", headers={"accept-encoding": "gzip"})
    assert response.headers["content-encoding"] == "gzip"


def test_the_privacy_page_is_linked_and_served():
    assert 'href="privacy.html"' in client.get("/").text
    page = client.get("/privacy.html")
    assert page.status_code == 200
    assert "Unsubscribing deletes your details" in page.text


def test_search_engines_are_kept_out_of_the_api_only():
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert robots.text.splitlines() == ["User-agent: *", "Disallow: /api/"]
    assert 'rel="canonical"' in client.get("/?confirm=abc").text

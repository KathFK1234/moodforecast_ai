"""Integration tests for API endpoints with mocked weather client."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from app.main import app
from app.models.db import Subscriber
from app.services import mailer


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


def test_subscribe_endpoint_valid(mock_weather):
    """POST /api/subscribe with valid data should return 201."""
    response = client.post("/api/subscribe", json={
        "email": "amina@example.com",
        "location": "Nairobi",
        "activity": "running",
        "language": "en"
    })
    assert response.status_code == 201
    data = response.json()
    
    assert "subscriber_id" in data
    assert data["email"] == "amina@example.com"
    assert data["location"] == "Nairobi, KE"
    assert data["activity"] == "running"
    assert data["status"] == "subscribed"


def test_subscribe_persists_subscriber(mock_weather):
    """POST /api/subscribe should store the subscriber in the database."""
    engine = memory_engine()
    
    with patch('app.routers.subscribe.get_engine', return_value=engine):
        response = client.post("/api/subscribe", json={
            "email": "amina@example.com",
            "location": "nairobi",
            "language": "sw"
        })
    assert response.status_code == 201
    
    with Session(engine) as session:
        subscribers = session.exec(select(Subscriber)).all()
    assert len(subscribers) == 1
    subscriber = subscribers[0]
    assert subscriber.id == response.json()["subscriber_id"]
    assert subscriber.email == "amina@example.com"
    assert subscriber.location == "nairobi"
    assert subscriber.place == "Nairobi, KE"
    assert (subscriber.lat, subscriber.lon) == (-1.2921, 36.8219)
    assert subscriber.utc_offset_seconds == 10800
    assert subscriber.activity is None
    assert subscriber.language == "sw"
    assert subscriber.active is True
    assert subscriber.token
    assert subscriber.created_at is not None


def test_subscribing_again_updates_the_subscription(mock_weather):
    """The same email should not be stored twice."""
    engine = memory_engine()
    
    with patch('app.routers.subscribe.get_engine', return_value=engine):
        first = client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
        second = client.post("/api/subscribe", json={
            "email": " Amina@Example.com ", "location": "Nairobi", "activity": "a picnic"
        })
    assert first.json()["status"] == "subscribed"
    assert second.status_code == 201
    assert second.json()["status"] == "updated"
    assert second.json()["subscriber_id"] == first.json()["subscriber_id"]
    
    with Session(engine) as session:
        subscribers = session.exec(select(Subscriber)).all()
    assert len(subscribers) == 1
    assert subscribers[0].activity == "a picnic"


@pytest.mark.parametrize("email", ["invalid", "amina@", "@example.com", "amina@example", "a b@example.com", ""])
def test_subscribe_rejects_malformed_email(mock_weather, email):
    """Emails need a name, an @ and a domain with a dot."""
    response = client.post("/api/subscribe", json={"email": email, "location": "Nairobi"})
    assert response.status_code == 422


def test_subscribe_understands_activities_in_free_text(mock_weather):
    """The activity is stored under the advisor's name for it."""
    response = client.post("/api/subscribe", json={
        "email": "amina@example.com", "location": "Nairobi", "activity": "Go for a run"
    })
    assert response.status_code == 201
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


def test_subscribe_rejects_unknown_location(mock_weather):
    """An alert can't be sent for a place the geocoder can't find."""
    mock_weather.get_location_by_name.return_value = {
        "error": "Location 'UnknownPlace123' not found",
        "lat": None,
        "lon": None
    }
    response = client.post("/api/subscribe", json={"email": "amina@example.com", "location": "UnknownPlace123"})
    assert response.status_code == 422
    assert "not found" in response.json()["detail"]


def test_unsubscribe(mock_weather):
    """POST /api/unsubscribe/{token} should stop the alerts, and subscribing again restarts them."""
    engine = memory_engine()
    
    with patch('app.routers.subscribe.get_engine', return_value=engine):
        token = client.post(
            "/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"}
        ).json()["unsubscribe_token"]
        
        response = client.post(f"/api/unsubscribe/{token}")
        assert response.status_code == 200
        assert response.json() == {"email": "amina@example.com", "status": "unsubscribed"}
        with Session(engine) as session:
            assert session.exec(select(Subscriber)).one().active is False
        
        # Unsubscribing twice is harmless
        assert client.post(f"/api/unsubscribe/{token}").status_code == 200
        
        again = client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
        assert again.json()["status"] == "subscribed"
        assert again.json()["unsubscribe_token"] == token
        with Session(engine) as session:
            assert session.exec(select(Subscriber)).one().active is True


def test_unsubscribe_unknown_token(mock_weather):
    response = client.post("/api/unsubscribe/not-a-real-token")
    assert response.status_code == 404


def test_first_daily_alert_waits_for_the_next_morning(mock_weather):
    """Subscribing after the alert hour should not trigger an alert the same day."""
    engine = memory_engine()
    # The mocked location is UTC+3: 12:00 UTC is 15:00 there, 02:00 UTC is 05:00
    afternoon = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    before_dawn = datetime(2026, 10, 5, 2, 0, tzinfo=timezone.utc)
    
    with patch('app.routers.subscribe.get_engine', return_value=engine), \
         patch('app.routers.subscribe.datetime') as clock:
        clock.now.return_value = afternoon
        client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
        clock.now.return_value = before_dawn
        client.post("/api/subscribe", json={"email": "ben@example.com", "location": "Nairobi"})
    
    with Session(engine) as session:
        by_email = {s.email: s for s in session.exec(select(Subscriber)).all()}
    assert by_email["amina@example.com"].last_sent_on == "2026-10-05"
    # Subscribed before the alert hour, so today's alert is still to come
    assert by_email["ben@example.com"].last_sent_on is None


def test_subscribe_without_email_configured_still_subscribes(mock_weather):
    response = client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
    assert response.status_code == 201
    assert response.json()["confirmation_sent"] is False


def test_subscribe_sends_a_confirmation_email(mock_weather, outbox):
    response = client.post("/api/subscribe", json={
        "email": "amina@example.com", "location": "Nairobi", "activity": "a picnic"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["confirmation_sent"] is True
    
    assert len(outbox) == 1
    message = outbox[0][1]
    assert message["To"] == "amina@example.com"
    assert message["Subject"] == "You're subscribed to MoodForecast for Nairobi, KE"
    link = f"https://moodforecast.test/?unsubscribe={data['unsubscribe_token']}"
    text = message.get_body(("plain",)).get_content()
    assert "how the weather suits a picnic" in text
    assert "around 07:00" in text
    assert link in text
    assert link in message.get_body(("html",)).get_content()
    assert message["List-Unsubscribe"] == (
        f"<https://moodforecast.test/api/unsubscribe/{data['unsubscribe_token']}>"
    )
    assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_subscribe_survives_a_mail_failure(mock_weather, outbox, monkeypatch):
    def unreachable(host, port, **kwargs):
        raise ConnectionRefusedError("nothing listening")
    
    monkeypatch.setattr(mailer.smtplib, "SMTP", unreachable)
    response = client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
    assert response.status_code == 201
    assert response.json()["confirmation_sent"] is False


def test_unsubscribe_link_is_emailed_to_subscribers_only(mock_weather, outbox):
    engine = memory_engine()
    
    with patch('app.routers.subscribe.get_engine', return_value=engine):
        token = client.post(
            "/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"}
        ).json()["unsubscribe_token"]
        outbox.clear()
        
        subscribed = client.post("/api/unsubscribe-link", json={"email": "Amina@example.com"})
        stranger = client.post("/api/unsubscribe-link", json={"email": "nobody@example.com"})
    
    # Same answer for both, so the endpoint doesn't reveal who is subscribed
    assert subscribed.status_code == stranger.status_code == 202
    assert subscribed.json() == stranger.json() == {"status": "sent_if_subscribed"}
    
    assert len(outbox) == 1
    message = outbox[0][1]
    assert message["To"] == "amina@example.com"
    assert f"https://moodforecast.test/?unsubscribe={token}" in message.get_body(("plain",)).get_content()


def test_repeat_requests_do_not_flood_an_inbox(mock_weather, outbox):
    """Typing someone's address into the forms again and again sends each email once."""
    for _ in range(5):
        response = client.post("/api/subscribe", json={"email": "amina@example.com", "location": "Nairobi"})
        assert response.status_code == 201
        assert response.json()["confirmation_sent"] is True
    assert [message["Subject"] for _, message in outbox] == ["You're subscribed to MoodForecast for Nairobi, KE"]
    
    outbox.clear()
    for _ in range(5):
        assert client.post("/api/unsubscribe-link", json={"email": "amina@example.com"}).status_code == 202
    assert [message["Subject"] for _, message in outbox] == ["Your MoodForecast unsubscribe link"]
    
    # A different address is not held back
    client.post("/api/subscribe", json={"email": "ben@example.com", "location": "Nairobi"})
    assert outbox[-1][1]["To"] == "ben@example.com"


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
    assert choices[0] == {"name": "running", "prompt": "Go for a run"}
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


def test_subscribe_rejects_an_activity_the_place_cannot_offer(mock_weather):
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
    assert response.status_code == 201


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

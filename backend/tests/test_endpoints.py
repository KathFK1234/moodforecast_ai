"""Integration tests for API endpoints with mocked weather client."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from app.main import app
from app.models.db import Subscriber


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
            "utc_offset_seconds": 10800
        })
        
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
    assert subscriber.last_sent_on is None


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
        assert f'"{asset}"' in response.text
        assert client.get(f"/{asset}").status_code == 200

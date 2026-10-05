"""Integration tests for API endpoints with mocked weather client."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from app.main import app
from app.models.db import Subscriber


client = TestClient(app)


@pytest.fixture
def mock_weather():
    """Mock weather client for all tests."""
    with patch('app.routers.forecast.get_weather_client') as mock_forecast, \
         patch('app.routers.wellbeing.get_weather_client') as mock_wellbeing, \
         patch('app.routers.subscribe.get_engine'):
        
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
            ]
        })
        
        mock_forecast.return_value = mock_client
        mock_wellbeing.return_value = mock_client
        
        yield mock_client


def test_health_check():
    """GET /health should return ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_subscribe_endpoint_valid(mock_weather):
    """POST /api/subscribe with valid data should return 201."""
    response = client.post("/api/subscribe", json={
        "phone": "+254712345678",
        "location": "Nairobi",
        "crop": "maize",
        "language": "en"
    })
    assert response.status_code == 201
    data = response.json()
    
    assert "subscriber_id" in data
    assert data["phone"] == "+254712345678"
    assert data["location"] == "Nairobi"
    assert data["status"] == "subscribed"


def test_subscribe_persists_subscriber():
    """POST /api/subscribe should store the subscriber in the database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    
    with patch('app.routers.subscribe.get_engine', return_value=engine):
        response = client.post("/api/subscribe", json={
            "phone": "+254712345678",
            "location": "Nairobi",
            "crop": "maize",
            "language": "sw"
        })
    assert response.status_code == 201
    
    with Session(engine) as session:
        subscribers = session.exec(select(Subscriber)).all()
    assert len(subscribers) == 1
    assert subscribers[0].id == response.json()["subscriber_id"]
    assert subscribers[0].phone == "+254712345678"
    assert subscribers[0].language == "sw"
    assert subscribers[0].active is True
    assert subscribers[0].created_at is not None


@pytest.mark.asyncio
async def test_subscribe_endpoint_invalid_phone(mock_weather):
    """POST /api/subscribe with invalid phone format should return 422."""
    response = client.post("/api/subscribe", json={
        "phone": "invalid",
        "location": "Nairobi"
    })
    assert response.status_code == 422


@pytest.mark.parametrize("phone", ["+abcdefghijk", "+0712345678", "+2547", "+2547123456789012345", "254712345678"])
def test_subscribe_rejects_malformed_phone(mock_weather, phone):
    """Phone numbers must be '+' followed by 8-15 digits."""
    response = client.post("/api/subscribe", json={"phone": phone, "location": "Nairobi"})
    assert response.status_code == 422


def test_subscribe_accepts_spaces_in_phone(mock_weather):
    """Spaces are stripped before the number is stored."""
    response = client.post("/api/subscribe", json={"phone": "+254 712 345 678", "location": "Nairobi"})
    assert response.status_code == 201
    assert response.json()["phone"] == "+254712345678"


def test_subscribe_rejects_blank_location(mock_weather):
    """A location of only spaces is not a location."""
    response = client.post("/api/subscribe", json={"phone": "+254712345678", "location": "   "})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_subscribe_endpoint_missing_phone(mock_weather):
    """POST /api/subscribe without phone should return 422."""
    response = client.post("/api/subscribe", json={
        "location": "Nairobi"
    })
    assert response.status_code == 422


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

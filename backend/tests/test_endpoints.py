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
        
        # Mock current conditions in the weather client's normalised format
        mock_client.get_current = AsyncMock(return_value={
            "temperature": 18,
            "humidity": 74,
            "wind_speed": 12,
            "condition_code": 2,
            "condition": "Partly Cloudy"
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
    assert data["location"] == "Nairobi"
    assert data["weather"] == {
        "temp_c": 18,
        "condition": "Partly Cloudy",
        "humidity": 74,
        "wind_kph": 12
    }


def test_wellbeing_endpoint(mock_weather):
    """GET /api/wellbeing should return weather plus mood scoring."""
    response = client.get("/api/wellbeing/Nairobi")
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "Nairobi"
    assert data["weather"]["condition"] == "Partly Cloudy"
    assert 0 <= data["mood_score"] <= 100
    assert data["energy_level"] in ["High", "Medium", "Low", "Very Low"]
    assert data["risk_level"] in ["Minimal", "Low", "Moderate", "High"]
    assert len(data["recommendations"]) > 0


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
    mock_weather.get_current.side_effect = RuntimeError("Server error")
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

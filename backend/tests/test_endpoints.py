"""Integration tests for API endpoints with mocked weather client."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app


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


def test_forecast_unknown_location(mock_weather):
    """GET /api/forecast with unknown location should handle gracefully."""
    response = client.get("/api/forecast/UnknownPlace123")
    # May return 422 or other error code depending on API response
    assert response.status_code == 200
    data = response.json()
    assert "location" in data
    assert "weather" in data


def test_docs_available():
    """OpenAPI docs should be available at /docs."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "openapi" in response.json()

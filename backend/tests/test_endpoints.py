"""Integration tests for API endpoints with mocked WeatherAI client."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


@pytest.fixture
def mock_weatherai():
    """Mock WeatherAI client for all tests."""
    with patch('app.routers.forecast.get_weatherai_client') as mock_forecast, \
         patch('app.routers.wellbeing.get_weatherai_client') as mock_wellbeing, \
         patch('app.routers.subscribe.get_engine'):
        
        mock_client = AsyncMock()
        mock_client.get_geo_lookup = AsyncMock(return_value={
            "lat": -1.2921,
            "lon": 36.8219,
            "name": "Nairobi, KE"
        })
        mock_client.get_weather = AsyncMock(return_value={
            "current": {
                "temp_c": 18,
                "condition": "Cloudy",
                "humidity": 74,
                "wind_kph": 12
            }
        })
        mock_client.get_forecast = AsyncMock(return_value={
            "current": {
                "temp_c": 18,
                "condition": "Cloudy",
                "humidity": 74,
                "wind_kph": 12
            }
        })
        mock_client.get_insights = AsyncMock(return_value={
            "summary": "Partly cloudy skies over Nairobi with mild temperatures."
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
async def test_forecast_endpoint(mock_weatherai):
    """GET /api/forecast/{location} should return forecast data."""
    response = client.get("/api/forecast/Nairobi")
    assert response.status_code == 200
    data = response.json()
    
    assert "location" in data
    assert "weather" in data
    assert "forecast_days" in data
    assert "ai_summary" in data
    
    weather = data["weather"]
    assert "temp_c" in weather
    assert "condition" in weather
    assert "humidity" in weather


@pytest.mark.asyncio
async def test_wellbeing_endpoint(mock_weatherai):
    """GET /api/wellbeing/{location} should return mood and recommendations."""
    response = client.get("/api/wellbeing/Nairobi")
    assert response.status_code == 200
    data = response.json()
    
    assert "location" in data
    assert "weather" in data
    assert "mood_score" in data
    assert "energy_level" in data
    assert "risk_level" in data
    assert "recommendations" in data
    
    # Validate ranges
    assert 0 <= data["mood_score"] <= 100
    assert data["energy_level"] in ["High", "Medium", "Low", "Very Low"]
    assert data["risk_level"] in ["Minimal", "Low", "Moderate", "High"]
    assert isinstance(data["recommendations"], list)
    assert len(data["recommendations"]) > 0


@pytest.mark.asyncio
async def test_subscribe_endpoint_valid(mock_weatherai):
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
async def test_subscribe_endpoint_invalid_phone(mock_weatherai):
    """POST /api/subscribe with invalid phone format should return 422."""
    response = client.post("/api/subscribe", json={
        "phone": "invalid",
        "location": "Nairobi"
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_subscribe_endpoint_missing_phone(mock_weatherai):
    """POST /api/subscribe without phone should return 422."""
    response = client.post("/api/subscribe", json={
        "location": "Nairobi"
    })
    assert response.status_code == 422


def test_forecast_unknown_location(mock_weatherai):
    """GET /api/forecast with unknown location should handle gracefully."""
    mock_weatherai.get_geo_lookup = AsyncMock(return_value={
        "lat": None,
        "lon": None
    })
    response = client.get("/api/forecast/UnknownPlace123")
    # Should return 422 because coordinates couldn't be resolved
    assert response.status_code in [422, 500]


def test_docs_available():
    """OpenAPI docs should be available at /docs."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "openapi" in response.json()

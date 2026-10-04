# MoodForecast AI - Backend

FastAPI service combining the Open-Meteo weather API with a rule-based mood scoring engine.

## Quick Start

### 1. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Setup

```bash
cp .env.example .env
# No API key needed - weather data comes from Open-Meteo
```

### 3. Run Development Server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/health`

## Project Structure

```
app/
  __init__.py          # Package marker
  main.py             # FastAPI app factory, CORS, static files
  config.py           # Pydantic Settings from .env
  
  routers/            # Endpoint handlers
    forecast.py       # GET /api/forecast/{location}
    wellbeing.py      # GET /api/wellbeing/{location}
    subscribe.py      # POST /api/subscribe
  
  services/           # Business logic
    weather.py        # Open-Meteo API client with caching
    geocoding.py      # Location name → coordinates
    mood_engine.py    # Rule-based mood scoring
    cache.py          # In-memory TTL cache
  
  models/             # Data schemas
    schemas.py        # Pydantic request/response models
    db.py            # SQLModel table definitions
  
  static/             # Frontend assets (served by FastAPI)

tests/
  test_mood_engine.py    # Unit tests (no I/O)
  test_endpoints.py      # Integration tests (mocked weather client)
  test_weather.py        # Open-Meteo client tests (mocked HTTP)
  test_geocoding.py      # Geocoding tests (mocked HTTP)
```

## API Endpoints

### Production Endpoints (Live Open-Meteo Data)

**GET /api/forecast/{location}**

- Returns current weather + summary
- Cached for 10 minutes
- Example: `curl http://localhost:8000/api/forecast/Nairobi`

**GET /api/wellbeing/{location}**

- Returns mood score, energy level, risk rating, recommendations
- Cached for 10 minutes
- Example: `curl http://localhost:8000/api/wellbeing/Nairobi`

### Subscriptions

**POST /api/subscribe**

- Register for SMS/USSD alerts
- Requires: phone (E.164), location, optional: crop, language
- Example:

  ```bash
  curl -X POST http://localhost:8000/api/subscribe \
    -H "Content-Type: application/json" \
    -d '{
      "phone": "+254712345678",
      "location": "Nairobi",
      "crop": "maize",
      "language": "en"
    }'
  ```

### System

**GET /health**

- Health check for Railway deploy probe
- Example: `curl http://localhost:8000/health`

## Running Tests

### Unit Tests (Mood Engine)

```bash
pytest tests/test_mood_engine.py -v
```

All tests are deterministic with no external I/O.

### Integration Tests (Endpoints with Mocked Weather Client)

```bash
pytest tests/test_endpoints.py -v
```

Uses FastAPI TestClient with mocked weather responses.

### Run All Tests

```bash
pytest tests/ -v
```

## Environment Variables

| Variable | Required | Description | Example |
| ---------- | ---- | ------------- | --------- |
| `WEATHER_API_URL` | No | Open-Meteo base URL (only change if self-hosting) | `https://api.open-meteo.com/v1` (default) |
| `DATABASE_URL` | No | SQLite or PostgreSQL connection string | `sqlite:///./moodforecast.db` |
| `ENVIRONMENT` | No | Deployment environment | `development` or `production` |
| `REDIS_URL` | No | Redis URL for distributed caching | `redis://localhost:6379/0` |
| `CACHE_TTL_SECONDS` | No | Cache time-to-live in seconds | `600` (default: 10 minutes) |

### Weather Provider

Weather data comes from [Open-Meteo](https://open-meteo.com), an open-source weather API.
No account or API key is needed. The free hosted API is for non-commercial use
(about 10,000 calls/day); for commercial use, self-host it or use their paid plan and
point `WEATHER_API_URL` at it.

## Deployment on Railway

### Prerequisites

- GitHub repository connected to Railway

### Steps

1. **Create Railway Project**
   - Link your GitHub repo
   - Railway will auto-detect `railway.toml`

2. **Configure Environment**
   - In Railway dashboard, set `ENVIRONMENT=production`
   - Railway auto-provisions PostgreSQL if needed

3. **Deploy**
   - Push to main branch
   - Railway auto-builds and deploys

4. **Smoke Test**

   ```bash
   curl https://<your-railway-url>/health
   curl https://<your-railway-url>/api/wellbeing/Nairobi
   ```

## Mood Scoring Model

The mood engine applies additive deltas to a baseline of 65:

| Factor | Condition | Delta | Rationale |
| -------- | ----------- | ------- | ----------- |
| **Condition** | Sunny | +15 | Sunlight boosts serotonin |
| | Cloudy | −5 | Reduced UV/light exposure |
| | Rainy | −10 | Barometric drop + reduced activity |
| | Stormy | −20 | High arousal/anxiety; low pressure |
| **Temperature** | 18–24°C | +10 | Thermal comfort zone |
| | <10°C or >35°C | −15 | Thermal stress |
| **Humidity** | >80% | −8 | Suppresses energy/concentration |

**Energy Level** (0-100 scale):

- 75-100: High
- 50-74: Medium
- 25-49: Low
- 0-24: Very Low

**Risk Level**:

- 75-100: Minimal
- 50-74: Low
- 25-49: Moderate
- 0-24: High

## Performance & Caching

- **TTL Cache**: 10-minute default (configurable via `CACHE_TTL_SECONDS`)
- **Cache Key Format**: `weather:{lat}:{lon}` and `geo:{location}`
- **Swappable**: In-memory cache can be replaced with Redis (same API)

## Weather Integration

Weather calls are made through `app/services/weather.py`:

- `GET https://api.open-meteo.com/v1/forecast` — Current temperature, humidity, wind speed and WMO weather code

Location names are resolved in `app/services/geocoding.py`:

- `GET https://nominatim.openstreetmap.org/search` — Resolve location to coordinates

## Notes

- SMS/USSD alerts need a separate SMS gateway; none is integrated yet
- Subscriber data is stored in database but SMS dispatch is currently stubbed

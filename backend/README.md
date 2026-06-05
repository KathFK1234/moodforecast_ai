# MoodForecast AI - Backend

FastAPI service combining WeatherAI API with a rule-based mood scoring engine.

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
# Edit .env and add your WeatherAI API key
# WEATHERAI_API_KEY=wai_your_key_here
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
    weatherai.py      # WeatherAI API client with caching
    mood_engine.py    # Rule-based mood scoring
    cache.py          # In-memory TTL cache
  
  models/             # Data schemas
    schemas.py        # Pydantic request/response models
    db.py            # SQLModel table definitions
  
  static/             # Frontend assets (served by FastAPI)

tests/
  test_mood_engine.py    # Unit tests (no I/O)
  test_endpoints.py      # Integration tests (mocked WeatherAI)
```

## API Endpoints

### Production Endpoints (Real WeatherAI API)

**GET /api/forecast/{location}**

- Returns current weather + 7-day forecast + AI summary
- Cached for 10 minutes
- Requires: Valid `WEATHERAI_API_KEY` in `.env`
- Example: `curl http://localhost:8000/api/forecast/Nairobi`

**GET /api/wellbeing/{location}**

- Returns mood score, energy level, risk rating, recommendations
- Cached for 10 minutes
- Requires: Valid `WEATHERAI_API_KEY` in `.env`
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

### Integration Tests (Endpoints with Mocked WeatherAI)

```bash
pytest tests/test_endpoints.py -v
```

Uses FastAPI TestClient with mocked WeatherAI responses.

### Run All Tests

```bash
pytest tests/ -v
```

## Environment Variables

| Variable | Required | Description | Example |
| ---------- | ---- | ------------- | --------- |
| `WEATHERAI_API_KEY` | ✓ Yes | Your Weather-AI.co API key (for production endpoints) | `wai_fac7de...` |
| `DATABASE_URL` | ✓ Yes | SQLite or PostgreSQL connection string | `sqlite:///./moodforecast.db` |
| `ENVIRONMENT` | ✓ Yes | Deployment environment | `development` or `production` |
| `REDIS_URL` | No | Redis URL for distributed caching | `redis://localhost:6379/0` |
| `CACHE_TTL_SECONDS` | No | Cache time-to-live in seconds | `600` (default: 10 minutes) |

### Getting a Weather-AI.co API Key

1. Visit [weather-ai.co](https://weather-ai.co)
2. Sign up for an account
3. Navigate to your dashboard
4. Copy your API key
5. Add to `.env` file: `WEATHERAI_API_KEY=your_key_here`

## Deployment on Railway

### Prerequisites

- GitHub repository connected to Railway
- WeatherAI API key

### Steps

1. **Create Railway Project**
   - Link your GitHub repo
   - Railway will auto-detect `railway.toml`

2. **Configure Environment**
   - In Railway dashboard, set `WEATHERAI_API_KEY`
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
- **Cache Key Format**: `{endpoint}:{lat}:{lon}`
- **Swappable**: In-memory cache can be replaced with Redis (same API)

## WeatherAI Integration

All calls made through `app/services/weatherai.py`:

- `GET /v1/geo/lookup` — Resolve location to coordinates
- `GET /v1/weather` — Current conditions + forecast
- `GET /v1/insights` — AI-generated summary
- `GET /v1/forecast` — Hourly + daily forecast

## Notes

- SMS/USSD gateway requires WeatherAI **Scale plan** and compliance approval
- Subscriber data is stored in database but SMS dispatch is currently stubbed

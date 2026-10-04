# MoodForecast AI - Backend

FastAPI service combining the Open-Meteo weather API with a rule-based mood scoring engine. It also serves the frontend.

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Optional - the defaults work without a .env file
cp .env.example .env

uvicorn app.main:app --reload
```

The app is available at `http://localhost:8000`

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/health`

Requires Python 3.11 or newer.

## Project Structure

```text
app/
  main.py             # FastAPI app factory, CORS, static files
  config.py           # Pydantic Settings from environment / .env
  
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
    db.py             # SQLModel table definitions
  
  static/             # Deployed copy of ../frontend (served by FastAPI)

tests/
  test_mood_engine.py    # Mood engine unit tests (no I/O)
  test_endpoints.py      # Endpoint tests (mocked weather client)
  test_weather.py        # Open-Meteo client tests (mocked HTTP)
  test_geocoding.py      # Geocoding tests (mocked HTTP)
  test_static_sync.py    # static/ matches ../frontend
```

## API Endpoints

### GET /api/forecast/{location}

Current weather and a 7-day forecast.

```bash
curl http://localhost:8000/api/forecast/Nairobi
```

```json
{
  "location": "Nairobi",
  "weather": {"temp_c": 18.6, "condition": "Mainly Clear", "humidity": 62.0, "wind_kph": 11.8},
  "forecast_days": 7,
  "daily": [
    {"date": "2026-10-05", "condition": "Drizzle", "temp_max_c": 28.3, "temp_min_c": 16.0}
  ],
  "ai_summary": "Weather in Nairobi: Mainly Clear"
}
```

### GET /api/wellbeing/{location}

Current weather plus mood score, energy level, risk level and recommendations.

```bash
curl http://localhost:8000/api/wellbeing/Nairobi
```

```json
{
  "location": "Nairobi",
  "weather": {"temp_c": 18.6, "condition": "Mainly Clear", "humidity": 62.0, "wind_kph": 11.8},
  "mood_score": 90,
  "energy_level": "High",
  "risk_level": "Minimal",
  "ai_summary": "Weather analysis for Nairobi: Mainly Clear. Your mood is affected by these conditions.",
  "recommendations": ["Take a 15-minute outdoor walk before 11am while light levels are highest."]
}
```

### POST /api/subscribe

Stores a subscriber. Requires `phone` (E.164) and `location`; `crop` and `language` (`en` or `sw`) are optional.

```bash
curl -X POST http://localhost:8000/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{"phone": "+254712345678", "location": "Nairobi", "crop": "maize", "language": "en"}'
```

```json
{"subscriber_id": "550e8400-e29b-41d4-a716-446655440000", "phone": "+254712345678", "location": "Nairobi", "status": "subscribed"}
```

### GET /health

Health check used by the Railway deploy probe. Returns `{"status": "ok"}`.

### Errors

| Status | Meaning |
| ------ | ------- |
| 422 | Location not found, or invalid request body |
| 503 | Weather or geocoding service unavailable (including rate limiting) |
| 504 | Weather or geocoding request timed out |

## Running Tests

```bash
pytest tests/ -v
```

All network calls are mocked, so the tests are deterministic and run offline.

`./verify_setup.sh` checks the whole local setup (virtual environment, dependencies, config, tests, and the server if it is running).

## Environment Variables

All are optional.

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `DATABASE_URL` | `sqlite:///./moodforecast.db` | SQLite or PostgreSQL connection string |
| `CACHE_TTL_SECONDS` | `600` | Cache time-to-live in seconds |
| `ENVIRONMENT` | `development` | `development` logs SQL statements; use `production` when deployed |
| `WEATHER_API_URL` | `https://api.open-meteo.com/v1` | Open-Meteo base URL (only change if self-hosting) |

## Weather Provider

Weather data comes from [Open-Meteo](https://open-meteo.com), an open-source weather API.
No account or API key is needed. The free hosted API is for non-commercial use
(about 10,000 calls/day); for commercial use, self-host it or use their paid plan and
point `WEATHER_API_URL` at it.

Calls are made through `app/services/weather.py`:

- `GET {WEATHER_API_URL}/forecast` — current temperature, humidity, wind speed and weather code, plus daily weather code and max/min temperature for 7 days

Conditions are WMO weather codes, mapped to text in `CONDITION_MAP`.

Location names are resolved in `app/services/geocoding.py`:

- A built-in list of popular cities is checked first (no network call)
- Otherwise `GET https://nominatim.openstreetmap.org/search` (OpenStreetMap, no API key)

## Mood Scoring Model

The mood engine applies additive deltas to a baseline of 65, then clamps to 0-100:

| Factor | Condition | Delta | Rationale |
| -------- | ----------- | ------- | ----------- |
| **Condition** | Sunny / Clear | +15 | Sunlight boosts serotonin |
| | Cloudy / Overcast | −5 | Reduced UV/light exposure |
| | Rain | −10 | Barometric drop + reduced activity |
| | Storm / Thunder | −20 | High arousal/anxiety; low pressure |
| **Temperature** | 18–24°C | +10 | Thermal comfort zone |
| | <10°C or >35°C | −15 | Thermal stress |
| | 10–18°C | −5 | Cool but tolerable |
| | 24–35°C | −3 | Warm but tolerable |
| **Humidity** | >80% | −8 | Suppresses energy/concentration |

| Mood score | Energy level | Risk level |
| ---------- | ------------ | ---------- |
| 75-100 | High | Minimal |
| 50-74 | Medium | Low |
| 25-49 | Low | Moderate |
| 0-24 | Very Low | High |

## Caching

- In-memory, per process; cleared when the server restarts
- TTL of 10 minutes by default (`CACHE_TTL_SECONDS`)
- Keys: `weather:{lat}:{lon}` and `geo:{location}`
- `/api/forecast` and `/api/wellbeing` share the same cached weather for a location

## Database

Tables are created on startup. SQLite is used by default; set `DATABASE_URL` to a PostgreSQL URL for production.

```bash
sqlite3 moodforecast.db "SELECT * FROM subscriber;"
```

## Notes

- Subscribers are stored, but no SMS/USSD messages are sent - no gateway is integrated yet
- Deployment: see [../DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md)

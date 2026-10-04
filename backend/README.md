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
    common.py         # Location lookup and weather model shared by both
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

Current weather and a 7-day forecast. Each day carries the mood score expected from its forecast.

```bash
curl http://localhost:8000/api/forecast/Nairobi
```

```json
{
  "location": "Nairobi, KE",
  "weather": {
    "temp_c": 18.0, "feels_like_c": 16.7, "condition": "Mainly Clear",
    "humidity": 65.0, "wind_kph": 10.9, "is_day": false
  },
  "forecast_days": 7,
  "daily": [
    {
      "date": "2026-10-05", "condition": "Drizzle",
      "temp_max_c": 28.3, "temp_min_c": 16.0,
      "precipitation_chance": 45.0, "uv_index": 9.8,
      "sunrise": "06:17", "sunset": "18:24",
      "mood_score": 70, "mood_label": "Steady"
    }
  ],
  "ai_summary": "Weather in Nairobi, KE: Mainly Clear"
}
```

`sunrise` and `sunset` are local times at the location. A day's mood score uses its condition, the average of its maximum and minimum temperature, and its mean humidity.

### GET /api/wellbeing/{location}

Current weather plus mood score, the factors behind it, energy level, risk level, a summary and recommendations.

```bash
curl http://localhost:8000/api/wellbeing/Nairobi
```

```json
{
  "location": "Nairobi, KE",
  "weather": {
    "temp_c": 18.0, "feels_like_c": 16.7, "condition": "Mainly Clear",
    "humidity": 65.0, "wind_kph": 10.9, "is_day": false
  },
  "mood_score": 80,
  "mood_label": "Upbeat",
  "baseline_score": 65,
  "factors": [
    {"label": "Clear night", "delta": 5},
    {"label": "Comfortable temperature", "delta": 10}
  ],
  "energy_level": "High",
  "risk_level": "Minimal",
  "ai_summary": "Mainly clear and 18°C in Nairobi, KE. Clear night and comfortable temperature are lifting the mood. A calm night to rest and recharge.",
  "recommendations": ["Clear night — a few minutes of fresh air outside can help you wind down."]
}
```

`mood_score` is `baseline_score` plus the `delta` of every factor, clamped to 0-100. `ai_summary` is written from those factors by rules in `mood_engine.py`; no language model is involved.

### POST /api/subscribe

Stores a subscriber. Requires `phone` (E.164: `+` then 8-15 digits) and `location`; `crop` and `language` (`en` or `sw`) are optional.

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

- `GET {WEATHER_API_URL}/forecast` — current temperature, feels-like, humidity, wind speed, day/night and weather code, plus 7 days of weather code, max/min temperature, mean humidity, chance of precipitation, UV index, sunrise and sunset

Conditions are WMO weather codes, mapped to text in `CONDITION_MAP`.

Location names are resolved in `app/services/geocoding.py`:

- A built-in list of popular cities is checked first (no network call)
- Otherwise `GET https://nominatim.openstreetmap.org/search` (OpenStreetMap, no API key)

## Mood Scoring Model

The mood engine applies additive deltas to a baseline of 65, then clamps to 0-100:

| Factor | Condition | Delta | Rationale |
| -------- | ----------- | ------- | ----------- |
| **Condition** | Sunny / Clear (day) | +15 | Sunlight boosts serotonin |
| | Clear (night) | +5 | Calm, but no sunlight to benefit from |
| | Cloudy / Overcast | −5 | Reduced UV/light exposure |
| | Drizzle, Snow or Fog | −5 | Low light, mild disruption |
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

| Mood score | Mood label |
| ---------- | ---------- |
| 85-100 | Radiant |
| 75-84 | Upbeat |
| 60-74 | Steady |
| 50-59 | Mellow |
| 35-49 | Subdued |
| 25-34 | Drained |
| 0-24 | Heavy |

Recommendations also depend on the time of day: daylight advice is replaced with wind-down advice at night.

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

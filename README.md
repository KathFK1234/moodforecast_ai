# MoodForecast AI

Weather and mood forecasting in one page. MoodForecast AI takes live weather for any location, scores how those conditions are likely to affect mood and energy, and gives practical wellbeing recommendations.

## Quick Start

```bash
git clone https://github.com/KathFK1234/moodforecast_ai.git
cd moodforecast_ai/backend

# Create a virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Optional - the defaults work without a .env file
cp .env.example .env

# Run
uvicorn app.main:app --reload
```

Then open:

- App: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

No API key is needed. Weather data comes from [Open-Meteo](https://open-meteo.com), an open-source weather API.

If port 8000 is already in use, pick another one: `uvicorn app.main:app --reload --port 8001`.

## Features

- **Live weather** - current conditions and a 7-day forecast from Open-Meteo
- **Mood scoring** - rule-based score (0-100) with energy and risk levels
- **Recommendations** - wellbeing tips based on condition, temperature and humidity
- **Any location** - place names are resolved with OpenStreetMap's Nominatim
- **Subscriptions** - stores phone, location, crop and language for future SMS alerts (sending is not implemented yet)
- **Caching** - repeat requests are answered from an in-memory cache

## Project Structure

```text
moodforecast_ai/
├── backend/
│   ├── app/
│   │   ├── main.py            # App factory, CORS, static files
│   │   ├── config.py          # Settings from environment / .env
│   │   ├── models/            # Database table and request/response schemas
│   │   ├── routers/           # forecast, wellbeing, subscribe endpoints
│   │   ├── services/          # weather, geocoding, mood engine, cache
│   │   └── static/            # Deployed copy of frontend/
│   ├── tests/                 # pytest suite
│   ├── requirements.txt
│   ├── .env.example
│   ├── Dockerfile
│   ├── railway.toml
│   └── verify_setup.sh        # Checks the local setup
├── frontend/                  # Frontend source (HTML, CSS, JS)
├── run_tests.sh               # Checks a running backend end to end
├── DEPLOYMENT_GUIDE.md        # Deploying to Railway / Docker
└── README.md
```

More detail: [backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md), [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

## API Endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/forecast/{location}` | Current weather and 7-day forecast |
| GET | `/api/wellbeing/{location}` | Current weather, mood score, energy, risk, recommendations |
| POST | `/api/subscribe` | Register a subscriber |
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI |

```bash
curl http://localhost:8000/api/forecast/Nairobi
curl http://localhost:8000/api/wellbeing/Kisumu
```

Errors: `422` location not found, `503` weather or geocoding service unavailable, `504` upstream timeout.

## Environment Variables

All are optional.

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `DATABASE_URL` | `sqlite:///./moodforecast.db` | SQLite or PostgreSQL connection string |
| `CACHE_TTL_SECONDS` | `600` | How long weather and geocoding results are cached |
| `ENVIRONMENT` | `development` | `development` logs SQL statements; use `production` when deployed |
| `WEATHER_API_URL` | `https://api.open-meteo.com/v1` | Only change this if you self-host Open-Meteo |

## Testing

```bash
cd backend
source venv/bin/activate
pytest tests/ -q
```

The tests mock all network calls, so they run offline.

Two helper scripts check a full setup:

```bash
# Local setup: venv, dependencies, config, tests
./backend/verify_setup.sh

# End-to-end against a running backend
./run_tests.sh

# Both accept another address if the backend is not on port 8000
BASE_URL=http://localhost:8001 ./run_tests.sh
```

## Frontend Development

The backend serves the files in `backend/app/static/`, which is a copy of `frontend/`. Edit the files in `frontend/`, then copy them across:

```bash
cp frontend/index.html frontend/app.js frontend/styles.css backend/app/static/
```

A test (`tests/test_static_sync.py`) fails if the two copies differ.

## Deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

## Troubleshooting

**Backend won't start** - check `python3 --version` is 3.11 or newer, the virtual environment is activated, and the port is free (`lsof -i :8000`).

**`venv/bin/python` fails after a system upgrade** - the virtual environment points at a Python that no longer exists. Delete `backend/venv` and create it again.

**"Location not found"** - check the spelling, or add the country (`Kisumu, Kenya`).

**"Weather service unavailable"** - Open-Meteo or Nominatim could not be reached. Check your connection:

```bash
curl "https://api.open-meteo.com/v1/forecast?latitude=-1.29&longitude=36.82&current=temperature_2m"
```

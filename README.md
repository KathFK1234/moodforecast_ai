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

- **Live weather** - current conditions, feels-like, rain chance, UV, sunrise and sunset from Open-Meteo
- **Mood scoring** - rule-based score (0-100) with a mood label, energy and risk levels
- **Why this score** - the factors that raised or lowered the score, and by how much
- **7-day mood outlook** - expected mood for each day of the forecast
- **Recommendations** - varied activity ideas and wellbeing tips based on condition, temperature, humidity and time of day; they change between visits
- **Activity check** - ask whether the weather somewhere suits a run, a picnic, a swim, stargazing and more, and get a go, maybe or skip with the reasons
- **Surprise me** - a random activity the current weather suits, different on every visit and every tap
- **Stay curious** - questions about the weather in other places, one tap away
- **Location suggestions** - matching places appear as you type in either location field
- **Weather-aware design** - the page's background follows the weather and day or night
- **Any location** - place names are resolved with OpenStreetMap's Nominatim
- **Daily email alerts** - subscribe with an email, a location and an activity (or a random pick each day); a confirmation goes out straight away and the alert every morning, local time. Every email has an unsubscribe link. Needs SMTP settings, see below
- **Caching** - repeat requests are answered from an in-memory cache

## Project Structure

```text
moodforecast_ai/
├── backend/
│   ├── app/
│   │   ├── main.py            # App factory, CORS, static files
│   │   ├── config.py          # Settings from environment / .env
│   │   ├── models/            # Database table and request/response schemas
│   │   ├── routers/           # forecast, wellbeing, activity, locations, subscribe endpoints
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
| GET | `/api/forecast/{location}` | Current weather and 7-day forecast with a mood outlook per day |
| GET | `/api/wellbeing/{location}` | Current weather, mood score and the factors behind it, energy, risk, recommendations |
| GET | `/api/activity/{location}?activity=...` | Whether the current weather suits an activity: go, maybe or skip, with reasons |
| GET | `/api/random-activity/{location}` | A random activity that the current weather suits |
| GET | `/api/locations?q=...` | Places matching what has been typed so far |
| GET | `/api/activities` | The activities a subscriber can choose from |
| POST | `/api/subscribe` | Subscribe an email address to daily alerts, or update its subscription |
| POST | `/api/unsubscribe/{token}` | Stop the alerts for a subscription |
| POST | `/api/unsubscribe-link` | Email a subscriber their unsubscribe link |
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI |

```bash
curl http://localhost:8000/api/forecast/Nairobi
curl http://localhost:8000/api/wellbeing/Kisumu
```

The page also accepts a location in the link, e.g. `http://localhost:8000/?q=Kisumu`.

Errors: `422` location not found, `503` weather or geocoding service unavailable, `504` upstream timeout.

## Environment Variables

All are optional.

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `DATABASE_URL` | `sqlite:///./moodforecast.db` | SQLite or PostgreSQL connection string |
| `CACHE_TTL_SECONDS` | `600` | How long weather and geocoding results are cached |
| `ENVIRONMENT` | `development` | `development` logs SQL statements; use `production` when deployed |
| `WEATHER_API_URL` | `https://api.open-meteo.com/v1` | Only change this if you self-host Open-Meteo |
| `SMTP_HOST` | (unset) | SMTP server for confirmation emails and daily alerts, e.g. `smtp.gmail.com`. Nothing is sent until this and `MAIL_FROM` are set |
| `SMTP_PORT` | `587` | `465` connects over TLS; other ports upgrade with STARTTLS |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | (unset) | SMTP login. For Gmail, your address and an [app password](https://myaccount.google.com/apppasswords) |
| `SMTP_STARTTLS` | `true` | Set to `false` only for a local test server without TLS |
| `MAIL_FROM` | (unset) | Sender, e.g. `MoodForecast <you@gmail.com>` |
| `PUBLIC_URL` | `http://localhost:8000` | Public address of the site, used for the unsubscribe links in emails |
| `ALERT_HOUR` | `7` | Local hour (0-23) at each subscriber's location when the daily alert is sent |

To check that email works, set the SMTP variables in `backend/.env` and run, from `backend/`:

```bash
python -m app.services.mailer you@example.com   # sends one test message
python -m app.services.alerts --all             # sends today's alert to every subscriber now
```

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

# MoodForecast AI - Deployment Guide

The backend and frontend deploy together as one service: FastAPI serves the API and the static frontend from the same container.

## Architecture

```text
Browser
   ↕
FastAPI (backend/app)
   ├── Static frontend      backend/app/static
   ├── Routers              forecast, wellbeing, subscribe
   ├── Services             weather, geocoding, mood engine, cache
   └── Database             SQLite or PostgreSQL (subscriber table)
   ↕
Open-Meteo (weather)  +  Nominatim / OpenStreetMap (geocoding)
```

Request flow for a search:

```text
Location name → geocoding → latitude/longitude → Open-Meteo
             → current conditions + 7-day forecast → mood engine → response
```

Neither external service needs an API key.

## Before You Deploy

```bash
cd backend
source venv/bin/activate
pytest tests/ -q
```

If you changed anything in `frontend/`, copy it into the deployed location first:

```bash
cp frontend/index.html frontend/app.js frontend/styles.css backend/app/static/
```

## Railway

### 1. Push to GitHub

```bash
git push origin main
```

### 2. Create the Project

1. Visit `https://railway.app`
2. Click "New Project" → "Deploy from GitHub repo"
3. Select the `moodforecast_ai` repository
4. Click "Deploy"

The build uses `backend/Dockerfile` and `backend/railway.toml`. Railway redeploys automatically on every push to `main`.

### 3. Set Variables

In the project's "Variables" tab:

| Variable | Value |
| -------- | ----- |
| `ENVIRONMENT` | `production` |
| `CACHE_TTL_SECONDS` | `600` (optional) |
| `DATABASE_URL` | PostgreSQL URL (recommended, see below) |

Variables left over from the old weather provider, such as `WEATHERAI_API_KEY`, are ignored and can be deleted.

**Database:** if `DATABASE_URL` is not set, the app uses a SQLite file inside the container. That file is lost on every redeploy, so subscribers will not persist. To keep them, add a PostgreSQL database in Railway and set `DATABASE_URL` to its connection URL. Tables are created on startup.

### 4. Verify

```bash
curl https://YOUR_DOMAIN/health
# {"status":"ok"}

curl https://YOUR_DOMAIN/api/forecast/Nairobi
curl https://YOUR_DOMAIN/api/wellbeing/London
```

Then open `https://YOUR_DOMAIN` in a browser, search for a few locations and submit the subscribe form.

## Docker

```bash
cd backend
docker build -t moodforecast .
docker run -p 8000:8000 -e ENVIRONMENT=production moodforecast
```

The container listens on `$PORT` if it is set, otherwise 8000.

## Environment Variables

All are optional.

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `DATABASE_URL` | `sqlite:///./moodforecast.db` | SQLite or PostgreSQL connection string |
| `CACHE_TTL_SECONDS` | `600` | How long weather and geocoding results are cached |
| `ENVIRONMENT` | `development` | `development` logs SQL statements; use `production` when deployed |
| `WEATHER_API_URL` | `https://api.open-meteo.com/v1` | Only change this if you self-host Open-Meteo |
| `PORT` | `8000` | Set by Railway |

## Open-Meteo Usage Limits

The free hosted Open-Meteo API is for non-commercial use, at about 10,000 calls per day. Results are cached per location, so normal use stays well below that. For commercial use, self-host Open-Meteo or use their paid plan and point `WEATHER_API_URL` at it.

## Troubleshooting

| Issue | What to check |
| ----- | ------------- |
| Build fails | Railway build logs; `backend/requirements.txt` installs locally |
| App crashes on start | Railway deploy logs; `DATABASE_URL` is a valid URL if set |
| "Location not found" (422) | Spelling of the location; try adding the country |
| "Weather service unavailable" (503) | Open-Meteo or Nominatim is unreachable or rate limiting - retry shortly |
| Timeout (504) | Upstream service is slow - retry shortly |
| Frontend shows old content | `backend/app/static/` was not updated from `frontend/`; browser cache |
| Subscribers disappear after deploy | `DATABASE_URL` is not set, so SQLite inside the container is being used |
| Stale weather | Results are cached for `CACHE_TTL_SECONDS`; restarting clears the cache |

To see request details:

```bash
curl -v https://YOUR_DOMAIN/api/forecast/Nairobi
```

## After Deployment Checklist

- [ ] `/health` returns `{"status":"ok"}`
- [ ] Different locations return different weather
- [ ] The 7-day forecast shows in the weather card
- [ ] Mood score and recommendations show
- [ ] The subscribe form returns a subscriber ID
- [ ] No errors in the browser console or the Railway logs

## References

- FastAPI: `https://fastapi.tiangolo.com`
- Railway: `https://docs.railway.app`
- Open-Meteo: `https://open-meteo.com/en/docs`
- Nominatim usage policy: `https://operations.osmfoundation.org/policies/nominatim/`

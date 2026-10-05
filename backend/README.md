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
    activity.py       # GET /api/activity, /api/random-activity, /api/activities[/{location}]
    locations.py      # GET /api/locations
    subscribe.py      # POST /api/subscribe, /api/unsubscribe/{token}, /api/unsubscribe-link
  
  services/           # Business logic
    weather.py        # Open-Meteo API client with caching
    geocoding.py      # Location name → coordinates
    mood_engine.py    # Rule-based mood scoring
    activity_advisor.py  # Whether an activity suits the weather and the place; random picks
    locality.py       # What a place can offer: coast, snow country, local sports and favourites
    curiosity.py      # Questions about other places
    mailer.py         # SMTP email
    alerts.py         # Confirmation and daily alert emails, and the daily send
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
  test_activity_advisor.py  # Activity rules and random picks (no I/O)
  test_curiosity.py      # Curiosity prompts (no I/O)
  test_mailer.py         # Mailer tests (fake SMTP)
  test_alerts.py         # Alert emails and the daily send (fake SMTP and weather)
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
  "recommendations": ["Clear night — a few minutes of fresh air outside can help you wind down."],
  "curiosity": [
    {"question": "It's night here — is the sun up in Tokyo?", "location": "Tokyo"},
    {"question": "Take a guess: is it warmer in Lisbon than here? Tap to find out.", "location": "Lisbon"},
    {"question": "What's the mood like in Cape Town today?", "location": "Cape Town"}
  ]
}
```

`mood_score` is `baseline_score` plus the `delta` of every factor, clamped to 0-100. `ai_summary` is written from those factors by rules in `mood_engine.py`; no language model is involved.

Each recommendation is picked at random from a pool of ideas that fit the conditions (a picnic or a bike ride on a clear day, a board game or a new recipe in the rain, stargazing on a clear night), so repeated requests for the same weather return different suggestions.

`curiosity` holds three questions about other places, each with the `location` to search to answer it. They lean towards contrast (somewhere cold when it is hot here, somewhere dry when it is raining) and never claim to know the weather there.

### GET /api/activity/{location}?activity=...

Whether the current weather at a location suits something you want to do. `activity` is free text, a single word or a whole question.

```bash
curl "http://localhost:8000/api/activity/Nairobi?activity=Can+I+have+a+picnic"
```

```json
{
  "location": "Nairobi, KE",
  "weather": {
    "temp_c": 19.0, "feels_like_c": 18.2, "condition": "Light Rain",
    "humidity": 82.0, "wind_kph": 9.0, "is_day": true
  },
  "activity": "a picnic",
  "recognised": true,
  "verdict": "skip",
  "headline": "I'd hold off on a picnic for now.",
  "reasons": ["It's raining, which rather spoils it."],
  "suggestion": "Swap it for a new recipe, a board game or a film marathon.",
  "curiosity": {
    "question": "Wonder where it's better for a picnic right now? Check:",
    "places": ["Lisbon", "Cape Town", "Sydney"]
  }
}
```

`verdict` is `go`, `maybe` (possible, with the caveats in `reasons`) or `skip`. `suggestion` is only set for `skip`. The rules live in `activity_advisor.py`: outdoor exercise, outdoor leisure, swimming, snow sports, stargazing, wind sports and indoor activities are each judged against the condition, temperature, humidity, wind and daylight. A question that matches none of the known activities is answered for general time outdoors, with `recognised` set to `false`.

The place is judged before the weather (see [Local Fit](#local-fit)). Asking about something the place can't offer is a `skip` with the reason and a local alternative:

```json
{
  "activity": "surfing",
  "verdict": "skip",
  "reasons": ["Nairobi isn't on the coast, so surfing would mean a trip to the sea first."],
  "suggestion": "Something that does work in Nairobi right now: hiking. Find a hill, bring water, earn the view."
}
```

### GET /api/random-activity/{location}

A random activity that suits the place and its current weather, in the same shape as the activity check. Activities the place can't offer, or where they aren't commonly done, are never picked, and ones that are popular in its country come up more often. Only activities with nothing in their way are picked, so `verdict` is always `go`; outdoor ones are preferred when any qualify, and indoor ones always do. Pass `exclude=<activity>` (the `activity` from the previous pick) to get a different one.

```bash
curl "http://localhost:8000/api/random-activity/Nairobi?exclude=camping"
```

### GET /api/locations?q=...

Up to five places matching what has been typed so far, for search-as-you-type. Uses Open-Meteo's geocoding API. Returns an empty list for fewer than two characters or if the lookup fails.

```bash
curl "http://localhost:8000/api/locations?q=kis"
```

```json
[
  {"name": "Kisumu", "region": "Kisumu County", "country": "Kenya", "label": "Kisumu, Kisumu County, Kenya"}
]
```

`label` is the text to search for. A label that came from this endpoint resolves to exactly that place.

### GET /api/activities

The names of every activity the advisor knows: `["running", "a walk", "cycling", ...]`.

### GET /api/activities/{location}

The activities that are practical at a location, local favourites first. The page uses it for the quick picks and for the subscription form's activity list.

```bash
curl http://localhost:8000/api/activities/Nairobi
```

```json
[
  {"name": "running", "prompt": "Go for a run"},
  {"name": "hiking", "prompt": "Go hiking"},
  {"name": "football", "prompt": "Play football"}
]
```

### POST /api/subscribe

Subscribes an email address to daily alerts for a location. Requires `email` and `location`. `activity` is optional: one of the names from `/api/activities` (free text such as "go for a run" is understood too), or omitted for a random pick each day. `language` (`en` or `sw`) is still accepted and stored, but the page no longer asks for it: emails are written in English only.

```bash
curl -X POST http://localhost:8000/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{"email": "amina@example.com", "location": "Nairobi", "activity": "running"}'
```

```json
{
  "subscriber_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "amina@example.com",
  "location": "Nairobi, KE",
  "activity": "running",
  "status": "subscribed",
  "unsubscribe_token": "dpBmuKD_4mX-H5PNjM9cc0IiXxA022Yb",
  "confirmation_sent": true
}
```

The location must be one the geocoder can find, and the activity one that can be done there: surfing in an inland town is refused with the reason (both 422). Subscribing again with the same email updates that subscription and returns `"status": "updated"`. `confirmation_sent` is `false` when email is not configured or the confirmation could not be sent; the subscription is stored either way.

### POST /api/unsubscribe/{token}

Stops the alerts for the subscription the token belongs to. The token is the `unsubscribe_token` from subscribing, and is in the link in every email. Returns `{"email": "...", "status": "unsubscribed"}`, or 404 for an unknown token. Subscribing again with the same email turns the alerts back on.

### POST /api/unsubscribe-link

Emails a subscriber their unsubscribe link, for when they have no alert email to hand. Body: `{"email": "amina@example.com"}`. Always answers 202 with `{"status": "sent_if_subscribed"}`, so it does not reveal who is subscribed. Returns 503 if email is not configured.

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
| `MARINE_API_URL` | `https://marine-api.open-meteo.com/v1` | Open-Meteo marine API, used to tell whether a place is by the sea |
| `SMTP_HOST` | (unset) | SMTP server for confirmation emails and daily alerts, e.g. `smtp.gmail.com`. Nothing is sent until this and `MAIL_FROM` are set |
| `SMTP_PORT` | `587` | `465` connects over TLS; other ports upgrade with STARTTLS |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | (unset) | SMTP login. For Gmail, your address and an [app password](https://myaccount.google.com/apppasswords) |
| `SMTP_STARTTLS` | `true` | Set to `false` only for a local test server without TLS |
| `MAIL_FROM` | (unset) | Sender, e.g. `MoodForecast <you@gmail.com>` |
| `PUBLIC_URL` | `http://localhost:8000` | Public address of the site, used for the unsubscribe links in emails |
| `ALERT_HOUR` | `7` | Local hour (0-23) at each subscriber's location when the daily alert is sent |

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
- Then places already looked up since the server started, or offered as suggestions
- Otherwise `GET https://nominatim.openstreetmap.org/search` (OpenStreetMap, no API key)
- If Nominatim can't be reached, Open-Meteo's geocoder is tried instead

Lookups for the same name made at the same moment share one request, which keeps the app within Nominatim's limit of one request per second for a single search.

Suggestions while typing come from `GET https://geocoding-api.open-meteo.com/v1/search` instead, because Nominatim's usage policy does not allow autocomplete.

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

## Local Fit

Advice is checked against the place as well as the weather, so an inland city is never offered a beach day. Three facts about a location are used, gathered in `app/services/locality.py`:

| Fact | Source | Used for |
| ---- | ------ | -------- |
| Open sea within about 20 km, and its temperature | Open-Meteo marine API (`get_sea` in `weather.py`) | A beach day, sailing, surfing, snorkelling (which also needs the sea at 20°C or more) |
| Latitude and elevation | Open-Meteo forecast | Snow sports: a skiing country, and at least 36° from the equator or 1,000 m up. Falling snow makes them possible anywhere |
| Country | Geocoder | Sports that are only common in some countries: cricket, baseball, rugby, golf, surfing |

Each activity in `activity_advisor.py` declares what it needs (`needs`). The rules are applied two ways:

- **Asked about** (`/api/activity`, a subscriber's chosen activity): something the place can't offer is a `skip`; a sport that isn't common there is a `maybe`. Anything unknown, such as a failed sea lookup, gets the benefit of the doubt.
- **Suggested unprompted** (`/api/random-activity`, `/api/activities/{location}`, the daily email's random pick): only what is confirmed practical is offered, so the unknown is left out.

`LOCAL_FAVOURITES` lists activities that are especially popular in a country; random picks choose them three times as often. `LOCAL_PITCHES` in `activity_advisor.py` words a suggestion the local way (nyama choma in Kenya, a braai in South Africa, an asado in Argentina).

Limits worth knowing:

- The country lists and favourites are hand-written judgement calls, by country, not by city. Edit them in `locality.py` where they are wrong for a place you know.
- The sea check does not see lakes or rivers, so lakeside towns such as Kisumu are treated as inland for beach days and sailing. Swimming and fishing are offered everywhere.
- Nothing checks for actual facilities: a football pitch, a pool or a hiking trail is assumed to be within reach.

## Caching

- In-memory, per process; cleared when the server restarts
- TTL of 10 minutes by default (`CACHE_TTL_SECONDS`)
- Keys: `weather:{lat}:{lon}`, `sea:{lat}:{lon}`, `geo:{location}` and `suggest:{query}`
- `/api/forecast` and `/api/wellbeing` share the same cached weather for a location
- Requests for the same forecast made at the same moment share one call to Open-Meteo
- A forecast request that times out or hits a server error is retried once. If Open-Meteo still can't be reached, the last forecast for that place is served if it is under an hour old

## Database

Tables are created on startup. SQLite is used by default; set `DATABASE_URL` to a PostgreSQL URL for production.

```bash
sqlite3 moodforecast.db "SELECT email, place, activity, active, last_sent_on FROM alert_subscriber;"
```

Subscribers are in `alert_subscriber`. A database created before email alerts also has a `subscriber` table of phone numbers; it is no longer read or written.

## Email Alerts

Email is sent over SMTP by `app/services/mailer.py`, using the `SMTP_*` and `MAIL_FROM` variables above. Until `SMTP_HOST` and `MAIL_FROM` are set nothing is sent: subscriptions are still stored, and the startup log says daily alerts are off.

```bash
python -m app.services.mailer you@example.com   # send one test message
python -m app.services.alerts                   # send the alerts that are due now
python -m app.services.alerts --all             # send to every active subscriber now
```

Three emails exist, all composed in `app/services/alerts.py` as plain text with an HTML alternative:

- **Confirmation** - sent when someone subscribes or changes their subscription
- **Daily alert** - current weather, the mood score and summary, today's outlook, the subscriber's activity judged against the weather (or a random pick that suits it), a recommendation, and a question about another place
- **Unsubscribe link** - sent on request from `/api/unsubscribe-link`

The confirmation and the unsubscribe link can be triggered by anyone typing an address into the site, so each is sent at most once per address per cache lifetime (`CACHE_TTL_SECONDS`, 10 minutes by default).

Every email ends with an unsubscribe link to `PUBLIC_URL/?unsubscribe=<token>`, where the page asks for confirmation, and carries `List-Unsubscribe` headers so mail apps can show their own unsubscribe button.

The daily send runs inside the web process: a background task started with the app checks every 15 minutes for subscribers where it is past `ALERT_HOUR` local time and today's alert has not gone out. A subscriber is marked as sent only after their email is accepted, so a failed send is retried on the next check. Someone who subscribes after `ALERT_HOUR` gets their first alert the next morning. Because the task runs in every process, run a single instance of the app, or each one will send its own copy.

## Notes

- Emails are in English only, so the page's subscribe form has no language choice
- Subscribing does not ask the address owner to confirm first (no double opt-in), so anyone can sign an address up; every email has an unsubscribe link
- Deployment: see [../DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md)

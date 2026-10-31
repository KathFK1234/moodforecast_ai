# MoodForecast AI - Backend

FastAPI service combining the Open-Meteo weather API with a rule-based mood scoring engine. It also serves the frontend.

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-dev.txt -c constraints.txt   # the app and its test tools

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
  main.py             # FastAPI app factory, CORS, security headers, rate limits, static files
  config.py           # Pydantic Settings from environment / .env
  
  routers/            # Endpoint handlers
    forecast.py       # GET /api/forecast/{location}
    wellbeing.py      # GET /api/wellbeing/{location}
    common.py         # Location lookup, weather model and error handling shared by the routes
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
    mailer.py         # Email through Brevo's API or SMTP
    alerts.py         # Confirmation and daily alert emails, and the daily send
    cache.py          # In-memory TTL cache
    rate_limit.py     # In-memory limit per visitor
  
  models/             # Data schemas
    schemas.py        # Pydantic request/response models
    db.py             # SQLModel table definitions
  
  static/             # Deployed copy of ../frontend (served by FastAPI)

browser_tests/        # The page in a real browser (see requirements-browser.txt)

tests/
  test_mood_engine.py    # Mood engine unit tests (no I/O)
  test_endpoints.py      # Endpoint tests (mocked weather client)
  test_weather.py        # Open-Meteo client tests (mocked HTTP)
  test_geocoding.py      # Geocoding tests (mocked HTTP)
  test_activity_advisor.py  # Activity rules and random picks (no I/O)
  test_curiosity.py      # Curiosity prompts (no I/O)
  test_locality.py       # Place facts: country, coast, late night (no I/O)
  test_cache.py          # In-memory cache: expiry and size limit
  test_db.py             # Database URL handling (Postgres driver)
  test_dependencies.py   # constraints.txt matches the requirements files
  test_mailer.py         # Mailer tests (fake SMTP)
  test_postgres.py       # Database code on real PostgreSQL (needs TEST_DATABASE_URL)
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

`verdict` is `go`, `maybe` (possible, with the caveats in `reasons`) or `skip`. `suggestion` is only set for `skip`. The rules live in `activity_advisor.py`: outdoor exercise, outdoor leisure, swimming, paddling, snow sports, stargazing, wind sports and indoor activities are each judged against the condition, temperature, humidity, wind and daylight.

Some activities have rules of their own on top:

- Wet surfaces (rain, drizzle, snow) rule out skateboarding, roller skating and rock climbing.
- Rock climbing, horse riding, kayaking, water parks and birdwatching need daylight.
- Rock climbing, kayaking (canoeing, paddleboarding, rowing) and boat trips have lower wind limits.
- Kayaking is judged on how cold a capsize would be, so below 5°C it is a skip.
- Barbecues and bonfires have lower wind limits, and in hot, dry air (28°C or more, under 30% humidity) they get a fire ban warning.
- Ice skating is judged as a rink, so it is always a go, and the answer always reminds you that ice on a pond or lake is only safe once it has been checked.

A question that matches none of the known activities is answered for general time outdoors, with `recognised` set to `false`.

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

The activities that are practical at a location, local favourites first. Each has a `group` (Sport and exercise, Out and about, On the water, Snow or Indoors) and `favourite`, which is `true` when it is especially popular in the location's country. The page uses it for the quick picks and for the subscription form's activity list, where favourites are listed first under "Popular here" and the rest by group.

```bash
curl http://localhost:8000/api/activities/Nairobi
```

```json
[
  {"name": "running", "prompt": "Go for a run", "group": "Sport and exercise", "favourite": true},
  {"name": "hiking", "prompt": "Go hiking", "group": "Sport and exercise", "favourite": true},
  ...
  {"name": "a nap", "prompt": "Take a nap", "group": "Indoors", "favourite": false}
]
```

### GET /api/alerts

`{"available": true}` when email is configured, so alerts can be signed up for; `false` otherwise. The page uses it to disable the subscribe form, with a note, instead of letting someone fill it in only to be refused.

### POST /api/subscribe

Asks for daily alerts for a location, or for a change to an existing subscription. Nothing starts or changes until the address is confirmed: the request is stored and an email with a link to `PUBLIC_URL/?confirm=<token>` is sent, valid for 48 hours. Returns 202. Requires `email` and `location`. `activity` is optional: one of the names from `/api/activities` (free text such as "go for a run" is understood too), or omitted for a random pick each day. `language` (`en` or `sw`) is still accepted and stored, but the page no longer asks for it: emails are written in English only.

```bash
curl -X POST http://localhost:8000/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{"email": "amina@example.com", "location": "Nairobi", "activity": "running"}'
```

```json
{
  "email": "amina@example.com",
  "location": "Nairobi, KE",
  "activity": "running",
  "status": "pending",
  "confirmation_sent": true
}
```

The location must be one the geocoder can find, and the activity one that can be done there: surfing in an inland town is refused with the reason (both 422). `confirmation_sent` is `false` if the email could not be sent. If a link went to the same address in the last 10 minutes, nothing new is stored or sent and `status` is `"already_sent"`, so the link already in the inbox stays the one that counts. One address gets at most 5 emails a day from the forms. Without email configured the request is refused with 503, since it could never be confirmed. The response never includes a subscriber's token, so typing someone's address in can't be used to unsubscribe them or change their alerts.

### POST /api/confirm/{token}

Confirms a request with the token from its email: starts the alerts, or applies the change to an existing subscription (`"status": "subscribed"` or `"updated"`), and sends the welcome email with the unsubscribe link. Other requests waiting for the same address are dropped. Returns `{"email", "location", "activity", "status"}`, or 404 for an unknown, used or expired token. The page opened from the email asks before calling it, so a mail scanner opening the link doesn't confirm. It also takes the token out of the address as soon as it opens, so a copied link doesn't carry it. Subscribers from before confirmation get no alerts until they confirm; each is asked once, by email (see [Email Alerts](#email-alerts)).

### POST /api/unsubscribe/{token}

Stops the alerts and deletes the subscriber's details, along with any request waiting for that address. The token is in the link in every email sent to a subscriber. Returns `{\"email\": \"...\", \"status\": \"unsubscribed\"}`, or 404 for an unknown token, which includes one already used. Subscribing again and confirming starts afresh.

### GET /api/unsubscribe/{token}

For mail apps that open the `List-Unsubscribe` address as a link. Redirects (303) to `/?unsubscribe=<token>`, where the page asks first. It changes nothing, so a mail scanner fetching it can't unsubscribe anyone.

### POST /api/unsubscribe-link

Emails a subscriber their unsubscribe link, for when they have no alert email to hand. Body: `{"email": "amina@example.com"}`. Always answers 202 with `{"status": "sent_if_subscribed"}`, and the email goes out after the response, so neither the answer nor its timing reveals who is subscribed. Returns 503 if email is not configured.

### GET /health

Health check used by the Railway deploy probe. Returns `{"status": "ok"}`.

### Errors

| Status | Meaning |
| ------ | ------- |
| 413 | Request body over 4 KB |
| 422 | Location not found, or invalid request body (`detail` lists each field's `type`, `loc` and `msg`; the input is not echoed) |
| 429 | Too many requests from one visitor; `Retry-After` says how long to wait |
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
| `SQL_ECHO` | `false` | `true` logs every SQL statement with its values, including email addresses and tokens. For local debugging only |
| `WEATHER_API_URL` | `https://api.open-meteo.com/v1` | Open-Meteo base URL (only change if self-hosting) |
| `MARINE_API_URL` | `https://marine-api.open-meteo.com/v1` | Open-Meteo marine API, used to tell whether a place is by the sea |
| `BREVO_API_URL` | `https://api.brevo.com/v3` | Brevo's API address; only change this to test against something else |
| `BREVO_API_KEY` | (unset) | Brevo API key: email goes through Brevo's HTTPS API instead of SMTP (needed on hosts that block SMTP, such as Railway's Hobby plan). `MAIL_FROM` must be a sender verified in Brevo |
| `SMTP_HOST` | (unset) | SMTP server, used when `BREVO_API_KEY` isn't set, e.g. `smtp.gmail.com`. Nothing is sent until `MAIL_FROM` and one of `BREVO_API_KEY` or `SMTP_HOST` are set |
| `SMTP_PORT` | `587` | `465` connects over TLS; other ports upgrade with STARTTLS |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | (unset) | SMTP login. For Gmail, your address and an [app password](https://myaccount.google.com/apppasswords) |
| `SMTP_STARTTLS` | `true` | Set to `false` only for a local test server without TLS |
| `MAIL_FROM` | (unset) | Sender, e.g. `MoodForecast <you@gmail.com>` |
| `PUBLIC_URL` | `http://localhost:8000` | Public address of the site, used for the confirmation and unsubscribe links in emails |
| `ALERT_HOUR` | `7` | Local hour (0-23) at each subscriber's location when the daily alert is sent. The app won't start with any other value |

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
| Country | Geocoder | Sports that are only common in some countries: cricket, baseball, rugby, golf, surfing, netball, kabaddi, sepak takraw, Gaelic football, Aussie rules. Safaris: only in East and Southern Africa |

Each activity in `activity_advisor.py` declares what it needs (`needs`). The rules are applied two ways:

- **Asked about** (`/api/activity`, a subscriber's chosen activity): something the place can't offer (the sea inland, slopes away from snow country, a safari outside wildlife country) is a `skip`; a sport that isn't common there is a `maybe`. Anything unknown, such as a failed sea lookup, gets the benefit of the doubt.
- **Suggested unprompted** (`/api/random-activity`, `/api/activities/{location}`, the daily email's random pick): only what is confirmed practical is offered, so the unknown is left out.

`LOCAL_FAVOURITES` lists activities that are especially popular in a country; random picks choose them three times as often. `LOCAL_PITCHES` in `activity_advisor.py` words a suggestion the local way (nyama choma in Kenya, a braai in South Africa, an asado in Argentina).

Limits worth knowing:

- The country lists and favourites are hand-written judgement calls, by country, not by city. Edit them in `locality.py` where they are wrong for a place you know.
- The sea check does not see lakes or rivers, so lakeside towns such as Kisumu are treated as inland for beach days and sailing. Swimming, fishing, kayaking and boat trips are offered everywhere.
- Nothing checks for actual facilities: a football pitch, a pool, a climbing crag, a stable or a hiking trail is assumed to be within reach.

## Caching

- In-memory, per process; cleared when the server restarts
- TTL of 10 minutes by default (`CACHE_TTL_SECONDS`)
- Keys: `weather:{lat}:{lon}`, `sea:{lat}:{lon}`, `geo:{location}` and `suggest:{query}`
- `/api/forecast` and `/api/wellbeing` share the same cached weather for a location
- Requests for the same forecast made at the same moment share one call to Open-Meteo
- A forecast request that times out or hits a server error is retried once. If Open-Meteo still can't be reached, the last forecast for that place is served if it is under an hour old

## Database

Tables are created on startup, and columns added to `alert_subscriber` since it first went live (`confirmed`, `confirm_requested_at`) are added to an existing table then too. SQLite is used by default; set `DATABASE_URL` to a PostgreSQL URL for production.

```bash
sqlite3 moodforecast.db "SELECT email, place, activity, active, confirmed, last_sent_on FROM alert_subscriber;"
```

Subscribers are in `alert_subscriber`. A database created before email alerts also has a `subscriber` table of phone numbers; it is no longer read or written.

## Email Alerts

Email is sent by `app/services/mailer.py`: through Brevo's HTTPS API when `BREVO_API_KEY` is set, otherwise over SMTP with the `SMTP_*` variables, always from `MAIL_FROM`. If Brevo refuses an email that carries the `List-Unsubscribe` headers, it is tried once more without them (the unsubscribe link in the body still works), and the log gives Brevo's reason. Until `MAIL_FROM` and one of `BREVO_API_KEY` or `SMTP_HOST` are set nothing is sent: subscribing is refused with a 503 (the page disables its form), and the startup log says daily alerts are off.

```bash
python -m app.services.mailer you@example.com   # send one test message
python -m app.services.alerts                   # ask earlier subscribers to confirm, and send the alerts that are due now
python -m app.services.alerts --all             # the same, sending to every active, confirmed subscriber now
```

Five emails exist, all composed in `app/services/alerts.py` as plain text with an HTML alternative:

- **Confirmation request** - sent when someone asks for alerts or a change to them, with the link that starts them
- **Welcome** - sent once the address is confirmed, with the unsubscribe link
- **Request to confirm** - sent once to each subscriber from before addresses had to be confirmed. Their alerts are paused until they follow its link, which works for 48 hours; after that their details are deleted, and they would need to sign up anew. The background loop sends these as soon as email is configured
- **Daily alert** - only to confirmed subscribers: current weather, the mood score and summary, today's outlook, the subscriber's activity judged against the weather (or a random pick that suits it), a recommendation, and a question about another place
- **Unsubscribe link** - sent on request from `/api/unsubscribe-link`

The confirmation request and the unsubscribe link can be triggered by anyone typing an address into the site, so each is sent at most once per address per cache lifetime (`CACHE_TTL_SECONDS`, 10 minutes by default). Each visitor can use the two forms 20 times an hour and the rest of the API 300 times a minute (429 beyond that). Together the forms are limited to 100 emails a day across all addresses (`MAX_FORM_EMAILS_PER_DAY` in `app/services/alerts.py`), so they can't use up the mail provider's daily allowance.

Every email to a subscriber ends with an unsubscribe link to `PUBLIC_URL/?unsubscribe=<token>`, where the page asks for confirmation, and carries `List-Unsubscribe` headers so mail apps can show their own unsubscribe button.

Details are not kept once they have no use: unsubscribing deletes a subscriber straight away, and the background loop deletes requests nobody confirmed within 48 hours and earlier subscribers who didn't confirm in time. Brevo keeps its own logs of sent emails for a period set by its plan.

The daily send runs inside the web process: a background task started with the app checks every 15 minutes for subscribers where it is past `ALERT_HOUR` local time and today's alert has not gone out. A subscriber is marked as sent only after their email is accepted, so a failed send is retried on the next check. Someone who subscribes after `ALERT_HOUR` gets their first alert the next morning. Because the task runs in every process, run a single instance of the app, or each one will send its own copy.

## Notes

- Emails are in English only, so the page's subscribe form has no language choice
- Nothing is sent to a new address beyond one confirmation request until its owner follows the link, and every email to a subscriber has an unsubscribe link
- Deployment: see [../DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md)

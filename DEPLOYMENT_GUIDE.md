# MoodForecast AI - Deployment Guide

The backend and frontend deploy together as one service: FastAPI serves the API and the static frontend from the same container.

## Architecture

```text
Browser
   ↕
FastAPI (backend/app)
   ├── Static frontend      backend/app/static
   ├── Routers              forecast, wellbeing, activity, locations, subscribe
   ├── Services             weather, geocoding, mood engine, cache
   └── Database             SQLite or PostgreSQL (alert_subscriber table)
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

GitHub Actions runs the same tests on every push to `main` and every pull request (`.github/workflows/tests.yml`), on Python 3.11 with the exact versions in `constraints.txt`. The Docker image installs only `requirements.txt`; the test tools are in `requirements-dev.txt`. Railway deploys on push regardless; turning on "Wait for CI" in the Railway service settings makes it deploy only after the tests pass.

If you changed anything in `frontend/`, copy it into the deployed location first:

```bash
cp -r frontend/. backend/app/static/ && rm backend/app/static/README.md
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
| `CACHE_TTL_SECONDS` | `600` (optional) |
| `DATABASE_URL` | PostgreSQL URL (recommended, see below) |
| `PUBLIC_URL` | `https://YOUR_DOMAIN` - used for the confirmation and unsubscribe links in emails |
| `BREVO_API_KEY`, `MAIL_FROM` | Your Brevo API key, and the sender you verified in Brevo (see below) |
| `ALERT_HOUR` | `7` (optional) - local hour the daily alert is sent |

Variables left over from earlier versions, such as `WEATHERAI_API_KEY` and `ENVIRONMENT`, are ignored and can be deleted.

**Database:** if `DATABASE_URL` is not set, the app uses a SQLite file inside the container. That file is lost on every redeploy, so subscribers will not persist. To keep them, add a PostgreSQL database in Railway and set `DATABASE_URL` to its connection URL. Tables are created on startup.

**Email:** Railway blocks outbound SMTP on its Free, Trial and Hobby plans, so on Railway the app sends through [Brevo](https://www.brevo.com)'s HTTPS API instead. Brevo's free plan allows 300 emails a day and needs no domain of your own:

1. Sign up at brevo.com (free plan).
2. Under **Senders, Domains & Dedicated IPs → Senders**, add the address emails should come from and confirm it from the email Brevo sends.
3. Under **SMTP & API → API Keys**, create an API key.
4. In Railway, set `BREVO_API_KEY` to that key and `MAIL_FROM` to the sender, e.g. `MoodForecast <you@gmail.com>`, and check `PUBLIC_URL` is the site's address.
5. After the redeploy, `https://YOUR_DOMAIN/api/alerts` shows `{"available":true}` and the subscribe form is enabled. Subscribe with your own address to see the confirmation email arrive.

Write `MAIL_FROM` without quotation marks. Brevo warns that a free address such as Gmail isn't compliant, because only the mail provider can set up DKIM and DMARC for it: the emails still go out, but Brevo replaces the address subscribers see with one at `brevosend.com`, and some inboxes file them as spam (the page reminds people to look there). Adding a domain you own in Brevo (**Senders, Domains & Dedicated IPs → Domains**) fixes that. Elsewhere, plain SMTP works too: leave `BREVO_API_KEY` unset and set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` and `MAIL_FROM` (see the environment variables in the README).

The daily send runs inside the web process, so keep the service at one replica. More replicas would each send their own copy of every alert.

Once email works, anyone who subscribed before addresses had to be confirmed gets one email asking them to confirm; their alerts are paused until they do, and their details are deleted if they haven't confirmed 48 hours later.

The deploy log shows `✓ Daily alerts scheduled for 07:00 local time` when email is configured, and `• Email not configured` when it is not.

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
docker run -p 8000:8000 moodforecast
```

The container listens on `$PORT` if it is set, otherwise 8000.

## Environment Variables

All are optional.

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `DATABASE_URL` | `sqlite:///./moodforecast.db` | SQLite or PostgreSQL connection string |
| `CACHE_TTL_SECONDS` | `600` | How long weather and geocoding results are cached |
| `SQL_ECHO` | `false` | `true` logs every SQL statement with its values, including email addresses and tokens. For local debugging only |
| `WEATHER_API_URL` | `https://api.open-meteo.com/v1` | Only change this if you self-host Open-Meteo |
| `MARINE_API_URL` | `https://marine-api.open-meteo.com/v1` | Open-Meteo marine API, used to tell whether a place is on the coast; only change this if you self-host it |
| `BREVO_API_URL` | `https://api.brevo.com/v3` | Brevo's API address; only change this to test against something else |
| `PORT` | `8000` | Set by Railway |

## Open-Meteo Usage Limits

The free hosted Open-Meteo API is for non-commercial use, at about 10,000 calls per day. Results are cached per location, so normal use stays well below that. For commercial use, self-host Open-Meteo or use their paid plan and point `WEATHER_API_URL` at it.

Place lookups use Nominatim, whose usage policy allows one request per second. The app keeps to that across all visitors; a lookup that would have to wait more than a few seconds uses Open-Meteo's geocoder instead.

## Troubleshooting

| Issue | What to check |
| ----- | ------------- |
| Build fails | Railway build logs; `pip install -r requirements.txt -c constraints.txt` works locally in `backend/` |
| App crashes on start | Railway deploy logs; `DATABASE_URL` is a valid URL if set |
| "Location not found" (422) | Spelling of the location; try adding the country |
| "The weather service can't be reached right now" (503) | Open-Meteo or Nominatim is unreachable or rate limiting - retry shortly |
| Timeout (504) | Upstream service is slow - retry shortly |
| Frontend shows old content | `backend/app/static/` was not updated from `frontend/`; browser cache |
| Subscribers disappear after deploy | `DATABASE_URL` is not set, so SQLite inside the container is being used |
| Subscribing says "Email alerts aren't available right now" (503) | `MAIL_FROM` and `BREVO_API_KEY` (or `SMTP_HOST`) are not set; requests can't be confirmed without email, so none are taken |
| A confirmation link says it has expired or been used | Links work once, for 48 hours; subscribe again for a new one |
| Subscribing works but no email arrives | The logs for `Could not send email` (Brevo's reason is included: `unauthorized` means a wrong key, `MAIL_FROM is not valid` means it's badly written, a sender error means it isn't a verified Brevo sender); the recipient's spam folder; with SMTP, whether the host allows it |
| Unsubscribe links point to localhost | `PUBLIC_URL` is not set to the site's public address |
| Shared links show the old address or no image after moving to a new domain | The `og:url`, `og:image` and `twitter:image` tags and the canonical links in `frontend/index.html` and `frontend/privacy.html`, plus `frontend/robots.txt` and `frontend/sitemap.xml`, name the address in full; update them and copy those files to `backend/app/static/`. Platforms keep old previews for a while: LinkedIn's Post Inspector refreshes them |
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
- [ ] Typing in a location field suggests places
- [ ] The activity card shows a pick, and "Surprise me" changes it
- [ ] Subscribing sends a confirmation email; its link starts the alerts, and the welcome email's unsubscribe link works
- [ ] No errors in the browser console or the Railway logs

## References

- FastAPI: `https://fastapi.tiangolo.com`
- Railway: `https://docs.railway.app`
- Open-Meteo: `https://open-meteo.com/en/docs`
- Nominatim usage policy: `https://operations.osmfoundation.org/policies/nominatim/`

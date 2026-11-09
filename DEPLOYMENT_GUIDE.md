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

1. Visit `https://railway.com`
2. Click "New Project" → "Deploy from GitHub repo"
3. Select the `moodforecast_ai` repository
4. In the service's settings, set **Root Directory** to `backend`, and **Config File** to `/backend/railway.toml` (the config file's path doesn't follow the root directory, so it needs the full path)
5. Click "Deploy"

The Dockerfile builds from `backend/`, so a service without that root directory can't find `requirements.txt`. Railway redeploys automatically on every push to `main`.

#### Railway's config file

Railway has deprecated `railway.toml` and **stops reading these files on 2026-12-01**, in favour of its [Infrastructure as Code](https://docs.railway.com/infrastructure-as-code) file, `.railway/railway.ts`. After that date the settings below come from the service's dashboard settings only, so move them before then:

| Setting | Value |
| ------- | ----- |
| Start command | Can be empty: the Docker image's own command is the same |
| Healthcheck path | `/health` |
| Healthcheck timeout | `60` seconds |
| Draining seconds | `15` |

Either enter them in the dashboard, or move them with the [Railway CLI](https://docs.railway.com/cli). `railway config migrate` on its own only previews, and `--apply` only writes the new file: Railway keeps reading `railway.toml` until the cutover in step 4. Run every command from the repository root:

1. Install and sign in: `bash <(curl -fsSL railway.com/install.sh)` (or `brew install railway`), then `railway login` and `railway link` (pick this project, the `production` environment and the app's service).
2. `railway config migrate --variables unmanaged` is a dry run: it shows what it would write and changes nothing (if it asks to write the file, say no). It should show the settings in the table above, for the app's service only. `--variables` is required; `unmanaged` leaves the variables (`BREVO_API_KEY`, `DATABASE_URL` and the rest) in the dashboard, out of the file.
3. `railway config migrate --apply --variables unmanaged` writes `.railway/railway.ts` and nothing else. If it offers to cut over now, say no. Read the file: it should hold the settings in the table above for the app's service, and nothing for any other service. If a later step says the `railway` package is missing, run `npm install --save-dev railway` at the repository root.
4. Do steps 4 to 6 one straight after another: between them the service runs on its dashboard settings. `railway config migrate cutover --service "<service name>"` stops Railway reading `railway.toml` for the service and redeploys it. `railway config migrate status` shows which services still read it, and `railway config migrate undo` puts it back.
5. `railway config plan`. **Read every line before going on.** It should only set the settings in the table on the app's service. If it marks anything as destroyed or deleted, above all a PostgreSQL service or a variable, stop and run `railway config migrate undo`: a project file treats a service it leaves out as one to delete.
6. `railway config apply`, and confirm only if the plan is what you read.
7. Commit `.railway/` (and `package.json` and `package-lock.json` if step 3 made them) and remove `backend/railway.toml` in the same push, never before step 6: a service can't be managed by both. Then check the deploy finished and `/health` answers, and that the service's dashboard settings show the values above.

### 3. Set Variables

In the project's "Variables" tab:

| Variable | Value |
| -------- | ----- |
| `CACHE_TTL_SECONDS` | `600` (optional) |
| `DATABASE_URL` | PostgreSQL URL (recommended, see below) |
| `PUBLIC_URL` | `https://YOUR_DOMAIN` - used for the confirmation and unsubscribe links in emails |
| `BREVO_API_KEY`, `MAIL_FROM` | Your Brevo API key, and the sender you verified in Brevo (see below) |
| `ALERT_HOUR` | `7` (optional) - local hour (0-23) the daily alert is sent; the app won't start with any other value |

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

The app runs as an unprivileged user that can't change its own code. Without `DATABASE_URL` its SQLite database is `/app/data/moodforecast.db`, the only place in the image that user can write.

## Environment Variables

All are optional. The email settings (`BREVO_API_KEY`, `MAIL_FROM`, `PUBLIC_URL`, `ALERT_HOUR`, and the `SMTP_*` ones including `SMTP_STARTTLS`) are in [the README's table](README.md#environment-variables); the rest are:

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
| Subscribers disappear after deploy | `DATABASE_URL` is not set, so SQLite inside the container is being used. The app logs a warning about this when it starts on Railway with email configured |
| Subscribing says "Email alerts aren't available right now" (503) | `MAIL_FROM` and `BREVO_API_KEY` (or `SMTP_HOST`) are not set; requests can't be confirmed without email, so none are taken |
| A confirmation link says it has expired or been used | Links work once, for 48 hours; subscribe again for a new one |
| Subscribing works but no email arrives | The logs for `Could not send email` (Brevo's reason is included: `unauthorized` means a wrong key, `MAIL_FROM is not valid` means it's badly written, a sender error means it isn't a verified Brevo sender); the recipient's spam folder; with SMTP, whether the host allows it |
| Unsubscribe links point to localhost | `PUBLIC_URL` is not set to the site's public address. The app logs a warning about this when it starts |
| Links in emails don't open | `PUBLIC_URL` is missing its `https://`, so mail apps can't follow the links. The app logs a warning about this when it starts |
| Shared links show the old address or no image after moving to a new domain | The `og:url`, `og:image` and `twitter:image` tags and the canonical links in `frontend/index.html` and `frontend/privacy.html`, plus `frontend/robots.txt` and `frontend/sitemap.xml`, name the address in full; update them and copy those files to `backend/app/static/`. Platforms keep old previews for a while: LinkedIn's Post Inspector refreshes them |
| Stale weather | Results are cached for `CACHE_TTL_SECONDS`; restarting clears the cache |

To see request details:

```bash
curl -v https://YOUR_DOMAIN/api/forecast/Nairobi
```

### When a deploy breaks the site

A new deployment only goes live once `/health` answers, so one that fails to start leaves the previous one running. If a deployment goes live and then misbehaves:

1. **Roll back.** In Railway, the service's Deployments tab: click the three dots at the end of the last good deployment and confirm the rollback. It brings back that deployment's image **and its variables**, so a variable changed since (a new `BREVO_API_KEY`, say) goes back too: set it again afterwards. A removed deployment can be rolled back only within your plan's image retention period (72 hours on Hobby); after that, use Redeploy on it, which rebuilds it from its source.
2. **Fix it in Git.** A rollback doesn't change `main`, and the next push deploys over it. Revert the change (`git revert <commit>`, then push) or push a fix.

The database is safe to roll back over: the app only ever adds columns at startup, never removes or changes them, so an older version runs on a database a newer one has upgraded.

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
- Railway: `https://docs.railway.com`
- Open-Meteo: `https://open-meteo.com/en/docs`
- Nominatim usage policy: `https://operations.osmfoundation.org/policies/nominatim/`

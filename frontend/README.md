# MoodForecast AI - Frontend

Single-page HTML/CSS/JS application for the MoodForecast AI service.

## Overview

The frontend is intentionally minimal:

- No build step or compilation
- Vanilla JavaScript (no frameworks)
- Responsive layout
- Talks to the FastAPI backend with relative URLs

## Files

| File | Purpose |
| ---- | ------- |
| `index.html` | Page structure |
| `app.js` | Search, rendering and subscribe logic |
| `learn.js` | Learns which activities the visitor likes, in their browser only |
| `leaflet.js`, `leaflet.css`, `leaflet-LICENSE.txt` | [Leaflet](https://leafletjs.com) 1.9.4 (BSD 2-Clause) for the map, served from here and loaded only when the map is opened. From the npm tarball, which matches npm's sha512 and the SRI hashes on leafletjs.com |
| `styles.css` | Styling |
| `favicon.ico`, `favicon.svg`, `apple-touch-icon.png` | Icons |
| `privacy.html` | What the site does with people's details |
| `robots.txt` | Keeps search engines out of the API and points them to the sitemap |
| `sitemap.xml` | The pages search engines should know about |
| `og-image.png` | The card shown when a link to the site is shared |
| `dm-sans-*.woff2`, `dm-sans-OFL.txt` | The page's font and its licence, served from here so visits don't reach Google |

## How It Is Served

The backend serves `backend/app/static/`, which is a copy of this directory. After editing files here, copy them across:

```bash
cp -r frontend/. backend/app/static/ && rm backend/app/static/README.md
```

The backend test `tests/test_static_sync.py` fails if the two copies differ.

## How to Run

Start the backend, which serves the frontend:

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

Then open **`http://localhost:8000`**. See [../README.md](../README.md) for first-time setup.

API calls use relative paths, so the page must be opened through the backend rather than as a file.

## How It Works

1. **Search** → user enters a location (matching places are suggested while typing, from `GET /api/locations`), picks a popular city, or opens a link with `?q=Kisumu`. The last search is remembered in the browser. The ◎ button in the search box (**Use my location**) asks the browser for the visitor's position, only when tapped; the page rounds it to about 1 km, gets the town there from `POST /api/place` and searches for it. A refusal, a timeout, a browser without geolocation or a page not served over https each get a plain message suggesting a search instead. The ▦ button (**Choose on map**) in the search box opens a map under it (and closes it again). Nothing of the map loads until then. Tapping a point rounds it to about 1 km, finds the town there (`POST /api/place`) and its weather (`GET /api/wellbeing/{location}`), and shows a small pop-up: the town, condition and temperature, the mood score and label, and **See full forecast**, which closes the map and searches the town. The place on screen has a blue dot. Taps less than a second apart, or while a place is being found, are ignored, to spare the map services. With a keyboard, the map takes focus: arrow keys move it, + and − zoom, Enter picks the middle, Escape closes the pop-up, and Tab carries on out of it. Tiles are OpenStreetMap's standard ones, loaded by the browser straight from `tile.openstreetmap.org`, with the site's origin as the Referer (their tile policy asks for one; the page sends none elsewhere), zoom 2-12 and no prefetching, as the [tile usage policy](https://operations.osmfoundation.org/policies/tiles/) asks.
2. **API calls** → `GET /api/forecast/{location}` and `GET /api/wellbeing/{location}`, in parallel
3. **Weather card** → icon, temperature, feels-like, humidity, wind, rain chance, peak UV, sunrise, sunset
4. **Mood card** → score gauge (0-100), mood label, energy and risk badges, summary, and the factors behind the score
5. **7-day mood outlook** → icon, rain chance, temperature range and expected mood per day
6. **Recommendations** → activity ideas and wellbeing tips for the current conditions, different on each visit
7. **Activity check** → type a question or pick one of the quick picks, which come from `GET /api/activities/{location}` and so fit the place; `GET /api/activity/{location}?activity=...` returns a verdict, the reasons, something to do instead, and other places to try. Picking one of those places searches it and asks the same question there. Until a question is asked, the card shows a pick from `GET /api/random-activity/{location}`; **Surprise me** rolls another. Under a pick, **Good pick? 👍 👎** teaches the page what this visitor likes (see [Learning](#learning)).
8. **Stay curious** → three questions about other places from the wellbeing response; tapping one searches that place
9. **Subscribe form** → if `GET /api/alerts` says email isn't available, the form is disabled with a note. Otherwise `POST /api/subscribe` with email, location, an activity (from `GET /api/activities/{location}` for the subscription's location, listed with local favourites first under "Popular here" and the rest grouped by kind, or a random pick each day). The page then says a confirmation link has been emailed; nothing starts until it is followed. The location field suggests places while typing. Under the form, **Already subscribed and want to opt out? Unsubscribe here** opens a pop-up with a one-field form that emails a link to finish unsubscribing (a subscription saved in this browser before email confirmation existed is still cancelled straight away).
10. **Email links** → the confirmation email links to `/?confirm=<token>`; the page asks "Start your daily MoodForecast emails?", then calls `POST /api/confirm/{token}`. Every alert email links to `/?unsubscribe=<token>`; a pop-up asks for confirmation, then calls `POST /api/unsubscribe/{token}`

Errors show the message returned by the API.

## Learning

`learn.js` learns which activities this visitor likes from the 👍 / 👎 under a pick, in the browser only. Nothing about the votes is sent to the server, and there are no accounts.

- **Model**: a contextual bandit with Thompson sampling. Each activity has a Beta(likes + 1, dislikes + 1) belief, kept separately for each kind of weather: warm (feels like 24°C or more), mild (12-24°C) or cold; dry or wet; day or evening, so 12 contexts. A vote also counts, more weakly, for the same activity in other weather (x0.5) and for its family in this weather (x0.35) and others (x0.15). Families such as "ball games" or "time on the water" come from `GET /api/activities/{location}`. So a few taps already change the picks.
- **Changing tastes**: votes fade with a 45-day half-life. Tapping the same vote again takes it back, and switching from 👍 to 👎 replaces it.
- **No feedback trap**: evidence for one activity is capped at 8 (decayed) votes, so nothing becomes certain and Thompson sampling keeps trying others. 15% of picks are left to the server's own random pick, and "Surprise me" never repeats the pick on screen.
- **Cold start**: until the first vote nothing changes. Picks are the server's random ones, and quick picks show local favourites first.
- **Safety**: it only chooses among the activities `/api/activities/{location}` marks `suited`, and sends the choice as `choose=` to `/api/random-activity`, which takes it only if the same rules allow it (thunderstorms, freezing rain, frostbite, heat, wind, wet ground, daylight, the hour, local fit). The rules always win.
- **Where it's used**: "Surprise me" and the first pick after a search, and the order of the quick picks (liked first, disliked last). The daily email's random pick is chosen on the server and doesn't learn, and neither does the mood score.
- **Transparency and control**: a learned pick says why ("You've liked cycling on mild, dry days."). "Forget what I've liked" clears everything. Stored under `moodforecast:tastes`; if storage is blocked, learning lasts for the visit.

## Design

- **Sky background** follows the weather and time of day. `applyTheme()` in `app.js` sets `data-theme` on `<body>`; each theme's colors are at the top of `styles.css`.
- **Mood levels** use four colors (`--level-high`, `--level-medium`, `--level-low`, `--level-verylow`), always next to a number or label so color is never the only cue.
- **Icons** are inline SVG, defined in `ICONS` in `app.js`.
- **Font**: DM Sans, served from this folder
- **Responsive**: two columns on desktop, one below 860px, compact forecast rows below 520px
- **Motion** is turned off when the visitor's system asks for reduced motion

## Attribution

The footer credits Open-Meteo and OpenStreetMap, and the map shows OpenStreetMap's attribution on the map itself. The licences require both, so keep them when changing the layout.

## Browser Support

Modern browsers (ES2020+): current Chrome, Firefox, Safari and Edge.

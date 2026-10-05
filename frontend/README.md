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
| `styles.css` | Styling |
| `favicon.ico`, `favicon.svg`, `apple-touch-icon.png` | Icons |

## How It Is Served

The backend serves `backend/app/static/`, which is a copy of this directory. After editing files here, copy them across:

```bash
cp frontend/index.html frontend/app.js frontend/styles.css backend/app/static/
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

1. **Search** → user enters a location (matching places are suggested while typing, from `GET /api/locations`), picks a popular city, or opens a link with `?q=Kisumu`. The last search is remembered in the browser.
2. **API calls** → `GET /api/forecast/{location}` and `GET /api/wellbeing/{location}`, in parallel
3. **Weather card** → icon, temperature, feels-like, humidity, wind, rain chance, peak UV, sunrise, sunset
4. **Mood card** → score gauge (0-100), mood label, energy and risk badges, summary, and the factors behind the score
5. **7-day mood outlook** → icon, rain chance, temperature range and expected mood per day
6. **Recommendations** → activity ideas and wellbeing tips for the current conditions, different on each visit
7. **Activity check** → type a question or pick one of the quick picks, which come from `GET /api/activities/{location}` and so fit the place; `GET /api/activity/{location}?activity=...` returns a verdict, the reasons, something to do instead, and other places to try. Picking one of those places searches it and asks the same question there. Until a question is asked, the card shows a random pick from `GET /api/random-activity/{location}`; **Surprise me** rolls another.
8. **Stay curious** → three questions about other places from the wellbeing response; tapping one searches that place
9. **Subscribe form** → `POST /api/subscribe` with email, location, an activity (from `GET /api/activities/{location}` for the subscription's location, or a random pick each day) and language. The location field suggests places while typing. Under the form, **Already subscribed and want to opt out? Unsubscribe here** opens a one-field form: a subscription made in this browser is cancelled straight away, and any other address is emailed a link to finish unsubscribing.
10. **Unsubscribe links** → emails link to `/?unsubscribe=<token>`; the page asks for confirmation, then calls `POST /api/unsubscribe/{token}`

Errors show the message returned by the API.

## Design

- **Sky background** follows the weather and time of day. `applyTheme()` in `app.js` sets `data-theme` on `<body>`; each theme's colors are at the top of `styles.css`.
- **Mood levels** use four colors (`--level-high`, `--level-medium`, `--level-low`, `--level-verylow`), always next to a number or label so color is never the only cue.
- **Icons** are inline SVG, defined in `ICONS` in `app.js`.
- **Font**: DM Sans (Google Fonts)
- **Responsive**: two columns on desktop, one below 860px, compact forecast rows below 520px
- **Motion** is turned off when the visitor's system asks for reduced motion

## Attribution

The footer credits Open-Meteo and OpenStreetMap. Both licences require this, so keep it when changing the layout.

## Browser Support

Modern browsers (ES2020+): current Chrome, Firefox, Safari and Edge.

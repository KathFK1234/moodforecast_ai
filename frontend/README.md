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

1. **Search** → user enters a location (the page searches for Nairobi on load)
2. **API calls** → `GET /api/forecast/{location}` and `GET /api/wellbeing/{location}`
3. **Weather card** → temperature, humidity, condition, wind and a 7-day forecast
4. **Wellbeing section** → mood score (0-100), energy and risk badges, summary, recommendations
5. **Subscribe form** → `POST /api/subscribe` with phone, location, optional crop and language

## Features

### Weather Display

- Current temperature, humidity, wind speed and condition
- 7-day forecast with condition and max/min temperature
- Live data from the Open-Meteo API (via the backend)

### Wellbeing Score

- **Mood Score**: 0-100 based on weather conditions
- **Energy Level**: High / Medium / Low / Very Low
- **Risk Level**: Minimal / Low / Moderate / High
- **Recommendations**: wellbeing tips for the current conditions

### Subscription Form

- Phone number in E.164 format (validated by the backend)
- Crop (optional)
- Language preference (English / Swahili)
- Confirmation with subscriber ID

## Styling

- **Color Scheme**: Purple gradient (#667eea → #764ba2)
- **Font**: DM Sans (Google Fonts)
- **Layout**: CSS Grid and Flexbox
- **Responsive**: single-column layout below 480px

## Browser Support

Modern browsers (ES2020+): current Chrome, Firefox, Safari and Edge.

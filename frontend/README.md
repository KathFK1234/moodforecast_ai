# MoodForecast AI - Frontend

Single-page HTML/CSS/JS application for the MoodForecast AI service.

## Overview

The frontend is intentionally minimal — **one well-crafted HTML page** with:

- No build step or compilation
- Vanilla JavaScript (no frameworks)
- Responsive design (mobile-first)
- Real-time interaction with FastAPI backend

## File Location

The actual frontend files are served from `/backend/app/static/`:

- `index.html` — Complete single-page application
- Styling: Embedded CSS
- Logic: Embedded JavaScript

## How It Works

1. **Search Bar** → User enters location (city name or coordinates)
2. **API Call** → Fetches `/api/forecast/{location}` and `/api/wellbeing/{location}`
3. **Display Weather** → Current conditions + humidity + wind
4. **Display Wellbeing** → Mood score (0-100) + energy level + recommendations
5. **Subscribe Form** → Optional SMS/USSD alert registration

## Features

### Weather Display

- Current temperature, humidity, wind speed, condition
- Real-time data from WeatherAI API

### Wellbeing Score

- **Mood Score**: 0-100 based on weather conditions
- **Energy Level**: High / Medium / Low / Very Low
- **Risk Level**: Minimal / Low / Moderate / High
- **Recommendations**: Context-aware wellness tips

### AI Summary

- Natural language forecast summary from WeatherAI's Gemini AI

### SMS Subscription

- E.164 phone format validation
- Crop selection (optional)
- Language preference (English / Swahili)
- Confirmation with subscriber ID

## Styling

Uses modern CSS with:

- **Color Scheme**: Purple gradient (#667eea → #764ba2)
- **Font**: DM Sans (Google Fonts)
- **Layout**: CSS Grid and Flexbox
- **Responsive**: Mobile-first approach
- **Accessibility**: Semantic HTML, good contrast ratios

## API Integration

All requests to the same domain (relative URLs):

- `GET /api/forecast/{location}`
- `GET /api/wellbeing/{location}`
- `POST /api/subscribe`

The frontend is served from FastAPI's static file handler, so API calls use relative paths.

## How to Run

The frontend is **automatically served** by the FastAPI backend:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your WeatherAI API key to .env
uvicorn app.main:app --reload
```

Then open: **`http://localhost:8000`**

## No Build Step

This frontend requires **zero build tools**:

- No npm, webpack, or bundler
- No TypeScript or JSX compilation
- Serve directly as static files

This makes deployment trivial and keeps the stack simple.

## Performance

- Page load: ~100ms (index.html is 15KB gzipped)
- API latency: ~200ms p95 (WeatherAI SLA)
- Cache hit: Instant response (10-minute TTL)

## Browser Support

Modern browsers (ES2020+):

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

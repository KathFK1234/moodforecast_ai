# MoodForecast AI - Setup Guide

Quick reference for setting up and running MoodForecast AI after cloning the repository.

## Prerequisites

- Python 3.11+ (tested on 3.12.3, 3.13+)
- Git
- Weather-AI.co API key (free tier available)

## Step 1: Get Your Weather-AI.co API Key

1. Visit [weather-ai.co](https://weather-ai.co)
2. Sign up for a free account
3. Navigate to your dashboard
4. Copy your API key (format: `wai_...`)

## Step 2: Backend Setup

### Initial Setup (One Time)

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your API key
# Open .env in your editor and update:
# WEATHERAI_API_KEY=wai_your_actual_key_here
```

### Verify Setup

```bash
# Run verification script
bash verify_setup.sh

# Or manually run tests
pytest tests/ -v
```

## Step 3: Run Backend

```bash
cd backend
source venv/bin/activate

# Development mode (with auto-reload)
uvicorn app.main:app --reload

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The backend will be available at:
- **Frontend**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Testing Endpoints

### With Real API (requires valid key in .env)

```bash
# Forecast endpoint
curl http://localhost:8000/api/forecast/Nairobi

# Wellbeing endpoint
curl http://localhost:8000/api/wellbeing/London

# Subscribe endpoint
curl -X POST http://localhost:8000/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+254712345678",
    "location": "Nairobi",
    "crop": "maize"
  }'
```

### With Demo Endpoints (no API key needed!)

```bash
# Demo forecast - returns mock data
curl http://localhost:8000/api/demo/forecast/Nairobi

# Demo wellbeing - returns mock mood data
curl http://localhost:8000/api/demo/wellbeing/London
```

### In Browser

- **Frontend with real API**: http://localhost:8000
- **Frontend with demo mode**: http://localhost:8000/?demo=true

## Running Tests

```bash
cd backend

# All tests
pytest tests/ -v

# Mood engine tests only
pytest tests/test_mood_engine.py -v

# Endpoint tests only
pytest tests/test_endpoints.py -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app factory
│   ├── config.py            # Environment configuration
│   ├── routers/             # API endpoints
│   │   ├── forecast.py      # /api/forecast
│   │   ├── wellbeing.py     # /api/wellbeing
│   │   ├── subscribe.py     # /api/subscribe
│   │   └── demo.py          # /api/demo/*
│   ├── services/            # Business logic
│   │   ├── weatherai.py     # WeatherAI API client
│   │   ├── mood_engine.py   # Mood scoring engine
│   │   └── cache.py         # In-memory cache
│   ├── models/              # Data schemas
│   │   ├── schemas.py       # Pydantic models
│   │   └── db.py            # Database models
│   └── static/              # Frontend files
│       ├── index.html
│       ├── app.js
│       └── styles.css
├── tests/                   # Test suite
│   ├── test_mood_engine.py
│   └── test_endpoints.py
├── requirements.txt         # Python dependencies
├── .env.example            # Example env file
├── Dockerfile              # Docker configuration
├── railway.toml            # Railway deployment config
└── README.md               # Detailed backend docs
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WEATHERAI_API_KEY` | Yes | N/A | Weather-AI.co API key |
| `DATABASE_URL` | Yes | `sqlite:///./moodforecast.db` | SQLite database file |
| `ENVIRONMENT` | Yes | `development` | Environment mode |
| `CACHE_TTL_SECONDS` | No | `600` | Cache duration (seconds) |
| `REDIS_URL` | No | N/A | Optional Redis for distributed cache |

## Troubleshooting

### "Module not found" errors
- Make sure virtual environment is activated: `source venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

### "API key is invalid" errors
- Verify key is correct in `.env` file
- Check key format: should start with `wai_`
- Get new key from https://weather-ai.co/dashboard

### Port 8000 already in use
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>
```

### Database errors
- Delete `moodforecast.db` to reset database
- Tables will be automatically recreated on next run

## Next Steps

1. **Frontend Development**: See `frontend/README.md`
2. **Deployment**: See deployment instructions in `backend/README.md`
3. **API Integration**: Use `/docs` endpoint for interactive API exploration

## Support

For issues or questions:
1. Check the `backend/README.md` for detailed documentation
2. Review test files for usage examples
3. Check the `.env.example` file for all available configuration options

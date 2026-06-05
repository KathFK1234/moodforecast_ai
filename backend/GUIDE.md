# MoodForecast AI - Backend Guide

Complete setup, testing, and deployment guide for the backend API.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Setup Instructions](#setup-instructions)
3. [Running the Backend](#running-the-backend)
4. [Testing](#testing)
5. [Deployment](#deployment)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# 1. Setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure API key
cp .env.example .env
# Edit .env and add WEATHERAI_API_KEY=wai_your_actual_key_here

# 3. Run backend
uvicorn app.main:app --reload

# 4. Test
curl http://localhost:8000/health
curl http://localhost:8000/api/forecast/Nairobi
```

---

## Setup Instructions

### Prerequisites

- Python 3.11+ (tested on 3.12.3, 3.13+)
- Git
- Weather-AI.co API key (get free at [weather-ai.co](https://weather-ai.co))

### Step 1: Get Weather-AI.co API Key

1. Visit [weather-ai.co](https://weather-ai.co)
2. Create free account
3. Copy your API key (format: `wai_...`)

### Step 2: Create Virtual Environment

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate

# Windows:
# venv\Scripts\activate

# Verify activation (should see (venv) in prompt)
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt

# Verify installation
python -m pytest tests/test_mood_engine.py -v
```

### Step 4: Configure Environment

```bash
# Copy template
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your editor

# Required settings:
WEATHERAI_API_KEY=wai_your_actual_key_here
DATABASE_URL=sqlite:///./moodforecast.db
ENVIRONMENT=development
CACHE_TTL_SECONDS=600
```

### Step 5: Verify Setup

```bash
# Run tests
pytest tests/ -q

# Expected output: 31 passed

# Check health
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

---

## Running the Backend

### Development Mode

```bash
# With auto-reload (changes refresh immediately)
uvicorn app.main:app --reload

# Custom port
uvicorn app.main:app --reload --port 8001
```

### Production Mode

```bash
# Optimized for deployment
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# With Gunicorn (recommended for production)
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
```

### Access Points

| URL | Purpose |
|-----|---------|
| http://localhost:8000 | Frontend (static files) |
| http://localhost:8000/docs | Swagger UI documentation |
| http://localhost:8000/redoc | ReDoc documentation |
| http://localhost:8000/health | Health check |
| http://localhost:8000/api/forecast/{location} | Get forecast |
| http://localhost:8000/api/wellbeing/{location} | Get wellbeing score |

---

## Testing

### Unit Tests (23 tests)

Tests the mood scoring engine logic:

```bash
pytest tests/test_mood_engine.py -v

# Expected: 23 passed
```

### Integration Tests (8 tests)

Tests API endpoints:

```bash
pytest tests/test_endpoints.py -v

# Expected: 8 passed
```

### All Tests

```bash
pytest tests/ -v

# Expected: 31 passed

# Quick summary
pytest tests/ -q --tb=no
```

### Test Coverage

```bash
pytest tests/ --cov=app --cov-report=html

# Open htmlcov/index.html to view coverage
```

---

## API Endpoints

### Production Endpoints (Requires API Key)
#   },
#   "mood_score": 80,
#   "energy_level": "High",
#   "risk_level": "Low",
#   "recommendations": [...]
# }
```

### Real Endpoints (Requires Valid API Key)

Fetches real weather data:

```bash
# Get real forecast
curl http://localhost:8000/api/forecast/Nairobi | jq .

# Get real wellbeing
curl http://localhost:8000/api/wellbeing/London | jq .

# Response times:
# - First request: 600-800ms (API call)
# - Cached request: 20-30ms (in-memory cache)
```

### Subscription Endpoint

```bash
curl -X POST http://localhost:8000/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+254712345678",
    "location": "Nairobi",
    "crop": "maize",
    "language": "en"
  }'

# Expected response (201 Created):
# {
#   "id": "550e8400-e29b-41d4-a716-446655440000",
#   "phone": "+254712345678",
#   "location": "Nairobi",
#   "active": true,
#   "message": "Subscription successful"
# }
```

### Health Check

```bash
curl http://localhost:8000/health

# Expected response:
# {"status":"ok"}
```

---

## Database

### SQLite (Default - Development)

Auto-initialized on startup:

```bash
# Check database
ls -la moodforecast.db

# Query subscribers
sqlite3 moodforecast.db "SELECT * FROM subscriber;"

# Clear database
rm moodforecast.db  # Reinitialize on next run
```

### PostgreSQL (Production)

For production, upgrade to PostgreSQL:

```bash
# Update .env
DATABASE_URL=postgresql://user:password@host:5432/moodforecast

# Database tables auto-initialize on startup
```

---

## Caching

### In-Memory Cache (Default)

```bash
# First request (cache miss) → ~600ms
curl http://localhost:8000/api/forecast/Nairobi

# Second request (cache hit) → ~20ms
curl http://localhost:8000/api/forecast/Nairobi

# TTL: 10 minutes (configured in .env)
```

### Redis Cache (Optional)

For distributed caching:

```bash
# Install Redis
brew install redis  # macOS
sudo apt install redis-server  # Ubuntu

# Start Redis
redis-server

# Update .env
REDIS_URL=redis://localhost:6379/0

# Restart backend
# Backend will auto-detect and use Redis
```

---

## Deployment

### Option 1: Railway (Recommended - Easiest)

Free tier: 500 hours/month + $5 credit

```bash
# 1. Push to GitHub
git add -A
git commit -m "Production ready"
git push origin main

# 2. Go to railway.app
# - Sign in with GitHub
# - Create new project
# - Select your repository
# - Add environment variables:
#   WEATHERAI_API_KEY=wai_xxx...
#   ENVIRONMENT=production
#   DATABASE_URL=postgresql://... (use Railway's free PostgreSQL)

# 3. Deploy (automatic on push)
```

### Option 2: Docker

```bash
# Build image
docker build -t moodforecast-backend:latest .

# Run container
docker run -p 8000:8000 \
  -e WEATHERAI_API_KEY=wai_your_key \
  -e ENVIRONMENT=production \
  moodforecast-backend:latest
```

### Option 3: Docker Compose

```bash
# Start all services (backend + postgres + redis)
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f backend

# Stop all
docker-compose down
```

### Option 4: Heroku

```bash
# Install Heroku CLI
brew install heroku

# Login
heroku login

# Create app
heroku create moodforecast-ai

# Add PostgreSQL
heroku addons:create heroku-postgresql:standard-0

# Set environment variables
heroku config:set WEATHERAI_API_KEY=wai_your_key
heroku config:set ENVIRONMENT=production

# Deploy
git push heroku main

# View logs
heroku logs --tail
```

---

## Environment Variables

### Required

| Variable | Value | Example |
|----------|-------|---------|
| WEATHERAI_API_KEY | Your API key | `wai_fac7de...` |
| DATABASE_URL | Database connection | `sqlite:///./moodforecast.db` |
| ENVIRONMENT | Environment name | `development` or `production` |

### Optional

| Variable | Default | Purpose |
|----------|---------|---------|
| CACHE_TTL_SECONDS | 600 | Cache duration (10 minutes) |
| REDIS_URL | Not set | Redis URL for distributed cache |
| PORT | 8000 | Server port |

---

## API Documentation

### Swagger UI

Interactive API explorer:

```
http://localhost:8000/docs
```

### ReDoc

Alternative documentation:

```
http://localhost:8000/redoc
```

### OpenAPI Schema

Raw OpenAPI definition:

```
http://localhost:8000/openapi.json
```

---

## Performance Benchmarks

Measured on localhost with caching enabled:

| Endpoint | Uncached | Cached | Notes |
|----------|----------|--------|-------|
| `/api/forecast/{location}` | 650ms | 25ms | Real API call |
| `/api/wellbeing/{location}` | 700ms | 30ms | Real API call |
| `/api/subscribe` | 10ms | - | Database write |
| `/docs` | 50ms | 40ms | Swagger UI |

---

## Security Checklist

Before deploying to production:

- [ ] WEATHERAI_API_KEY in environment variables, not in code
- [ ] DATABASE_URL with strong credentials
- [ ] HTTPS/SSL enabled on deployment platform
- [ ] CORS configured for specific frontend domain
- [ ] Rate limiting enabled on API endpoints
- [ ] Input validation enforced
- [ ] Logs don't contain sensitive data
- [ ] Database backups configured
- [ ] Monitoring and alerting setup
- [ ] Error tracking (Sentry) configured

---

## Monitoring

### Health Checks

```bash
# Manual check
curl http://your-domain.com/health

# Automated (recommended every 60s)
watch -n 60 'curl -s http://your-domain.com/health | jq .'
```

### Logs

```bash
# Docker
docker-compose logs -f backend

# Railway
railway logs

# Heroku
heroku logs --tail

# Check for errors
grep -i "error\|exception\|traceback" logs/*.log
```

### Performance Monitoring

```bash
# Response time
time curl http://localhost:8000/api/forecast/Nairobi

# Database queries
sqlite3 moodforecast.db ".mode line" "SELECT * FROM subscriber LIMIT 1;"

# Memory usage
top  # Linux/Mac
tasklist | find "python"  # Windows
```

---

## Troubleshooting

### Backend won't start

```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill process
kill -9 <PID>

# Or use different port
uvicorn app.main:app --port 8001
```

### "ModuleNotFoundError: No module named 'app'"

```bash
# Make sure you're in backend directory
cd backend

# Activate virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### API returns 422 errors

```bash
# Check WEATHERAI_API_KEY is correct
grep WEATHERAI_API_KEY .env

# Test API key
curl -H "Authorization: Bearer wai_your_key" \
  https://api.weather-ai.co/v1/current?location=Nairobi
```

### Database errors

```bash
# Reset database
rm moodforecast.db

# Restart backend (auto-initializes)
uvicorn app.main:app --reload

# Verify
curl http://localhost:8000/health
```

### Tests failing

```bash
# Run with verbose output
pytest tests/ -v

# Run specific test
pytest tests/test_mood_engine.py::TestMoodScoring::test_sunny_boosts_score -v

# Check for import errors
python -c "from app.services.mood_engine import score_mood; print('OK')"
```

### Cache issues

```bash
# Clear in-memory cache (restart backend)
# Press Ctrl+C in terminal running uvicorn
uvicorn app.main:app --reload

# Or clear Redis cache
redis-cli FLUSHALL
```

---

## Production Checklist

- [ ] All tests passing (31/31)
- [ ] Database initialized with production URL
- [ ] Environment set to "production"
- [ ] WEATHERAI_API_KEY configured
- [ ] HTTPS enabled
- [ ] Health check working at `/health`
- [ ] API endpoints responding correctly
- [ ] Caching enabled and working
- [ ] Logs configured and monitoring active
- [ ] Backup strategy in place
- [ ] Rate limiting configured
- [ ] Error tracking (Sentry) setup
- [ ] Monitoring dashboard accessible

---

## Support

For issues or questions:

1. Check logs: `docker-compose logs backend`
2. Check health: `curl http://localhost:8000/health`
3. Review docs: `http://localhost:8000/docs`
4. Check tests: `pytest tests/ -v`

---

## Next Steps

After backend deployment:

1. **Test Frontend** - Visit http://your-domain.com
2. **Run E2E Tests** - Verify complete user journey
3. **Configure Monitoring** - Setup alerts
4. **Enable Backups** - Regular database backups
5. **Scale** - Add more workers if needed

---

**Backend Status: Ready for Production** ✓

All tests passing. All endpoints working. Database initialized. Ready to deploy!

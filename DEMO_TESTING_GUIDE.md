# MoodForecast AI - Demo & Testing Guide

**Status**: ✅ Ready for testing - Backend, frontend, and demo endpoints fully functional

---

## 🚀 Quick Start

### Option A: Demo Mode (No API Key Required)
Perfect for testing the full UI and workflow without needing a valid WeatherAI API key.

```bash
# 1. Ensure backend is running
cd /home/kk/Programming/moodforecast_ai/backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 2. In browser, navigate to:
http://localhost:8000/index-demo.html
```

✅ You'll see:
- Location search (pre-filled with "Nairobi")
- Weather card: 21.5°C, Sunny, 65% humidity
- Mood Score: 80
- Energy Level: High
- Risk Level: Minimal
- 4 wellbeing recommendations
- Subscription form

---

## 📋 Three Testing Options

### Option 1: Local Frontend Testing (Recommended First)
**Goal**: Test the full UI with real weather data by adding WeatherAI API key

**Prerequisites:**
- Valid WeatherAI API key from [weatherapi.com](https://www.weatherapi.com/)

**Steps:**
1. Get free API key from [weatherapi.com](https://www.weatherapi.com/):
   - Sign up for free account
   - Copy API key from dashboard

2. Update backend configuration:
   ```bash
   # Edit backend/.env
   WEATHERAI_API_KEY=your_actual_api_key_here
   ```

3. Restart backend:
   ```bash
   # Kill existing process (if running in background)
   pkill -f "uvicorn app.main"
   
   # Restart with new key
   cd /home/kk/Programming/moodforecast_ai/backend
   source venv/bin/activate
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. Test in browser:
   ```
   http://localhost:8000  # Regular mode (uses real WeatherAI API)
   http://localhost:8000/?demo=true  # Demo mode (uses mock data)
   ```

**Test Scenarios:**
```bash
# Test different locations
Enter: "London" → Should show London weather
Enter: "New York" → Should show New York weather
Enter: "Tokyo" → Should show Tokyo weather

# Test mood scoring with different weather conditions
# Sunny = High mood
# Rainy = Lower mood
# Storm = Very low mood

# Test subscription
Phone: +254712345678
Location: Nairobi
Crop: Maize
Language: English
→ Should see "✓ Subscribed! Subscriber ID: [UUID]"
```

---

### Option 2: End-to-End Integration Testing
**Goal**: Verify all endpoints work correctly and data flows properly

**Test All Endpoints:**
```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Forecast endpoint (requires valid API key)
curl http://localhost:8000/api/forecast/Nairobi

# 3. Wellbeing endpoint (requires valid API key)
curl http://localhost:8000/api/wellbeing/Nairobi

# 4. Subscribe endpoint
curl -X POST http://localhost:8000/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+254712345678",
    "location": "Nairobi",
    "crop": "Maize",
    "language": "en"
  }'

# 5. API documentation
curl http://localhost:8000/docs  # Swagger UI
curl http://localhost:8000/redoc  # ReDoc UI
```

**Verify Response Format:**
- `/api/forecast/{location}` returns ForecastResponse with weather data
- `/api/wellbeing/{location}` returns WellbeingResponse with mood score and recommendations
- `/api/subscribe` returns 201 status with subscriber_id and other fields
- All errors should return appropriate HTTP status codes

**Database Verification:**
```bash
# Check subscriber records
python -c "
from app.models.db import get_engine
from sqlmodel import Session, select
from app.models.db import Subscriber

engine = get_engine()
with Session(engine) as session:
    subscribers = session.exec(select(Subscriber)).all()
    for sub in subscribers:
        print(f'{sub.phone} → {sub.location} ({sub.crop})')
"
```

---

### Option 3: Railway Deployment
**Goal**: Deploy to production on Railway cloud platform

**Prerequisites:**
- GitHub repository with code
- Railway account
- Valid WeatherAI API key

**Deployment Steps:**

1. **Commit and push to GitHub:**
   ```bash
   cd /home/kk/Programming/moodforecast_ai
   git add .
   git commit -m "Complete MoodForecast AI with demo and production ready"
   git push origin main
   ```

2. **Connect to Railway:**
   - Go to [railway.app](https://railway.app)
   - Click "New Project" → "Deploy from GitHub"
   - Select your repository

3. **Configure Environment:**
   - In Railway dashboard → Environment tab
   - Add variable: `WEATHERAI_API_KEY=your_key`
   - Add variable: `ENVIRONMENT=production`
   - Add variable: `DATABASE_URL=postgresql://...` (if using prod DB)

4. **Deploy Backend:**
   - Set Root Directory to `backend/`
   - Expose PORT 8000
   - Health check: `/health`

5. **Deploy Frontend (Optional Separate Service):**
   - Option A: Serve from backend (default) ✅
   - Option B: Deploy to Netlify/Vercel separately

6. **Verify Deployment:**
   ```bash
   # Get your Railway domain
   curl https://your-railway-domain.up.railway.app/health
   curl https://your-railway-domain.up.railway.app/api/forecast/Nairobi
   ```

7. **Update Frontend (if separately deployed):**
   ```javascript
   // In frontend/app.js, change:
   const API_BASE = 'https://your-railway-domain.up.railway.app';
   ```

---

## 🔍 Demo Endpoints Reference

These endpoints return **mock data** for testing without API key:

### GET /api/demo/forecast/{location}
**Response:**
```json
{
  "location": "Nairobi",
  "weather": {
    "temp_c": 21.5,
    "condition": "Sunny",
    "humidity": 65.0,
    "wind_kph": 12.0
  },
  "forecast_days": 7,
  "ai_summary": "The weather in Nairobi looks pleasant..."
}
```

### GET /api/demo/wellbeing/{location}
**Response:**
```json
{
  "location": "Nairobi",
  "weather": {
    "temp_c": 21.5,
    "condition": "Sunny",
    "humidity": 65.0,
    "wind_kph": 12.0
  },
  "mood_score": 80,
  "energy_level": "High",
  "risk_level": "Minimal",
  "ai_summary": "Excellent conditions...",
  "recommendations": [
    "Get outside for 30+ minutes of sunlight exposure",
    "Maintain hydration with 2-3 liters of water today",
    "Consider a walk or light exercise...",
    "Plan social activities during peak sunshine hours..."
  ]
}
```

---

## 📝 Test Checklist

- [ ] Backend server starts without errors
- [ ] Health endpoint responds: `/health` → `{"status": "ok"}`
- [ ] Demo endpoints work: `/api/demo/forecast/Nairobi` and `/api/demo/wellbeing/Nairobi`
- [ ] Frontend loads at `http://localhost:8000`
- [ ] Demo mode shows mock data at `http://localhost:8000/index-demo.html`
- [ ] Search function works with different locations
- [ ] Mood score changes based on weather conditions
- [ ] Recommendations display correctly
- [ ] Subscribe button works with valid phone number
- [ ] Subscribe button rejects invalid phone number
- [ ] API documentation accessible at `/docs`
- [ ] All 31 unit + integration tests pass: `pytest tests/`

---

## 🐛 Troubleshooting

### Issue: "Location not found or API error"
**Solution:**
- Check if API key is set correctly in `backend/.env`
- Use demo mode: add `?demo=true` to URL
- Verify backend is running: `curl http://localhost:8000/health`

### Issue: Frontend doesn't load
**Solution:**
```bash
# Ensure frontend files are in static directory
ls -la backend/app/static/
# Should show: index.html, styles.css, app.js

# If missing, copy them:
cp frontend/*.{html,css,js} backend/app/static/
```

### Issue: "Port 8000 already in use"
**Solution:**
```bash
# Find and kill existing process
lsof -i :8000
kill -9 <PID>

# Or use different port
uvicorn app.main:app --port 8001
```

### Issue: Database errors on subscribe
**Solution:**
```bash
# Reset database
rm backend/moodforecast.db
rm backend/app/*.db

# Restart backend to recreate tables
```

---

## 📊 Project Structure

```
/home/kk/Programming/moodforecast_ai/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Settings from .env
│   │   ├── static/              # Frontend files served here
│   │   │   ├── index.html       # Main page
│   │   │   ├── index-demo.html  # Demo mode page
│   │   │   ├── styles.css       # Styling
│   │   │   └── app.js           # JavaScript logic
│   │   ├── models/
│   │   │   ├── schemas.py       # Pydantic models
│   │   │   └── db.py            # SQLModel definitions
│   │   ├── routers/
│   │   │   ├── forecast.py      # GET /api/forecast/{location}
│   │   │   ├── wellbeing.py     # GET /api/wellbeing/{location}
│   │   │   ├── subscribe.py     # POST /api/subscribe
│   │   │   └── demo.py          # GET /api/demo/* (mock endpoints)
│   │   ├── services/
│   │   │   ├── mood_engine.py   # Mood scoring logic
│   │   │   └── weatherai.py     # WeatherAI API client
│   │   └── tests/
│   │       ├── test_mood_engine.py  # 23 unit tests ✓
│   │       └── test_endpoints.py    # 8 integration tests ✓
│   ├── Dockerfile
│   ├── railway.toml
│   ├── requirements.txt
│   ├── .env                     # Configuration (keep secret!)
│   └── venv/                    # Python virtual environment
│
├── frontend/
│   ├── index.html
│   ├── index-demo.html
│   ├── styles.css
│   ├── app.js
│   └── app-demo.js
│
└── [Deployment Guides]
    ├── TESTING_DEPLOYMENT.md
    └── DEMO_TESTING_GUIDE.md    # This file
```

---

## ✅ Current Status

| Component | Status | Tests | Notes |
|-----------|--------|-------|-------|
| Backend Server | ✅ Ready | 31/31 passing | Python 3.13 compatible |
| Frontend UI | ✅ Ready | N/A | HTML5/CSS3/Vanilla JS |
| Demo Endpoints | ✅ Ready | Mock data | No API key needed |
| Real Endpoints | ⏳ Ready* | Real data | *Requires WeatherAI API key |
| Database | ✅ Ready | Working | SQLite + SQLModel |
| Docker | ✅ Ready | Can build | Multi-stage Alpine image |
| Railway Config | ✅ Ready | Can deploy | Configuration complete |

---

## 🎯 Next Steps

1. **For Testing (Recommended):**
   - Start with **Demo Mode**: http://localhost:8000/index-demo.html
   - Then add WeatherAI API key for **Option 1**
   - Run through **Option 2** checklist

2. **For Production:**
   - Complete **Option 2** testing
   - Prepare **Option 3** deployment
   - Deploy to Railway

3. **For Debugging:**
   - Check logs: `tail -f backend/logs/app.log`
   - Database: `sqlite3 backend/moodforecast.db`
   - API Docs: http://localhost:8000/docs

---

## 📞 Support

**Common Commands:**
```bash
# Run tests
cd backend && pytest tests/ -v

# Check Python version
python --version

# Activate environment
source backend/venv/bin/activate

# Start backend
cd backend && uvicorn app.main:app --reload --port 8000

# Clear cache in browser
Ctrl+Shift+Delete (open DevTools) → Cache Storage → Clear

# Check backend health
curl http://localhost:8000/health | python -m json.tool
```

---

**Last Updated**: 2024-06-05  
**Version**: 1.0.0  
**Author**: MoodForecast AI Team

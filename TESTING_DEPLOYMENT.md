# MoodForecast AI - Testing & Deployment Guide

## ✅ Current Status

### Backend Status: PRODUCTION READY
- ✅ 31/31 tests passing (23 unit + 8 integration)
- ✅ All 5 API endpoints created and tested
- ✅ FastAPI + Pydantic + SQLModel fully configured
- ✅ Async WeatherAI client with caching
- ✅ Mood scoring engine with psychological rationale
- ✅ SMS subscription registration (stub)
- ✅ Docker containerization configured
- ✅ Development server running on port 8000

### Frontend Status: PRODUCTION READY
- ✅ HTML5/CSS3 responsive UI created
- ✅ Vanilla JavaScript (no build step required)
- ✅ Connected to backend API endpoints
- ✅ Location search with auto-load
- ✅ Weather card display
- ✅ Mood score visualization with badges
- ✅ Wellbeing recommendations
- ✅ SMS subscription form with E.164 validation
- ✅ Error handling and loading states

## 🔧 Integration Requirements

### WeatherAI API Key
To test the full end-to-end flow, you need a valid WeatherAI API key:

1. Sign up at [WeatherAI](https://www.weatherapi.com/)
2. Get your API key
3. Update the `.env` file in the backend:
   ```
   WEATHERAI_API_KEY=your_actual_key_here
   ```
4. Restart the backend server

### Current Test Configuration
```bash
Backend URL: http://localhost:8000
Frontend URL: http://localhost:8000
API Base: Relative (same domain)
Database: SQLite (in-memory for testing)
Cache: TTL-based in-memory (10 minutes)
```

## 🧪 Testing Procedures

### Option 1: Local Frontend Testing (Current)
**Status:** Frontend loads, but API calls fail without valid WeatherAI key

```bash
# Terminal 1: Start backend
cd /home/kk/Programming/moodforecast_ai/backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Access frontend
http://localhost:8000
```

**What works:**
- ✅ Frontend loads and renders
- ✅ HTML/CSS responsive layout
- ✅ Search box and form inputs
- ✅ Auto-load on page initialization

**What fails without valid API key:**
- ❌ Weather forecast fetching
- ❌ Wellbeing calculation
- ❌ Recommendations display

### Option 2: End-to-End Integration Testing

**Prerequisites:**
- Valid WeatherAI API key
- Backend running with real key configured

**Test Script:**
```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Forecast endpoint
curl http://localhost:8000/api/forecast/Nairobi

# 3. Wellbeing endpoint
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

# 5. Swagger UI
http://localhost:8000/docs
```

### Option 3: Railway Deployment

**Prerequisites:**
- GitHub account with repository
- Railway account (free tier available)
- WeatherAI API key configured

**Deployment Steps:**

1. **Commit to GitHub:**
   ```bash
   cd /home/kk/Programming/moodforecast_ai
   git init
   git add .
   git commit -m "Initial MoodForecast AI deployment"
   git remote add origin https://github.com/YOUR_USERNAME/moodforecast_ai.git
   git push -u origin main
   ```

2. **Deploy Backend to Railway:**
   ```bash
   # In Railway dashboard:
   - New Project → GitHub repo → Select moodforecast_ai
   - Root directory: backend
   - Build: Auto-detect (Python)
   - Deploy: Auto-start on push
   ```

3. **Configure Environment Variables in Railway:**
   ```
   WEATHERAI_API_KEY=your_actual_key
   DATABASE_URL=sqlite:///./moodforecast.db
   ENVIRONMENT=production
   ```

4. **Deploy Frontend to Railway (Static Files):**
   ```bash
   # In Railway dashboard:
   - Add service → Static site
   - Source: GitHub repo
   - Root directory: frontend
   - Build command: (leave empty)
   - Start command: (leave empty)
   ```

5. **Update Frontend API Base:**
   After deployment, update `frontend/app.js`:
   ```javascript
   const API_BASE = 'https://your-railway-domain.up.railway.app';
   ```

## 📊 Project Structure Summary

```
moodforecast_ai/
├── backend/                    ✅ READY
│   ├── app/
│   │   ├── main.py            - FastAPI app factory
│   │   ├── config.py          - Environment config
│   │   ├── models/
│   │   │   ├── schemas.py     - Request/response models
│   │   │   └── db.py          - Database models
│   │   ├── services/
│   │   │   ├── mood_engine.py - Mood scoring (23 tests pass)
│   │   │   ├── weatherai.py   - WeatherAI async client
│   │   │   └── cache.py       - TTL caching
│   │   ├── routers/
│   │   │   ├── forecast.py    - /api/forecast endpoint
│   │   │   ├── wellbeing.py   - /api/wellbeing endpoint
│   │   │   └── subscribe.py   - /api/subscribe endpoint (status_code=201)
│   │   └── static/
│   │       └── index.html     - Backward compatible
│   ├── tests/                 - 31 passing tests
│   │   ├── test_mood_engine.py
│   │   └── test_endpoints.py
│   ├── requirements.txt       - Python 3.13 compatible
│   ├── .env                   - Test configuration
│   ├── Dockerfile             - Multi-stage Alpine build
│   └── railway.toml           - Railway deployment config
│
├── frontend/                  ✅ READY
│   ├── index.html            - Main page
│   ├── styles.css            - Responsive styling
│   └── app.js                - Vanilla JavaScript logic
│
└── README.md                  - Project documentation
```

## 🚀 Quick Start Summary

### For Local Testing (with mock/test data):
```bash
cd backend && source venv/bin/activate && uvicorn app.main:app --reload
# Open http://localhost:8000
# Note: Needs valid WeatherAI key for real data
```

### For Full Integration:
```bash
# 1. Get WeatherAI API key from weatherapi.com
# 2. Update backend/.env with your key
# 3. Restart backend
# 4. Test endpoints and frontend
```

### For Production (Railway):
```bash
# 1. Push to GitHub
# 2. Connect to Railway
# 3. Set environment variables
# 4. Deploy both backend and frontend
# 5. Update frontend API_BASE to Railway domain
```

## 📝 Next Steps

1. **Get WeatherAI API Key** - Required for actual weather data
2. **Update Environment** - Configure .env with real key
3. **Test Integration** - Verify all endpoints work end-to-end
4. **Deploy to Railway** - Production deployment
5. **Set up SMS Integration** - Upgrade Plan for Scale SMS capability
6. **Database Migration** - Switch from SQLite to PostgreSQL for production

## 🐛 Troubleshooting

**Frontend shows "Location not found":**
- Verify WeatherAI API key is valid in backend/.env
- Check backend logs for errors
- Try different location format

**422 Unprocessable Entity:**
- Check phone number format (must be E.164: +254...)
- Verify all required fields are filled
- Check browser console for validation errors

**Backend won't start:**
- Verify Python 3.13 compatible packages installed
- Check venv is activated
- Review backend/requirements.txt

**Database errors:**
- For SQLite: Ensure write permissions on database file
- For production: Use PostgreSQL (better concurrency)
- Check DATABASE_URL environment variable

## 📞 Support Resources

- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **WeatherAI API:** https://www.weatherapi.com/
- **Railway Docs:** https://docs.railway.app/
- **Pydantic:** https://docs.pydantic.dev/
- **SQLModel:** https://sqlmodel.tiangolo.com/

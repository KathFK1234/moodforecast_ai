## Quick Start - Demo Mode (No API Key)

```bash
# 1. Start backend (from backend directory)
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# 2. Open in browser (demo mode - uses mock weather data)
http://localhost:8000/index-demo.html
```

✅ You'll see mock weather data, mood scoring, and recommendations instantly!

---

## Testing & Deployment Workflow

We provide **three testing options** before production:

### 📝 Option 1: Local Frontend Testing (Recommended)
Add WeatherAI API key for real weather data

### 🔄 Option 2: End-to-End Integration
Test all endpoints with real API responses

### 🚀 Option 3: Railway Cloud Deployment
Deploy to production on Railway platform

**For complete testing guide, see:** [DEMO_TESTING_GUIDE.md](DEMO_TESTING_GUIDE.md)

---

## ✅ Project Status

| Component | Status | Details |
|-----------|--------|---------|
| Backend API | ✅ Ready | FastAPI 0.115.0, Python 3.13 compatible |
| Frontend UI | ✅ Ready | HTML5/CSS3/Vanilla JS, no build step |
| Mood Engine | ✅ Ready | 23/23 unit tests passing |
| API Endpoints | ✅ Ready | 8/8 integration tests passing |
| Database | ✅ Ready | SQLite with SQLModel ORM |
| Demo Mode | ✅ Ready | Mock endpoints, no API key needed |
| Docker | ✅ Ready | Multi-stage Alpine build |
| Railway Config | ✅ Ready | Cloudflare integration ready |

**Total Test Coverage**: 31/31 tests passing ✓

---

## 🚀 Try It Now

```bash
# Demo mode (uses mock weather data - fastest way to test)
http://localhost:8000/index-demo.html

# Regular mode (requires WeatherAI API key)
http://localhost:8000

# API Documentation
http://localhost:8000/docs          # Swagger UI
http://localhost:8000/redoc         # ReDoc

# Demo Endpoints (no API key needed)
curl http://localhost:8000/api/demo/forecast/Nairobi
curl http://localhost:8000/api/demo/wellbeing/Nairobi
```

---

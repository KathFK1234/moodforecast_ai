# MoodForecast AI

Your personal AI-powered weather and mood forecasting platform. Combines real-time weather data with mood scoring algorithms to provide personalized wellness recommendations.

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone <your-repo-url>
cd moodforecast_ai
```

### 2. Setup Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add WEATHERAI_API_KEY=wai_your_actual_key_here
```

### 3. Run Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

Backend starts at: **http://localhost:8000**
- Frontend: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### 4. Test

```bash
# Run full test suite
cd backend
pytest tests/ -q
# Expected: 31 passed ✓
```

## 📚 Documentation

### For Backend Development & Deployment

See [backend/GUIDE.md](backend/GUIDE.md) for:
- Complete setup instructions
- Running and testing the API
- Database configuration
- Deployment options (Railway, Docker, Heroku, AWS)
- Environment variables
- Troubleshooting

### For Frontend Development & Deployment

See [frontend/GUIDE.md](frontend/GUIDE.md) for:
- Frontend architecture
- Local development setup
- Testing scenarios
- Customization guide
- **Frontend deployment info** (answer to "what do I need to share?")

## 🏗️ Project Structure

```
moodforecast_ai/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py            # Application entry point
│   │   ├── config.py          # Configuration
│   │   ├── models/            # Database models
│   │   ├── routers/           # API endpoints
│   │   ├── services/          # Business logic
│   │   └── static/            # Frontend files
│   ├── tests/                 # Test suite (31 tests, all passing)
│   ├── requirements.txt       # Python dependencies
│   ├── .env.example          # Environment template
│   ├── Dockerfile            # Container image
│   └── GUIDE.md              # Backend documentation
│
├── frontend/                   # Frontend application
│   ├── index.html            # Main HTML
│   ├── app.js                # JavaScript logic
│   ├── styles.css            # Styling

│   └── GUIDE.md              # Frontend documentation
│
├── README.md                  # This file
├── SETUP_GUIDE.md            # Quick setup reference
└── .gitignore                # Git ignore rules
```

## 🎯 Features

✅ **Real-time Weather** - Integration with Weather-AI.co API
✅ **Mood Scoring** - AI-powered mood prediction engine
✅ **Smart Recommendations** - Context-aware wellness tips
✅ **Subscription Alerts** - Register for SMS/USSD notifications (backend ready)

✅ **Responsive Design** - Works on desktop, tablet, mobile
✅ **Caching** - Fast repeat requests
✅ **Error Handling** - Graceful error messages
✅ **Comprehensive Tests** - 31 unit & integration tests

## 🔧 Technology Stack

### Backend
- **Framework**: FastAPI 0.115.0 (Python async web framework)
- **Database**: SQLite (development) / PostgreSQL (production)
- **Validation**: Pydantic 2.8.0
- **ORM**: SQLModel 0.0.14
- **HTTP Client**: httpx 0.27.0
- **Testing**: pytest 8.3.2

### Frontend
- **HTML/CSS/JavaScript** - Vanilla (no frameworks/build tools)
- **Responsive Design** - Mobile-first approach
- **API Communication** - Fetch API

## 📊 Test Status

```
✓ Unit Tests (23):          mood_engine.py logic
✓ Integration Tests (8):    API endpoints
───────────────────────────
✓ Total: 31/31 passing
```

Run tests:
```bash
cd backend
pytest tests/ -q
```

## 🚀 Deployment

### Quick Deploy to Railway (Recommended)

1. Push to GitHub
2. Go to railway.app
3. Connect repository
4. Add environment variables
5. Deploy (automatic on push)

**See [backend/GUIDE.md](backend/GUIDE.md) for complete deployment options**

Options:
- ✅ Railway (free tier with $5 credit)
- ✅ Docker (local/VPS)
- ✅ Heroku (paid, no free tier anymore)
- ✅ AWS (Lightsail/ECS)

## 📖 Key Commands

### Backend Development

```bash
# Setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
uvicorn app.main:app --reload

# Test
pytest tests/ -v

# Check API docs
# Open: http://localhost:8000/docs
```

### Frontend Development

Frontend files are at `frontend/` directory and automatically served by backend at `http://localhost:8000`.

For local frontend development:
```bash
cd frontend
python -m http.server 8001
# or: npm install -g http-server && http-server
```

Then edit:
- `frontend/index.html` - Page structure
- `frontend/app.js` - Functionality
- `frontend/styles.css` - Styling

Changes are automatically reflected when you refresh the browser.

## 🔑 Environment Variables

### Required

```
WEATHERAI_API_KEY=wai_your_actual_key_here  # Get from weather-ai.co
ENVIRONMENT=development                      # or production
```

### Optional

```
DATABASE_URL=sqlite:///./moodforecast.db     # Default SQLite
CACHE_TTL_SECONDS=600                        # Cache duration (10 min)
REDIS_URL=redis://localhost:6379/0           # Optional Redis cache
```

## 📝 API Endpoints

### Production (Requires API Key)
- `GET /api/forecast/{location}` - Real weather forecast
- `GET /api/wellbeing/{location}` - Mood score & recommendations
- `POST /api/subscribe` - Register for alerts

### Utility
- `GET /health` - Health check
- `GET /docs` - Swagger UI documentation
- `GET /redoc` - ReDoc documentation

## 🐛 Troubleshooting

### Backend won't start
```bash
# Check Python version
python --version  # Should be 3.11+

# Check port 8000 is available
lsof -i :8000

# Install dependencies
cd backend && pip install -r requirements.txt
```

### API returns errors
```bash
# Check API key in .env
grep WEATHERAI_API_KEY backend/.env

# Check backend is running
curl http://localhost:8000/health

# Check logs
docker-compose logs backend  # If using Docker
```

### Frontend not showing
```bash
# Check backend is running
curl http://localhost:8000

# Check frontend files exist
ls backend/app/static/

# Clear browser cache
# Ctrl+Shift+Delete (or Cmd+Shift+Delete on Mac)
```

## 📚 Additional Documentation

- [Backend GUIDE](backend/GUIDE.md) - Complete backend documentation
- [Frontend GUIDE](frontend/GUIDE.md) - Complete frontend documentation
- [API Docs](http://localhost:8000/docs) - Interactive API documentation (when backend is running)

## 🎓 Learning Resources

### Understanding the Codebase

1. **Entry Point**: `backend/app/main.py`
2. **Routes**: `backend/app/routers/`
3. **Business Logic**: `backend/app/services/`
4. **Database**: `backend/app/models/`
5. **Tests**: `backend/tests/`

### Modifying Features

See [frontend/GUIDE.md - Customization](frontend/GUIDE.md#frontend-customization) for:
- Adding new sections
- Changing colors/theme
- Adding functionality
- Customizing recommendations

## 🤝 Contributing

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes
3. Run tests: `pytest tests/ -v`
4. Commit: `git commit -m "Add feature"`
5. Push: `git push origin feature/your-feature`
6. Create pull request

## ✅ Pre-Deployment Checklist

- [ ] All tests passing (31/31)
- [ ] Backend starts without errors
- [ ] Frontend loads at http://localhost:8000
- [ ] Search works for multiple locations
- [ ] Subscription form works
- [ ] API key configured
- [ ] Database initialized
- [ ] No sensitive data in code

## 🚀 Next Steps

1. **Setup Backend** - Follow "Quick Start" above
2. **Test API** - Use actual endpoints
3. **Test Frontend** - Search for locations
4. **Run Tests** - Verify everything works
5. **Deploy** - See [backend/GUIDE.md](backend/GUIDE.md) for deployment

## 📞 Support

Having issues?

1. **Backend**: See [backend/GUIDE.md - Troubleshooting](backend/GUIDE.md#troubleshooting)
2. **Frontend**: See [frontend/GUIDE.md - Troubleshooting](frontend/GUIDE.md#troubleshooting)
3. **Tests**: Run with verbose output: `pytest tests/ -v`
4. **Logs**: Check `docker-compose logs backend`

## 📄 License

[Your License Here]

---

**Status: Ready for Development & Deployment** ✓

All systems operational. 31 tests passing. Documentation complete.

Start with: `cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`

Then: `uvicorn app.main:app --reload`


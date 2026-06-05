#!/bin/bash
# MoodForecast AI - Setup Verification Script
# Run this to verify everything is ready for deployment

echo "🔍 MoodForecast AI - Setup Verification"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
    fi
}

fail() {
    echo -e "${RED}✗ $1${NC}"
}

pass() {
    echo -e "${GREEN}✓ $1${NC}"
}

# 1. Check Python environment
echo "1. Python Environment"
cd /home/kk/Programming/moodforecast_ai/backend
if [ -d "venv" ]; then
    pass "Virtual environment exists"
else
    fail "Virtual environment missing"
    exit 1
fi

if source venv/bin/activate; then
    pass "Virtual environment activates"
else
    fail "Cannot activate virtual environment"
    exit 1
fi

python_version=$(python --version 2>&1)
pass "Python version: $python_version"
echo ""

# 2. Check dependencies
echo "2. Dependencies"
pip list | grep -q "fastapi" && pass "FastAPI installed" || fail "FastAPI missing"
pip list | grep -q "sqlmodel" && pass "SQLModel installed" || fail "SQLModel missing"
pip list | grep -q "pytest" && pass "pytest installed" || fail "pytest missing"
pip list | grep -q "pydantic" && pass "Pydantic installed" || fail "Pydantic missing"
echo ""

# 3. Check configuration
echo "3. Configuration"
if [ -f ".env" ]; then
    pass ".env file exists"
    if grep -q "WEATHERAI_API_KEY" .env; then
        pass "WEATHERAI_API_KEY configured"
        api_key=$(grep "WEATHERAI_API_KEY" .env | cut -d= -f2)
        if [ -z "$api_key" ] || [ "$api_key" = "your_api_key_here" ]; then
            fail "API key is still placeholder or empty"
            echo "   Get API key from: https://weather-ai.co"
        else
            pass "API key configured (weather-ai.co)"
        fi
    else
        fail "WEATHERAI_API_KEY not in .env"
    fi
else
    fail ".env file missing"
fi
echo ""

# 4. Check database
echo "4. Database"
if python -c "from app.models.db import create_tables; create_tables(); print('OK')" &>/dev/null; then
    pass "Database tables can be created"
else
    fail "Database initialization failed"
fi
echo ""

# 5. Check frontend files
echo "5. Frontend Files"
if [ -f "app/static/index.html" ]; then
    pass "Frontend index.html deployed"
else
    fail "Frontend index.html missing"
fi

[ -f "app/static/styles.css" ] && pass "styles.css deployed" || fail "styles.css missing"
[ -f "app/static/app.js" ] && pass "app.js deployed" || fail "app.js missing"
echo ""

# 6. Check tests
echo "6. Tests"
test_count=$(pytest tests/ --collect-only -q 2>/dev/null | tail -1 | grep -oP '\d+(?= test)' || echo "0")
if [ "$test_count" -gt 0 ]; then
    pass "Found $test_count tests"
    if pytest tests/ -q &>/dev/null; then
        pass "All tests passing"
    else
        fail "Some tests failing"
    fi
else
    fail "No tests found"
fi
echo ""

# 7. Check Docker
echo "7. Docker Configuration"
if [ -f "Dockerfile" ]; then
    pass "Dockerfile exists"
else
    fail "Dockerfile missing"
fi

if [ -f "railway.toml" ]; then
    pass "railway.toml exists"
else
    fail "railway.toml missing"
fi
echo ""

# 8. Check backend server
echo "8. Backend Server"
if pgrep -f "uvicorn app.main" > /dev/null; then
    pass "Backend server running on port 8000"
    
    # Test endpoints
    health=$(curl -s http://localhost:8000/health 2>/dev/null)
    if echo "$health" | grep -q '"status"'; then
        pass "Health endpoint working"
    else
        fail "Health endpoint not responding"
    fi
    
    # Test demo endpoints
    demo=$(curl -s http://localhost:8000/api/demo/forecast/Nairobi 2>/dev/null)
    if echo "$demo" | grep -q '"location"'; then
        pass "Demo endpoints working"
    else
        fail "Demo endpoints not responding"
    fi
else
    fail "Backend server not running"
    echo "   Start with: cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
fi
echo ""

# Summary
echo "=========================================="
echo "✅ Setup Verification Complete"
echo ""
echo "Next steps:"
echo "1. If not already running, start backend:"
echo "   cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo ""
echo "2. Run testing workflow:"
echo "   - Test in browser: http://localhost:8000"
echo "   - Or demo mode: http://localhost:8000/?demo=true"
echo "   - Or separate page: http://localhost:8000/index-demo.html"
echo ""
echo "3. Run full test suite:"
echo "   pytest tests/ -v"
echo ""
echo "4. When ready to deploy:"
echo "   - See DEPLOYMENT_READY.md for complete instructions"
echo "   - Commit to GitHub"
echo "   - Deploy to Railway dashboard"
echo ""

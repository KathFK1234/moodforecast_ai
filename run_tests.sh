#!/bin/bash

# MoodForecast AI - Complete Testing & Validation Script
# Run all tests and validations before deployment

set -e  # Exit on first error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
SKIPPED=0

# Helper functions
pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED++))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED++))
}

skip() {
    echo -e "${YELLOW}⊘${NC} $1"
    ((SKIPPED++))
}

test_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

# Start testing
echo -e "${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║  MoodForecast AI - Testing Suite          ║"
echo "║  $(date '+%Y-%m-%d %H:%M:%S')                 ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# Check backend is running
test_header "1. Backend Service"

if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    pass "Backend is running on port 8000"
else
    fail "Backend is NOT running - Start with: cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
    exit 1
fi

# Check API Key
if grep -q "WEATHERAI_API_KEY" backend/.env && grep -v "^#" backend/.env | grep "WEATHERAI_API_KEY" | grep -v "your_api_key_here" | grep -v "=" > /dev/null; then
    pass "WEATHERAI_API_KEY configured"
else
    fail "WEATHERAI_API_KEY not configured in .env"
fi

# Test endpoints
test_header "2. API Endpoints"

# Health
health=$(curl -s http://localhost:8000/health | grep -o '"status":"ok"')
[ -n "$health" ] && pass "Health endpoint working" || fail "Health endpoint not working"

# Forecast
forecast=$(curl -s http://localhost:8000/api/forecast/Nairobi | grep -o '"location"')
[ -n "$forecast" ] && pass "Forecast endpoint working" || fail "Forecast endpoint not working"

# Wellbeing
wellbeing=$(curl -s http://localhost:8000/api/wellbeing/London | grep -o '"mood_score"')
[ -n "$wellbeing" ] && pass "Wellbeing endpoint working" || fail "Wellbeing endpoint not working"

# Demo
demo=$(curl -s http://localhost:8000/api/demo/forecast/Test | grep -o '"location"')
[ -n "$demo" ] && pass "Demo endpoint working" || fail "Demo endpoint not working"

# Subscribe
subscribe=$(curl -s -X POST http://localhost:8000/api/subscribe \
  -H "Content-Type: application/json" \
  -d '{"phone":"+254712345678","location":"Nairobi"}' | grep -o '"message"')
[ -n "$subscribe" ] && pass "Subscribe endpoint working" || fail "Subscribe endpoint not working"

# Documentation
docs=$(curl -s http://localhost:8000/docs | grep -o 'swagger')
[ -n "$docs" ] && pass "API documentation available at /docs" || fail "API documentation not accessible"

# Unit Tests
test_header "3. Unit Tests"

cd backend

if [ -f "tests/test_mood_engine.py" ]; then
    test_count=$(pytest tests/test_mood_engine.py --collect-only -q 2>/dev/null | tail -1 | grep -oP '\d+(?= test)' || echo "0")
    if pytest tests/test_mood_engine.py -q > /dev/null 2>&1; then
        pass "Unit tests ($test_count tests) - ALL PASSING"
    else
        fail "Unit tests - SOME FAILING"
    fi
else
    skip "Unit tests - test file not found"
fi

# Integration Tests
if [ -f "tests/test_endpoints.py" ]; then
    int_test_count=$(pytest tests/test_endpoints.py --collect-only -q 2>/dev/null | tail -1 | grep -oP '\d+(?= test)' || echo "0")
    if pytest tests/test_endpoints.py -q > /dev/null 2>&1; then
        pass "Integration tests ($int_test_count tests) - ALL PASSING"
    else
        fail "Integration tests - SOME FAILING"
    fi
else
    skip "Integration tests - test file not found"
fi

cd ..

# Frontend Tests
test_header "4. Frontend"

if [ -f "backend/app/static/index.html" ]; then
    pass "Frontend index.html deployed"
else
    fail "Frontend index.html missing"
fi

if [ -f "backend/app/static/app.js" ]; then
    pass "Frontend JavaScript deployed"
else
    fail "Frontend JavaScript missing"
fi

if [ -f "backend/app/static/styles.css" ]; then
    pass "Frontend CSS deployed"
else
    fail "Frontend CSS missing"
fi

# Database
test_header "5. Database"

if [ -f "backend/moodforecast.db" ]; then
    pass "SQLite database initialized"
    
    # Check record count
    record_count=$(cd backend && sqlite3 moodforecast.db "SELECT COUNT(*) FROM subscriber;" 2>/dev/null || echo "0")
    pass "Database has $record_count subscriber record(s)"
else
    fail "Database not found - may initialize on first run"
fi

# Configuration
test_header "6. Configuration"

if [ -f ".env.example" ]; then
    pass ".env.example template exists"
else
    fail ".env.example template missing"
fi

if [ -f "SETUP_GUIDE.md" ]; then
    pass "Setup guide documentation exists"
else
    fail "Setup guide documentation missing"
fi

if [ -f "DEPLOYMENT.md" ]; then
    pass "Deployment guide documentation exists"
else
    fail "Deployment guide documentation missing"
fi

if [ -f "E2E_TESTING.md" ]; then
    pass "E2E testing documentation exists"
else
    fail "E2E testing documentation missing"
fi

if [ -f ".gitignore" ]; then
    pass ".gitignore configured"
else
    fail ".gitignore not found"
fi

# Performance
test_header "7. Performance"

# First request (uncached)
start=$(date +%s%N)
curl -s http://localhost:8000/api/forecast/Berlin > /dev/null
end=$(date +%s%N)
time1=$((($end - $start) / 1000000))  # Convert to ms

# Second request (cached)
start=$(date +%s%N)
curl -s http://localhost:8000/api/forecast/Berlin > /dev/null
end=$(date +%s%N)
time2=$((($end - $start) / 1000000))  # Convert to ms

if [ $time1 -lt 1000 ]; then
    pass "Uncached request: ${time1}ms (Good)"
else
    fail "Uncached request: ${time1}ms (Slow - check API)"
fi

if [ $time2 -lt 50 ]; then
    pass "Cached request: ${time2}ms (Excellent)"
else
    fail "Cached request: ${time2}ms (Slow - check cache)"
fi

# Docker & Deployment
test_header "8. Deployment Configuration"

if [ -f "backend/Dockerfile" ]; then
    pass "Docker configuration exists"
else
    fail "Docker configuration missing"
fi

if [ -f "backend/railway.toml" ]; then
    pass "Railway configuration exists"
else
    fail "Railway configuration missing"
fi

if [ -f "backend/requirements.txt" ]; then
    pass "Python requirements file exists"
else
    fail "Python requirements file missing"
fi

# Final Summary
test_header "📊 TEST SUMMARY"

TOTAL=$((PASSED + FAILED + SKIPPED))
PERCENT=$((PASSED * 100 / TOTAL))

echo "Total Tests:    $TOTAL"
echo -e "Passed:         ${GREEN}$PASSED${NC}"
echo -e "Failed:         ${RED}$FAILED${NC}"
echo -e "Skipped:        ${YELLOW}$SKIPPED${NC}"
echo ""
echo "Success Rate:   ${PERCENT}%"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL CHECKS PASSED - READY FOR DEPLOYMENT${NC}"
    exit 0
else
    echo -e "${RED}✗ SOME CHECKS FAILED - FIX ISSUES BEFORE DEPLOYMENT${NC}"
    exit 1
fi

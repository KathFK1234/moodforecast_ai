# MoodForecast AI - Frontend Guide

Complete guide for the frontend application - development, testing, and deployment.

## Table of Contents

1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
3. [File Structure](#file-structure)
4. [Local Development](#local-development)
5. [Testing](#testing)
6. [Deployment](#deployment)
7. [Frontend Architecture](#frontend-architecture)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The MoodForecast AI frontend is a lightweight, responsive single-page application (SPA) built with vanilla HTML/CSS/JavaScript. It communicates with the backend API to fetch weather data and mood scores.

### Key Features

- **Responsive Design** - Works on desktop, tablet, and mobile
- **Dark/Light Theme** - Auto-detects system preference
- **Real-time Weather** - Fetches live data from Weather-AI.co API
- **Mood Scoring** - Displays AI-powered mood predictions
- **Demo Mode** - Works without API key for testing
- **Subscription Management** - Easy alert registration
- **Error Handling** - Graceful error messages
- **Caching** - Fast repeat requests

---

## Technology Stack

- **Frontend**: Vanilla JavaScript (no frameworks)
- **Styling**: Pure CSS3 (no build tools)
- **Backend**: FastAPI (Python)
- **API**: Weather-AI.co REST API
- **Storage**: Browser LocalStorage for preferences

### Why Vanilla JS?

- No build tools required
- Fast initial load
- Works offline after first load
- Easy to understand and modify
- Minimal dependencies
- Perfect for mobile-first applications

---

## File Structure

```
frontend/
├── index.html              # Main HTML file (production)
├── index-demo.html         # Demo version (for testing without API)
├── app.js                  # Main application logic (production)
├── app-demo.js            # Demo version (mock data)
├── styles.css             # All styling
├── GUIDE.md               # This file
└── README.md              # Quick overview
```

### How Frontend is Deployed

The frontend files are served by the backend:

```
backend/app/static/
├── index.html  → served as frontend root
├── app.js
└── styles.css
```

When you run the backend, it automatically serves these files at `http://localhost:8000`

---

## Local Development

### Prerequisites

- Any modern browser (Chrome, Firefox, Safari, Edge)
- Backend running at `http://localhost:8000`
- (Optional) Node.js for simple server

### Option 1: Using Backend Server (Recommended)

```bash
# In backend directory
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

# Frontend automatically available at:
# http://localhost:8000
```

### Option 2: Using Python Simple Server

```bash
# In frontend directory
cd frontend
python -m http.server 8001

# Access at: http://localhost:8001
# Edit files and refresh browser to see changes
```

### Option 3: Using Node.js Server

```bash
# Install simple-http-server
npm install -g http-server

# In frontend directory
cd frontend
http-server

# Access at: http://localhost:8080
```

### Option 4: Using VS Code Live Server

1. Install "Live Server" extension in VS Code
2. Right-click on index.html
3. Select "Open with Live Server"
4. Auto-opens at `http://127.0.0.1:5500`

---

## Editing & Customization

### Editing HTML (index.html)

The HTML file contains the page structure:

```html
<!-- Search box -->
<input id="locationInput" type="text" placeholder="Enter location">

<!-- Weather display -->
<div id="weatherDisplay">...</div>

<!-- Mood scores -->
<div id="moodDisplay">...</div>

<!-- Subscribe form -->
<form id="subscribeForm">...</form>
```

To add sections:

1. Add a new `<div>` in HTML
2. Add CSS in `styles.css`
3. Add JavaScript handler in `app.js`

### Editing CSS (styles.css)

CSS is organized by component:

```css
/* Layout */
:root { --primary-color: #007bff; }
body { font-family: -apple-system, BlinkMacSystemFont; }

/* Components */
.search-box { ... }
.weather-card { ... }
.mood-display { ... }
.button { ... }
```

To customize:

1. Change colors: Update `--primary-color`, `--accent-color`, etc.
2. Change fonts: Update `font-family`
3. Change breakpoints: Update mobile media query
4. Add animations: Add `@keyframes`

### Editing JavaScript (app.js)

JavaScript structure:

```javascript
// 1. Configuration
const API_BASE = 'http://localhost:8000';

// 2. Helper functions
async function getLocation(lat, lon) { }
function displayWeather(data) { }

// 3. Event handlers
document.getElementById('searchBtn').addEventListener('click', searchLocation);

// 4. Initialization
document.addEventListener('DOMContentLoaded', init);
```

To add features:

1. Add function for new feature
2. Add event listener to trigger it
3. Update HTML to add UI element
4. Update CSS to style it

---

## Testing

### Manual Testing - Real API

Test with actual weather data:

```bash
# 1. Start backend (with valid WEATHERAI_API_KEY)
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

# 2. Open frontend
open http://localhost:8000

# 3. Test scenarios
```

### Manual Testing Scenarios

1. **Search Location**
   - [ ] Enter "Nairobi" in search box
   - [ ] Click search or press Enter
   - [ ] Weather card appears with real data
   - [ ] Response time < 1 second (if cached)

2. **Check Weather Display**
   - [ ] Temperature shows in Celsius
   - [ ] Weather condition matches (Sunny, Cloudy, Rainy, etc.)
   - [ ] Humidity and wind displayed
   - [ ] Icons update with condition

3. **Check Mood Scores**
   - [ ] Mood score 0-100 displayed
   - [ ] Energy level shows (High/Medium/Low/Very Low)
   - [ ] Risk level shows (Minimal/Low/Moderate/High)
   - [ ] Recommendations appear

4. **Test Subscription**
   - [ ] Enter phone number: +254712345678
   - [ ] Enter location: Nairobi
   - [ ] (Optional) Select crop and language
   - [ ] Submit form
   - [ ] Success message appears
   - [ ] Form clears

5. **Test Error Handling**
   - [ ] Search invalid location → error message
   - [ ] Network offline → error message
   - [ ] Invalid phone → validation error
   - [ ] Errors clear when valid input provided

6. **Test Responsive Design**
   - [ ] Desktop (1200px+): Side-by-side layout
   - [ ] Tablet (768px-1199px): Stacked layout
   - [ ] Mobile (< 768px): Full width, touch-friendly
   - [ ] Buttons/links easily clickable on mobile

7. **Test Demo Mode**
   - [ ] Open: `http://localhost:8000?demo=true`
   - [ ] Instant responses (no network call)
   - [ ] Mock data displays
   - [ ] Search any location, gets same mock response
   - [ ] Useful for testing without API key

### Automated Testing

Create test file (optional):

```javascript
// frontend/test.js
async function testFrontend() {
  console.log('Testing frontend...');
  
  // Test 1: Can fetch weather
  const response = await fetch('/api/demo/forecast/Nairobi');
  const data = await response.json();
  console.assert(data.weather.temp_c > 0, 'Temperature should be > 0');
  
  // Test 2: Can fetch wellbeing
  const wellbeing = await fetch('/api/demo/wellbeing/Nairobi').then(r => r.json());
  console.assert(wellbeing.mood_score >= 0, 'Mood score should be >= 0');
  
  console.log('✓ All tests passed');
}

testFrontend();
```

Run in browser console:
```javascript
// In DevTools Console tab
await testFrontend();
```

---

## Browser Testing

### Test in Multiple Browsers

- [ ] Chrome/Chromium (latest)
- [ ] Firefox (latest)
- [ ] Safari (on macOS/iOS)
- [ ] Edge (Windows)
- [ ] Mobile browsers (iOS Safari, Chrome Android)

### Test in Browser DevTools

```javascript
// Open DevTools (F12 or Cmd+Option+I)

// Check localStorage
localStorage.getItem('theme');
localStorage.getItem('recentLocation');

// Check API calls
// Go to Network tab, perform search
// Should see: api/forecast/{location}

// Check console errors
// Go to Console tab
// Should be clean (no red errors)

// Test responsive design
// DevTools → Toggle device toolbar (Cmd+Shift+M)
// Test mobile, tablet, desktop sizes
```

### Mobile Device Testing

```bash
# Get your computer's IP
ifconfig | grep "inet " | head -1

# Run backend on all interfaces
uvicorn app.main:app --host 0.0.0.0 --port 8000

# On mobile device, navigate to:
# http://YOUR_IP:8000

# Test on actual mobile:
# - Touch interactions
# - Scroll performance
# - Text readability
# - Button sizes
```

---

## Deployment

The frontend is part of the backend deployment. When you deploy the backend, the frontend goes with it.

### Step 1: Ensure Frontend Files are Updated

```bash
# Files are at: backend/app/static/
# They're auto-served by backend

# Just ensure they're in git
git add backend/app/static/
git commit -m "Update frontend"
```

### Step 2: Deploy Backend (Frontend deploys with it)

#### Railway (Recommended)

```bash
# 1. Push to GitHub
git push origin main

# 2. Railway auto-deploys
# 3. Frontend available at: https://your-app.railroad.app

# 4. Test
curl https://your-app.railroad.app
# Should return HTML
```

#### Docker

```bash
# Frontend files auto-included in docker build
docker build -t moodforecast .
docker run -p 8000:8000 moodforecast

# Access at: http://localhost:8000
```

#### Heroku

```bash
git push heroku main

# Frontend auto-deployed
# Access at: https://your-app.herokuapp.com
```

### Step 3: Verify Deployment

```bash
# Health check
curl https://your-domain.com/health

# Frontend loads
curl https://your-domain.com | grep "<html"

# API works
curl https://your-domain.com/api/demo/forecast/Nairobi
```

---

## Frontend Architecture

### How Requests Flow

```
User Input
    ↓
Event Handler (app.js)
    ↓
API Call (fetch)
    ↓
Backend (/api/forecast, /api/wellbeing)
    ↓
Response (JSON)
    ↓
Parse & Validate
    ↓
Update DOM (display results)
    ↓
Cache Result (localStorage)
```

### Component Communication

```javascript
// 1. User enters location
<input id="locationInput">

// 2. JavaScript captures it
document.getElementById('searchBtn').addEventListener('click', async () => {
  const location = document.getElementById('locationInput').value;
  
  // 3. Call API
  const weather = await fetch(`/api/forecast/${location}`).then(r => r.json());
  
  // 4. Display result
  document.getElementById('weatherDisplay').innerHTML = `
    <h2>${weather.location}</h2>
    <p>${weather.weather.condition}</p>
  `;
});
```

### State Management

Data stored in:

```javascript
// Session (cleared on refresh)
const cache = {};

// Local storage (persists across sessions)
localStorage.setItem('recentLocation', location);
localStorage.getItem('recentLocation');

// DOM (real-time)
document.getElementById('weatherDisplay').textContent = 'Loading...';
```

### Error Handling

```javascript
try {
  const response = await fetch(`/api/forecast/${location}`);
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  const data = await response.json();
  displayWeather(data);
  
} catch (error) {
  console.error('Error:', error);
  displayError(`Could not fetch weather: ${error.message}`);
}
```

---

## Performance Optimization

### Already Implemented

- [x] Minimal CSS (no framework bloat)
- [x] Vanilla JavaScript (no library overhead)
- [x] Responsive images
- [x] CSS media queries
- [x] LocalStorage caching
- [x] Gzip compression (via backend)

### Further Optimization

If needed:

```javascript
// 1. Service Worker for offline support
// 2. Lazy loading for images
// 3. Code splitting for large apps
// 4. Image optimization
// 5. CSS minification
```

---

## Troubleshooting

### Frontend Won't Load

```javascript
// Check in browser console
1. Network tab → see if index.html loaded
2. Console tab → any red errors?
3. Application tab → check LocalStorage

// If 404 error:
// - Backend not running?
// - Wrong URL?
// - Frontend files not in backend/app/static/?
```

### API Calls Failing

```javascript
// Check in browser DevTools Network tab

// CORS error? Check backend CORS config
// 401/403? Check API key in backend .env
// 422? Check request format
// 500? Backend error - check backend logs

// Manual test
fetch('/api/demo/forecast/Nairobi')
  .then(r => r.json())
  .then(d => console.log(d))
  .catch(e => console.error(e));
```

### Styling Issues

```css
/* Check CSS is loaded */
/* DevTools → Elements → <head> → should see styles.css */

/* Check CSS syntax */
/* DevTools → Console → should be clean */

/* Check responsive breakpoints */
/* DevTools → Device toolbar, test sizes */
```

### Mobile Issues

```
Buttons too small?
→ Increase button size in media query

Text too small?
→ Increase font-size in mobile breakpoint

Overflow on screen?
→ Check max-width, add overflow-x: hidden

Touch interactions not working?
→ Ensure buttons have min 44x44px touch target
```

---

## Frontend Customization

### Change Theme Colors

Edit in `styles.css`:

```css
:root {
  --primary-color: #007bff;    /* Change this */
  --accent-color: #ff6b6b;     /* And this */
  --bg-color: #f8f9fa;         /* And this */
}
```

### Change Weather Icons

In `app.js`, update condition to icon mapping:

```javascript
function getWeatherIcon(condition) {
  const icons = {
    'Sunny': '☀️',
    'Cloudy': '☁️',
    'Rainy': '🌧️',
    // Add more
  };
  return icons[condition] || '🌤️';
}
```

### Add New Fields

1. Update HTML (add new element)
2. Update CSS (style it)
3. Update JavaScript (populate it from API response)
4. Update API backend if needed

---

## What Needs to Be Shared/Deployed for Frontend?

### Everything is Included in Backend

The frontend files are automatically deployed with the backend:

**You just deploy the backend, frontend comes along.**

### Files That Deploy:

```
backend/app/static/
├── index.html       ← Main frontend page
├── app.js          ← Frontend JavaScript
└── styles.css      ← Frontend styles
```

### Deployment Process

1. **Update frontend files** (if you made changes)
   ```bash
   # Edit files in frontend/ directory
   nano frontend/index.html
   ```

2. **Copy to backend** (so they get deployed)
   ```bash
   # Files are already here if using standard setup
   cp frontend/index.html backend/app/static/
   cp frontend/app.js backend/app/static/
   cp frontend/styles.css backend/app/static/
   ```

3. **Deploy backend** (frontend deploys with it)
   ```bash
   git add -A
   git commit -m "Update frontend"
   git push origin main  # If using Railway/GitHub
   ```

### No Separate Frontend Deployment Needed

- ✅ No need for Vercel/Netlify
- ✅ No need for separate frontend hosting
- ✅ No need for build process
- ✅ No need for Node.js deployment

The backend serves the frontend directly!

---

## Production Checklist

- [ ] All tests passing
- [ ] Frontend loads at domain root
- [ ] Search works with real locations
- [ ] Subscription form works
- [ ] Mobile responsive tested
- [ ] Errors display clearly
- [ ] API key configured in backend
- [ ] Backend deployed and running
- [ ] HTTPS enabled
- [ ] Monitoring active

---

## Support

### Check Logs

```bash
# Backend logs (shows frontend issues)
docker-compose logs backend

# Browser console (F12)
# Look for red errors
```

### Test Endpoints

```javascript
// In browser console
fetch('/health').then(r => r.json()).then(console.log);
fetch('/api/demo/forecast/Nairobi').then(r => r.json()).then(console.log);
fetch('/api/demo/wellbeing/London').then(r => r.json()).then(console.log);
```

---

## Next Steps

1. ✅ Backend running locally
2. ✅ Frontend loads and works
3. ✅ Tests passing
4. → **Deploy backend (with frontend)**
5. → Monitor in production

---

**Frontend Status: Ready for Deployment** ✓

No build process needed. No separate deployment required. Deploys with backend!

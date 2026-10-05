const API_BASE = '';  // Use same domain as frontend

const POPULAR_CITIES = ['Nairobi', 'Mombasa', 'Kisumu', 'Lagos', 'London', 'Tokyo', 'New York'];
const POPULAR_ACTIVITIES = [
    'Go for a run', 'Have a picnic', 'Go swimming', 'Ride a bike', 'Fly a kite',
    'Stargaze', 'Have a barbecue', 'Go skiing', 'Read a book',
];
const LAST_LOCATION_KEY = 'moodforecast:lastLocation';

// Line icons, drawn on a 24x24 grid
const CLOUD = '<path d="M7 18h10a4 4 0 0 0 .6-7.96A6 6 0 0 0 6.2 9.2 4.5 4.5 0 0 0 7 18z"/>';
const CLOUD_HIGH = '<path d="M7 15h10a4 4 0 0 0 .6-7.96A6 6 0 0 0 6.2 6.2 4.5 4.5 0 0 0 7 15z"/>';
const ICONS = {
    'clear-day': '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    'clear-night': '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a7 7 0 1 0 10.5 10.5z"/>',
    'partly-day': '<circle cx="8" cy="8" r="3"/><path d="M8 2v1.5M2 8h1.5M3.8 3.8l1 1M12.2 3.8l-1 1"/><path d="M9 20h8a3.5 3.5 0 0 0 .5-6.96A5 5 0 0 0 8.3 12.3 3.9 3.9 0 0 0 9 20z"/>',
    'partly-night': '<path d="M11.5 3.5a4.5 4.5 0 0 0 5 5.9 4.5 4.5 0 0 1-5-5.900z"/><path d="M7 20h9a3.5 3.5 0 0 0 .5-6.96A5 5 0 0 0 6.8 12.3 3.9 3.9 0 0 0 7 20z"/>',
    'cloudy': CLOUD,
    'fog': CLOUD_HIGH + '<path d="M5 18.5h14M7 21.5h10"/>',
    'drizzle': CLOUD_HIGH + '<path d="M9 18.5v.5M12 18.5v.5M15 18.5v.5M10.5 21.5v.5M13.5 21.5v.5"/>',
    'rain': CLOUD_HIGH + '<path d="M9 18l-1 3M13 18l-1 3M17 18l-1 3"/>',
    'snow': CLOUD_HIGH + '<path d="M9 19h.01M12 21h.01M15 19h.01M9 22.5h.01M15 22.5h.01"/>',
    'storm': CLOUD_HIGH + '<path d="M12.5 16.500l-2.5 3.500h3.500L11 23.5"/>',
    'search': '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
    'check': '<path d="M5 12.5l4.5 4.500L19 7.5"/>',
};

// Mood score bands, matching the backend's energy levels
function scoreLevel(score) {
    if (score >= 75) return 'high';
    if (score >= 50) return 'medium';
    if (score >= 25) return 'low';
    return 'verylow';
}

function icon(name) {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.cloudy}</svg>`;
}

// Map a condition description to an icon / theme family
function conditionKind(condition) {
    const c = (condition || '').toLowerCase();
    if (c.includes('thunder') || c.includes('storm')) return 'storm';
    if (c.includes('snow')) return 'snow';
    if (c.includes('drizzle')) return 'drizzle';
    if (c.includes('rain')) return 'rain';
    if (c.includes('fog')) return 'fog';
    if (c.includes('partly')) return 'partly';
    if (c.includes('cloud') || c.includes('overcast')) return 'cloudy';
    if (c.includes('clear') || c.includes('sunny')) return 'clear';
    return 'cloudy';
}

function conditionIcon(condition, isDay = true) {
    const kind = conditionKind(condition);
    if (kind === 'clear' || kind === 'partly') return icon(`${kind}-${isDay ? 'day' : 'night'}`);
    return icon(kind);
}

function applyTheme(condition, isDay) {
    const kind = conditionKind(condition);
    let theme = kind;
    if (kind === 'clear' || kind === 'partly') theme = isDay ? 'clear-day' : 'clear-night';
    else if (kind === 'drizzle') theme = 'rain';
    else if (!isDay) theme = `${kind}-night`;
    document.body.dataset.theme = theme;
}

const el = (id) => document.getElementById(id);
const round = (value) => Math.round(value);
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

let searchToken = 0;  // Guards against a slow earlier search overwriting a newer one
let hasResults = false;
let currentLocation = '';  // The place the results on screen are for
let lastActivity = '';     // Re-asked when the place changes
let activityToken = 0;

// Read the API's error message, whatever shape it comes in
async function errorMessage(response, fallback) {
    try {
        const body = await response.json();
        if (typeof body.detail === 'string') return body.detail;
        if (Array.isArray(body.detail) && body.detail.length) {
            return body.detail.map((d) => (d.msg || '').replace(/^Value error, /, '')).join(' ');
        }
    } catch (e) {
        // Not JSON - fall through
    }
    return fallback;
}

async function fetchJson(path, fallback) {
    let response;
    try {
        response = await fetch(`${API_BASE}${path}`);
    } catch (e) {
        throw new Error('Could not reach the server. Check your connection and try again.');
    }
    if (!response.ok) throw new Error(await errorMessage(response, fallback));
    return response.json();
}

async function handleSearch(location) {
    location = (location || '').trim();
    if (!location) {
        showError('Enter a location to search.');
        return;
    }

    const token = ++searchToken;
    hideError();
    showLoading(true);
    el('searchButton').disabled = true;

    try {
        const encoded = encodeURIComponent(location);
        const [forecastData, wellbeingData] = await Promise.all([
            fetchJson(`/api/forecast/${encoded}`, 'Could not load the forecast.'),
            fetchJson(`/api/wellbeing/${encoded}`, 'Could not calculate wellbeing.'),
        ]);
        if (token !== searchToken) return;

        applyTheme(wellbeingData.weather.condition, wellbeingData.weather.is_day);
        displayWeather(forecastData);
        displayForecast(forecastData.daily || []);
        displayWellbeing(wellbeingData);

        el('cropLocationInput').value = wellbeingData.location;
        currentLocation = location;
        el('activityPlace').textContent = wellbeingData.location;
        if (lastActivity) askActivity(lastActivity);
        el('results').classList.remove('hidden');
        hasResults = true;
        replayReveal();
        highlightChip(location);
        try {
            localStorage.setItem(LAST_LOCATION_KEY, location);
        } catch (e) {
            // Storage unavailable (private mode) - not needed for the page to work
        }
    } catch (error) {
        if (token !== searchToken) return;
        showError(error.message || 'Something went wrong. Please try again.');
    } finally {
        if (token === searchToken) {
            showLoading(false);
            el('searchButton').disabled = false;
        }
    }
}

function displayWeather(data) {
    const weather = data.weather;
    const today = (data.daily || [])[0] || {};

    el('locationName').textContent = data.location;
    el('nowMeta').textContent = weather.is_day ? 'Right now · Daytime' : 'Right now · Night';
    el('nowIcon').innerHTML = conditionIcon(weather.condition, weather.is_day);
    el('tempValue').textContent = round(weather.temp_c);
    el('conditionValue').textContent = weather.condition;
    el('feelsValue').textContent = weather.feels_like_c == null
        ? ''
        : `Feels like ${round(weather.feels_like_c)}°`;

    el('humidityValue').textContent = `${round(weather.humidity)}%`;
    el('windValue').textContent = `${round(weather.wind_kph)} km/h`;
    el('rainValue').textContent = today.precipitation_chance == null ? '–' : `${round(today.precipitation_chance)}%`;
    el('uvValue').textContent = today.uv_index == null ? '–' : `${round(today.uv_index)} · ${uvLabel(today.uv_index)}`;
    el('sunriseValue').textContent = today.sunrise || '–';
    el('sunsetValue').textContent = today.sunset || '–';
}

function uvLabel(uv) {
    if (uv < 3) return 'Low';
    if (uv < 6) return 'Moderate';
    if (uv < 8) return 'High';
    if (uv < 11) return 'Very high';
    return 'Extreme';
}

function displayForecast(days) {
    const list = el('forecastList');
    list.innerHTML = '';

    const weekMin = Math.min(...days.map((d) => d.temp_min_c));
    const weekMax = Math.max(...days.map((d) => d.temp_max_c));
    const span = Math.max(weekMax - weekMin, 1);

    days.forEach((day, index) => {
        // Parse as local midnight so the weekday doesn't shift with the browser's timezone
        const date = new Date(day.date + 'T00:00:00');
        const label = index === 0 ? 'Today' : date.toLocaleDateString('en', { weekday: 'short' });
        const level = scoreLevel(day.mood_score);

        const li = document.createElement('li');
        li.className = 'day';
        li.style.setProperty('--i', index);
        li.title = [
            day.sunrise && day.sunset ? `Sunrise ${day.sunrise}, sunset ${day.sunset}` : '',
            day.uv_index == null ? '' : `UV index ${round(day.uv_index)} (${uvLabel(day.uv_index)})`,
        ].filter(Boolean).join(' · ');

        const dayEl = document.createElement('div');
        dayEl.className = 'day-name';
        dayEl.textContent = label;
        const dateEl = document.createElement('span');
        dateEl.className = 'day-date';
        dateEl.textContent = date.toLocaleDateString('en', { day: 'numeric', month: 'short' });
        dayEl.appendChild(dateEl);

        const condEl = document.createElement('div');
        condEl.className = 'day-cond';
        const iconEl = document.createElement('span');
        iconEl.className = 'day-icon';
        iconEl.innerHTML = conditionIcon(day.condition, true);
        const condText = document.createElement('span');
        condText.className = 'day-cond-text';
        condText.textContent = day.condition;
        condEl.append(iconEl, condText);

        const rainEl = document.createElement('div');
        rainEl.className = 'day-rain';
        rainEl.textContent = day.precipitation_chance == null ? '' : `${round(day.precipitation_chance)}%`;
        rainEl.setAttribute('aria-label', day.precipitation_chance == null ? '' : `${round(day.precipitation_chance)}% chance of rain`);

        const tempEl = document.createElement('div');
        tempEl.className = 'day-temp';
        const minEl = document.createElement('span');
        minEl.className = 'temp-min';
        minEl.textContent = `${round(day.temp_min_c)}°`;
        const track = document.createElement('span');
        track.className = 'temp-track';
        const range = document.createElement('span');
        range.className = 'temp-range';
        range.style.left = `${((day.temp_min_c - weekMin) / span) * 100}%`;
        range.style.width = `${Math.max(((day.temp_max_c - day.temp_min_c) / span) * 100, 6)}%`;
        track.appendChild(range);
        const maxEl = document.createElement('span');
        maxEl.className = 'temp-max';
        maxEl.textContent = `${round(day.temp_max_c)}°`;
        tempEl.append(minEl, track, maxEl);

        const moodEl = document.createElement('div');
        moodEl.className = 'day-mood';
        moodEl.dataset.level = level;
        const meter = document.createElement('span');
        meter.className = 'mood-meter';
        const fill = document.createElement('span');
        fill.className = 'mood-meter-fill';
        fill.style.width = `${day.mood_score}%`;
        meter.appendChild(fill);
        const scoreEl = document.createElement('span');
        scoreEl.className = 'day-score';
        scoreEl.textContent = day.mood_score;
        const moodLabel = document.createElement('span');
        moodLabel.className = 'day-mood-label';
        moodLabel.textContent = day.mood_label;
        moodEl.append(scoreEl, meter, moodLabel);

        li.append(dayEl, condEl, rainEl, tempEl, moodEl);
        list.appendChild(li);
    });

    el('forecastSection').classList.toggle('hidden', days.length === 0);
}

function displayWellbeing(data) {
    const level = scoreLevel(data.mood_score);

    // Gauge
    const gauge = el('gauge');
    gauge.dataset.level = level;
    const fill = el('gaugeFill');
    const circumference = 2 * Math.PI * 52;
    fill.style.strokeDasharray = circumference;
    fill.style.strokeDashoffset = circumference;
    // Force a reflow so the ring animates from empty each time
    fill.getBoundingClientRect();
    fill.style.strokeDashoffset = circumference * (1 - data.mood_score / 100);
    el('gaugeLabel').textContent = `Mood score ${data.mood_score} out of 100`;
    countUp(el('moodScore'), data.mood_score);

    el('moodLabel').textContent = data.mood_label;

    setBadge(el('energyBadge'), `${data.energy_level} energy`, level);
    const riskLevel = { Minimal: 'high', Low: 'medium', Moderate: 'low', High: 'verylow' }[data.risk_level] || 'medium';
    setBadge(el('riskBadge'), `${data.risk_level} risk`, riskLevel);

    // Summary
    const summary = el('aiSummaryDiv');
    summary.textContent = data.ai_summary || '';
    summary.classList.toggle('hidden', !data.ai_summary);

    // Why this score
    const factors = el('factorsList');
    factors.innerHTML = '';
    factors.appendChild(factorRow('Baseline', data.baseline_score, true));
    (data.factors || []).forEach((factor) => factors.appendChild(factorRow(factor.label, factor.delta, false)));
    if (!(data.factors || []).length) {
        const none = document.createElement('li');
        none.className = 'factor-none';
        none.textContent = 'Nothing in the current conditions moves the score.';
        factors.appendChild(none);
    }

    // Recommendations
    const recList = el('recommendationsList');
    recList.innerHTML = '';
    data.recommendations.forEach((rec) => {
        const li = document.createElement('li');
        li.textContent = rec;
        recList.appendChild(li);
    });

    displayCuriosity(data.curiosity || []);
}

// Questions about other places; tapping one searches that place
function displayCuriosity(prompts) {
    const list = el('curiosityList');
    list.innerHTML = '';
    prompts.forEach((prompt) => {
        const li = document.createElement('li');
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'curiosity-prompt';
        const question = document.createElement('span');
        question.textContent = prompt.question;
        const place = document.createElement('span');
        place.className = 'curiosity-place';
        place.textContent = `${prompt.location} →`;
        button.append(question, place);
        button.addEventListener('click', () => searchPlace(prompt.location));
        li.appendChild(button);
        list.appendChild(li);
    });
    el('curiositySection').classList.toggle('hidden', prompts.length === 0);
}

// Search a suggested place, by default bringing the results back into view
function searchPlace(place, scrollToTop = true) {
    el('locationInput').value = place;
    if (scrollToTop) window.scrollTo({ top: 0, behavior: reducedMotion ? 'auto' : 'smooth' });
    return handleSearch(place);
}

// Ask whether the weather at the current place suits an activity
async function askActivity(question) {
    question = (question || '').trim();
    const error = el('activityError');
    if (!question) {
        showNotice(error, 'Type something you would like to do.', true);
        return;
    }
    if (!currentLocation) return;

    lastActivity = question;
    const token = ++activityToken;
    error.classList.add('hidden');
    el('activityButton').disabled = true;

    try {
        const data = await fetchJson(
            `/api/activity/${encodeURIComponent(currentLocation)}?activity=${encodeURIComponent(question)}`,
            'Could not check that activity.'
        );
        if (token !== activityToken) return;
        displayActivity(data);
    } catch (e) {
        if (token !== activityToken) return;
        el('activityResult').classList.add('hidden');
        showNotice(error, e.message, true);
    } finally {
        if (token === activityToken) el('activityButton').disabled = false;
    }
}

function displayActivity(data) {
    const verdict = {
        go: ['Go for it', 'high'],
        maybe: ['With a little care', 'low'],
        skip: ['Not right now', 'verylow'],
    }[data.verdict] || ['', 'medium'];
    setBadge(el('activityVerdict'), verdict[0], verdict[1]);
    el('activityHeadline').textContent = data.headline;

    const reasons = el('activityReasons');
    reasons.innerHTML = '';
    data.reasons.forEach((reason) => {
        const li = document.createElement('li');
        li.textContent = reason;
        reasons.appendChild(li);
    });

    const suggestion = el('activitySuggestion');
    suggestion.textContent = data.suggestion || '';
    suggestion.classList.toggle('hidden', !data.suggestion);

    // Other places to try the same question
    el('activityCuriosity').textContent = data.curiosity.question;
    const places = el('activityPlaces');
    places.innerHTML = '';
    data.curiosity.places.forEach((place) => {
        places.appendChild(chipButton(place, () => searchPlace(place, false)));
    });

    el('activityResult').classList.remove('hidden');
}

function chipButton(text, onClick) {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'chip';
    chip.textContent = text;
    chip.addEventListener('click', onClick);
    return chip;
}

function factorRow(label, value, isBaseline) {
    const li = document.createElement('li');
    li.className = 'factor';

    const name = document.createElement('span');
    name.className = 'factor-name';
    name.textContent = label;

    const bar = document.createElement('span');
    bar.className = 'factor-bar';
    if (!isBaseline) {
        const fill = document.createElement('span');
        fill.className = `factor-fill ${value >= 0 ? 'is-up' : 'is-down'}`;
        // Largest single factor is ±20, which fills one half of the bar
        fill.style.width = `${Math.min(Math.abs(value) / 20, 1) * 50}%`;
        bar.appendChild(fill);
    } else {
        bar.classList.add('is-empty');
    }

    const amount = document.createElement('span');
    amount.className = 'factor-value';
    amount.textContent = isBaseline ? value : `${value > 0 ? '+' : '−'}${Math.abs(value)}`;

    li.append(name, bar, amount);
    return li;
}

function setBadge(badge, text, level) {
    badge.className = `badge level-${level}`;
    badge.textContent = text;
}

function countUp(node, target) {
    if (reducedMotion) {
        node.textContent = target;
        return;
    }
    const start = performance.now();
    const duration = 900;
    function frame(now) {
        const progress = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        node.textContent = Math.round(target * eased);
        if (progress < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
}

// Restart the entrance animation for each new result
function replayReveal() {
    document.querySelectorAll('.reveal').forEach((node, index) => {
        node.style.setProperty('--i', index);
        node.classList.remove('is-in');
        node.getBoundingClientRect();
        node.classList.add('is-in');
    });
}

async function handleSubscribe(event) {
    event.preventDefault();

    const phone = el('phoneInput').value.trim();
    const location = el('cropLocationInput').value.trim();
    const crop = el('cropInput').value.trim() || null;
    const language = el('languageSelect').value;
    const msg = el('subscribeMessage');

    if (!phone || !location) {
        showNotice(msg, 'Enter a phone number and a location.', true);
        return;
    }

    const btn = el('subscribeBtn');
    btn.disabled = true;
    btn.textContent = 'Subscribing…';

    try {
        let res;
        try {
            res = await fetch(`${API_BASE}/api/subscribe`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ phone, location, crop, language })
            });
        } catch (e) {
            throw new Error('Could not reach the server. Check your connection and try again.');
        }

        if (!res.ok) throw new Error(await errorMessage(res, 'Subscription failed. Please try again.'));

        const data = await res.json();
        showNotice(msg, `Subscribed. Your subscriber ID is ${data.subscriber_id}`, false);
        el('phoneInput').value = '';
        el('cropInput').value = '';
    } catch (error) {
        showNotice(msg, error.message, true);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Subscribe';
    }
}

function showNotice(node, text, isError) {
    node.className = `notice ${isError ? 'notice-error' : 'notice-success'}`;
    node.textContent = text;
}

function showLoading(show) {
    // First load shows placeholders; later searches dim the current results instead
    el('loadingState').classList.toggle('hidden', !show || hasResults);
    el('results').classList.toggle('is-refreshing', show && hasResults);
}

function hideError() {
    el('errorState').classList.add('hidden');
}

function showError(message) {
    const node = el('errorState');
    node.textContent = message;
    node.classList.remove('hidden');
}

function highlightChip(location) {
    document.querySelectorAll('#cityChips .chip').forEach((chip) => {
        chip.classList.toggle('is-active', chip.textContent.toLowerCase() === location.toLowerCase());
    });
}

function buildChips() {
    const wrap = el('cityChips');
    POPULAR_CITIES.forEach((city) => {
        wrap.appendChild(chipButton(city, () => {
            el('locationInput').value = city;
            handleSearch(city);
        }));
    });

    const activities = el('activityChips');
    POPULAR_ACTIVITIES.forEach((activity) => {
        activities.appendChild(chipButton(activity, () => {
            el('activityInput').value = activity;
            askActivity(activity);
        }));
    });
}

function init() {
    el('brandMark').innerHTML = icon('partly-day');
    el('searchIcon').innerHTML = icon('search');
    buildChips();

    el('searchForm').addEventListener('submit', (event) => {
        event.preventDefault();
        handleSearch(el('locationInput').value);
    });
    el('activityForm').addEventListener('submit', (event) => {
        event.preventDefault();
        askActivity(el('activityInput').value);
    });
    el('subscribeForm').addEventListener('submit', handleSubscribe);

    // Start from ?q= in the link, then the last place searched, then the default
    let initial = el('locationInput').value;
    try {
        initial = localStorage.getItem(LAST_LOCATION_KEY) || initial;
    } catch (e) {
        // Storage unavailable - use the default
    }
    initial = new URLSearchParams(window.location.search).get('q') || initial;
    el('locationInput').value = initial;
    handleSearch(initial);
}

init();

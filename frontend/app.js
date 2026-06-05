const API_BASE = '';  // Use same domain as frontend

async function handleSearch() {
    const location = document.getElementById('locationInput').value.trim();
    if (!location) {
        showError('Please enter a location');
        return;
    }

    showLoading(true);
    hideError();
    hideWellbeing();

    try {
        // Fetch forecast
        const forecastRes = await fetch(`${API_BASE}/api/forecast/${encodeURIComponent(location)}`);
        if (!forecastRes.ok) throw new Error('Location not found or API error');
        const forecastData = await forecastRes.json();

        // Fetch wellbeing
        const wellbeingRes = await fetch(`${API_BASE}/api/wellbeing/${encodeURIComponent(location)}`);
        if (!wellbeingRes.ok) throw new Error('Unable to calculate wellbeing');
        const wellbeingData = await wellbeingRes.json();

        // Display weather
        displayWeather(forecastData);

        // Display wellbeing
        displayWellbeing(wellbeingData);

        // Show subscribe form and populate location
        document.getElementById('cropLocationInput').value = wellbeingData.location;
        document.getElementById('subscribeSection').classList.remove('hidden');

    } catch (error) {
        showError(error.message || 'Failed to fetch data. Please try again.');
    } finally {
        showLoading(false);
    }
}

function displayWeather(data) {
    document.getElementById('locationName').textContent = data.location;
    document.getElementById('tempValue').textContent = data.weather.temp_c + '°C';
    document.getElementById('humidityValue').textContent = data.weather.humidity + '%';
    document.getElementById('conditionValue').textContent = data.weather.condition;
    document.getElementById('windValue').textContent = data.weather.wind_kph + ' kph';
    document.getElementById('weatherCard').classList.remove('hidden');
}

function displayWellbeing(data) {
    document.getElementById('moodScore').textContent = data.mood_score;

    // Energy level badge
    const energyClass = {
        'High': 'level-high',
        'Medium': 'level-medium',
        'Low': 'level-low',
        'Very Low': 'level-verylow'
    }[data.energy_level] || 'level-medium';
    document.getElementById('energyBadge').className = `level-badge ${energyClass}`;
    document.getElementById('energyBadge').textContent = data.energy_level + ' Energy';

    // Risk level badge
    const riskClass = {
        'Minimal': 'level-high',
        'Low': 'level-medium',
        'Moderate': 'level-low',
        'High': 'level-verylow'
    }[data.risk_level] || 'level-medium';
    document.getElementById('riskBadge').className = `level-badge ${riskClass}`;
    document.getElementById('riskBadge').textContent = data.risk_level + ' Risk';

    // AI summary
    if (data.ai_summary) {
        document.getElementById('aiSummaryDiv').textContent = data.ai_summary;
        document.getElementById('aiSummaryDiv').classList.remove('hidden');
    } else {
        document.getElementById('aiSummaryDiv').classList.add('hidden');
    }

    // Recommendations
    const recList = document.getElementById('recommendationsList');
    recList.innerHTML = '';
    data.recommendations.forEach(rec => {
        const li = document.createElement('li');
        li.textContent = rec;
        recList.appendChild(li);
    });

    document.getElementById('wellbeingSection').classList.remove('hidden');
}

async function handleSubscribe(event) {
    event.preventDefault();

    const phone = document.getElementById('phoneInput').value.trim();
    const location = document.getElementById('cropLocationInput').value.trim();
    const crop = document.getElementById('cropInput').value.trim() || null;
    const language = document.getElementById('languageSelect').value;

    if (!phone || !location) {
        alert('Please fill in required fields');
        return;
    }

    const btn = document.getElementById('subscribeBtn');
    btn.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/api/subscribe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone, location, crop, language })
        });

        if (!res.ok) throw new Error('Subscription failed');

        const data = await res.json();
        const msg = document.getElementById('subscribeMessage');
        msg.className = 'subscribe-success';
        msg.textContent = `✓ Subscribed! Subscriber ID: ${data.subscriber_id}`;
    } catch (error) {
        const msg = document.getElementById('subscribeMessage');
        msg.className = 'error';
        msg.textContent = error.message;
    } finally {
        btn.disabled = false;
    }
}

function showLoading(show) {
    document.getElementById('loadingState').classList.toggle('hidden', !show);
}

function hideError() {
    document.getElementById('errorState').classList.add('hidden');
}

function showError(message) {
    const el = document.getElementById('errorState');
    el.textContent = message;
    el.classList.remove('hidden');
}

function hideWellbeing() {
    document.getElementById('weatherCard').classList.add('hidden');
    document.getElementById('wellbeingSection').classList.add('hidden');
    document.getElementById('subscribeSection').classList.add('hidden');
}

// Allow Enter key to search
document.getElementById('locationInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') handleSearch();
});

// Auto-load on page load
window.addEventListener('load', function() {
    handleSearch();
});

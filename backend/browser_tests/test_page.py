"""Tests of the page in a real browser, under its real security headers.

Run from backend/ with: pytest browser_tests -q
The API is answered here, so these need no network. BROWSER_CHANNEL=chrome
uses an installed Chrome instead of Playwright's Chromium.
"""

import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
import pytest
from playwright.sync_api import Page, expect, sync_playwright

BACKEND = Path(__file__).resolve().parents[1]
SUBSCRIBED = {"email": "amina@example.com", "location": "Nairobi, KE", "activity": None}


@pytest.fixture(scope="session")
def site(tmp_path_factory):
    """The real app, on a free port, with a throwaway database."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}"}
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=BACKEND, env=env
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"{url}/health")
                break
            except OSError:
                time.sleep(0.1)
        yield url
    finally:
        server.terminate()
        server.wait()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=os.environ.get("BROWSER_CHANNEL") or None)
        yield browser
        browser.close()


@pytest.fixture(params=[390, 1280], ids=["phone", "desktop"])
def page(request, browser):
    """A page that fails the test on any script error, with the API answered here."""
    context = browser.new_context(viewport={"width": request.param, "height": 800})
    page = context.new_page()
    page.set_default_timeout(5000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("**/api/**", lambda route: route.abort())
    page.route("**/api/alerts", lambda route: route.fulfill(json={"available": True}))
    page.route("**/api/unsubscribe-link", lambda route: route.fulfill(status=202, json={"status": "sent_if_subscribed"}))
    page.route("**/api/unsubscribe/used", lambda route: route.fulfill(status=404, json={"detail": "Already used."}))
    page.route("**/api/unsubscribe/good", lambda route: route.fulfill(json={"email": SUBSCRIBED["email"], "status": "unsubscribed"}))
    page.route("**/api/confirm/good", lambda route: route.fulfill(json={**SUBSCRIBED, "status": "subscribed"}))
    page.route("**/api/subscribe", lambda route: route.fulfill(status=202, json={**SUBSCRIBED, "status": "pending", "confirmation_sent": True}))
    yield page
    context.close()
    assert errors == []


def open_page(page: Page, site: str, query: str = "") -> None:
    page.goto(f"{site}/{query}")
    # The results hold the subscribe form; these tests answer no forecast
    page.evaluate("document.getElementById('results').classList.remove('hidden')")


def test_the_page_fits_the_screen(page, site):
    open_page(page, site)
    width = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    assert width[0] <= width[1]


def test_the_font_loads_from_this_site(page, site):
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    open_page(page, site)
    assert page.evaluate("document.fonts.load(\"16px 'DM Sans'\").then((faces) => faces.length)") > 0
    assert all(url.startswith(site) for url in requests)


def test_the_form_reminds_people_about_spam(page, site):
    open_page(page, site)
    page.fill("#emailInput", SUBSCRIBED["email"])
    page.fill("#subLocationInput", "Nairobi")
    page.click("#subscribeBtn")
    expect(page.locator("#subscribeMessage")).to_contain_text("check your spam folder")


def test_the_unsubscribe_pop_up_opens_closes_and_sends_a_link(page, site):
    open_page(page, site)
    dialog = page.locator("#optOutDialog")
    
    page.click("#optOutToggle")
    expect(dialog).to_be_visible()
    expect(page.locator("#optOutEmail")).to_be_focused()
    page.click("#optOutBtn")
    expect(page.locator("#optOutMessage")).to_contain_text("Enter the email")
    
    page.fill("#optOutEmail", SUBSCRIBED["email"])
    page.click("#optOutBtn")
    expect(page.locator("#optOutMessage")).to_contain_text("spam folder")
    expect(page.locator("#optOutForm")).to_be_hidden()
    # The form's button has gone, so focus stays in the dialog, on what's left to do
    expect(page.locator("#optOutClose")).to_be_focused()
    
    page.click("#optOutClose")
    expect(dialog).to_be_hidden()
    expect(page.locator("#optOutToggle")).to_be_focused()
    
    page.click("#optOutToggle")
    expect(page.locator("#optOutForm")).to_be_visible()
    expect(page.locator("#optOutMessage")).to_be_hidden()
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    
    page.click("#optOutToggle")
    page.mouse.click(2, 2)
    expect(dialog).to_be_hidden()


def test_an_email_link_unsubscribes_from_the_pop_up_and_clears_the_saved_subscription(page, site):
    open_page(page, site)
    page.evaluate(
        "localStorage.setItem('moodforecast:subscription', "
        "JSON.stringify({email: 'amina@example.com', location: 'Nairobi, KE'}))"
    )
    open_page(page, site, "?unsubscribe=good")
    expect(page.locator("#optOutDialog")).to_be_visible()
    expect(page.locator("#optOutForm")).to_be_hidden()
    
    page.click("#optOutConfirm")
    expect(page.locator("#optOutMessage")).to_contain_text("has been unsubscribed")
    expect(page.locator("#optOutConfirm")).to_be_hidden()
    expect(page.locator("#optOutClose")).to_be_focused()
    assert "unsubscribe" not in page.url
    assert page.evaluate("localStorage.getItem('moodforecast:subscription')") is None


@pytest.mark.parametrize("link", ["?unsubscribe=good", "?confirm=good"])
def test_an_email_links_token_leaves_the_address_at_once(page, site, link):
    open_page(page, site, f"{link}&q=Nairobi")
    assert "good" not in page.url
    assert "q=Nairobi" in page.url
    page.keyboard.press("Escape")
    assert "good" not in page.url


def test_a_used_email_link_says_so_and_the_pop_up_recovers(page, site):
    open_page(page, site, "?unsubscribe=used")
    page.click("#optOutConfirm")
    expect(page.locator("#optOutMessage")).to_contain_text("Already used.")
    expect(page.locator("#optOutConfirm")).to_be_enabled()
    
    page.click("#optOutClose")
    page.evaluate("document.getElementById('results').classList.remove('hidden')")
    page.click("#optOutToggle")
    expect(page.locator("#optOutForm")).to_be_visible()
    expect(page.locator("#optOutConfirm")).to_be_hidden()


def test_a_confirmation_link_asks_first_then_confirms(page, site):
    open_page(page, site, "?confirm=good")
    banner = page.locator("#emailLinkBanner")
    expect(banner).to_contain_text("Start your daily MoodForecast emails?")
    
    banner.get_by_role("button").click()
    expect(banner).to_contain_text("Confirmed.")
    expect(banner).to_contain_text("spam")
    expect(banner).to_be_focused()
    assert not re.search("confirm=", page.url)


def test_a_confirmation_that_did_not_get_through_can_be_tried_again(page, site):
    # The page fixture refuses every API call it doesn't answer, like a dropped connection
    open_page(page, site, "?confirm=flaky")
    banner = page.locator("#emailLinkBanner")
    banner.get_by_role("button").click()
    expect(banner).to_contain_text("Could not reach the server")
    expect(banner.get_by_role("button")).to_be_enabled()
    
    page.route("**/api/confirm/flaky", lambda route: route.fulfill(json={**SUBSCRIBED, "status": "subscribed"}))
    banner.get_by_role("button").click()
    expect(banner).to_contain_text("Confirmed.")


def test_a_used_confirmation_link_says_so_and_offers_no_retry(page, site):
    page.route("**/api/confirm/used", lambda route: route.fulfill(status=404, json={"detail": "Already used."}))
    open_page(page, site, "?confirm=used")
    banner = page.locator("#emailLinkBanner")
    banner.get_by_role("button").click()
    expect(banner).to_contain_text("Already used.")
    expect(banner.get_by_role("button")).to_have_count(0)
    expect(banner).to_be_focused()


@pytest.mark.parametrize("link, button", [
    ("?confirm=offline", "#emailLinkBanner button"),
    ("?unsubscribe=offline", "#optOutConfirm"),
])
def test_a_button_gets_keyboard_focus_back_after_its_request(page, site, link, button):
    # The page fixture refuses these requests, like a dropped connection
    open_page(page, site, link)
    page.focus(button)
    page.keyboard.press("Enter")
    expect(page.get_by_text("Could not reach the server").first).to_be_visible()
    expect(page.locator(button)).to_be_focused()


def test_the_form_points_to_a_field_left_empty(page, site):
    open_page(page, site)
    page.fill("#subLocationInput", "")
    page.click("#subscribeBtn")
    expect(page.locator("#emailInput")).to_be_focused()
    expect(page.locator("#emailInput")).to_have_attribute("aria-invalid", "true")
    
    page.fill("#emailInput", SUBSCRIBED["email"])
    page.click("#subscribeBtn")
    expect(page.locator("#subLocationInput")).to_be_focused()
    expect(page.locator("#emailInput")).to_have_attribute("aria-invalid", "false")


# A place's answers, for the tests that need results on screen
WEATHER = {"temp_c": 18, "feels_like_c": 17, "condition": "Partly Cloudy", "humidity": 60, "wind_kph": 10, "is_day": True}
FORECAST = {
    "location": "Nairobi, KE", "weather": WEATHER, "forecast_days": 1, "ai_summary": "",
    "daily": [{
        "date": "2026-11-16", "condition": "Clear", "temp_max_c": 24, "temp_min_c": 14,
        "precipitation_chance": 10, "uv_index": 9, "sunrise": "06:20", "sunset": "18:30",
        "mood_score": 80, "mood_label": "Upbeat",
    }],
}
WELLBEING = {
    "location": "Nairobi, KE", "weather": WEATHER, "mood_score": 80, "mood_label": "Upbeat", "baseline_score": 65,
    "factors": [{"label": "Comfortable temperature", "delta": 10}], "energy_level": "High", "risk_level": "Minimal",
    "ai_summary": "Mild in Nairobi.", "recommendations": ["Take a walk."], "curiosity": [],
}
CHOICES = [
    {"name": "running", "prompt": "Go for a run", "group": "Sport and exercise", "favourite": True,
     "family": "runs, walks and workouts", "suited": True},
    {"name": "cycling", "prompt": "Ride a bike", "group": "Sport and exercise", "favourite": False,
     "family": "rides and wheels", "suited": True},
    {"name": "skateboarding", "prompt": "Go skateboarding", "group": "Sport and exercise", "favourite": False,
     "family": "rides and wheels", "suited": False},
    {"name": "kayaking", "prompt": "Go kayaking", "group": "On the water", "favourite": False,
     "family": "time on the water", "suited": False},
    {"name": "reading", "prompt": "Read a book", "group": "Indoors", "favourite": False,
     "family": "quiet time in", "suited": True},
]
# Math.random from a seed, so a learned pick is made the same way every run
SEEDED_RANDOM = """
(() => {
    let seed = 12345;
    Math.random = () => {
        seed = (seed + 0x6D2B79F5) | 0;
        let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
})();
"""


def pick_of(name):
    return {
        "location": "Nairobi, KE", "weather": WEATHER, "activity": name, "recognised": True, "verdict": "go",
        "headline": f"How about {name} in Nairobi?", "reasons": ["Mild and dry."], "suggestion": None,
        "curiosity": {"question": "Compare with:", "places": ["Lisbon"]},
    }


def serve_place(page, picks):
    """Answer a search for Nairobi; random picks are recorded in `picks` and answered with the chosen or a first pick."""
    page.route("**/api/forecast/**", lambda route: route.fulfill(json=FORECAST))
    page.route("**/api/wellbeing/**", lambda route: route.fulfill(json=WELLBEING))
    page.route("**/api/activities/**", lambda route: route.fulfill(json=CHOICES))
    
    def random_pick(route):
        query = dict(part.split("=", 1) for part in route.request.url.split("?", 1)[1].split("&"))
        picks.append(query)
        route.fulfill(json=pick_of(query.get("choose") or "running"))
    page.route("**/api/random-activity/**", random_pick)
    page.route("**/api/activity/**", lambda route: route.fulfill(json={**pick_of("running"), "headline": "Go on, then."}))


def test_learned_picks_stay_within_what_the_rules_allow(page, site):
    page.route("**/api/**", lambda route: route.abort())
    page.goto(f"{site}/")
    allowed = page.evaluate("""(choices) => {
        // Love everything, the ruled-out ones most of all
        choices.forEach((c) => { for (let i = 0; i < 30; i++) Learner.vote({ ...c, ctx: 'mild-dry-day' }, c.suited ? 1 : 1); });
        for (let i = 0; i < 30; i++) Learner.vote({ name: 'kayaking', family: 'time on the water', ctx: 'mild-dry-day' }, 1);
        const picked = new Set();
        for (let i = 0; i < 2000; i++) picked.add(Learner.choose(choices, 'mild-dry-day', 'running'));
        return [...picked];
    }""", CHOICES)
    assert set(allowed) <= {"cycling", "reading", None}
    assert {"cycling", "reading"} <= set(allowed)


def test_learning_does_not_trap_the_visitor_in_one_activity(page, site):
    page.route("**/api/**", lambda route: route.abort())
    page.goto(f"{site}/")
    counts = page.evaluate("""(choices) => {
        for (let i = 0; i < 50; i++) Learner.vote({ name: 'cycling', family: 'rides and wheels', ctx: 'mild-dry-day' }, 1);
        // As the page does it: each "Surprise me" leaves out the pick on screen
        const counts = {};
        let shown = '';
        for (let i = 0; i < 3000; i++) {
            const chosen = Learner.choose(choices, 'mild-dry-day', shown);
            // The server's own random pick, when learning leaves it to chance
            shown = chosen || ['running', 'cycling', 'reading'].filter((n) => n !== shown)[i % 2];
            counts[chosen || 'random'] = (counts[chosen || 'random'] || 0) + 1;
        }
        return counts;
    }""", CHOICES)
    # Liked most, but never every time, and the others and the server's own random pick still come up
    assert counts["cycling"] > counts["running"]
    assert counts["cycling"] < 1600
    assert counts["running"] > 300 and counts["reading"] > 100 and counts["random"] > 250


def test_a_vote_is_kept_shown_and_can_be_forgotten(page, site):
    picks = []
    serve_place(page, picks)
    page.goto(f"{site}/")
    feedback = page.locator("#pickFeedback")
    expect(feedback).to_be_visible()
    expect(page.locator("#pickMemory")).to_be_hidden()
    
    page.click("#likeButton")
    expect(page.locator("#likeButton")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#pickThanks")).to_contain_text("more like this")
    expect(page.locator("#pickMemory")).to_be_visible()
    assert "running" in page.evaluate("localStorage.getItem('moodforecast:tastes')")
    
    # Changing one's mind replaces the vote rather than adding to it
    page.click("#dislikeButton")
    expect(page.locator("#likeButton")).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#dislikeButton")).to_have_attribute("aria-pressed", "true")
    likes, dislikes = page.evaluate("(() => { const e = Learner.evidence('running', '', 'mild-dry-day'); return [e.likes, e.dislikes]; })()")
    assert likes < 0.01 and 0.99 < dislikes < 1.01
    
    page.click("#forgetButton")
    expect(page.locator("#pickThanks")).to_contain_text("Forgotten")
    expect(page.locator("#pickMemory")).to_be_hidden()
    expect(page.locator("#likeButton")).to_be_focused()
    assert page.evaluate("localStorage.getItem('moodforecast:tastes')") is None
    
    # A question that was asked, not picked, has nothing to vote on
    page.fill("#activityInput", "Can I go for a run?")
    page.click("#activityButton")
    expect(page.locator("#activityHeadline")).to_have_text("Go on, then.")
    expect(feedback).to_be_hidden()


def test_a_learned_pick_is_asked_for_and_says_why(page, site):
    page.add_init_script(SEEDED_RANDOM)
    page.add_init_script("""localStorage.setItem('moodforecast:tastes', JSON.stringify({
        v: 1, a: {cycling: {'mild-dry-day': [5, 0, Date.now()]}}, f: {'rides and wheels': {'mild-dry-day': [5, 0, Date.now()]}}
    }))""")
    picks = []
    serve_place(page, picks)
    page.goto(f"{site}/")
    expect(page.locator("#activityHeadline")).to_contain_text("How about")
    for _ in range(6):
        if picks[-1].get("choose") == "cycling":
            break
        page.click("#surpriseButton")
        expect(page.locator("#activityResult")).not_to_have_class(re.compile("is-refreshing"))
    assert picks[-1].get("choose") == "cycling"
    expect(page.locator("#pickWhy")).to_have_text("✦ You've liked cycling on mild, dry days.")
    # The quick picks put what's liked first
    expect(page.locator("#activityChips .chip").first).to_have_text("Ride a bike")


def test_the_page_works_with_storage_blocked(page, site):
    page.add_init_script("""Object.defineProperty(window, 'localStorage', {
        get() { throw new DOMException('Blocked', 'SecurityError'); }
    })""")
    picks = []
    serve_place(page, picks)
    page.goto(f"{site}/")
    expect(page.locator("#pickFeedback")).to_be_visible()
    page.click("#likeButton")
    expect(page.locator("#pickThanks")).to_contain_text("more like this")
    # Learned for this visit only
    expect(page.locator("#pickMemory")).to_be_visible()
    page.click("#forgetButton")
    expect(page.locator("#pickMemory")).to_be_hidden()


def test_my_location_is_asked_for_only_on_tap_and_sent_rounded(page, site):
    page.add_init_script("""
        window.locationAsks = 0;
        const real = navigator.geolocation.getCurrentPosition.bind(navigator.geolocation);
        navigator.geolocation.getCurrentPosition = (...args) => { window.locationAsks++; return real(...args); };
    """)
    page.context.grant_permissions(["geolocation"], origin=site)
    page.context.set_geolocation({"latitude": -0.712345, "longitude": 36.431987})
    sent = []
    
    def place(route):
        sent.append(route.request.post_data_json)
        route.fulfill(json={"name": "Naivasha", "region": "Nakuru County", "country": "Kenya",
                            "label": "Naivasha, Nakuru County, Kenya", "lat": -0.7167, "lon": 36.4333})
    serve_place(page, [])
    page.route("**/api/place", place)
    page.goto(f"{site}/")
    expect(page.locator("#locationName")).to_have_text("Nairobi, KE")
    assert page.evaluate("window.locationAsks") == 0
    
    searched = []
    page.on("request", lambda request: searched.append(request.url) if "/api/forecast/" in request.url else None)
    page.click("#locateButton")
    expect(page.locator("#locationInput")).to_have_value("Naivasha, Nakuru County, Kenya")
    page.wait_for_url(re.compile("q=Naivasha"))
    assert sent == [{"lat": -0.71, "lon": 36.43}]
    assert any("Naivasha" in url for url in searched)
    # The coordinates are in no address the page used
    assert all("36.43" not in url for url in searched + [page.url])


@pytest.mark.parametrize("failure, message", [
    ("navigator.geolocation.getCurrentPosition = (ok, fail) => fail({ code: 1 });", "Location access is off"),
    ("navigator.geolocation.getCurrentPosition = (ok, fail) => fail({ code: 3 });", "took too long"),
    ("Object.defineProperty(Navigator.prototype, 'geolocation', { get: () => undefined });", "can't share your location"),
])
def test_my_location_failing_says_what_to_do_instead(page, site, failure, message):
    page.add_init_script(failure)
    page.route("**/api/place", lambda route: pytest.fail("No point should be sent"))
    open_page(page, site)
    page.click("#locateButton")
    expect(page.locator("#errorState")).to_contain_text(message)
    expect(page.locator("#errorState")).to_contain_text(re.compile("search", re.I))
    expect(page.locator("#locateButton")).not_to_have_attribute("aria-busy", "true")


def test_no_place_at_my_location_says_so(page, site):
    page.add_init_script("navigator.geolocation.getCurrentPosition = (ok) => ok({ coords: { latitude: 0, longitude: -30 } });")
    page.route("**/api/place", lambda route: route.fulfill(status=422, json={"detail": "There's no named place there."}))
    open_page(page, site)
    page.click("#locateButton")
    expect(page.locator("#errorState")).to_have_text("There's no named place there.")

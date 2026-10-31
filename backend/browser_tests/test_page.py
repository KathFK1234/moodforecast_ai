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
    assert not re.search("confirm=", page.url)

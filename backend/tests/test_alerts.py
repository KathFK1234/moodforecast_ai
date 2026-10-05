"""Unit tests for alert emails and the daily send - SMTP and weather are faked."""

import random
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from app.config import settings
from app.models.db import Subscriber
from app.services import alerts, mailer


FORECAST = {
    "current": {
        "temperature": 22.4, "feels_like": 22.0, "humidity": 55, "wind_speed": 9,
        "is_day": True, "condition_code": 0, "condition": "Clear",
    },
    "daily": [{
        "date": "2026-10-05", "condition": "Light Rain Showers", "temp_max": 26.2, "temp_min": 15.8,
        "humidity": 60, "precipitation_chance": 40, "uv_index": 9.8,
        "sunrise": "06:17", "sunset": "18:24",
    }],
    "utc_offset_seconds": 10800,
}

# 05:00 UTC is 08:00 in Nairobi (UTC+3), an hour past the 07:00 alert
MORNING = datetime(2026, 10, 5, 5, 0, tzinfo=timezone.utc)
# 03:00 UTC is 06:00 in Nairobi, an hour before it
BEFORE_DAWN = datetime(2026, 10, 5, 3, 0, tzinfo=timezone.utc)


def make_subscriber(**overrides) -> Subscriber:
    fields = dict(
        id="sub-1", email="amina@example.com", token="tok-1",
        location="nairobi", place="Nairobi, KE", lat=-1.2921, lon=36.8219,
        utc_offset_seconds=10800,
    )
    fields.update(overrides)
    return Subscriber(**fields)


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def weather():
    """Fake weather client answering every forecast request with FORECAST."""
    client = AsyncMock()
    client.get_forecast = AsyncMock(return_value=FORECAST)
    with patch("app.services.alerts.get_weather_client", return_value=client):
        yield client


def add(engine, *subscribers):
    with Session(engine) as session:
        for subscriber in subscribers:
            session.add(subscriber)
        session.commit()


def stored(engine, subscriber_id="sub-1") -> Subscriber:
    with Session(engine) as session:
        return session.exec(select(Subscriber).where(Subscriber.id == subscriber_id)).one()


class TestDailyEmail:
    """Test what the daily alert says."""
    
    @pytest.fixture(autouse=True)
    def site(self, monkeypatch):
        monkeypatch.setattr(settings, "public_url", "https://moodforecast.test/")
    
    def test_covers_weather_mood_and_outlook(self):
        email = alerts.daily_email(make_subscriber(), FORECAST, rng=random.Random(1))
        assert email.subject == "Nairobi, KE: Radiant today, 22°C and clear"
        assert "Clear and 22°C in Nairobi, KE." in email.text
        assert "Mood score: 90 out of 100 (Radiant), with high energy." in email.text
        assert "Today: light rain showers, 16 to 26°C, 40% chance of rain." in email.text
    
    def test_chosen_activity_is_judged_against_the_weather(self):
        email = alerts.daily_email(make_subscriber(activity="snow sports"), FORECAST)
        assert "snow sports" in email.text
        assert "There's no snow falling and it's 22°C." in email.text
    
    def test_without_a_chosen_activity_one_is_picked(self):
        picks = {
            alerts.daily_email(make_subscriber(), FORECAST, rng=random.Random(seed)).text
            for seed in range(20)
        }
        assert len(picks) > 5
    
    def test_links_back_to_the_site_and_to_unsubscribe(self):
        email = alerts.daily_email(make_subscriber(location="Kisumu, Kenya"), FORECAST)
        assert "https://moodforecast.test/?q=Kisumu%2C%20Kenya" in email.text
        assert "Unsubscribe: https://moodforecast.test/?unsubscribe=tok-1" in email.text
        assert 'href="https://moodforecast.test/?unsubscribe=tok-1"' in email.html
        assert "Look up " in email.text
    
    def test_html_escapes_place_names(self):
        email = alerts.daily_email(make_subscriber(place="<b>Nairobi</b>, KE"), FORECAST)
        assert "<b>Nairobi</b>" not in email.html
        assert "&lt;b&gt;Nairobi&lt;/b&gt;" in email.html


class TestIsDue:
    """Test when a subscriber's daily alert should go out."""
    
    def test_due_once_the_alert_hour_has_passed_locally(self):
        assert alerts.is_due(make_subscriber(), MORNING) is True
        assert alerts.is_due(make_subscriber(), BEFORE_DAWN) is False
    
    def test_local_time_decides_not_utc(self):
        """05:00 UTC is 08:00 in Nairobi but only 01:00 in New York."""
        assert alerts.is_due(make_subscriber(utc_offset_seconds=-14400), MORNING) is False
    
    def test_not_due_twice_on_the_same_local_day(self):
        assert alerts.is_due(make_subscriber(last_sent_on="2026-10-05"), MORNING) is False
        assert alerts.is_due(make_subscriber(last_sent_on="2026-10-04"), MORNING) is True
    
    def test_unsubscribed_is_never_due(self):
        assert alerts.is_due(make_subscriber(active=False), MORNING) is False
    
    def test_alert_hour_is_configurable(self, monkeypatch):
        monkeypatch.setattr(settings, "alert_hour", 9)
        assert alerts.is_due(make_subscriber(), MORNING) is False


class TestSendDueAlerts:
    """Test the daily send."""
    
    @pytest.mark.asyncio
    async def test_sends_to_due_subscribers_and_marks_them(self, engine, weather, outbox):
        add(
            engine,
            make_subscriber(),
            make_subscriber(id="sub-2", email="ben@example.com", token="tok-2", utc_offset_seconds=-14400),
            make_subscriber(id="sub-3", email="chao@example.com", token="tok-3", active=False),
        )
        with patch("app.services.alerts.get_engine", return_value=engine):
            assert await alerts.send_due_alerts(MORNING) == 1
        
        assert [message["To"] for _, message in outbox] == ["amina@example.com"]
        assert outbox[0][1]["List-Unsubscribe"] == "<https://moodforecast.test/api/unsubscribe/tok-1>"
        assert stored(engine).last_sent_on == "2026-10-05"
        assert stored(engine, "sub-2").last_sent_on is None
    
    @pytest.mark.asyncio
    async def test_a_second_run_the_same_day_sends_nothing(self, engine, weather, outbox):
        add(engine, make_subscriber())
        with patch("app.services.alerts.get_engine", return_value=engine):
            assert await alerts.send_due_alerts(MORNING) == 1
            assert await alerts.send_due_alerts(MORNING) == 0
        assert len(outbox) == 1
    
    @pytest.mark.asyncio
    async def test_a_failed_send_is_retried_on_the_next_run(self, engine, weather, outbox, monkeypatch):
        add(engine, make_subscriber())
        working_smtp = mailer.smtplib.SMTP
        
        def unreachable(host, port, **kwargs):
            raise ConnectionRefusedError("nothing listening")
        
        with patch("app.services.alerts.get_engine", return_value=engine):
            monkeypatch.setattr(mailer.smtplib, "SMTP", unreachable)
            assert await alerts.send_due_alerts(MORNING) == 0
            assert stored(engine).last_sent_on is None
            
            monkeypatch.setattr(mailer.smtplib, "SMTP", working_smtp)
            assert await alerts.send_due_alerts(MORNING) == 1
        assert stored(engine).last_sent_on == "2026-10-05"
    
    @pytest.mark.asyncio
    async def test_one_bad_forecast_does_not_stop_the_others(self, engine, weather, outbox):
        add(
            engine,
            make_subscriber(),
            make_subscriber(id="sub-2", email="ben@example.com", token="tok-2"),
        )
        weather.get_forecast.side_effect = [RuntimeError("Weather API down"), FORECAST]
        with patch("app.services.alerts.get_engine", return_value=engine):
            assert await alerts.send_due_alerts(MORNING) == 1
        assert len(outbox) == 1
    
    @pytest.mark.asyncio
    async def test_force_ignores_the_schedule(self, engine, weather, outbox):
        add(engine, make_subscriber(last_sent_on="2026-10-05"))
        with patch("app.services.alerts.get_engine", return_value=engine):
            assert await alerts.send_due_alerts(BEFORE_DAWN, force=True) == 1
    
    @pytest.mark.asyncio
    async def test_nothing_is_sent_or_marked_without_email_configured(self, engine, weather):
        add(engine, make_subscriber())
        with patch("app.services.alerts.get_engine", return_value=engine):
            assert await alerts.send_due_alerts(MORNING) == 0
        assert stored(engine).last_sent_on is None
    
    @pytest.mark.asyncio
    async def test_follows_a_change_in_utc_offset(self, engine, weather, outbox):
        add(engine, make_subscriber(utc_offset_seconds=7200))
        with patch("app.services.alerts.get_engine", return_value=engine):
            await alerts.send_due_alerts(MORNING)
        assert stored(engine).utc_offset_seconds == 10800

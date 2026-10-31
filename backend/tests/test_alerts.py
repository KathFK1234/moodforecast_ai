"""Unit tests for alert emails and the daily send - SMTP and weather are faked."""

import asyncio
import random
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import time
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from app.config import settings
from app.models.db import PendingSubscription, Subscriber
from app.services import alerts, mailer
from app.services.rate_limit import RateLimiter


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
        utc_offset_seconds=10800, confirmed=True,
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
    client.get_sea = AsyncMock(return_value={"coastal": False, "sea_temp_c": None})
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
        email = alerts.daily_email(make_subscriber(activity="stargazing"), FORECAST)
        assert "stargazing" in email.text
        assert "It's still daytime — but skies are clear, so tonight could be a good one." in email.text
    
    def test_random_pick_fits_the_place(self):
        """Nairobi is inland and far from snow, whatever the forecast says."""
        inland = {"coastal": False, "sea_temp_c": None}
        for seed in range(60):
            text = alerts.daily_email(make_subscriber(), FORECAST, rng=random.Random(seed), sea=inland).text
            for absent in ["a beach day", "surfing", "snorkelling", "sailing", "snow sports", "cricket"]:
                assert absent not in text
    
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


class TestSendOnce:
    """Test the one-email-per-address guard on the site's forms."""
    
    @pytest.mark.asyncio
    async def test_requests_at_the_same_moment_send_one_email(self, outbox):
        email = alerts.Email("Subject", "Text", "<p>Html</p>")
        
        results = await asyncio.gather(*[alerts.send_once("a@example.com", email, "confirm") for _ in range(3)])
        
        assert results == [True, True, True]
        assert len(outbox) == 1
    
    @pytest.mark.asyncio
    async def test_a_failed_send_can_be_tried_again_straight_away(self, outbox):
        email = alerts.Email("Subject", "Text", "<p>Html</p>")
        
        with patch("app.services.alerts.send_to", AsyncMock(return_value=False)):
            assert await alerts.send_once("a@example.com", email, "confirm") is False
        
        assert await alerts.send_once("a@example.com", email, "confirm") is True
        assert len(outbox) == 1


class TestDeleteUnusedData:
    """Test that details nobody will use again are deleted."""
    
    def test_deletes_only_what_will_not_be_used(self, engine):
        old = MORNING - timedelta(hours=alerts.CONFIRM_HOURS + 1)
        recent = MORNING - timedelta(hours=1)
        add(
            engine,
            make_subscriber(id="keep-confirmed", email="a@example.com", token="a"),
            make_subscriber(id="keep-not-asked", email="b@example.com", token="b", confirmed=False),
            make_subscriber(
                id="keep-still-time", email="c@example.com", token="c", confirmed=False, confirm_requested_at=recent
            ),
            make_subscriber(id="unsubscribed", email="d@example.com", token="d", active=False),
            make_subscriber(
                id="never-confirmed", email="e@example.com", token="e", confirmed=False, confirm_requested_at=old
            ),
        )
        shared = {"location": "Nairobi", "place": "Nairobi, KE", "lat": -1.3, "lon": 36.8}
        with Session(engine) as session:
            session.add(PendingSubscription(token="old", email="f@example.com", created_at=old, **shared))
            session.add(PendingSubscription(token="new", email="g@example.com", created_at=recent, **shared))
            session.commit()
        
        with patch("app.services.alerts.get_engine", return_value=engine):
            assert alerts.delete_unused_data(MORNING) == 3
        
        with Session(engine) as session:
            kept = {subscriber.id for subscriber in session.exec(select(Subscriber))}
            requests = [request.token for request in session.exec(select(PendingSubscription))]
        assert kept == {"keep-confirmed", "keep-not-asked", "keep-still-time"}
        assert requests == ["new"]


class TestFormEmailLimit:
    """Test the daily limit on emails sent from the site's forms."""
    
    @pytest.mark.asyncio
    async def test_nothing_more_is_sent_once_the_limit_is_reached(self, outbox, monkeypatch):
        monkeypatch.setattr(alerts, "MAX_FORM_EMAILS_PER_DAY", 2)
        email = alerts.Email("Subject", "Text", "<p>Html</p>")
        
        results = [await alerts.send_once(f"p{n}@example.com", email, "confirm") for n in range(3)]
        
        assert results == [True, True, False]
        assert len(outbox) == 2
    
    @pytest.mark.asyncio
    async def test_a_day_old_send_no_longer_counts(self, outbox, monkeypatch):
        monkeypatch.setattr(alerts, "MAX_FORM_EMAILS_PER_DAY", 1)
        alerts._form_emails_sent.append(time.time() - 86401)
        
        assert await alerts.send_once("a@example.com", alerts.Email("S", "T", "H"), "confirm") is True


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
    async def test_unsubscribing_during_the_run_only_affects_that_subscriber(self, engine, weather, outbox):
        add(
            engine,
            make_subscriber(),
            make_subscriber(id="sub-2", email="ben@example.com", token="tok-2"),
            make_subscriber(id="sub-3", email="chao@example.com", token="tok-3"),
        )
        real_send = alerts.send
        
        async def unsubscribe_someone(subscriber, email):
            sent = await real_send(subscriber, email)
            if subscriber.id == "sub-1":
                with Session(engine) as other:
                    other.delete(other.get(Subscriber, "sub-1"))
                    other.delete(other.get(Subscriber, "sub-2"))
                    other.commit()
            return sent
        
        with patch("app.services.alerts.get_engine", return_value=engine), \
                patch("app.services.alerts.send", unsubscribe_someone):
            await alerts.send_due_alerts(MORNING)
        
        assert [message["To"] for _, message in outbox] == ["amina@example.com", "chao@example.com"]
        assert stored(engine, "sub-3").last_sent_on == "2026-10-05"
    
    @pytest.mark.asyncio
    async def test_a_second_run_the_same_day_sends_nothing(self, engine, weather, outbox):
        add(engine, make_subscriber())
        with patch("app.services.alerts.get_engine", return_value=engine):
            assert await alerts.send_due_alerts(MORNING) == 1
            assert await alerts.send_due_alerts(MORNING) == 0
        assert len(outbox) == 1
    
    @pytest.mark.asyncio
    async def test_an_alert_that_cant_be_written_only_costs_that_subscriber(self, engine, weather, outbox):
        add(
            engine,
            make_subscriber(),
            make_subscriber(id="sub-2", email="ben@example.com", token="tok-2"),
        )
        real_daily_email = alerts.daily_email
        
        def fail_for_the_first(subscriber, forecast, sea=None):
            if subscriber.id == "sub-1":
                raise KeyError("condition")
            return real_daily_email(subscriber, forecast, sea=sea)
        
        with patch("app.services.alerts.get_engine", return_value=engine), \
                patch("app.services.alerts.daily_email", fail_for_the_first):
            assert await alerts.send_due_alerts(MORNING) == 1
        
        assert [message["To"] for _, message in outbox] == ["ben@example.com"]
        assert stored(engine).last_sent_on is None
    
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


class TestEarlierSubscribers:
    """Subscribers from before confirmation get no alerts until they confirm, and are asked once."""
    
    def test_an_unconfirmed_subscriber_is_never_due(self):
        assert not alerts.is_due(make_subscriber(confirmed=False), MORNING)
    
    @pytest.mark.asyncio
    async def test_no_alerts_go_to_them_even_when_forced(self, engine, weather, outbox):
        add(engine, make_subscriber(confirmed=False))
        with patch("app.services.alerts.get_engine", return_value=engine):
            assert await alerts.send_due_alerts(MORNING, force=True) == 0
        assert outbox == []
    
    @pytest.mark.asyncio
    async def test_each_is_asked_to_confirm_once(self, engine, outbox):
        add(
            engine,
            make_subscriber(confirmed=False, activity="running"),
            make_subscriber(id="sub-2", email="ben@example.com", token="tok-2"),  # Already confirmed
            make_subscriber(id="sub-3", email="cy@example.com", token="tok-3", confirmed=False, active=False),
        )
        with patch("app.services.alerts.get_engine", return_value=engine):
            assert await alerts.request_confirmations(MORNING) == 1
            assert await alerts.request_confirmations(MORNING) == 0
        
        assert [message["To"] for _, message in outbox] == ["amina@example.com"]
        message = outbox[0][1]
        assert message["Subject"] == "Please confirm your MoodForecast alerts for Nairobi, KE"
        text = message.get_body(("plain",)).get_content()
        assert "paused until you do" in text
        assert "how the weather suits running" in text
        assert message["List-Unsubscribe"] is None
        with Session(engine) as session:
            pending = session.exec(select(PendingSubscription)).one()
        assert f"https://moodforecast.test/?confirm={pending.token}" in text
        assert (pending.email, pending.activity, pending.location) == ("amina@example.com", "running", "nairobi")
        assert stored(engine).confirm_requested_at is not None
    
    @pytest.mark.asyncio
    async def test_a_failed_request_is_retried_on_the_next_run(self, engine, outbox, monkeypatch):
        add(engine, make_subscriber(confirmed=False))
        real_smtp = mailer.smtplib.SMTP
        
        def unreachable(host, port, **kwargs):
            raise ConnectionRefusedError("nothing listening")
        
        monkeypatch.setattr(mailer.smtplib, "SMTP", unreachable)
        with patch("app.services.alerts.get_engine", return_value=engine):
            assert await alerts.request_confirmations(MORNING) == 0
            with Session(engine) as session:
                assert session.exec(select(PendingSubscription)).all() == []
            assert stored(engine).confirm_requested_at is None
            
            monkeypatch.setattr(mailer.smtplib, "SMTP", real_smtp)
            assert await alerts.request_confirmations(MORNING) == 1
    
    @pytest.mark.asyncio
    async def test_nothing_is_asked_without_email_configured(self, engine):
        add(engine, make_subscriber(confirmed=False))
        with patch("app.services.alerts.get_engine", return_value=engine):
            assert await alerts.request_confirmations(MORNING) == 0
        assert stored(engine).confirm_requested_at is None


class TestRateLimiter:
    """Test the limiter on its own."""
    
    def test_a_use_counts_only_for_its_window(self):
        limiter = RateLimiter(1, 60)
        with patch("app.services.rate_limit.time.monotonic", side_effect=[0, 1, 61]):
            assert limiter.allow("a") is True
            assert limiter.allow("a") is False
            assert limiter.allow("a") is True
    
    def test_the_quietest_visitors_are_forgotten_first(self, monkeypatch):
        monkeypatch.setattr("app.services.rate_limit.MAX_VISITORS", 2)
        limiter = RateLimiter(1, 60)
        for visitor in "abc":
            limiter.allow(visitor)
        assert list(limiter._uses) == ["b", "c"]


class TestAlertLoop:
    """Test the background loop."""
    
    @pytest.mark.asyncio
    async def test_it_waits_first_then_sends_and_tidies_up(self):
        pauses = []
        
        async def pause(seconds):
            pauses.append(seconds)
            if len(pauses) == 2:
                raise asyncio.CancelledError
        
        with patch("app.services.alerts.asyncio.sleep", pause), \
                patch("app.services.alerts.request_confirmations", AsyncMock(return_value=0)) as asked, \
                patch("app.services.alerts.send_due_alerts", AsyncMock(return_value=0)) as sent, \
                patch("app.services.alerts.delete_unused_data", return_value=0) as deleted:
            with pytest.raises(asyncio.CancelledError):
                await alerts.run_alert_loop()
        
        assert pauses == [alerts.STARTUP_DELAY_SECONDS, alerts.CHECK_INTERVAL_SECONDS]
        asked.assert_awaited_once()
        sent.assert_awaited_once()
        deleted.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_a_failed_tidy_up_does_not_stop_the_loop(self):
        pauses = []
        
        async def pause(seconds):
            pauses.append(seconds)
            if len(pauses) == 2:
                raise asyncio.CancelledError
        
        with patch("app.services.alerts.asyncio.sleep", pause), \
                patch("app.services.alerts.request_confirmations", AsyncMock(return_value=0)), \
                patch("app.services.alerts.send_due_alerts", AsyncMock(return_value=0)), \
                patch("app.services.alerts.delete_unused_data", side_effect=RuntimeError("database")):
            with pytest.raises(asyncio.CancelledError):
                await alerts.run_alert_loop()
        
        assert len(pauses) == 2


def test_one_address_gets_only_so_many_form_emails_in_a_day(outbox):
    email = alerts.Email("Subject", "Text", "<p>Text</p>")
    results = []
    for _ in range(alerts.MAX_FORM_EMAILS_PER_ADDRESS + 2):
        results.append(asyncio.run(alerts.send_once("target@example.com", email, "confirm")))
        alerts._recently_sent.clear()  # As if the 10-minute guard had lifted
    
    assert results == [True] * alerts.MAX_FORM_EMAILS_PER_ADDRESS + [False] * 2
    assert asyncio.run(alerts.send_once("other@example.com", email, "confirm")) is True

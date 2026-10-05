"""Shared test fixtures."""

import pytest
from app.config import settings
from app.services import mailer


class FakeSMTP:
    """Stands in for smtplib.SMTP and records what would have been sent."""
    
    def __init__(self, outbox, host, port, **kwargs):
        self.outbox = outbox
        self.host = host
        self.port = port
        self.started_tls = False
        self.logged_in_as = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        return False
    
    def starttls(self, **kwargs):
        self.started_tls = True
    
    def login(self, username, password):
        self.logged_in_as = username
    
    def send_message(self, message):
        self.outbox.append((self, message))


@pytest.fixture(autouse=True)
def no_real_email(monkeypatch):
    """Tests never send real email, whatever the developer's .env says."""
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "mail_from", "")


@pytest.fixture
def outbox(monkeypatch):
    """Configure email and collect sent messages as (connection, message) pairs."""
    sent = []
    monkeypatch.setattr(settings, "smtp_host", "smtp.test")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_username", "mailer")
    monkeypatch.setattr(settings, "smtp_password", "secret")
    monkeypatch.setattr(settings, "smtp_starttls", True)
    monkeypatch.setattr(settings, "mail_from", "MoodForecast <alerts@moodforecast.test>")
    monkeypatch.setattr(settings, "public_url", "https://moodforecast.test")
    monkeypatch.setattr(
        mailer.smtplib, "SMTP", lambda host, port, **kwargs: FakeSMTP(sent, host, port, **kwargs)
    )
    monkeypatch.setattr(
        mailer.smtplib, "SMTP_SSL", lambda host, port, **kwargs: FakeSMTP(sent, host, port, **kwargs)
    )
    return sent

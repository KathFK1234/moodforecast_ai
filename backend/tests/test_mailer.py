"""Unit tests for the mailer - SMTP is faked."""

import smtplib

import pytest
from app.config import settings
from app.services import mailer


def test_not_configured_by_default():
    assert mailer.is_configured() is False
    with pytest.raises(mailer.MailError, match="not configured"):
        mailer.send_email("amina@example.com", "Hello", "Hi")


def test_sends_text_and_html_with_headers(outbox):
    mailer.send_email(
        "amina@example.com", "Hello", "Plain words", "<p>Rich words</p>",
        {"List-Unsubscribe": "<https://moodforecast.test/api/unsubscribe/abc>"}
    )
    assert len(outbox) == 1
    connection, message = outbox[0]
    assert (connection.host, connection.port) == ("smtp.test", 587)
    assert connection.started_tls is True
    assert connection.logged_in_as == "mailer"
    assert message["To"] == "amina@example.com"
    assert message["From"] == "MoodForecast <alerts@moodforecast.test>"
    assert message["Subject"] == "Hello"
    assert message["List-Unsubscribe"] == "<https://moodforecast.test/api/unsubscribe/abc>"
    assert message.get_body(("plain",)).get_content().strip() == "Plain words"
    assert message.get_body(("html",)).get_content().strip() == "<p>Rich words</p>"


def test_port_465_connects_over_tls_without_starttls(outbox, monkeypatch):
    monkeypatch.setattr(settings, "smtp_port", 465)
    mailer.send_email("amina@example.com", "Hello", "Hi")
    assert outbox[0][0].port == 465
    assert outbox[0][0].started_tls is False


def test_no_login_without_a_username(outbox, monkeypatch):
    monkeypatch.setattr(settings, "smtp_username", "")
    monkeypatch.setattr(settings, "smtp_starttls", False)
    mailer.send_email("amina@example.com", "Hello", "Hi")
    assert outbox[0][0].logged_in_as is None
    assert outbox[0][0].started_tls is False


def test_smtp_failure_becomes_a_mail_error(outbox, monkeypatch):
    def refuse(host, port, **kwargs):
        raise smtplib.SMTPConnectError(421, "busy")
    
    monkeypatch.setattr(mailer.smtplib, "SMTP", refuse)
    with pytest.raises(mailer.MailError, match="amina@example.com"):
        mailer.send_email("amina@example.com", "Hello", "Hi")


def test_connection_failure_becomes_a_mail_error(outbox, monkeypatch):
    def unreachable(host, port, **kwargs):
        raise ConnectionRefusedError("nothing listening")
    
    monkeypatch.setattr(mailer.smtplib, "SMTP", unreachable)
    with pytest.raises(mailer.MailError):
        mailer.send_email("amina@example.com", "Hello", "Hi")

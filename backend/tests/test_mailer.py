"""Unit tests for the mailer - SMTP and Brevo's API are faked."""

import asyncio
import json
import smtplib

import httpx
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



def send(*args):
    asyncio.run(mailer.send_email_async(*args))


def test_brevo_counts_as_configured_without_smtp(monkeypatch):
    monkeypatch.setattr(settings, "brevo_api_key", "xkeysib-test")
    assert mailer.is_configured() is False  # Still needs a sender
    monkeypatch.setattr(settings, "mail_from", "alerts@moodforecast.test")
    assert mailer.is_configured() is True
    assert mailer.uses_brevo() is True


def test_sends_through_brevo(brevo):
    sent, _ = brevo
    send(
        "amina@example.com", "Hello", "Plain words", "<p>Rich words</p>",
        {"List-Unsubscribe": "<https://moodforecast.test/api/unsubscribe/abc>"}
    )
    assert len(sent) == 1
    request = sent[0]
    assert (request.method, str(request.url)) == ("POST", "https://api.brevo.com/v3/smtp/email")
    assert request.headers["api-key"] == "xkeysib-test"
    assert json.loads(request.content) == {
        "sender": {"email": "alerts@moodforecast.test", "name": "MoodForecast"},
        "to": [{"email": "amina@example.com"}],
        "subject": "Hello",
        "textContent": "Plain words",
        "htmlContent": "<p>Rich words</p>",
        "headers": {"List-Unsubscribe": "<https://moodforecast.test/api/unsubscribe/abc>"},
    }


def test_brevo_is_preferred_over_smtp(brevo, outbox, monkeypatch):
    sent, _ = brevo
    monkeypatch.setattr(settings, "brevo_api_key", "xkeysib-test")
    send("amina@example.com", "Hello", "Hi")
    assert len(sent) == 1
    assert outbox == []


def test_plain_text_only_gets_a_simple_html_part(brevo):
    sent, _ = brevo
    send("amina@example.com", "Hello", "Line one\n<two>")
    assert json.loads(sent[0].content)["htmlContent"] == "<pre>Line one\n&lt;two&gt;</pre>"


def test_refused_headers_are_dropped_and_the_email_still_goes(brevo):
    sent, state = brevo
    state["respond"] = lambda request: (
        httpx.Response(400, json={"code": "invalid_parameter", "message": "headers not allowed"})
        if "headers" in json.loads(request.content)
        else httpx.Response(201, json={"messageId": "<1@relay>"})
    )
    send("amina@example.com", "Hello", "Hi", "<p>Hi</p>", {"List-Unsubscribe": "<https://x.test/u>"})
    assert len(sent) == 2
    assert "headers" not in json.loads(sent[1].content)


def test_a_refusal_for_another_reason_says_so_after_the_retry(brevo, caplog):
    """A 400 can be about anything (an unverified sender, say), so the reason is passed on, not guessed."""
    sent, state = brevo
    state["respond"] = lambda request: httpx.Response(
        400, json={"code": "invalid_parameter", "message": "sender is not valid"}
    )
    with pytest.raises(mailer.MailError, match="400 invalid_parameter: sender is not valid"):
        send("amina@example.com", "Hello", "Hi", "<p>Hi</p>", {"List-Unsubscribe": "<https://x.test/u>"})
    assert len(sent) == 2
    assert "Brevo refused the email (invalid_parameter: sender is not valid)" in caplog.text


def test_brevo_refusal_becomes_a_mail_error_without_the_key(brevo):
    sent, state = brevo
    state["respond"] = lambda request: httpx.Response(
        401, json={"code": "unauthorized", "message": "Key not found"}
    )
    with pytest.raises(mailer.MailError) as raised:
        send("amina@example.com", "Hello", "Hi")
    assert "amina@example.com" in str(raised.value)
    assert "401 unauthorized: Key not found" in str(raised.value)
    assert "xkeysib-test" not in str(raised.value)
    assert len(sent) == 1  # Only a 400 about the headers is worth a second try


@pytest.mark.parametrize("mail_from", ['"MoodForecast <a@example.com>"', "MoodForecast [a@example.com]", "MoodForecast"])
def test_a_malformed_mail_from_is_named_and_never_reaches_brevo(brevo, monkeypatch, mail_from):
    sent, _ = brevo
    monkeypatch.setattr(settings, "mail_from", mail_from)
    
    with pytest.raises(mailer.MailError, match="MAIL_FROM is not valid"):
        send("amina@example.com", "Subject", "Body")
    
    assert sent == []


def test_brevo_unreachable_becomes_a_mail_error(brevo):
    _, state = brevo
    
    def unreachable(request):
        raise httpx.ConnectError("no route")
    
    state["respond"] = unreachable
    with pytest.raises(mailer.MailError, match="Brevo unreachable"):
        send("amina@example.com", "Hello", "Hi")


@pytest.mark.parametrize("response", [
    httpx.Response(502, text="<html>Bad gateway</html>"),
    httpx.Response(500, json=["unexpected", "shape"]),
])
def test_an_unexpected_brevo_error_body_still_becomes_a_mail_error(brevo, response):
    """Whatever comes back, the caller gets a MailError it knows how to handle."""
    _, state = brevo
    state["respond"] = lambda request: response
    with pytest.raises(mailer.MailError, match=f"Brevo said {response.status_code}"):
        send("amina@example.com", "Hello", "Hi")

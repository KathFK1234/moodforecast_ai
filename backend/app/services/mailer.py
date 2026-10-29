"""Send email through Brevo's HTTPS API, or over SMTP."""

import asyncio
import logging
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from html import escape as escape_html
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

NOT_CONFIGURED = "Email is not configured: set MAIL_FROM, and BREVO_API_KEY or SMTP_HOST"


class MailError(RuntimeError):
    """An email could not be sent."""


def is_configured() -> bool:
    """Whether the settings needed to send email are present: a sender, and Brevo or SMTP."""
    return bool(settings.mail_from and (settings.brevo_api_key or settings.smtp_host))


def uses_brevo() -> bool:
    """Whether email goes through Brevo's API rather than SMTP."""
    return bool(settings.brevo_api_key)


def send_email(
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
    headers: dict[str, str] | None = None
) -> None:
    """
    Send one email over SMTP, as plain text with an optional HTML alternative.
    
    Port 465 connects over TLS; other ports upgrade with STARTTLS unless
    SMTP_STARTTLS is off. Logs in if SMTP_USERNAME is set.
    
    Raises MailError if email is not configured or the server refuses it.
    """
    if not (settings.smtp_host and settings.mail_from):
        raise MailError(NOT_CONFIGURED)
    
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid()
    for name, value in (headers or {}).items():
        message[name] = value
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")
    
    try:
        if settings.smtp_port == 465:
            server = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port,
                timeout=15, context=ssl.create_default_context()
            )
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        with server:
            if settings.smtp_port != 465 and settings.smtp_starttls:
                server.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as e:
        raise MailError(f"Could not send email to {to}: {e}") from e


async def send_email_async(
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
    headers: dict[str, str] | None = None
) -> None:
    """
    Send one email without blocking the event loop: through Brevo if
    BREVO_API_KEY is set, otherwise over SMTP.
    
    Raises MailError if email is not configured or the email can't be sent.
    """
    if not is_configured():
        raise MailError(NOT_CONFIGURED)
    if uses_brevo():
        await send_with_brevo(to, subject, text, html, headers)
    else:
        await asyncio.to_thread(send_email, to, subject, text, html, headers)


async def send_with_brevo(
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
    headers: dict[str, str] | None = None
) -> None:
    """
    Send one email with Brevo's transactional email API (POST /smtp/email).
    
    MAIL_FROM must be a sender verified in Brevo. If Brevo refuses the extra
    headers (List-Unsubscribe), the email is sent again without them: the
    unsubscribe link in the body still works. Raises MailError on failure.
    """
    name, address = parseaddr(settings.mail_from)
    sender = {"email": address, "name": name} if name else {"email": address}
    payload = {
        "sender": sender,
        "to": [{"email": to}],
        "subject": subject,
        "textContent": text,
        # Brevo needs HTML; plain text in a <pre> keeps its line breaks
        "htmlContent": html or f"<pre>{escape_html(text)}</pre>",
    }
    attempts = [{**payload, "headers": headers}, payload] if headers else [payload]
    
    async with httpx.AsyncClient(base_url=settings.brevo_api_url, timeout=15.0) as client:
        for attempt, body in enumerate(attempts):
            try:
                response = await client.post(
                    "/smtp/email",
                    json=body,
                    headers={"api-key": settings.brevo_api_key, "accept": "application/json"},
                )
            except httpx.HTTPError as e:
                raise MailError(f"Could not send email to {to}: Brevo unreachable ({e})") from e
            if response.status_code in (200, 201, 202):
                return
            reason = _brevo_reason(response)
            if response.status_code == 400 and attempt + 1 < len(attempts):
                logger.warning("Brevo refused the email (%s); trying again without the extra headers", reason)
                continue
            raise MailError(f"Could not send email to {to}: Brevo said {response.status_code} {reason}")


def _brevo_reason(response: httpx.Response) -> str:
    """Brevo's explanation of a refusal, e.g. 'unauthorized: Key not found'."""
    try:
        body = response.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        return response.text[:200]
    return f"{body.get('code', '')}: {body.get('message', '')}".strip(": ")


if __name__ == "__main__":
    # python -m app.services.mailer you@example.com
    if len(sys.argv) != 2:
        sys.exit("Usage: python -m app.services.mailer <your email address>")
    try:
        asyncio.run(send_email_async(
            sys.argv[1],
            "MoodForecast test email",
            "If you are reading this, MoodForecast can send email.",
        ))
    except MailError as e:
        sys.exit(str(e))
    via = "Brevo" if uses_brevo() else f"{settings.smtp_host}:{settings.smtp_port}"
    print(f"Sent a test email to {sys.argv[1]} via {via}")

"""Send email over SMTP."""

import asyncio
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from app.config import settings


class MailError(RuntimeError):
    """An email could not be sent."""


def is_configured() -> bool:
    """Whether the SMTP settings needed to send email are present."""
    return bool(settings.smtp_host and settings.mail_from)


def send_email(
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
    headers: dict[str, str] | None = None
) -> None:
    """
    Send one email, as plain text with an optional HTML alternative.
    
    Port 465 connects over TLS; other ports upgrade with STARTTLS unless
    SMTP_STARTTLS is off. Logs in if SMTP_USERNAME is set.
    
    Raises MailError if email is not configured or the server refuses it.
    """
    if not is_configured():
        raise MailError("Email is not configured: set SMTP_HOST and MAIL_FROM")
    
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
    """send_email without blocking the event loop."""
    await asyncio.to_thread(send_email, to, subject, text, html, headers)


if __name__ == "__main__":
    # python -m app.services.mailer you@example.com
    if len(sys.argv) != 2:
        sys.exit("Usage: python -m app.services.mailer <your email address>")
    try:
        send_email(
            sys.argv[1],
            "MoodForecast test email",
            "If you are reading this, MoodForecast can send email.",
        )
    except MailError as e:
        sys.exit(str(e))
    print(f"Sent a test email to {sys.argv[1]} via {settings.smtp_host}:{settings.smtp_port}")

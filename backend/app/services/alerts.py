"""Emails sent to daily alert subscribers."""

import html
import logging
from typing import NamedTuple
from app.config import settings
from app.models.db import Subscriber
from app.services import mailer

logger = logging.getLogger(__name__)


class Email(NamedTuple):
    """A composed email, ready to send."""
    subject: str
    text: str
    html: str


def unsubscribe_url(token: str) -> str:
    """Link that opens the site and asks to confirm unsubscribing."""
    return f"{settings.public_url.rstrip('/')}/?unsubscribe={token}"


def unsubscribe_headers(token: str) -> dict[str, str]:
    """Headers that give mail apps their own one-click unsubscribe button."""
    return {
        "List-Unsubscribe": f"<{settings.public_url.rstrip('/')}/api/unsubscribe/{token}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def _compose(subject: str, heading: str, paragraphs: list[str], token: str, footer: str) -> Email:
    """Lay an email out as plain text and as simple HTML, ending with the unsubscribe link."""
    link = unsubscribe_url(token)
    text = "\n\n".join([heading, *paragraphs, f"{footer}\nUnsubscribe: {link}"])
    
    body = "".join(
        f'<p style="margin:0 0 14px;line-height:1.55">{html.escape(paragraph)}</p>'
        for paragraph in paragraphs
    )
    page = (
        '<div style="font-family:Helvetica,Arial,sans-serif;font-size:15px;color:#1b2233;'
        'max-width:520px;margin:0 auto;padding:24px">'
        f'<h1 style="font-size:20px;margin:0 0 16px">{html.escape(heading)}</h1>'
        f"{body}"
        '<p style="margin:24px 0 0;padding-top:14px;border-top:1px solid #dde2ee;'
        'font-size:12px;color:#6b7590;line-height:1.5">'
        f'{html.escape(footer)} <a href="{html.escape(link)}" style="color:#3987e5">Unsubscribe</a>'
        "</p></div>"
    )
    return Email(subject, text, page)


def welcome_email(subscriber: Subscriber) -> Email:
    """Confirmation sent when someone subscribes or changes their subscription."""
    if subscriber.activity:
        about = f"how the weather suits {subscriber.activity}"
    else:
        about = "a new activity to try, picked to suit the weather"
    return _compose(
        subject=f"You're subscribed to MoodForecast for {subscriber.place}",
        heading=f"Daily alerts for {subscriber.place} are on",
        paragraphs=[
            f"Each day you'll get the weather in {subscriber.place}, how it is likely "
            f"to affect mood and energy, and {about}.",
            f"It goes out around {settings.alert_hour:02d}:00, local time in {subscriber.place}.",
        ],
        token=subscriber.token,
        footer="Didn't sign up, or changed your mind?",
    )


def unsubscribe_link_email(subscriber: Subscriber) -> Email:
    """Sent when someone asks for their unsubscribe link."""
    return _compose(
        subject="Your MoodForecast unsubscribe link",
        heading="Unsubscribe from MoodForecast",
        paragraphs=[
            f"You asked for a link to stop the daily alerts for {subscriber.place}. "
            "Use the link below. If this wasn't you, ignore this email and nothing changes.",
        ],
        token=subscriber.token,
        footer="To stop the daily alerts:",
    )


async def send(subscriber: Subscriber, email: Email) -> bool:
    """
    Send a composed email to a subscriber.
    
    Returns False, without raising, if email isn't configured or sending fails -
    a subscription should not fail because of a mail problem.
    """
    if not mailer.is_configured():
        return False
    try:
        await mailer.send_email_async(
            subscriber.email, email.subject, email.text, email.html,
            unsubscribe_headers(subscriber.token)
        )
        return True
    except mailer.MailError as e:
        logger.warning("%s", e)
        return False

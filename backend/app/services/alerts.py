"""Emails sent to daily alert subscribers."""

import asyncio
import html
import logging
import random
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple
from urllib.parse import quote
from sqlmodel import Session, select
from app.config import settings
from app.models.db import Subscriber, create_tables, get_engine
from app.services import mailer
from app.services.activity_advisor import check_activity, random_activity
from app.services.curiosity import curiosity_prompts
from app.services.mood_engine import build_summary, score_mood
from app.services.weather import get_weather_client

logger = logging.getLogger(__name__)

# How often the background loop looks for subscribers whose alert is due
CHECK_INTERVAL_SECONDS = 900

# A paragraph is plain text, or (text, link label, link url)
Paragraph = str | tuple[str, str, str]


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


def _compose(subject: str, heading: str, paragraphs: list[Paragraph], token: str, footer: str) -> Email:
    """Lay an email out as plain text and as simple HTML, ending with the unsubscribe link."""
    link = unsubscribe_url(token)
    
    text_parts = []
    body = ""
    for paragraph in paragraphs:
        if isinstance(paragraph, str):
            text_parts.append(paragraph)
            content = html.escape(paragraph)
        else:
            words, label, url = paragraph
            text_parts.append(f"{words}\n{label}: {url}")
            content = (
                f'{html.escape(words)} '
                f'<a href="{html.escape(url)}" style="color:#3987e5">{html.escape(label)}</a>'
            )
        body += f'<p style="margin:0 0 14px;line-height:1.55">{content}</p>'
    text = "\n\n".join([heading, *text_parts, f"{footer}\nUnsubscribe: {link}"])
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


def daily_email(
    subscriber: Subscriber,
    forecast: dict[str, Any],
    rng: random.Random | None = None
) -> Email:
    """
    The daily alert: weather, mood, and an activity.
    
    The activity is the one the subscriber chose, judged against the weather,
    or a random pick that suits it. `forecast` is WeatherClient.get_forecast's result.
    """
    place = subscriber.place
    site = settings.public_url.rstrip("/")
    current = forecast["current"]
    condition = current.get("condition") or "Unknown"
    temperature = float(current.get("temperature", 0))
    humidity = float(current.get("humidity", 0))
    wind = float(current.get("wind_speed", 0))
    is_day = current.get("is_day", True)
    
    mood = score_mood(condition, temperature, humidity, is_day)
    paragraphs: list[Paragraph] = [
        build_summary(place, condition, temperature, mood["mood_score"], mood["factors"], is_day),
        f"Mood score: {mood['mood_score']} out of 100 ({mood['mood_label']}), "
        f"with {mood['energy_level'].lower()} energy.",
    ]
    
    daily = forecast.get("daily") or []
    if daily:
        today = daily[0]
        outlook = (
            f"Today: {today['condition'].lower()}, "
            f"{round(today['temp_min'])} to {round(today['temp_max'])}°C"
        )
        if today.get("precipitation_chance") is not None:
            outlook += f", {round(today['precipitation_chance'])}% chance of rain"
        paragraphs.append(outlook + ".")
    
    weather = (place, condition, temperature, humidity, wind, is_day)
    if subscriber.activity:
        advice = check_activity(subscriber.activity, *weather, rng=rng, searched_as=subscriber.location)
    else:
        advice = random_activity(*weather, rng=rng, searched_as=subscriber.location)
    activity = " ".join([advice["headline"], *advice["reasons"]])
    if advice["suggestion"]:
        activity += f" {advice['suggestion']}"
    paragraphs.append(activity)
    paragraphs.append(mood["recommendations"][0])
    
    for prompt in curiosity_prompts(
        place, condition, temperature, is_day, count=1, rng=rng, searched_as=subscriber.location
    ):
        paragraphs.append(
            (prompt["question"], f"Look up {prompt['location']}", f"{site}/?q={quote(prompt['location'])}")
        )
    paragraphs.append(
        ("Want the 7-day outlook?", "Open the full forecast", f"{site}/?q={quote(subscriber.location)}")
    )
    
    return _compose(
        subject=f"{place}: {mood['mood_label']} today, {round(temperature)}°C and {condition.lower()}",
        heading=f"{place} today",
        paragraphs=paragraphs,
        token=subscriber.token,
        footer=f"You get this because you subscribed to daily alerts for {place}.",
    )


def local_date(utc_offset_seconds: int, now_utc: datetime) -> str:
    """Today's date at a location, YYYY-MM-DD."""
    return (now_utc + timedelta(seconds=utc_offset_seconds)).date().isoformat()


def is_due(subscriber: Subscriber, now_utc: datetime) -> bool:
    """Whether it is past the alert hour where the subscriber is and today's alert hasn't gone out."""
    local = now_utc + timedelta(seconds=subscriber.utc_offset_seconds)
    return (
        subscriber.active
        and local.hour >= settings.alert_hour
        and subscriber.last_sent_on != local.date().isoformat()
    )


async def send_due_alerts(now_utc: datetime | None = None, force: bool = False) -> int:
    """
    Email every active subscriber whose daily alert is due.
    
    A subscriber is marked as sent only once their email has gone out, so a
    failure is retried on the next run. `force` sends to every active
    subscriber regardless of the time or what was sent today.
    
    Returns the number of emails sent.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    client = get_weather_client()
    sent = 0
    
    with Session(get_engine()) as session:
        subscribers = session.exec(
            select(Subscriber).where(Subscriber.active == True)  # noqa: E712
        ).all()
        for subscriber in subscribers:
            if not (force or is_due(subscriber, now_utc)):
                continue
            try:
                forecast = await client.get_forecast(subscriber.lat, subscriber.lon)
            except Exception as e:
                logger.warning("No forecast for %s, alert not sent: %s", subscriber.place, e)
                continue
            
            # Follow daylight saving changes
            subscriber.utc_offset_seconds = forecast.get("utc_offset_seconds", subscriber.utc_offset_seconds)
            if await send(subscriber, daily_email(subscriber, forecast)):
                subscriber.last_sent_on = local_date(subscriber.utc_offset_seconds, now_utc)
                sent += 1
            session.add(subscriber)
            session.commit()
    
    return sent


async def run_alert_loop() -> None:
    """Send due alerts every CHECK_INTERVAL_SECONDS until cancelled."""
    while True:
        try:
            sent = await send_due_alerts()
            if sent:
                logger.info("Sent %d daily alert(s)", sent)
        except Exception:
            logger.exception("Daily alert run failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    # python -m app.services.alerts          send the alerts that are due now
    # python -m app.services.alerts --all    send to every active subscriber now
    if not mailer.is_configured():
        sys.exit("Email is not configured: set SMTP_HOST and MAIL_FROM")
    create_tables()
    count = asyncio.run(send_due_alerts(force="--all" in sys.argv[1:]))
    print(f"Sent {count} daily alert(s)")

"""Emails sent to daily alert subscribers."""

import asyncio
import html
import logging
import random
import secrets
import sys
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple
from urllib.parse import quote
from sqlalchemy import and_, delete, or_
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import Session, select
from app.config import settings
from app.models.db import PendingSubscription, Subscriber, create_tables, get_engine
from app.services import mailer
from app.services.activity_advisor import check_activity, random_activity
from app.services.cache import TTLCache
from app.services.curiosity import curiosity_prompts
from app.services.locality import build_place
from app.services.mood_engine import build_summary, score_mood
from app.services.weather import get_weather_client

logger = logging.getLogger(__name__)

# How often the background loop looks for subscribers whose alert is due
CHECK_INTERVAL_SECONDS = 900

# How long a newly started app waits before its first check
STARTUP_DELAY_SECONDS = 60

# How long a confirmation link works
CONFIRM_HOURS = 48

# Emails anyone can trigger from the site's forms, recently sent, by kind and address.
# Kept apart from the shared cache so a burst of searches can't push these out early.
_recently_sent = TTLCache(settings.cache_ttl_seconds)

# Emails the site's forms may send in a day, across all addresses. Stops someone
# typing in thousands of addresses from using up the mail provider's daily
# allowance (300 on Brevo's free plan), which the daily alerts need too.
MAX_FORM_EMAILS_PER_DAY = 100
_form_emails_sent: deque[float] = deque()

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


def _compose(subject: str, heading: str, paragraphs: list[Paragraph], token: str | None, footer: str) -> Email:
    """
    Lay an email out as plain text and as simple HTML.
    
    With a subscriber's `token` it ends with their unsubscribe link; without
    one (a confirmation request, before there is a subscription) the footer
    stands alone.
    """
    link = unsubscribe_url(token) if token else None
    
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
    text = "\n\n".join([heading, *text_parts, f"{footer}\nUnsubscribe: {link}" if link else footer])
    footer_link = f' <a href="{html.escape(link)}" style="color:#3987e5">Unsubscribe</a>' if link else ""
    page = (
        '<div style="font-family:Helvetica,Arial,sans-serif;font-size:15px;color:#1b2233;'
        'max-width:520px;margin:0 auto;padding:24px">'
        f'<h1 style="font-size:20px;margin:0 0 16px">{html.escape(heading)}</h1>'
        f"{body}"
        '<p style="margin:24px 0 0;padding-top:14px;border-top:1px solid #dde2ee;'
        'font-size:12px;color:#6b7590;line-height:1.5">'
        f"{html.escape(footer)}{footer_link}"
        "</p></div>"
    )
    return Email(subject, text, page)


def _about(activity: str | None) -> str:
    """What the daily email says about the activity, for the emails describing it."""
    return f"how the weather suits {activity}" if activity else "a new activity to try, picked to suit the weather"


def confirm_url(token: str) -> str:
    """Link that opens the site and asks to confirm a subscription."""
    return f"{settings.public_url.rstrip('/')}/?confirm={token}"


def confirm_email(pending: PendingSubscription, valid_hours: int) -> Email:
    """Sent when someone asks for alerts: nothing else is sent until its link is followed."""
    about = _about(pending.activity)
    return _compose(
        subject=f"Confirm your MoodForecast alerts for {pending.place}",
        heading="Confirm your daily alerts",
        paragraphs=[
            f"Someone, hopefully you, asked for a daily email with the weather in {pending.place}, "
            f"how it is likely to affect mood and energy, and {about}.",
            ("Nothing will be sent until you confirm.", "Confirm my alerts", confirm_url(pending.token)),
            f"The link works for {valid_hours} hours.",
        ],
        token=None,
        footer="Didn't ask for this? Ignore this email and nothing more will be sent.",
    )


def reconfirm_email(pending: PendingSubscription, valid_hours: int) -> Email:
    """Sent once to a subscriber from before addresses had to be confirmed."""
    about = _about(pending.activity)
    return _compose(
        subject=f"Please confirm your MoodForecast alerts for {pending.place}",
        heading="Please confirm your daily alerts",
        paragraphs=[
            f"This address was signed up for a daily email with the weather in {pending.place}, "
            f"how it is likely to affect mood and energy, and {about}.",
            "MoodForecast now asks everyone to confirm their address before sending anything, "
            "so these alerts are paused until you do.",
            ("To keep them:", "Confirm my alerts", confirm_url(pending.token)),
            f"The link works for {valid_hours} hours. After that you can sign up again on the site.",
        ],
        token=None,
        footer="Didn't sign up? Ignore this email and nothing more will be sent.",
    )


def welcome_email(subscriber: Subscriber) -> Email:
    """Confirmation sent when someone subscribes or changes their subscription."""
    about = _about(subscriber.activity)
    return _compose(
        subject=f"You're subscribed to MoodForecast for {subscriber.place}",  # Sent once confirmed
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


def _form_email_allowance_left() -> bool:
    """Whether the site's forms may send another email today."""
    day_ago = time.time() - 86400
    while _form_emails_sent and _form_emails_sent[0] < day_ago:
        _form_emails_sent.popleft()
    return len(_form_emails_sent) < MAX_FORM_EMAILS_PER_DAY


def recently_sent(to: str, kind: str) -> bool:
    """Whether send_once sent this kind of email to this address within the last cache lifetime."""
    return bool(_recently_sent.get(f"{kind}:{to}"))


async def send_once(to: str, email: Email, kind: str, token: str | None = None) -> bool:
    """
    Send an email that anyone can trigger by typing an address into the site,
    at most once per address per cache lifetime (10 minutes by default).
    
    Stops the subscribe and unsubscribe forms being used to flood someone's
    inbox, and sends nothing once MAX_FORM_EMAILS_PER_DAY is reached. Returns True if the email was sent now or is already on its way
    from a moment ago. `token` is the subscriber's, for the unsubscribe
    headers, if there is one.
    """
    cache_key = f"{kind}:{to}"
    if _recently_sent.get(cache_key):
        return True
    if not _form_email_allowance_left():
        logger.warning("Daily limit of %d form emails reached, not sent", MAX_FORM_EMAILS_PER_DAY)
        return False
    # Marked before sending: a second request arriving during the send must not send again
    _recently_sent.set(cache_key, True)
    sent = await send_to(to, email, token)
    if sent:
        _form_emails_sent.append(time.time())
    else:
        _recently_sent.delete(cache_key)
    return sent


async def send(subscriber: Subscriber, email: Email) -> bool:
    """Send a composed email to a subscriber, with their unsubscribe headers."""
    return await send_to(subscriber.email, email, subscriber.token)


async def send_to(to: str, email: Email, token: str | None = None) -> bool:
    """
    Send a composed email, with unsubscribe headers when there is a subscriber `token`.
    
    Returns False, without raising, if email isn't configured or sending fails -
    a subscription should not fail because of a mail problem.
    """
    if not mailer.is_configured():
        return False
    try:
        await mailer.send_email_async(
            to, email.subject, email.text, email.html,
            unsubscribe_headers(token) if token else None
        )
        return True
    except mailer.MailError as e:
        logger.warning("%s", e)
        return False


def daily_email(
    subscriber: Subscriber,
    forecast: dict[str, Any],
    rng: random.Random | None = None,
    sea: dict[str, Any] | None = None
) -> Email:
    """
    The daily alert: weather, mood, and an activity.
    
    The activity is the one the subscriber chose, judged against the weather,
    or a random pick that suits it and the place. `forecast` is
    WeatherClient.get_forecast's result and `sea` is get_sea's.
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
    local = {
        "rng": rng,
        "searched_as": subscriber.location,
        "place": build_place(place, subscriber.lat, forecast, sea),
    }
    if subscriber.activity:
        advice = check_activity(subscriber.activity, *weather, **local)
    else:
        advice = random_activity(*weather, **local)
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
        and subscriber.confirmed
        and local.hour >= settings.alert_hour
        and subscriber.last_sent_on != local.date().isoformat()
    )


async def send_due_alerts(now_utc: datetime | None = None, force: bool = False) -> int:
    """
    Email every active, confirmed subscriber whose daily alert is due.
    
    A subscriber is marked as sent only once their email has gone out, so a
    failure is retried on the next run. `force` sends to every active,
    confirmed subscriber regardless of the time or what was sent today.
    
    Returns the number of emails sent.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    client = get_weather_client()
    sent = 0
    
    with Session(get_engine()) as session:
        subscriber_ids = session.exec(
            select(Subscriber.id).where(Subscriber.active == True, Subscriber.confirmed == True)  # noqa: E712
        ).all()
        for subscriber_id in subscriber_ids:
            # Fetched one at a time: anyone can unsubscribe, deleting their row, during the run
            subscriber = session.get(Subscriber, subscriber_id)
            if subscriber is None or not (force or is_due(subscriber, now_utc)):
                continue
            try:
                forecast = await client.get_forecast(subscriber.lat, subscriber.lon)
            except Exception as e:
                logger.warning("No forecast for %s, alert not sent: %s", subscriber.place, e)
                continue
            
            # Follow daylight saving changes
            subscriber.utc_offset_seconds = forecast.get("utc_offset_seconds", subscriber.utc_offset_seconds)
            try:
                sea = await client.get_sea(subscriber.lat, subscriber.lon)
                email = daily_email(subscriber, forecast, sea=sea)
            except Exception:
                # One subscriber's unusual data must not cost everyone after them their alert
                logger.exception("Alert for %s could not be written, not sent", subscriber.place)
                continue
            if await send(subscriber, email):
                subscriber.last_sent_on = local_date(subscriber.utc_offset_seconds, now_utc)
                sent += 1
            session.add(subscriber)
            _commit_unless_deleted(session)
    
    return sent


async def request_confirmations(now_utc: datetime | None = None) -> int:
    """
    Ask each subscriber from before addresses had to be confirmed, once, to confirm.
    
    Their alerts are paused until they follow the link. A subscriber is marked
    as asked only once the email has gone out, so a failure is retried on the
    next run; if they still do not confirm, delete_unused_data removes them.
    
    Returns the number of emails sent.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    sent = 0
    with Session(get_engine()) as session:
        unconfirmed = session.exec(
            select(Subscriber.id).where(
                Subscriber.active == True,  # noqa: E712
                Subscriber.confirmed == False,  # noqa: E712
                Subscriber.confirm_requested_at == None,  # noqa: E711
            )
        ).all()
        for subscriber_id in unconfirmed:
            subscriber = session.get(Subscriber, subscriber_id)
            if subscriber is None:
                continue
            pending = PendingSubscription(
                token=secrets.token_urlsafe(24),
                email=subscriber.email,
                location=subscriber.location,
                place=subscriber.place,
                lat=subscriber.lat,
                lon=subscriber.lon,
                utc_offset_seconds=subscriber.utc_offset_seconds,
                activity=subscriber.activity,
                language=subscriber.language,
            )
            session.add(pending)
            session.commit()
            if await send_to(subscriber.email, reconfirm_email(pending, CONFIRM_HOURS)):
                subscriber.confirm_requested_at = now_utc
                session.add(subscriber)
                sent += 1
            else:
                session.delete(pending)
            _commit_unless_deleted(session)
    return sent


def delete_unused_data(now_utc: datetime | None = None) -> int:
    """
    Delete what will never be used again: subscribers who have unsubscribed,
    earlier subscribers who didn't confirm in time, and requests nobody confirmed.
    
    Returns the number of records deleted.
    """
    cutoff = (now_utc or datetime.now(timezone.utc)) - timedelta(hours=CONFIRM_HOURS)
    with Session(get_engine()) as session:
        subscribers = session.exec(delete(Subscriber).where(
            or_(
                Subscriber.active == False,  # noqa: E712
                and_(Subscriber.confirmed == False, Subscriber.confirm_requested_at < cutoff),  # noqa: E712
            )
        ))
        requests = session.exec(delete(PendingSubscription).where(PendingSubscription.created_at < cutoff))
        session.commit()
        return subscribers.rowcount + requests.rowcount


def _commit_unless_deleted(session: Session) -> None:
    """Save a subscriber's progress, unless they unsubscribed while their email was going out."""
    try:
        session.commit()
    except StaleDataError:
        session.rollback()


async def run_alert_loop() -> None:
    """Send due alerts, and confirmation requests, every CHECK_INTERVAL_SECONDS until cancelled."""
    # During a deploy the old instance runs on briefly; waiting stops both sending the same alerts
    await asyncio.sleep(STARTUP_DELAY_SECONDS)
    while True:
        try:
            asked = await request_confirmations()
            if asked:
                logger.info("Asked %d earlier subscriber(s) to confirm", asked)
            sent = await send_due_alerts()
            if sent:
                logger.info("Sent %d daily alert(s)", sent)
            # Last, so a problem here can't cost anyone their alert
            deleted = delete_unused_data()
            if deleted:
                logger.info("Deleted %d record(s) no longer needed", deleted)
        except Exception:
            logger.exception("Daily alert run failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    # python -m app.services.alerts          send the alerts that are due now
    # python -m app.services.alerts --all    send to every active, confirmed subscriber now
    if not mailer.is_configured():
        sys.exit(mailer.NOT_CONFIGURED)
    create_tables()
    asked = asyncio.run(request_confirmations())
    count = asyncio.run(send_due_alerts(force="--all" in sys.argv[1:]))
    print(f"Asked {asked} earlier subscriber(s) to confirm; sent {count} daily alert(s)")

"""Subscribe router - GET /api/alerts; POST /api/subscribe, /api/confirm/{token}, /api/unsubscribe/{token} and /api/unsubscribe-link"""

import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from app.models.db import PendingSubscription, Subscriber, as_utc, get_engine, utc_now
from app.models.schemas import (
    AlertsStatus,
    ConfirmResponse,
    SubscribeRequest,
    SubscribeResponse,
    UnsubscribeLinkRequest,
    UnsubscribeLinkResponse,
    UnsubscribeResponse,
)
from app.routers.common import friendly_errors, resolve_location
from app.services import alerts, mailer
from app.services.activity_advisor import find_activity
from app.services.locality import build_place, local_issue
from app.services.weather import get_weather_client

router = APIRouter(prefix="/api", tags=["subscribe"])


CONFIRM_HOURS = alerts.CONFIRM_HOURS

# What secrets.token_urlsafe produces. Anything else is no token of ours, and
# PostgreSQL refuses to look up text with a NUL byte in it.
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]+")

EMAIL_UNAVAILABLE_MESSAGE = "Email alerts aren't available right now. Please try again later."


@router.get("/alerts")
async def alerts_status() -> AlertsStatus:
    """Whether daily email alerts can be signed up for, so the page can say so before anyone fills in the form."""
    return AlertsStatus(available=mailer.is_configured())


@router.post("/subscribe", status_code=202)
@friendly_errors
async def subscribe(request: SubscribeRequest) -> SubscribeResponse:
    """
    Ask for daily alerts about a location, or for a change to existing ones.
    
    Nothing starts or changes until the email address is confirmed: this
    stores the request and emails a link to POST /api/confirm/{token}, valid
    for CONFIRM_HOURS. The location must be one the geocoder can find, and the
    activity one that can be done there.
    
    Returns 503 if email is not configured, since the request could never be
    confirmed. `confirmation_sent` says whether the email went out. If a link
    went to the address in the last few minutes, no new request is stored or
    sent and `status` is "already_sent".
    """
    if not mailer.is_configured():
        raise HTTPException(status_code=503, detail=EMAIL_UNAVAILABLE_MESSAGE)
    
    client = get_weather_client()
    lat, lon, place = await resolve_location(client, request.location)
    forecast = await client.get_forecast(lat, lon)
    
    # A daily report on something the place can't offer would only ever say no
    if request.activity:
        local_place = build_place(place, lat, forecast, await client.get_sea(lat, lon))
        issue = local_issue(find_activity(request.activity).needs, request.activity, local_place)
        if issue and issue[0] == 2:
            raise HTTPException(status_code=422, detail=f"{issue[1]} Pick another activity.")
    
    # A link went out minutes ago and no new one will until the guard
    # lifts, so say so rather than store details the emailed link won't apply
    if alerts.recently_sent(request.email, "confirm"):
        return SubscribeResponse(
            email=request.email,
            location=place,
            activity=request.activity,
            status="already_sent",
            confirmation_sent=True
        )
    
    pending = PendingSubscription(
        token=secrets.token_urlsafe(24),
        email=request.email,
        location=request.location,
        place=place,
        lat=lat,
        lon=lon,
        utc_offset_seconds=forecast.get("utc_offset_seconds", 0),
        activity=request.activity,
        language=request.language,
    )
    with Session(get_engine()) as session:
        session.add(pending)
        session.commit()
        session.refresh(pending)
    
    confirmation_sent = await alerts.send_once(
        pending.email, alerts.confirm_email(pending, CONFIRM_HOURS), "confirm"
    )
    
    return SubscribeResponse(
        email=pending.email,
        location=pending.place,
        activity=pending.activity,
        confirmation_sent=confirmation_sent
    )


@router.post("/confirm/{token}")
async def confirm(token: str) -> ConfirmResponse:
    """
    Confirm a subscription request with the token from its email.
    
    Starts the alerts, or applies the change to an existing subscription, and
    sends the welcome email with the unsubscribe link. Other requests waiting
    for the same address are dropped. Returns 404 for an unknown, used or
    expired token.
    """
    with Session(get_engine()) as session:
        pending = session.get(PendingSubscription, token) if TOKEN_PATTERN.fullmatch(token) else None
        if pending is None or as_utc(pending.created_at) < utc_now() - timedelta(hours=CONFIRM_HOURS):
            raise HTTPException(
                status_code=404,
                detail="This confirmation link has expired or has already been used. Subscribe again to get a new one."
            )
        
        subscriber = session.exec(
            select(Subscriber).where(Subscriber.email == pending.email)
        ).first()
        status = "updated" if subscriber and subscriber.active else "subscribed"
        if subscriber is None:
            subscriber = Subscriber(
                id=str(uuid.uuid4()),
                email=pending.email,
                token=secrets.token_urlsafe(24),
                location=pending.location,
                place=pending.place,
                lat=pending.lat,
                lon=pending.lon
            )
        
        subscriber.location = pending.location
        subscriber.place = pending.place
        subscriber.lat = pending.lat
        subscriber.lon = pending.lon
        subscriber.utc_offset_seconds = pending.utc_offset_seconds
        subscriber.activity = pending.activity
        subscriber.language = pending.language
        subscriber.active = True
        subscriber.confirmed = True
        # The welcome email covers today if the alert hour has already passed,
        # so the first daily alert arrives the next morning
        now = datetime.now(timezone.utc)
        if subscriber.last_sent_on is None and alerts.is_due(subscriber, now):
            subscriber.last_sent_on = alerts.local_date(subscriber.utc_offset_seconds, now)
        session.add(subscriber)
        
        for request in session.exec(select(PendingSubscription).where(PendingSubscription.email == pending.email)):
            session.delete(request)
        session.commit()
        session.refresh(subscriber)
    
    await alerts.send(subscriber, alerts.welcome_email(subscriber))
    return ConfirmResponse(
        email=subscriber.email,
        location=subscriber.place,
        activity=subscriber.activity,
        status=status
    )


@router.post("/unsubscribe/{token}")
async def unsubscribe(token: str) -> UnsubscribeResponse:
    """
    Stop daily alerts and delete the subscriber's details.
    
    The token comes from the link in every email to a subscriber. Requests
    waiting for the same address go too. Subscribing again starts afresh with
    a new token. Returns 404 for an unknown token, which includes one already
    used.
    """
    with Session(get_engine()) as session:
        subscriber = None
        if TOKEN_PATTERN.fullmatch(token):
            subscriber = session.exec(
                select(Subscriber).where(Subscriber.token == token)
            ).first()
        if subscriber is None:
            raise HTTPException(
                status_code=404,
                detail="This link has already been used, so you're already unsubscribed."
            )
        
        email = subscriber.email
        for request in session.exec(select(PendingSubscription).where(PendingSubscription.email == email)):
            session.delete(request)
        session.delete(subscriber)
        session.commit()
        return UnsubscribeResponse(email=email)


@router.get("/unsubscribe/{token}", include_in_schema=False)
async def unsubscribe_page(token: str) -> RedirectResponse:
    """
    Send someone who opened the List-Unsubscribe address in a browser to the page.
    
    Mail apps without one-click support open it as a link. This changes nothing:
    mail scanners fetch links too, so unsubscribing stays a POST the page asks about.
    """
    return RedirectResponse(f"/?unsubscribe={quote(token, safe='')}", status_code=303)


@router.post("/unsubscribe-link", status_code=202)
async def send_unsubscribe_link(request: UnsubscribeLinkRequest, background: BackgroundTasks) -> UnsubscribeLinkResponse:
    """
    Email a subscriber their unsubscribe link.
    
    For someone who no longer has an alert email to hand. The response is the
    same whether or not the address is subscribed, so it can't be used to find
    out who is. The email goes out after the response, because waiting for it
    would make the answer slower for subscribers and show who is that way.
    Returns 503 if email is not configured.
    """
    if not mailer.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Unsubscribing here isn't available right now. Use the Unsubscribe link in any alert email instead."
        )
    
    engine = get_engine()
    with Session(engine) as session:
        subscriber = session.exec(
            select(Subscriber).where(Subscriber.email == request.email, Subscriber.active == True)  # noqa: E712
        ).first()
    
    if subscriber is not None:
        background.add_task(
            alerts.send_once,
            subscriber.email, alerts.unsubscribe_link_email(subscriber), "unsubscribe-link", subscriber.token
        )
    
    return UnsubscribeLinkResponse()

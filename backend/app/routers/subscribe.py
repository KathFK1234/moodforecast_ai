"""Subscribe router - POST /api/subscribe, /api/confirm/{token}, /api/unsubscribe/{token} and /api/unsubscribe-link"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select
from app.models.db import PendingSubscription, Subscriber, as_utc, get_engine, utc_now
from app.models.schemas import (
    ConfirmResponse,
    SubscribeRequest,
    SubscribeResponse,
    UnsubscribeLinkRequest,
    UnsubscribeLinkResponse,
    UnsubscribeResponse,
)
from app.routers.common import TIMEOUT_MESSAGE, UNAVAILABLE_MESSAGE, UNEXPECTED_MESSAGE, resolve_location
from app.services import alerts, mailer
from app.services.activity_advisor import find_activity
from app.services.locality import build_place, local_issue
from app.services.weather import get_weather_client

router = APIRouter(prefix="/api", tags=["subscribe"])
logger = logging.getLogger(__name__)


# How long a confirmation link works
CONFIRM_HOURS = 48

EMAIL_UNAVAILABLE_MESSAGE = "Email alerts aren't available right now. Please try again later."


@router.post("/subscribe", status_code=202)
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
    
    try:
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
            # Requests nobody confirmed in time are dropped
            cutoff = utc_now() - timedelta(hours=CONFIRM_HOURS)
            for expired in session.exec(select(PendingSubscription).where(PendingSubscription.created_at < cutoff)):
                session.delete(expired)
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
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except TimeoutError:
        raise HTTPException(status_code=504, detail=TIMEOUT_MESSAGE)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=UNAVAILABLE_MESSAGE)
    except Exception:
        logger.exception("Unexpected error")
        raise HTTPException(status_code=500, detail=UNEXPECTED_MESSAGE)


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
        pending = session.get(PendingSubscription, token)
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
    Stop daily alerts for the subscription the token belongs to.
    
    The token comes from the subscribe response and from the link in every
    email. Unsubscribing twice is fine. Returns 404 for an unknown token.
    """
    engine = get_engine()
    with Session(engine) as session:
        subscriber = session.exec(
            select(Subscriber).where(Subscriber.token == token)
        ).first()
        if subscriber is None:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        subscriber.active = False
        session.add(subscriber)
        session.commit()
        return UnsubscribeResponse(email=subscriber.email)


@router.post("/unsubscribe-link", status_code=202)
async def send_unsubscribe_link(request: UnsubscribeLinkRequest) -> UnsubscribeLinkResponse:
    """
    Email a subscriber their unsubscribe link.
    
    For someone who no longer has an alert email to hand. The response is the
    same whether or not the address is subscribed, so it can't be used to find
    out who is. Returns 503 if email is not configured.
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
        await alerts.send_once(
            subscriber.email, alerts.unsubscribe_link_email(subscriber), "unsubscribe-link", subscriber.token
        )
    
    return UnsubscribeLinkResponse()

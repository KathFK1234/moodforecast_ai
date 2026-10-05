"""Subscribe router - POST /api/subscribe, /api/unsubscribe/{token} and /api/unsubscribe-link"""

import secrets
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select
from app.models.db import Subscriber, get_engine
from app.models.schemas import (
    SubscribeRequest,
    SubscribeResponse,
    UnsubscribeLinkRequest,
    UnsubscribeLinkResponse,
    UnsubscribeResponse,
)
from app.routers.common import TIMEOUT_MESSAGE, UNAVAILABLE_MESSAGE, resolve_location
from app.services import alerts, mailer
from app.services.activity_advisor import find_activity
from app.services.locality import build_place, local_issue
from app.services.weather import get_weather_client

router = APIRouter(prefix="/api", tags=["subscribe"])


@router.post("/subscribe", status_code=201)
async def subscribe(request: SubscribeRequest) -> SubscribeResponse:
    """
    Register an email address for daily alerts about a location.
    
    Stores: email, location, activity, language. The location must be one the
    geocoder can find, and the activity one that can be done there. Subscribing again with the same email updates the
    existing subscription instead of adding another.
    
    Sends a confirmation email if email is configured; the subscription is
    stored either way, and `confirmation_sent` says which happened.
    
    Returns subscriber ID, confirmation, and the token that unsubscribes.
    """
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
        
        # Save to database
        engine = get_engine()
        with Session(engine) as session:
            subscriber = session.exec(
                select(Subscriber).where(Subscriber.email == request.email)
            ).first()
            status = "updated" if subscriber and subscriber.active else "subscribed"
            if subscriber is None:
                subscriber = Subscriber(
                    id=str(uuid.uuid4()),
                    email=request.email,
                    token=secrets.token_urlsafe(24),
                    location=request.location,
                    place=place,
                    lat=lat,
                    lon=lon
                )
            
            subscriber.location = request.location
            subscriber.place = place
            subscriber.lat = lat
            subscriber.lon = lon
            subscriber.utc_offset_seconds = forecast.get("utc_offset_seconds", 0)
            subscriber.activity = request.activity
            subscriber.language = request.language
            subscriber.active = True
            # The confirmation covers today if the alert hour has already passed,
            # so the first daily alert arrives the next morning
            now = datetime.now(timezone.utc)
            if subscriber.last_sent_on is None and alerts.is_due(subscriber, now):
                subscriber.last_sent_on = alerts.local_date(subscriber.utc_offset_seconds, now)
            
            session.add(subscriber)
            session.commit()
            session.refresh(subscriber)
        
        confirmation_sent = await alerts.send(subscriber, alerts.welcome_email(subscriber))
        
        return SubscribeResponse(
            subscriber_id=subscriber.id,
            email=subscriber.email,
            location=subscriber.place,
            activity=subscriber.activity,
            status=status,
            unsubscribe_token=subscriber.token,
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Subscription failed: {str(e)}")


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
        await alerts.send(subscriber, alerts.unsubscribe_link_email(subscriber))
    
    return UnsubscribeLinkResponse()

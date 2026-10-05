"""Subscribe router - POST /api/subscribe"""

import secrets
import uuid
from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select
from app.models.db import Subscriber, get_engine
from app.models.schemas import SubscribeRequest, SubscribeResponse
from app.routers.common import resolve_location
from app.services.weather import get_weather_client

router = APIRouter(prefix="/api", tags=["subscribe"])


@router.post("/subscribe", status_code=201)
async def subscribe(request: SubscribeRequest) -> SubscribeResponse:
    """
    Register an email address for daily alerts about a location.
    
    Stores: email, location, activity, language. The location must be one the
    geocoder can find. Subscribing again with the same email updates the
    existing subscription instead of adding another.
    
    Returns subscriber ID and confirmation.
    """
    try:
        client = get_weather_client()
        lat, lon, place = await resolve_location(client, request.location)
        forecast = await client.get_forecast(lat, lon)
        
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
            
            session.add(subscriber)
            session.commit()
            session.refresh(subscriber)
        
        return SubscribeResponse(
            subscriber_id=subscriber.id,
            email=subscriber.email,
            location=subscriber.place,
            activity=subscriber.activity,
            status=status
        )
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Weather API timeout")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail="Weather service unavailable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Subscription failed: {str(e)}")

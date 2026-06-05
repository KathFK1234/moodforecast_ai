"""Subscribe router - POST /api/subscribe"""

import uuid
from fastapi import APIRouter, HTTPException
from sqlmodel import Session, create_engine, select
from app.config import settings
from app.models.db import Subscriber, get_engine
from app.models.schemas import SubscribeRequest, SubscribeResponse

router = APIRouter(prefix="/api", tags=["subscribe"])


@router.post("/subscribe", status_code=201)
async def subscribe(request: SubscribeRequest) -> SubscribeResponse:
    """
    Register a subscriber for SMS/USSD alerts.
    
    Stores: phone, location, crop, language.
    Phone must be in E.164 format (e.g., +254712345678).
    
    Returns subscriber ID and confirmation.
    """
    try:
        # Validate phone format (basic E.164 check)
        if not request.phone.startswith("+") or len(request.phone) < 10:
            raise HTTPException(
                status_code=422,
                detail="Phone must be in E.164 format (e.g., +254712345678)"
            )
        
        # Create subscriber
        subscriber_id = str(uuid.uuid4())
        subscriber = Subscriber(
            id=subscriber_id,
            phone=request.phone,
            location=request.location,
            crop=request.crop,
            language=request.language
        )
        
        # Save to database
        engine = get_engine()
        with Session(engine) as session:
            session.add(subscriber)
            session.commit()
            session.refresh(subscriber)
        
        return SubscribeResponse(
            subscriber_id=subscriber_id,
            phone=request.phone,
            location=request.location,
            status="subscribed"
        )
    
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Subscription failed: {str(e)}")

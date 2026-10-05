"""Database models and schema definitions."""

from datetime import datetime, timezone
from functools import lru_cache
from sqlmodel import SQLModel, Field, create_engine
from app.config import settings


class Subscriber(SQLModel, table=True):
    """
    Daily email alert subscriber table.
    
    Named alert_subscriber so it sits beside the earlier phone-based
    "subscriber" table instead of clashing with it.
    """
    __tablename__ = "alert_subscriber"
    
    id: str | None = Field(default=None, primary_key=True)
    email: str = Field(..., index=True, unique=True, description="Lowercase")
    location: str = Field(..., description="As the subscriber typed it")
    place: str = Field(..., description="Resolved display name, e.g. 'Nairobi, KE'")
    lat: float
    lon: float
    utc_offset_seconds: int = Field(default=0, description="Local time at the location minus UTC")
    activity: str | None = Field(default=None, description="Activity to report on; None for a random pick")
    language: str = Field("en")
    active: bool = Field(default=True)
    token: str = Field(..., index=True, unique=True, description="Secret used to unsubscribe")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_sent_on: str | None = Field(default=None, description="Local date of the last daily alert, YYYY-MM-DD")


@lru_cache
def get_engine():
    """Get the shared database engine, created from settings on first use."""
    return create_engine(
        settings.database_url,
        echo=settings.environment == "development"
    )


def create_tables():
    """Create all tables."""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)

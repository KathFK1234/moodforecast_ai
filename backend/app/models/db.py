"""Database models and schema definitions."""

from datetime import datetime
from sqlmodel import SQLModel, Field, create_engine
from app.config import settings


class Subscriber(SQLModel, table=True):
    """SMS subscriber table."""
    id: str | None = Field(default=None, primary_key=True)
    phone: str = Field(..., index=True, description="E.164 format")
    location: str
    crop: str | None = None
    language: str = Field("en")
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


def get_engine():
    """Create database engine from settings."""
    return create_engine(
        settings.database_url,
        echo=settings.environment == "development"
    )


def create_tables():
    """Create all tables."""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)

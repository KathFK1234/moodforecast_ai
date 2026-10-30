"""Database models and schema definitions."""

from datetime import datetime, timezone
from functools import lru_cache
from sqlalchemy import inspect, text
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
    confirmed: bool = Field(default=False, description="The address was confirmed from an emailed link")
    confirm_requested_at: datetime | None = Field(
        default=None, description="When a subscriber from before confirmation was asked to confirm"
    )


def engine_url(url: str) -> str:
    """
    The database URL with the PostgreSQL driver named.
    
    A bare postgresql:// URL (as Railway provides) means psycopg 3 to
    SQLAlchemy 2.1, but psycopg2 is the driver installed, so name it.
    The older postgres:// spelling is accepted too.
    """
    for scheme in ("postgresql://", "postgres://"):
        if url.startswith(scheme):
            return "postgresql+psycopg2://" + url.removeprefix(scheme)
    return url


def utc_now() -> datetime:
    """The time now, in UTC."""
    return datetime.now(timezone.utc)


def as_utc(moment: datetime) -> datetime:
    """A stored time as UTC; databases without time zones hand it back naive."""
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


class PendingSubscription(SQLModel, table=True):
    """
    A subscription, or a change to one, waiting for its email address to be confirmed.
    
    Nothing but the confirmation email goes to an address until the link in it
    is followed, so nobody can sign someone else up or change their alerts.
    """
    __tablename__ = "alert_pending"
    
    token: str = Field(..., primary_key=True, description="Secret in the confirmation link")
    email: str = Field(..., index=True, description="Lowercase")
    location: str = Field(..., description="As the subscriber typed it")
    place: str = Field(..., description="Resolved display name, e.g. 'Nairobi, KE'")
    lat: float
    lon: float
    utc_offset_seconds: int = Field(default=0)
    activity: str | None = Field(default=None)
    language: str = Field("en")
    created_at: datetime = Field(default_factory=utc_now)


@lru_cache
def get_engine():
    """Get the shared database engine, created from settings on first use."""
    return create_engine(
        engine_url(settings.database_url),
        echo=settings.environment == "development",
        # A connection the database closed while idle is replaced, not handed to a request
        pool_pre_ping=True
    )


# Columns added to alert_subscriber after it went live, with the value existing
# rows get (None: left empty). create_all doesn't change an existing table.
ADDED_SUBSCRIBER_COLUMNS = {"confirmed": "FALSE", "confirm_requested_at": None}


def create_tables():
    """Create all tables, and add any columns an older alert_subscriber table lacks."""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _add_missing_columns(engine)


def _add_missing_columns(engine) -> None:
    """Bring an existing alert_subscriber table up to the model, e.g. after an upgrade."""
    table = Subscriber.__table__
    existing = {column["name"] for column in inspect(engine).get_columns(table.name)}
    with engine.begin() as connection:
        for name, default in ADDED_SUBSCRIBER_COLUMNS.items():
            if name in existing:
                continue
            column_type = table.c[name].type.compile(dialect=engine.dialect)
            ddl = f"ALTER TABLE {table.name} ADD COLUMN {name} {column_type}"
            if default is not None:
                ddl += f" NOT NULL DEFAULT {default}"
            connection.execute(text(ddl))

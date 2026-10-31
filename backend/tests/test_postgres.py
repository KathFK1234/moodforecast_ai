"""Tests against a real PostgreSQL server, where the live site keeps its data.

Skipped unless TEST_DATABASE_URL is set, as it is in CI.
"""

import os
from datetime import timedelta
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select
from app.main import app
from app.models import db
from app.models.db import PendingSubscription, Subscriber, engine_url, utc_now
from app.services import alerts

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not set")

PLACE = {"location": "Nairobi", "place": "Nairobi, KE", "lat": -1.3, "lon": 36.8}


def subscriber(name: str, **overrides) -> Subscriber:
    fields = {"id": name, "email": f"{name}@example.com", "token": f"token-{name}", "confirmed": True}
    return Subscriber(**{**PLACE, **fields, **overrides})


@pytest.fixture
def engine():
    engine = create_engine(engine_url(DATABASE_URL))
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


def test_unused_details_are_deleted(engine):
    now = utc_now()
    old = now - timedelta(hours=alerts.CONFIRM_HOURS + 1)
    with Session(engine) as session:
        session.add(subscriber("keep"))
        session.add(subscriber("waiting", confirmed=False, confirm_requested_at=now))
        session.add(subscriber("left", active=False))
        session.add(subscriber("silent", confirmed=False, confirm_requested_at=old))
        session.add(PendingSubscription(token="old", email="a@example.com", created_at=old, **PLACE))
        session.add(PendingSubscription(token="new", email="b@example.com", **PLACE))
        session.commit()
    
    with patch("app.services.alerts.get_engine", return_value=engine):
        assert alerts.delete_unused_data() == 3
    
    with Session(engine) as session:
        assert {row.id for row in session.exec(select(Subscriber))} == {"keep", "waiting"}
        assert [row.token for row in session.exec(select(PendingSubscription))] == ["new"]


def test_unsubscribing_deletes_the_row(engine):
    with Session(engine) as session:
        session.add(subscriber("amina"))
        session.add(PendingSubscription(token="change", email="amina@example.com", **PLACE))
        session.commit()
    
    with patch("app.routers.subscribe.get_engine", return_value=engine):
        response = TestClient(app).post("/api/unsubscribe/token-amina")
    
    assert response.status_code == 200
    with Session(engine) as session:
        assert session.exec(select(Subscriber)).all() == []
        assert session.exec(select(PendingSubscription)).all() == []


@pytest.mark.parametrize("path", ["/api/confirm/abc%00def", "/api/unsubscribe/abc%00def"])
def test_a_nul_byte_in_a_token_is_a_404_not_a_database_error(engine, path):
    """SQLite shrugs at these; PostgreSQL raises, which is why this runs here."""
    with patch("app.routers.subscribe.get_engine", return_value=engine):
        assert TestClient(app).post(path).status_code == 404


def test_columns_added_since_launch_are_added_to_an_older_table(engine):
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE alert_subscriber DROP COLUMN confirmed"))
    
    with patch("app.models.db.get_engine", return_value=engine):
        db.create_tables()
    
    with Session(engine) as session:
        session.add(subscriber("amina"))
        session.commit()
        assert session.exec(select(Subscriber)).one().confirmed is True

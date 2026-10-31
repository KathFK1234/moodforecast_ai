"""Unit tests for the database URL handling and table upgrades."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from app.config import Settings
from app.models.db import connect_args, create_tables, engine_url, get_engine


@pytest.mark.parametrize("url", [
    "postgresql://user:secret@db.railway.internal:5432/railway",
    "postgres://user:secret@db.railway.internal:5432/railway",
])
def test_postgres_urls_use_the_installed_driver(url):
    """SQLAlchemy 2.1 reads a bare postgresql:// as psycopg 3, which isn't installed."""
    fixed = engine_url(url)
    assert fixed == "postgresql+psycopg2://user:secret@db.railway.internal:5432/railway"
    # Creating the engine loads the driver without connecting
    assert create_engine(fixed).dialect.driver == "psycopg2"


@pytest.mark.parametrize("url", [
    "sqlite:///./moodforecast.db",
    "postgresql+psycopg2://user:secret@localhost/db",
])
def test_other_urls_are_left_alone(url):
    assert engine_url(url) == url


def test_an_older_subscriber_table_gets_the_new_columns(tmp_path):
    """create_all leaves an existing table alone, so create_tables adds what is missing."""
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as connection:
        # alert_subscriber as it was before confirmation
        connection.execute(text(
            "CREATE TABLE alert_subscriber (id VARCHAR PRIMARY KEY, email VARCHAR NOT NULL, "
            "location VARCHAR NOT NULL, place VARCHAR NOT NULL, lat FLOAT NOT NULL, lon FLOAT NOT NULL, "
            "utc_offset_seconds INTEGER NOT NULL, activity VARCHAR, language VARCHAR NOT NULL, "
            "active BOOLEAN NOT NULL, token VARCHAR NOT NULL, created_at DATETIME NOT NULL, last_sent_on VARCHAR)"
        ))
        connection.execute(text(
            "INSERT INTO alert_subscriber VALUES ('old-1', 'amina@example.com', 'nairobi', 'Nairobi, KE', "
            "-1.29, 36.82, 10800, NULL, 'en', 1, 'tok', '2026-10-01 07:00:00', NULL)"
        ))
    
    with patch("app.models.db.get_engine", return_value=engine):
        create_tables()
        create_tables()  # Running again on an up-to-date table changes nothing
    
    columns = {column["name"] for column in inspect(engine).get_columns("alert_subscriber")}
    assert {"confirmed", "confirm_requested_at"} <= columns
    with engine.connect() as connection:
        row = connection.execute(text("SELECT confirmed, confirm_requested_at FROM alert_subscriber")).one()
    # Existing subscribers start unconfirmed, and haven't been asked yet
    assert row == (0, None)


def test_queries_and_their_values_are_not_logged_unless_asked_for():
    assert Settings(_env_file=None).sql_echo is False


@pytest.mark.parametrize("hour", [-1, 24])
def test_an_alert_hour_that_never_comes_is_refused(hour):
    with pytest.raises(ValidationError):
        Settings(alert_hour=hour, _env_file=None)


def test_postgresql_connections_give_up_rather_than_hang():
    assert connect_args(engine_url("postgres://u:p@db/x")) == {"connect_timeout": 10}


def test_sqlite_is_not_given_a_postgresql_option():
    assert connect_args("sqlite:///./moodforecast.db") == {}


def test_a_failed_query_doesnt_put_its_values_in_the_error(monkeypatch, tmp_path):
    monkeypatch.setattr("app.models.db.settings.database_url", f"sqlite:///{tmp_path / 'test.db'}")
    get_engine.cache_clear()
    try:
        with get_engine().connect() as connection, pytest.raises(OperationalError) as failure:
            connection.execute(text("SELECT * FROM no_such_table WHERE email = :email"), {"email": "amina@example.com"})
    finally:
        get_engine.cache_clear()
    assert "amina@example.com" not in str(failure.value)

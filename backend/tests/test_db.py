"""Unit tests for the database URL handling."""

import pytest
from sqlalchemy import create_engine
from app.models.db import engine_url


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

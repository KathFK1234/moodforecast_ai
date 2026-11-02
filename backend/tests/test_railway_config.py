"""railway.toml must stay something Railway acts on: it ignores keys it doesn't know, without a word."""

import tomllib
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
CONFIG = tomllib.loads((BACKEND / "railway.toml").read_text())
# The keys in use today from Railway's published schema, https://railway.com/railway.schema.json
KNOWN_KEYS = {
    "build": {"builder", "dockerfilePath", "watchPatterns"},
    "deploy": {
        "startCommand", "healthcheckPath", "healthcheckTimeout", "drainingSeconds",
        "restartPolicyType", "restartPolicyMaxRetries", "numReplicas",
    },
}


def test_only_keys_railway_knows():
    assert set(CONFIG) <= set(KNOWN_KEYS)
    for section, keys in CONFIG.items():
        assert set(keys) <= KNOWN_KEYS[section], f"[{section}] has a key Railway would ignore"


def test_health_check_points_at_the_health_route_and_outlasts_the_database_timeout():
    from app.models.db import DB_CONNECT_TIMEOUT_SECONDS
    
    assert CONFIG["deploy"]["healthcheckPath"] == "/health"
    assert CONFIG["deploy"]["healthcheckTimeout"] > DB_CONNECT_TIMEOUT_SECONDS


def test_start_command_matches_the_docker_image():
    """Once Railway stops reading this file the image's own CMD runs, which must behave the same."""
    assert CONFIG["deploy"]["startCommand"].removeprefix("sh -c '").removesuffix("'") in (BACKEND / "Dockerfile").read_text()

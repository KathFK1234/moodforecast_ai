""".railway/railway.ts must keep the settings the app depends on on Railway (see DEPLOYMENT_GUIDE.md)."""

import re
from pathlib import Path

from app.models.db import DB_CONNECT_TIMEOUT_SECONDS

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
IAC = (REPO / ".railway" / "railway.ts").read_text()
DOCKERFILE = (BACKEND / "Dockerfile").read_text()


def setting(name: str) -> str:
    match = re.search(rf"\b{name}:\s*(\"[^\"]*\"|[0-9]+)", IAC)
    assert match, f"{name} is missing from .railway/railway.ts"
    return match.group(1).strip('"')


def test_old_config_file_is_gone():
    """Railway stops reading it on 2026-12-01, and a service can't be managed by both."""
    assert not (BACKEND / "railway.toml").exists()
    assert not (REPO / "railway.toml").exists()


def test_builds_the_dockerfile_from_backend():
    assert setting("builder") == "DOCKERFILE"
    assert setting("rootDirectory") == "/backend"


def test_health_check_points_at_the_health_route_and_outlasts_the_database_timeout():
    assert setting("healthcheck") == "/health"
    assert int(setting("healthcheckTimeout")) > DB_CONNECT_TIMEOUT_SECONDS


def test_draining_outlasts_uvicorns_graceful_shutdown():
    graceful = int(re.search(r"--timeout-graceful-shutdown (\d+)", DOCKERFILE).group(1))
    assert int(setting("drainingSeconds")) > graceful


def test_start_command_matches_the_docker_image():
    """Without a start command on Railway the image's own CMD runs, which must behave the same."""
    start = re.search(r"\bstart:\s*\"(.*)\",", IAC).group(1)
    assert start.removeprefix("sh -c '").removesuffix("'") in DOCKERFILE


def test_variables_stay_out_of_the_file():
    """Secrets such as BREVO_API_KEY stay in Railway's dashboard, never in the repository."""
    assert "managed: false" in IAC
    assert not re.search(r"\b(env|variables)\s*:\s*\{(?!\s*managed: false)", IAC)

"""Guard against frontend/ and backend/app/static/ drifting apart."""

from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = REPO_ROOT / "frontend"
STATIC_DIR = REPO_ROOT / "backend" / "app" / "static"


@pytest.mark.skipif(not FRONTEND_DIR.exists(), reason="frontend/ not available (e.g. Docker image)")
def test_static_matches_frontend():
    """backend/app/static is the deployed copy of frontend/ - they must be identical."""
    for static_file in STATIC_DIR.iterdir():
        source = FRONTEND_DIR / static_file.name
        assert source.exists(), f"{static_file.name} is missing from frontend/"
        assert source.read_bytes() == static_file.read_bytes(), (
            f"{static_file.name} differs - copy frontend/{static_file.name} to backend/app/static/"
        )

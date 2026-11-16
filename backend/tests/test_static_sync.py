"""Guard against frontend/ and backend/app/static/ drifting apart."""

import base64
import hashlib
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


def test_the_map_library_is_the_published_leaflet_1_9_4():
    """leaflet.js and leaflet.css are served from here; they must stay byte for byte as released."""
    published = {
        # The SRI hashes leafletjs.com gives for 1.9.4, which match the npm tarball
        "leaflet.js": "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=",
        "leaflet.css": "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=",
    }
    for name, digest in published.items():
        data = (STATIC_DIR / name).read_bytes()
        assert "sha256-" + base64.b64encode(hashlib.sha256(data).digest()).decode() == digest, name
    assert "Copyright (c) 2010-2023, Volodymyr Agafonkin" in (STATIC_DIR / "leaflet-LICENSE.txt").read_text()

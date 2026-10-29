"""constraints.txt must keep up with the requirements files."""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def pins(filename: str) -> dict[str, str]:
    """name -> version for each 'name[extras]==version' line, names normalised."""
    found = {}
    for line in (BACKEND / filename).read_text().splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?==([^\s;]+)", line.strip())
        if match:
            found[re.sub(r"[-_.]+", "-", match.group(1)).lower()] = match.group(2)
    return found


def test_every_requirement_is_constrained_to_the_same_version():
    """After changing requirements.txt or requirements-dev.txt, refresh constraints.txt (see its header)."""
    requirements = pins("requirements.txt") | pins("requirements-dev.txt")
    constraints = pins("constraints.txt")
    assert {"fastapi", "pytest"} <= set(requirements)
    for name, version in requirements.items():
        assert constraints.get(name) == version, f"{name}: requirements {version}, constraints {constraints.get(name)}"


def test_the_docker_image_does_not_install_the_test_tools():
    runtime = pins("requirements.txt")
    assert "pytest" not in runtime
    assert "pytest-asyncio" not in runtime

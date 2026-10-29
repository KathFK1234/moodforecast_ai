"""constraints.txt must keep up with requirements.txt."""

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
    """After changing requirements.txt, refresh constraints.txt (see its header)."""
    requirements = pins("requirements.txt")
    constraints = pins("constraints.txt")
    assert requirements
    for name, version in requirements.items():
        assert constraints.get(name) == version, f"{name}: requirements {version}, constraints {constraints.get(name)}"

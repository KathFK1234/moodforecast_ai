"""Numbers in text match the figures the page rounds itself."""

import pytest
from app.services.mood_engine import build_summary, score_mood
from app.services.numbers import shown


# What JavaScript's Math.round gives, as the page shows the temperature
@pytest.mark.parametrize("value, page", [
    (22.5, 23), (23.5, 24), (0.5, 1), (-2.5, -2), (-3.5, -3), (-0.5, 0), (22.4, 22), (22.6, 23), (18, 18),
])
def test_halves_go_up_as_on_the_page(value, page):
    assert shown(value) == page


def test_the_summary_gives_the_temperature_the_page_shows():
    mood = score_mood("Clear", 22.5, 50)
    summary = build_summary("Nairobi, KE", "Clear", 22.5, mood["mood_score"], mood["factors"])
    assert summary.startswith("Clear and 23°C in Nairobi, KE.")

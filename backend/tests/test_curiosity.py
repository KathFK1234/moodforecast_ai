"""Unit tests for the curiosity prompts - no I/O dependencies."""

import random

from app.services import curiosity
from app.services.curiosity import curiosity_prompts, pick_places


class TestCuriosityPrompts:
    """Test the questions about other places."""

    def test_returns_the_requested_number_of_different_places(self):
        prompts = curiosity_prompts("Nairobi, KE", "Cloudy", 20)
        assert len(prompts) == 3
        assert len({p["location"] for p in prompts}) == 3

    def test_each_question_names_its_place(self):
        for prompt in curiosity_prompts("Nairobi, KE", "Rain", 20, count=5):
            assert prompt["location"] in prompt["question"]
            assert "{place}" not in prompt["question"]

    def test_never_suggests_the_place_being_viewed(self):
        for seed in range(50):
            prompts = curiosity_prompts(
                "Reykjavik, IS", "Clear", 35, count=6, rng=random.Random(seed)
            )
            assert all(p["location"] != "Reykjavik" for p in prompts)

    def test_never_suggests_the_place_as_the_user_typed_it(self):
        """The resolved name can be in another script, so the typed name counts too."""
        for seed in range(50):
            prompts = curiosity_prompts(
                "東京都, JP", "Cloudy", 20, count=6, rng=random.Random(seed), searched_as="tokyo"
            )
            assert all(p["location"] != "Tokyo" for p in prompts)

    def test_heat_points_to_somewhere_cold(self):
        prompts = curiosity_prompts("Dubai, AE", "Cloudy", 40, count=2)
        assert any(p["location"] in curiosity.COLD_PLACES for p in prompts)

    def test_cold_points_to_somewhere_warm(self):
        prompts = curiosity_prompts("Oslo, NO", "Cloudy", -3, count=2)
        assert any(p["location"] in curiosity.WARM_PLACES for p in prompts)

    def test_rain_points_to_somewhere_dry(self):
        prompts = curiosity_prompts("Bergen, NO", "Light Rain", 15, count=2)
        assert any(p["location"] in curiosity.DRY_PLACES for p in prompts)

    def test_night_asks_about_daylight_elsewhere(self):
        prompts = curiosity_prompts("Nairobi, KE", "Cloudy", 20, is_day=False, count=1)
        templates = [q.split("{place}")[0] for q in curiosity.NIGHT_QUESTIONS]
        assert any(prompts[0]["question"].startswith(t) for t in templates)

    def test_seeded_rng_gives_repeatable_prompts(self):
        first = curiosity_prompts("Nairobi, KE", "Clear", 30, rng=random.Random(3))
        second = curiosity_prompts("Nairobi, KE", "Clear", 30, rng=random.Random(3))
        assert first == second


class TestPickPlaces:
    """Test choosing places to suggest."""

    def test_leaves_out_the_current_location(self):
        picked = pick_places(("Mombasa", "Zanzibar"), "Mombasa, KE", 2)
        assert picked == ["Zanzibar"]

    def test_no_duplicates(self):
        picked = pick_places(curiosity.WORLD_PLACES, "Nairobi, KE", 5)
        assert len(set(picked)) == 5

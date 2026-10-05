"""Unit tests for the activity advisor - no I/O dependencies."""

import random

import pytest
from app.services import activity_advisor
from app.services.activity_advisor import ACTIVITIES, check_activity, find_activity


def advise(question, condition="Clear", temp=22, humidity=50, wind=10, is_day=True, location="Nairobi, KE"):
    return check_activity(question, location, condition, temp, humidity, wind, is_day)


class TestFindActivity:
    """Test picking the activity out of a question."""
    
    @pytest.mark.parametrize("question,expected", [
        ("run", "running"),
        ("Can I go for a run?", "running"),
        ("Is it a good day for a PICNIC", "a picnic"),
        ("nyama choma with friends", "a barbecue"),
        ("should we play a board game", "games"),
        ("go to the beach", "swimming"),
        ("look at the stars", "stargazing"),
        ("fly a kite", "kite flying"),
    ])
    def test_recognises_activities_in_free_text(self, question, expected):
        assert find_activity(question).name == expected
    
    def test_matches_whole_words_only(self):
        """'run' should not be found inside 'brunch'."""
        assert find_activity("brunch") is None
    
    def test_unknown_activity(self):
        assert find_activity("underwater basket weaving") is None
    
    def test_no_alias_belongs_to_two_activities(self):
        aliases = [alias for activity in ACTIVITIES for alias in activity.aliases]
        assert len(aliases) == len(set(aliases))


class TestVerdicts:
    """Test the weather rules behind each verdict."""
    
    def test_good_weather_is_a_go(self):
        advice = advise("run")
        assert advice["verdict"] == "go"
        assert advice["suggestion"] is None
        assert len(advice["reasons"]) == 1
    
    def test_thunderstorm_rules_out_anything_outdoors(self):
        for question in ["run", "picnic", "swim", "ski", "stargaze", "kite"]:
            assert advise(question, condition="Thunderstorm")["verdict"] == "skip"
    
    def test_rain_is_a_caveat_for_a_run_but_spoils_a_picnic(self):
        assert advise("run", condition="Light Rain")["verdict"] == "maybe"
        assert advise("picnic", condition="Light Rain")["verdict"] == "skip"
    
    def test_extreme_heat_rules_out_exercise(self):
        assert advise("cycling", temp=38)["verdict"] == "skip"
        assert advise("cycling", temp=32)["verdict"] == "maybe"
    
    def test_swimming_needs_warmth(self):
        assert advise("swim", temp=28)["verdict"] == "go"
        assert advise("swim", temp=18)["verdict"] == "maybe"
        assert advise("swim", temp=8)["verdict"] == "skip"
    
    def test_snow_sports_need_snow(self):
        assert advise("ski", condition="Snow Showers", temp=-2)["verdict"] == "go"
        assert advise("ski", condition="Clear", temp=-5)["verdict"] == "maybe"
        assert advise("ski", condition="Clear", temp=20)["verdict"] == "skip"
    
    def test_stargazing_needs_a_clear_night(self):
        assert advise("stargazing", condition="Clear", is_day=False)["verdict"] == "go"
        assert advise("stargazing", condition="Partly Cloudy", is_day=False)["verdict"] == "maybe"
        assert advise("stargazing", condition="Overcast", is_day=False)["verdict"] == "skip"
        assert advise("stargazing", condition="Clear", is_day=True)["verdict"] == "maybe"
        assert advise("stargazing", condition="Overcast", is_day=True)["verdict"] == "skip"
    
    def test_kites_need_some_wind_but_not_too_much(self):
        assert advise("kite", wind=3)["verdict"] == "skip"
        assert advise("kite", wind=10)["verdict"] == "maybe"
        assert advise("kite", wind=20)["verdict"] == "go"
        assert advise("kite", wind=40)["verdict"] == "maybe"
        assert advise("kite", wind=55)["verdict"] == "skip"
    
    def test_strong_wind_affects_other_outdoor_plans(self):
        assert advise("picnic", wind=40)["verdict"] == "maybe"
        assert advise("picnic", wind=65)["verdict"] == "skip"
    
    def test_darkness_is_a_caveat_unless_the_activity_suits_the_night(self):
        assert advise("run", is_day=False)["verdict"] == "maybe"
        assert advise("barbecue", is_day=False)["verdict"] == "go"
    
    def test_indoor_activities_are_always_a_go(self):
        for condition, temp in [("Thunderstorm", 5), ("Clear", 40), ("Heavy Snow", -10)]:
            assert advise("read a book", condition=condition, temp=temp)["verdict"] == "go"
    
    def test_every_activity_gets_an_answer_in_any_weather(self):
        for activity in ACTIVITIES:
            for condition in ["Clear", "Partly Cloudy", "Overcast", "Fog", "Light Drizzle", "Rain", "Snow", "Thunderstorm"]:
                for temp in [-10, 3, 12, 20, 28, 33, 40]:
                    for wind in [0, 10, 40, 70]:
                        for is_day in [True, False]:
                            advice = advise(activity.aliases[0], condition, temp, 85, wind, is_day)
                            assert advice["activity"] == activity.name
                            assert advice["verdict"] in ("go", "maybe", "skip")
                            assert advice["reasons"]
                            assert "{" not in advice["headline"]


class TestAdvice:
    """Test what comes back alongside the verdict."""
    
    def test_unrecognised_activity_is_judged_as_time_outdoors(self):
        advice = advise("underwater basket weaving")
        assert advice["recognised"] is False
        assert advice["activity"] == "time outdoors"
        assert advice["verdict"] == "go"
        assert "don't know that one" in advice["reasons"][0]
    
    def test_a_no_comes_with_something_to_do_instead(self):
        advice = advise("picnic", condition="Rain")
        assert advice["suggestion"] in activity_advisor.INDOOR_SWAPS
    
    def test_headline_names_the_activity(self):
        assert "a picnic" in advise("picnic")["headline"]
    
    def test_curiosity_points_to_places_that_suit_the_activity(self):
        advice = advise("ski", temp=25)
        assert len(advice["curiosity"]["places"]) == 3
        assert all(p in activity_advisor.curiosity.SNOW_PLACES for p in advice["curiosity"]["places"])
        assert "snow sports" in advice["curiosity"]["question"]
    
    def test_curiosity_leaves_out_the_current_location(self):
        for seed in range(30):
            advice = check_activity(
                "swim", "Mombasa, KE", "Clear", 30, 60, 10, rng=random.Random(seed)
            )
            assert "Mombasa" not in advice["curiosity"]["places"]
    
    def test_curiosity_leaves_out_the_location_as_the_user_typed_it(self):
        for seed in range(30):
            advice = check_activity(
                "ski", "札幌市, JP", "Snow", -3, 80, 10,
                rng=random.Random(seed), searched_as="Sapporo"
            )
            assert "Sapporo" not in advice["curiosity"]["places"]
    
    def test_seeded_rng_gives_repeatable_advice(self):
        first = check_activity("run", "Nairobi, KE", "Rain", 15, 85, 10, rng=random.Random(5))
        second = check_activity("run", "Nairobi, KE", "Rain", 15, 85, 10, rng=random.Random(5))
        assert first == second

"""Unit tests for the activity advisor - no I/O dependencies."""

import random

import pytest
from app.services import activity_advisor
from app.services.activity_advisor import (
    ACTIVITIES, check_activity, find_activity, local_activities, random_activity
)
from app.services.locality import Place


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
        ("go to the beach", "a beach day"),
        ("a dip in the pool", "swimming"),
        ("catch some waves and surf", "surfing"),
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


class TestRandomActivity:
    """Test the random pick."""
    
    def pick(self, seed, condition="Clear", temp=22, wind=10, is_day=True, exclude=""):
        return random_activity(
            "Nairobi, KE", condition, temp, 50, wind, is_day,
            rng=random.Random(seed), exclude=exclude
        )
    
    def test_pick_always_suits_the_weather(self):
        for condition, temp, wind, is_day in [
            ("Clear", 22, 10, True), ("Thunderstorm", 15, 50, True), ("Snow", -4, 5, True),
            ("Clear", 38, 5, True), ("Overcast", 12, 70, False), ("Clear", 18, 20, False),
        ]:
            for seed in range(40):
                advice = self.pick(seed, condition, temp, wind, is_day)
                assert advice["verdict"] == "go"
                assert advice["recognised"] is True
                assert advice["suggestion"] is None
    
    def test_storm_only_offers_indoor_activities(self):
        indoor = {a.name for a in ACTIVITIES if a.category == "indoor"}
        assert {self.pick(seed, "Thunderstorm")["activity"] for seed in range(60)} <= indoor
    
    def test_good_weather_mostly_offers_outdoor_activities(self):
        indoor = {a.name for a in ACTIVITIES if a.category == "indoor"}
        picks = [self.pick(seed)["activity"] for seed in range(200)]
        assert sum(pick not in indoor for pick in picks) > 120
        assert len(set(picks)) > 8
    
    def test_snow_and_clear_nights_bring_out_their_specials(self):
        assert "snow sports" in {self.pick(seed, "Snow", -3)["activity"] for seed in range(100)}
        assert "stargazing" in {self.pick(seed, is_day=False)["activity"] for seed in range(100)}
    
    def test_exclude_gives_a_different_pick(self):
        for seed in range(40):
            first = self.pick(seed)["activity"]
            assert self.pick(seed, exclude=first)["activity"] != first
    
    def test_pick_comes_with_a_pitch(self):
        advice = self.pick(1)
        assert advice["reasons"][-1] == activity_advisor.PITCHES[advice["activity"]]
        assert advice["activity"] in advice["headline"]
    
    def test_every_activity_has_a_pitch(self):
        assert set(activity_advisor.PITCHES) == {a.name for a in ACTIVITIES}
    
    def test_every_activity_has_a_prompt(self):
        assert all(a.prompt for a in ACTIVITIES)
    
    def test_local_pitches_and_favourites_name_real_activities(self):
        names = {a.name for a in ACTIVITIES}
        assert {activity for activity, _ in activity_advisor.LOCAL_PITCHES} <= names
        for favourites in activity_advisor.LOCAL_FAVOURITES.values():
            assert set(favourites) <= names


NAIROBI = Place(name="Nairobi", country="KE", lat=-1.29, elevation=1668, coastal=False)
MOMBASA = Place(name="Mombasa", country="KE", lat=-4.05, elevation=19, coastal=True, sea_temp_c=27.6)
CAPE_TOWN = Place(name="Cape Town", country="ZA", lat=-33.92, elevation=24, coastal=True, sea_temp_c=14.4)
INNSBRUCK = Place(name="Innsbruck", country="AT", lat=47.27, elevation=574, coastal=False)
MUMBAI = Place(name="Mumbai", country="IN", lat=19.08, elevation=8, coastal=True, sea_temp_c=28.5)
UNKNOWN = Place(name="Somewhere")


def advise_at(place, question, condition="Clear", temp=24, wind=15, is_day=True, seed=1):
    return check_activity(
        question, f"{place.name}, {place.country}", condition, temp, 50, wind, is_day,
        rng=random.Random(seed), place=place
    )


class TestLocalFit:
    """Test that advice fits the place, not just the weather."""
    
    def test_sea_activities_are_ruled_out_inland(self):
        for question in ["beach", "surf", "snorkel", "sailing"]:
            advice = advise_at(NAIROBI, question)
            assert advice["verdict"] == "skip"
            assert advice["reasons"] == [
                f"Nairobi isn't on the coast, so {advice['activity']} would mean a trip to the sea first."
            ]
    
    def test_sea_activities_work_on_the_coast(self):
        assert advise_at(MOMBASA, "beach")["verdict"] == "go"
        assert "with the sea at 28°C" in advise_at(MOMBASA, "beach")["reasons"][0]
        assert advise_at(MOMBASA, "snorkel")["verdict"] == "go"
    
    def test_swimming_is_fine_anywhere(self):
        """A pool doesn't need a coast."""
        assert advise_at(NAIROBI, "swim")["verdict"] == "go"
    
    def test_cold_sea_rules_out_snorkelling_and_needs_a_wetsuit_otherwise(self):
        assert advise_at(CAPE_TOWN, "snorkel")["verdict"] == "skip"
        surf = advise_at(CAPE_TOWN, "surf")
        assert surf["verdict"] == "maybe"
        assert surf["reasons"] == ["The sea is 14°C — a wetsuit will make all the difference."]
    
    def test_snow_sports_need_snow_country(self):
        advice = advise_at(NAIROBI, "ski", temp=-2)
        assert advice["verdict"] == "skip"
        assert "aren't something people do around Nairobi" in advice["reasons"][0]
        # In the Alps the answer depends on the weather again
        assert advise_at(INNSBRUCK, "ski", condition="Snow", temp=-2)["verdict"] == "go"
        assert advise_at(INNSBRUCK, "ski", temp=-2)["verdict"] == "maybe"
    
    def test_snow_falling_makes_snow_play_possible_anywhere(self):
        assert advise_at(NAIROBI, "build a snowman", condition="Snow", temp=-1)["verdict"] == "go"
    
    def test_low_warm_parts_of_a_skiing_country_do_not_count(self):
        sydney = Place(name="Sydney", country="AU", lat=-33.87, elevation=40, coastal=True)
        assert advise_at(sydney, "ski")["verdict"] == "skip"
    
    def test_uncommon_sports_get_a_caveat_not_a_refusal(self):
        advice = advise_at(NAIROBI, "cricket")
        assert advice["verdict"] == "maybe"
        assert "isn't widely played around Nairobi" in advice["reasons"][0]
        assert advise_at(MUMBAI, "cricket")["verdict"] == "go"
    
    def test_place_refusal_suggests_something_that_works_there(self):
        practical = {a.name for a in local_activities(NAIROBI)}
        for seed in range(30):
            suggestion = advise_at(NAIROBI, "surf", seed=seed)["suggestion"]
            assert suggestion.startswith("Something that does work in Nairobi right now: ")
            assert any(f": {name}. " in suggestion for name in practical)
    
    def test_unknown_facts_get_the_benefit_of_the_doubt_when_asked(self):
        assert advise_at(UNKNOWN, "beach")["verdict"] == "go"
        assert advise_at(UNKNOWN, "cricket")["verdict"] == "go"


class TestLocalActivities:
    """Test which activities are offered for a place."""
    
    def test_inland_kenya(self):
        names = [a.name for a in local_activities(NAIROBI)]
        for absent in ["a beach day", "surfing", "snorkelling", "sailing", "snow sports", "cricket", "baseball", "golf"]:
            assert absent not in names
        for present in ["running", "football", "a barbecue", "hiking", "rugby", "swimming", "reading"]:
            assert present in names
    
    def test_local_favourites_come_first(self):
        names = [a.name for a in local_activities(NAIROBI)]
        assert set(names[:5]) == {"running", "football", "a barbecue", "hiking", "rugby"}
    
    def test_coast_adds_sea_activities(self):
        names = {a.name for a in local_activities(MOMBASA)}
        assert {"a beach day", "snorkelling", "sailing"} <= names
    
    def test_surfing_needs_a_surfing_country_as_well_as_a_coast(self):
        assert "surfing" not in {a.name for a in local_activities(MOMBASA)}
        assert "surfing" in {a.name for a in local_activities(CAPE_TOWN)}
        asked = advise_at(MOMBASA, "surf")
        assert asked["verdict"] == "maybe"
        assert "isn't a big thing around Mombasa" in asked["reasons"][0]
    
    def test_cold_sea_leaves_out_snorkelling(self):
        names = {a.name for a in local_activities(CAPE_TOWN)}
        assert "surfing" in names
        assert "snorkelling" not in names
    
    def test_alps_offer_snow_sports(self):
        assert "snow sports" in {a.name for a in local_activities(INNSBRUCK)}
    
    def test_unknown_place_offers_nothing_that_needs_confirming(self):
        assert all(not a.needs for a in local_activities(UNKNOWN))
    
    def test_no_place_means_everything(self):
        assert local_activities(None) == list(ACTIVITIES)


class TestLocalRandomActivity:
    """Test that random picks fit the place."""
    
    def picks(self, place, condition="Clear", temp=24, wind=15, is_day=True, count=300):
        return [
            random_activity(
                f"{place.name}, {place.country}", condition, temp, 50, wind, is_day,
                rng=random.Random(seed), place=place
            )
            for seed in range(count)
        ]
    
    def test_never_picks_what_the_place_cannot_offer(self):
        practical = {a.name for a in local_activities(NAIROBI)}
        assert {advice["activity"] for advice in self.picks(NAIROBI)} <= practical
        # Even with snow-sport temperatures and kite-surfing wind
        cold = {advice["activity"] for advice in self.picks(NAIROBI, temp=-3, wind=25)}
        assert not cold & {"snow sports", "sailing", "surfing", "a beach day"}
    
    def test_coast_brings_out_the_sea(self):
        picked = {advice["activity"] for advice in self.picks(MOMBASA, temp=29)}
        assert picked & {"a beach day", "surfing", "snorkelling", "sailing"}
    
    def test_local_favourites_come_up_more_often(self):
        names = [advice["activity"] for advice in self.picks(NAIROBI, count=600)]
        assert names.count("running") > names.count("tennis") * 1.5
    
    def test_pitch_uses_the_local_idiom(self):
        def barbecue_pitch(place):
            return next(
                advice["reasons"][-1] for advice in self.picks(place, count=600)
                if advice["activity"] == "a barbecue"
            )
        
        london = Place(name="London", country="GB", lat=51.5, elevation=16, coastal=False)
        assert "nyama choma" in barbecue_pitch(NAIROBI)
        assert "nyama choma" not in barbecue_pitch(london)


class TestLateNightPicks:
    """Test that random picks suit the hour."""
    
    def picks(self, hour, condition="Clear"):
        place = NAIROBI._replace(local_hour=hour)
        return {
            random_activity(
                "Nairobi, KE", condition, 18, 50, 8, False, rng=random.Random(seed), place=place
            )["activity"]
            for seed in range(200)
        }
    
    def test_small_hours_only_get_quiet_picks(self):
        for hour in [23, 0, 2, 4]:
            assert self.picks(hour) <= set(activity_advisor.LATE_NIGHT_PICKS)
        # Stargazing drops out when the sky is covered
        assert "stargazing" not in self.picks(2, "Overcast")
        assert "stargazing" in self.picks(2)
    
    def test_evening_still_gets_evening_activities(self):
        assert "a barbecue" in self.picks(20)
    
    def test_asking_is_not_restricted_by_the_hour(self):
        place = NAIROBI._replace(local_hour=2)
        advice = check_activity("barbecue", "Nairobi, KE", "Clear", 18, 50, 8, False, place=place)
        assert advice["verdict"] == "go"

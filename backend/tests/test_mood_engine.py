"""Unit tests for mood engine - no I/O dependencies."""

import random

import pytest
from app.services import mood_engine
from app.services.mood_engine import (
    BASELINE_SCORE,
    build_summary,
    calculate_mood_score,
    classify_mood_label,
    mood_factors,
    classify_energy_level,
    classify_risk_level,
    generate_recommendations,
    score_mood
)


class TestMoodScoring:
    """Test mood score calculation."""
    
    def test_neutral_baseline(self):
        """Neutral conditions should score around baseline."""
        score = calculate_mood_score("Cloudy", 20, 50)
        assert 60 <= score <= 70  # Close to 65 baseline
    
    def test_sunny_boosts_score(self):
        """Sunny weather should increase score."""
        sunny_score = calculate_mood_score("Sunny", 20, 50)
        cloudy_score = calculate_mood_score("Cloudy", 20, 50)
        assert sunny_score > cloudy_score
    
    def test_rainy_reduces_score(self):
        """Rainy weather should decrease score."""
        rainy_score = calculate_mood_score("Rainy", 20, 50)
        sunny_score = calculate_mood_score("Sunny", 20, 50)
        assert rainy_score < sunny_score
    
    def test_stormy_very_negative(self):
        """Stormy weather with extreme conditions should significantly reduce score."""
        # Stormy: -20, Cold temp (5C): -5, High humidity (85%): -8
        # 65 - 20 - 5 - 8 = 32 (< 50)
        stormy_score = calculate_mood_score("Stormy", 5, 85)
        assert stormy_score < 50
    
    def test_optimal_temperature_bonus(self):
        """Temperature 18-24°C should get bonus."""
        optimal = calculate_mood_score("Cloudy", 21, 50)
        cold = calculate_mood_score("Cloudy", 5, 50)
        assert optimal > cold
    
    def test_extreme_temperature_penalty(self):
        """Extreme temperatures should reduce score."""
        extreme_cold = calculate_mood_score("Cloudy", 5, 50)
        extreme_hot = calculate_mood_score("Cloudy", 40, 50)
        moderate = calculate_mood_score("Cloudy", 20, 50)
        assert extreme_cold < moderate
        assert extreme_hot < moderate
    
    def test_high_humidity_penalty(self):
        """High humidity (>80%) should reduce score."""
        high_humidity = calculate_mood_score("Cloudy", 20, 85)
        low_humidity = calculate_mood_score("Cloudy", 20, 50)
        assert high_humidity < low_humidity
    
    def test_score_clamped_to_range(self):
        """Score must be between 0 and 100."""
        extreme_positive = calculate_mood_score("Sunny", 21, 30)
        extreme_negative = calculate_mood_score("Stormy", 5, 95)
        assert 0 <= extreme_positive <= 100
        assert 0 <= extreme_negative <= 100


class TestEnergyLevelClassification:
    """Test energy level classification."""
    
    def test_high_energy(self):
        assert classify_energy_level(75) == "High"
        assert classify_energy_level(100) == "High"
    
    def test_medium_energy(self):
        assert classify_energy_level(50) == "Medium"
        assert classify_energy_level(62) == "Medium"
        assert classify_energy_level(74) == "Medium"
    
    def test_low_energy(self):
        assert classify_energy_level(25) == "Low"
        assert classify_energy_level(40) == "Low"
        assert classify_energy_level(49) == "Low"
    
    def test_very_low_energy(self):
        assert classify_energy_level(0) == "Very Low"
        assert classify_energy_level(10) == "Very Low"
        assert classify_energy_level(24) == "Very Low"


class TestRiskLevelClassification:
    """Test risk level classification."""
    
    def test_minimal_risk(self):
        assert classify_risk_level(75) == "Minimal"
        assert classify_risk_level(100) == "Minimal"
    
    def test_low_risk(self):
        assert classify_risk_level(50) == "Low"
        assert classify_risk_level(62) == "Low"
    
    def test_moderate_risk(self):
        assert classify_risk_level(25) == "Moderate"
        assert classify_risk_level(40) == "Moderate"
    
    def test_high_risk(self):
        assert classify_risk_level(0) == "High"
        assert classify_risk_level(10) == "High"


class TestRecommendationGeneration:
    """Test wellbeing recommendation generation."""
    
    def test_sunny_recommendations(self):
        """Sunny weather should suggest something from the clear-day pool."""
        recs = generate_recommendations(75, "Sunny", 22, 50)
        assert recs[0] in mood_engine.CLEAR_DAY_IDEAS
    
    def test_hot_sun_avoids_exertion_in_full_sun(self):
        """Above 30°C a clear day should not suggest runs or picnics."""
        recs = generate_recommendations(60, "Sunny", 36, 50)
        assert recs[0] in mood_engine.HOT_SUN_IDEAS
        assert recs[1] in mood_engine.HOT_IDEAS
    
    def test_rainy_recommendations(self):
        """Rainy weather should suggest something from the rain pool."""
        recs = generate_recommendations(50, "Rainy", 18, 70)
        assert recs[0] in mood_engine.RAIN_IDEAS
    
    def test_storm_and_snow_have_their_own_ideas(self):
        assert generate_recommendations(40, "Thunderstorm", 18, 70)[0] in mood_engine.STORM_IDEAS
        assert generate_recommendations(40, "Snow Showers", 0, 70)[0] in mood_engine.SNOW_IDEAS
    
    def test_extreme_cold_recommendations(self):
        """Cold weather should suggest warmth."""
        recs = generate_recommendations(30, "Cloudy", 5, 50)
        assert any(r in mood_engine.COLD_IDEAS for r in recs)
        assert all("warm" in r.lower() or "cold" in r.lower() for r in mood_engine.COLD_IDEAS)
    
    def test_high_humidity_recommendations(self):
        """High humidity should mention hydration."""
        recs = generate_recommendations(50, "Cloudy", 28, 85)
        assert any(r in mood_engine.HUMID_IDEAS for r in recs)
        assert all("hydration" in r.lower() or "water" in r.lower() for r in mood_engine.HUMID_IDEAS)
    
    def test_low_mood_includes_wellness(self):
        """Low mood should add a pick-me-up."""
        recs = generate_recommendations(30, "Stormy", 10, 80)
        assert recs[-1] in mood_engine.LOW_MOOD_IDEAS
    
    def test_recommendations_vary(self):
        """The same weather should not always give the same advice."""
        seen = {generate_recommendations(75, "Sunny", 22, 50)[0] for _ in range(200)}
        assert len(seen) > 1
    
    def test_seeded_rng_gives_repeatable_picks(self):
        first = generate_recommendations(40, "Rain", 15, 85, rng=random.Random(7))
        second = generate_recommendations(40, "Rain", 15, 85, rng=random.Random(7))
        assert first == second


class TestFullMoodEngine:
    """Integration tests for complete mood engine."""
    
    def test_score_mood_returns_all_fields(self):
        """Full mood engine should return all required fields."""
        result = score_mood("Sunny", 22, 60)
        assert "mood_score" in result
        assert "energy_level" in result
        assert "risk_level" in result
        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)
    
    def test_score_mood_consistency(self):
        """Same weather should produce same score."""
        result1 = score_mood("Cloudy", 20, 70)
        result2 = score_mood("Cloudy", 20, 70)
        assert result1["mood_score"] == result2["mood_score"]
        assert result1["energy_level"] == result2["energy_level"]


class TestMoodFactors:
    """Test the breakdown behind the score."""
    
    def test_factors_add_up_to_score(self):
        """Baseline plus factor deltas should equal the score."""
        factors = mood_factors("Rain", 15, 85)
        score = calculate_mood_score("Rain", 15, 85)
        assert score == BASELINE_SCORE + sum(f["delta"] for f in factors)
        assert [f["label"] for f in factors] == ["Rain", "Cool air", "High humidity"]
    
    def test_neutral_conditions_have_no_factors(self):
        """Unknown condition in a neutral temperature gap should not move the score."""
        assert mood_factors("Unknown", 17.99, 50) == [{"label": "Cool air", "delta": -5}]
        assert mood_factors("Unknown", 20, 50) == [{"label": "Comfortable temperature", "delta": 10}]
    
    def test_clear_night_scores_lower_than_clear_day(self):
        """There is no sunlight boost at night."""
        day_score = calculate_mood_score("Clear", 20, 50, is_day=True)
        night_score = calculate_mood_score("Clear", 20, 50, is_day=False)
        assert night_score < day_score
    
    def test_thunderstorm_counts_as_storm_not_rain(self):
        """A thunderstorm takes the storm penalty only."""
        factors = mood_factors("Thunderstorm with Hail", 20, 50)
        assert {"label": "Stormy weather", "delta": -20} in factors
        assert all(f["label"] != "Rain" for f in factors)
    
    def test_drizzle_snow_and_fog_reduce_score(self):
        """Conditions the weather provider reports should all affect the score."""
        neutral = calculate_mood_score("Unknown", 20, 50)
        for condition in ["Light Drizzle", "Snow Showers", "Foggy"]:
            assert calculate_mood_score(condition, 20, 50) < neutral


class TestMoodLabel:
    """Test mood label classification."""
    
    def test_labels_cover_the_scale(self):
        assert classify_mood_label(95) == "Radiant"
        assert classify_mood_label(80) == "Upbeat"
        assert classify_mood_label(65) == "Steady"
        assert classify_mood_label(55) == "Mellow"
        assert classify_mood_label(40) == "Subdued"
        assert classify_mood_label(30) == "Drained"
        assert classify_mood_label(10) == "Heavy"


class TestNightRecommendations:
    """Test recommendations after dark."""
    
    def test_night_advice_comes_from_the_night_pools(self):
        recs = generate_recommendations(80, "Clear", 20, 50, is_day=False)
        assert recs[0] in mood_engine.CLEAR_NIGHT_IDEAS
        assert recs[1] in mood_engine.MILD_NIGHT_IDEAS
        
        recs = generate_recommendations(55, "Overcast", 18, 60, is_day=False)
        assert recs[0] in mood_engine.NIGHT_IDEAS
    
    def test_night_pools_have_no_daytime_advice(self):
        night_ideas = (
            mood_engine.CLEAR_NIGHT_IDEAS
            + mood_engine.NIGHT_IDEAS
            + mood_engine.MILD_NIGHT_IDEAS
        )
        for idea in night_ideas:
            assert "11am" not in idea
            assert "2pm" not in idea
            assert "midday" not in idea
            assert "lunch" not in idea


class TestSummary:
    """Test the plain-language summary."""
    
    def test_positive_summary(self):
        factors = mood_factors("Clear", 21, 50)
        summary = build_summary("Nairobi", "Clear", 21, 90, factors)
        assert summary == (
            "Clear and 21°C in Nairobi. Clear skies and comfortable temperature are "
            "lifting the mood. A good time to take on something demanding."
        )
    
    def test_negative_summary(self):
        factors = mood_factors("Rain", 8, 90)
        summary = build_summary("Bergen", "Rain", 8, 32, factors)
        assert summary == (
            "Rain and 8°C in Bergen. Rain, cold stress and high humidity are "
            "weighing on the mood. Go easy on yourself and plan for lower energy."
        )
    
    def test_night_summary_does_not_suggest_demanding_work(self):
        factors = mood_factors("Mainly Clear", 20, 50, is_day=False)
        summary = build_summary("Nairobi", "Mainly Clear", 20, 80, factors, is_day=False)
        assert summary == (
            "Mainly clear and 20°C in Nairobi. Clear night and comfortable temperature are "
            "lifting the mood. A calm night to rest and recharge."
        )
    
    def test_verbs_agree_with_plural_factors(self):
        """'Clear skies' is plural on its own; 'cold stress' is not."""
        factors = mood_factors("Clear", 27, 50)
        summary = build_summary("Nairobi", "Clear", 27, 77, factors)
        assert "Clear skies help, while warm air pulls the score down." in summary
        
        factors = mood_factors("Clear", 30, 50, is_day=True)[:1]
        assert "Clear skies are lifting the mood." in build_summary("Nairobi", "Clear", 30, 80, factors)
        
        factors = mood_factors("Unknown", 5, 50)
        assert "Cold stress is weighing on the mood." in build_summary("Oslo", "Unknown", 5, 50, factors)
    
    def test_neutral_summary(self):
        summary = build_summary("Lima", "Unknown", 20, 65, [])
        assert "neutral" in summary

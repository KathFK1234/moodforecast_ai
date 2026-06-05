"""Unit tests for mood engine - no I/O dependencies."""

import pytest
from app.services.mood_engine import (
    calculate_mood_score,
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
        """Sunny weather should include outdoor activity recommendations."""
        recs = generate_recommendations(75, "Sunny", 22, 50)
        assert len(recs) > 0
        assert any("outdoor" in r.lower() or "walk" in r.lower() for r in recs)
    
    def test_rainy_recommendations(self):
        """Rainy weather should suggest indoor focus work."""
        recs = generate_recommendations(50, "Rainy", 18, 70)
        assert len(recs) > 0
        # Should suggest indoor activities
        assert any("indoor" in r.lower() for r in recs)
    
    def test_extreme_cold_recommendations(self):
        """Cold weather should suggest warmth and hydration."""
        recs = generate_recommendations(30, "Cloudy", 5, 50)
        assert len(recs) > 0
        assert any("warm" in r.lower() or "cold" in r.lower() for r in recs)
    
    def test_high_humidity_recommendations(self):
        """High humidity should mention hydration."""
        recs = generate_recommendations(50, "Cloudy", 28, 85)
        assert len(recs) > 0
        assert any("hydration" in r.lower() or "water" in r.lower() for r in recs)
    
    def test_low_mood_includes_wellness(self):
        """Low mood should include mindfulness or wellness tips."""
        recs = generate_recommendations(30, "Stormy", 10, 80)
        assert len(recs) > 0
        assert any("mindfulness" in r.lower() or "stretch" in r.lower() for r in recs)


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

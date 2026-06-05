"""Rule-based mood scoring engine with psychological rationale."""

from typing import TypedDict


class MoodEngineOutput(TypedDict):
    """Output from mood scoring engine."""
    mood_score: int
    energy_level: str
    risk_level: str
    recommendations: list[str]


def calculate_mood_score(
    condition: str,
    temperature_c: float,
    humidity: float
) -> int:
    """
    Calculate mood score (0-100) from weather parameters.
    
    Baseline: 65 (neutral)
    Additive deltas applied per condition, temperature, and humidity.
    Final score clamped to [0, 100].
    """
    score = 65  # neutral baseline
    
    # Condition deltas (psychological rationale)
    condition_lower = condition.lower()
    if "sunny" in condition_lower or "clear" in condition_lower:
        score += 15  # Sunlight boosts serotonin
    elif "cloudy" in condition_lower or "overcast" in condition_lower:
        score -= 5   # Reduced UV and light exposure
    elif "rain" in condition_lower:
        score -= 10  # Barometric drop + reduced activity
    elif "storm" in condition_lower or "thunder" in condition_lower:
        score -= 20  # High arousal / anxiety; low pressure
    
    # Temperature deltas (thermal comfort zone)
    if 18 <= temperature_c <= 24:
        score += 10  # Optimal thermal comfort
    elif temperature_c < 10 or temperature_c > 35:
        score -= 15  # Thermal stress
    elif temperature_c < 18:
        score -= 5   # Cool but tolerable
    elif temperature_c > 24:
        score -= 3   # Warm but tolerable
    
    # Humidity deltas
    if humidity > 80:
        score -= 8  # High humidity suppresses energy
    
    # Clamp to [0, 100]
    return max(0, min(100, score))


def classify_energy_level(mood_score: int) -> str:
    """Classify energy level based on mood score."""
    if mood_score >= 75:
        return "High"
    elif mood_score >= 50:
        return "Medium"
    elif mood_score >= 25:
        return "Low"
    else:
        return "Very Low"


def classify_risk_level(mood_score: int) -> str:
    """Classify risk level based on mood score."""
    if mood_score >= 75:
        return "Minimal"
    elif mood_score >= 50:
        return "Low"
    elif mood_score >= 25:
        return "Moderate"
    else:
        return "High"


def generate_recommendations(
    mood_score: int,
    condition: str,
    temperature_c: float,
    humidity: float
) -> list[str]:
    """Generate wellbeing recommendations based on weather parameters."""
    recommendations = []
    
    condition_lower = condition.lower()
    
    # Light-based recommendations
    if "sunny" in condition_lower or "clear" in condition_lower:
        recommendations.append(
            "Take a 15-minute outdoor walk before 11am while light levels are highest."
        )
    elif "cloudy" in condition_lower or "overcast" in condition_lower:
        recommendations.append(
            "Consider a brief midday break by a window to maintain light exposure."
        )
    elif "rain" in condition_lower or "storm" in condition_lower:
        recommendations.append(
            "Schedule indoor focus work; use this weather for reflection or creative tasks."
        )
    
    # Temperature-based recommendations
    if temperature_c < 10:
        recommendations.append(
            "Bundle up warmly — cold stress impairs focus. Stay hydrated indoors."
        )
    elif temperature_c > 30:
        recommendations.append(
            "Prioritize hydration and indoor breaks. Heat stress reduces mental clarity."
        )
    else:
        recommendations.append(
            "Schedule your most focused work before 2pm — energy typically dips mid-afternoon."
        )
    
    # Humidity-based recommendations
    if humidity > 80:
        recommendations.append(
            "High humidity can mask fluid loss — maintain active hydration."
        )
    elif humidity < 30:
        recommendations.append(
            "Dry air can affect concentration. Use a humidifier or drink extra water."
        )
    
    # General mood management
    if mood_score < 50:
        recommendations.append(
            "Consider a brief mindfulness break or gentle stretching to reset your mood."
        )
    
    return recommendations


def score_mood(
    condition: str,
    temperature_c: float,
    humidity: float
) -> MoodEngineOutput:
    """
    Main entry point: score mood from weather parameters.
    
    Returns: mood_score, energy_level, risk_level, recommendations.
    """
    mood_score = calculate_mood_score(condition, temperature_c, humidity)
    energy_level = classify_energy_level(mood_score)
    risk_level = classify_risk_level(mood_score)
    recommendations = generate_recommendations(
        mood_score, condition, temperature_c, humidity
    )
    
    return {
        "mood_score": mood_score,
        "energy_level": energy_level,
        "risk_level": risk_level,
        "recommendations": recommendations,
    }

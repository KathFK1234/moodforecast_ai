"""Rule-based mood scoring engine with psychological rationale."""

from typing import TypedDict


class MoodFactor(TypedDict):
    """One contribution to the mood score."""
    label: str
    delta: int


class MoodEngineOutput(TypedDict):
    """Output from mood scoring engine."""
    mood_score: int
    mood_label: str
    energy_level: str
    risk_level: str
    factors: list[MoodFactor]
    recommendations: list[str]


BASELINE_SCORE = 65  # neutral baseline


def mood_factors(
    condition: str,
    temperature_c: float,
    humidity: float,
    is_day: bool = True
) -> list[MoodFactor]:
    """
    List what moves the mood score away from the baseline, and by how much.
    
    At most one factor each for condition, temperature and humidity.
    """
    factors: list[MoodFactor] = []
    
    # Condition deltas (psychological rationale)
    condition_lower = condition.lower()
    if "storm" in condition_lower or "thunder" in condition_lower:
        factors.append({"label": "Stormy weather", "delta": -20})  # High arousal / anxiety; low pressure
    elif "sunny" in condition_lower or "clear" in condition_lower:
        if is_day:
            factors.append({"label": "Clear skies", "delta": 15})  # Sunlight boosts serotonin
        else:
            factors.append({"label": "Clear night", "delta": 5})   # Calm, but no sunlight to benefit from
    elif "cloudy" in condition_lower or "overcast" in condition_lower:
        factors.append({"label": "Cloud cover", "delta": -5})      # Reduced UV and light exposure
    elif "rain" in condition_lower:
        factors.append({"label": "Rain", "delta": -10})            # Barometric drop + reduced activity
    elif "drizzle" in condition_lower:
        factors.append({"label": "Drizzle", "delta": -5})          # Dull light, mild disruption
    elif "snow" in condition_lower:
        factors.append({"label": "Snow", "delta": -5})             # Cold and reduced mobility
    elif "fog" in condition_lower:
        factors.append({"label": "Fog", "delta": -5})              # Low light and visibility
    
    # Temperature deltas (thermal comfort zone)
    if 18 <= temperature_c <= 24:
        factors.append({"label": "Comfortable temperature", "delta": 10})  # Optimal thermal comfort
    elif temperature_c < 10:
        factors.append({"label": "Cold stress", "delta": -15})             # Thermal stress
    elif temperature_c > 35:
        factors.append({"label": "Heat stress", "delta": -15})             # Thermal stress
    elif temperature_c < 18:
        factors.append({"label": "Cool air", "delta": -5})                 # Cool but tolerable
    elif temperature_c > 24:
        factors.append({"label": "Warm air", "delta": -3})                 # Warm but tolerable
    
    # Humidity deltas
    if humidity > 80:
        factors.append({"label": "High humidity", "delta": -8})  # High humidity suppresses energy
    
    return factors


def calculate_mood_score(
    condition: str,
    temperature_c: float,
    humidity: float,
    is_day: bool = True
) -> int:
    """
    Calculate mood score (0-100) from weather parameters.
    
    Baseline: 65 (neutral)
    Additive deltas applied per condition, temperature, and humidity.
    Final score clamped to [0, 100].
    """
    factors = mood_factors(condition, temperature_c, humidity, is_day)
    score = BASELINE_SCORE + sum(factor["delta"] for factor in factors)
    
    # Clamp to [0, 100]
    return max(0, min(100, score))


def classify_mood_label(mood_score: int) -> str:
    """Short name for a mood score."""
    if mood_score >= 85:
        return "Radiant"
    elif mood_score >= 75:
        return "Upbeat"
    elif mood_score >= 60:
        return "Steady"
    elif mood_score >= 50:
        return "Mellow"
    elif mood_score >= 35:
        return "Subdued"
    elif mood_score >= 25:
        return "Drained"
    else:
        return "Heavy"


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
    humidity: float,
    is_day: bool = True
) -> list[str]:
    """Generate wellbeing recommendations based on weather parameters."""
    recommendations = []
    
    condition_lower = condition.lower()
    
    # Light-based recommendations (daylight advice only applies during the day)
    if not is_day:
        if "sunny" in condition_lower or "clear" in condition_lower:
            recommendations.append(
                "Clear night — a few minutes of fresh air outside can help you wind down."
            )
        else:
            recommendations.append(
                "Wind down with dim lights and a screen-free half hour before bed."
            )
    elif "storm" in condition_lower or "thunder" in condition_lower or "rain" in condition_lower:
        recommendations.append(
            "Schedule indoor focus work; use this weather for reflection or creative tasks."
        )
    elif "sunny" in condition_lower or "clear" in condition_lower:
        recommendations.append(
            "Take a 15-minute outdoor walk before 11am while light levels are highest."
        )
    elif "cloudy" in condition_lower or "overcast" in condition_lower:
        recommendations.append(
            "Consider a brief midday break by a window to maintain light exposure."
        )
    elif "drizzle" in condition_lower or "snow" in condition_lower or "fog" in condition_lower:
        recommendations.append(
            "Light is low today — keep indoor spaces bright and take short movement breaks."
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
    elif is_day:
        recommendations.append(
            "Schedule your most focused work before 2pm — energy typically dips mid-afternoon."
        )
    else:
        recommendations.append(
            "Keep a consistent bedtime — tomorrow's energy starts with tonight's rest."
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


def build_summary(
    location: str,
    condition: str,
    temperature_c: float,
    mood_score: int,
    factors: list[MoodFactor],
    is_day: bool = True
) -> str:
    """Describe the conditions and what is driving the mood score, in plain language."""
    summary = f"{condition.capitalize()} and {round(temperature_c)}°C in {location}."
    
    lifts = [f["label"].lower() for f in factors if f["delta"] > 0]
    drags = [f["label"].lower() for f in factors if f["delta"] < 0]
    
    if lifts and drags:
        summary += (
            f" {_join(lifts).capitalize()} {_verb(lifts, 'helps', 'help')},"
            f" while {_join(drags)} {_verb(drags, 'pulls', 'pull')} the score down."
        )
    elif lifts:
        summary += f" {_join(lifts).capitalize()} {_verb(lifts, 'is', 'are')} lifting the mood."
    elif drags:
        summary += f" {_join(drags).capitalize()} {_verb(drags, 'is', 'are')} weighing on the mood."
    else:
        summary += " Conditions are neutral, with little effect on mood either way."
    
    if mood_score >= 75 and is_day:
        summary += " A good time to take on something demanding."
    elif mood_score >= 75:
        summary += " A calm night to rest and recharge."
    elif mood_score < 50:
        summary += " Go easy on yourself and plan for lower energy."
    
    return summary


def _join(items: list[str]) -> str:
    """Join as 'a', 'a and b' or 'a, b and c'."""
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _verb(subjects: list[str], singular: str, plural: str) -> str:
    """Pick the verb form that agrees with the number of subjects."""
    return singular if len(subjects) == 1 else plural


def score_mood(
    condition: str,
    temperature_c: float,
    humidity: float,
    is_day: bool = True
) -> MoodEngineOutput:
    """
    Main entry point: score mood from weather parameters.
    
    Returns: mood_score, mood_label, energy_level, risk_level, factors, recommendations.
    """
    factors = mood_factors(condition, temperature_c, humidity, is_day)
    mood_score = calculate_mood_score(condition, temperature_c, humidity, is_day)
    energy_level = classify_energy_level(mood_score)
    risk_level = classify_risk_level(mood_score)
    recommendations = generate_recommendations(
        mood_score, condition, temperature_c, humidity, is_day
    )
    
    return {
        "mood_score": mood_score,
        "mood_label": classify_mood_label(mood_score),
        "energy_level": energy_level,
        "risk_level": risk_level,
        "factors": factors,
        "recommendations": recommendations,
    }

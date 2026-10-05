"""Rule-based mood scoring engine with psychological rationale."""

import random
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


# Recommendation pools: one entry is picked at random from the pool that fits,
# so the same weather doesn't always give the same advice.

CLEAR_DAY_IDEAS = (
    "Sun's out — take a walk, a jog or a bike ride while the light is at its best.",
    "Perfect picnic weather. Take lunch outside and let the daylight do its thing.",
    "Call a friend for an outdoor catch-up — a park bench beats a group chat today.",
    "Get your hands dirty: water the plants, pull some weeds or start that garden project.",
    "Kick a ball, shoot some hoops or throw a frisbee — playing outside counts as self-care.",
    "Take your camera or phone out and photograph five things that make you smile.",
    "Move your workout outdoors — skipping rope, yoga on the grass or a dance in the yard.",
    "Explore somewhere new: a market, a trail or a street you've never walked down.",
)

HOT_SUN_IDEAS = (
    "Blazing out there — if you can get to a pool or the sea, a swim is the best move today.",
    "Save outdoor plans for early morning or after sunset, and find a shady spot in between.",
    "Hot and bright: read under a tree with something cold to drink within reach.",
    "Make it an ice cream or smoothie kind of day, and keep outings short and shaded.",
)

RAIN_IDEAS = (
    "Rainy-day classic: put a pot on the stove and try a new recipe.",
    "Great weather for a movie marathon, a good book or that series everyone keeps recommending.",
    "Put on a playlist and dance it out in the living room — no one's watching.",
    "Break out a board game, a puzzle or a deck of cards.",
    "Use the rain as cover for indoor focus work, then reward yourself with a hot drink.",
    "Get creative indoors: sketch, journal, write, or pick the guitar back up.",
    "Grab an umbrella and splash through a few puddles — a short wet walk is oddly refreshing.",
    "Tidy one drawer, shelf or corner. Small indoor wins feel great on grey days.",
)

STORM_IDEAS = (
    "Stay in and get cosy — blanket, hot drink and a film you've seen a hundred times.",
    "Storm outside, calm inside: try an indoor yoga or stretching session.",
    "Good day for a long phone or video call with someone you miss.",
    "Bake something — the house will smell amazing while the storm does its thing.",
    "Light a candle and settle into a book, a puzzle or some indoor crafting.",
    "Listen to the storm from somewhere comfortable, with a podcast or an album start to finish.",
)

CLOUDY_IDEAS = (
    "No glare, no sweat — cloudy days are great for a run, a hike or a long bike ride.",
    "Soft light is a photographer's dream. Go for a photo walk.",
    "Wander to a café, museum, library or market you haven't visited in a while.",
    "Sit by a window or step outside at lunch — daylight still counts through the clouds.",
    "Meet a friend for a coffee, or just a lap around the block.",
    "Good conditions for errands on foot. Add a detour through a park.",
    "Try a workout class, a swim or a gym session — let endorphins fill in for sunshine.",
)

LOW_LIGHT_IDEAS = (
    "Light is low today — keep indoor spaces bright and take short movement breaks.",
    "Moody weather outside: lean in with tea, a candle and a good book.",
    "Put on a jacket and take a short misty walk — quiet streets are oddly calming.",
    "Do ten minutes of stretching or a quick home workout to wake yourself up.",
    "Cook something warm and colourful — soup, curry or a big stew.",
    "Start a small project: a puzzle, a playlist, a sketch or a photo album.",
)

SNOW_IDEAS = (
    "Snow day! Build a snowman, throw a snowball or go and make the first footprints.",
    "Go sledding or take a crunchy winter walk, then thaw out with hot chocolate.",
    "Watch the snow fall from a warm spot with a book and a big mug.",
    "Snow brightens everything — wrap up well and step out for a few minutes of daylight.",
    "Slow-cook or bake something hearty and let it warm the whole house.",
)

CLEAR_NIGHT_IDEAS = (
    "Clear night — a few minutes of fresh air outside can help you wind down.",
    "Clear skies tonight — step outside and see how many stars you can spot.",
    "Sit outside with a warm drink and let the day settle.",
    "Nice night to eat dinner outside or by an open window.",
    "Look up and find the moon, then take five slow breaths before heading in.",
)

NIGHT_IDEAS = (
    "Wind down with dim lights and a screen-free half hour before bed.",
    "Put on some calm music and do a few gentle stretches before bed.",
    "Take a warm shower or bath and let the day rinse off.",
    "Write down three good things from today, however small.",
    "Cosy night in: a film, a puzzle or a slow home-cooked dinner.",
    "Brew a caffeine-free tea and plan one thing to look forward to tomorrow.",
)

COLD_IDEAS = (
    "Bundle up warmly — cold stress impairs focus. Layers, a hat and a hot drink go a long way.",
    "Cold out: warm up from the inside with soup, tea or hot chocolate.",
    "Get your blood moving — a brisk walk in warm layers or a quick indoor workout.",
    "Cold days are made for warm socks, a blanket and something baking in the oven.",
    "Keep warm and keep sipping water — it's easy to forget to drink when it's cold.",
)

HOT_IDEAS = (
    "Prioritize hydration and breaks indoors or in the shade. Heat stress reduces mental clarity.",
    "Keep a water bottle within reach — add ice, lemon or mint to make it interesting.",
    "Slow the pace: do demanding things early or late and rest through the hottest hours.",
    "Cool down with a cold shower, an iced drink or some frozen fruit.",
    "Wear light, loose clothing and keep your space shaded and breezy.",
)

MILD_DAY_IDEAS = (
    "Schedule your most focused work before 2pm — energy typically dips mid-afternoon.",
    "Tackle your hardest task first, then celebrate with a proper break.",
    "Take a stretch break every hour — shoulders, neck and a lap around the room.",
    "Learn something small today: a new word, a recipe, a chord or a dance step.",
    "Send a message to someone you've been meaning to check in on.",
    "Eat lunch away from your screen — your afternoon self will thank you.",
    "Put on a favourite song between tasks and move for the length of it.",
)

MILD_NIGHT_IDEAS = (
    "Keep a consistent bedtime — tomorrow's energy starts with tonight's rest.",
    "Lay out what you need for tomorrow so the morning starts easy.",
    "Swap the last scroll of the night for a few pages of a book or a podcast.",
    "Try a few slow breaths before sleep: in for four, out for six.",
)

HUMID_IDEAS = (
    "High humidity can mask fluid loss — maintain active hydration.",
    "Sticky air today: drink water regularly and choose light, breathable clothes.",
    "Humidity makes effort feel harder — ease the pace and keep water nearby.",
    "Muggy out — a fan, a cool shower and plenty of water will keep you fresher.",
)

DRY_IDEAS = (
    "Dry air can affect concentration. Use a humidifier or drink extra water.",
    "Dry air today — keep a glass of water close, and lip balm and moisturiser closer.",
    "Low humidity: sip water through the day, and give your houseplants a drink too.",
)

LOW_MOOD_IDEAS = (
    "Consider a brief mindfulness break or gentle stretching to reset your mood.",
    "Put on a song you love and sing along, badly if necessary.",
    "Call or text someone who makes you laugh.",
    "Watch something silly — a favourite comedy or ten minutes of animal videos.",
    "Be kind to yourself today: pick one small, doable thing and call that a win.",
    "Make a favourite comfort meal or snack and actually sit down to enjoy it.",
    "Try five minutes of doodling, colouring or journaling — no talent required.",
    "Give a pet, a plant or a person some attention — caring for something lifts the mood.",
)


def generate_recommendations(
    mood_score: int,
    condition: str,
    temperature_c: float,
    humidity: float,
    is_day: bool = True,
    rng: random.Random | None = None
) -> list[str]:
    """
    Generate wellbeing recommendations based on weather parameters.
    
    Each recommendation is picked at random from the pool that fits the conditions.
    Pass a seeded rng for repeatable picks.
    """
    pick = (rng or random).choice
    recommendations = []
    
    condition_lower = condition.lower()
    
    # Light-based recommendations (daylight advice only applies during the day)
    if not is_day:
        if "sunny" in condition_lower or "clear" in condition_lower:
            recommendations.append(pick(CLEAR_NIGHT_IDEAS))
        else:
            recommendations.append(pick(NIGHT_IDEAS))
    elif "storm" in condition_lower or "thunder" in condition_lower:
        recommendations.append(pick(STORM_IDEAS))
    elif "rain" in condition_lower:
        recommendations.append(pick(RAIN_IDEAS))
    elif "sunny" in condition_lower or "clear" in condition_lower:
        # Too hot for a run or a picnic in full sun
        recommendations.append(pick(HOT_SUN_IDEAS if temperature_c > 30 else CLEAR_DAY_IDEAS))
    elif "cloudy" in condition_lower or "overcast" in condition_lower:
        recommendations.append(pick(CLOUDY_IDEAS))
    elif "snow" in condition_lower:
        recommendations.append(pick(SNOW_IDEAS))
    elif "drizzle" in condition_lower or "fog" in condition_lower:
        recommendations.append(pick(LOW_LIGHT_IDEAS))
    
    # Temperature-based recommendations
    if temperature_c < 10:
        recommendations.append(pick(COLD_IDEAS))
    elif temperature_c > 30:
        recommendations.append(pick(HOT_IDEAS))
    elif is_day:
        recommendations.append(pick(MILD_DAY_IDEAS))
    else:
        recommendations.append(pick(MILD_NIGHT_IDEAS))
    
    # Humidity-based recommendations
    if humidity > 80:
        recommendations.append(pick(HUMID_IDEAS))
    elif humidity < 30:
        recommendations.append(pick(DRY_IDEAS))
    
    # General mood management
    if mood_score < 50:
        recommendations.append(pick(LOW_MOOD_IDEAS))
    
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


# Factor labels that are grammatically plural on their own ("clear skies help")
PLURAL_LABELS = {"clear skies"}


def _verb(subjects: list[str], singular: str, plural: str) -> str:
    """Pick the verb form that agrees with the subjects."""
    if len(subjects) == 1 and subjects[0] not in PLURAL_LABELS:
        return singular
    return plural


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

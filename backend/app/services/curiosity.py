"""Prompts that invite the user to look up the weather somewhere else."""

import random
from typing import TypedDict


class CuriosityPrompt(TypedDict):
    """A question about another place, and the place to search for the answer."""
    question: str
    location: str


# Places grouped by what they are known for. The questions never claim to know
# the weather there - finding out is the point.
WORLD_PLACES = (
    "Reykjavik", "Tokyo", "Cape Town", "Rio de Janeiro", "Marrakech", "Sydney",
    "Vancouver", "Mumbai", "Lisbon", "Kigali", "Buenos Aires", "Singapore",
    "Cairo", "Zanzibar", "Kathmandu", "Honolulu", "Istanbul", "Mexico City",
)
COLD_PLACES = ("Reykjavik", "Tromsø", "Ushuaia", "Nuuk", "Ulaanbaatar", "Anchorage")
WARM_PLACES = ("Mombasa", "Zanzibar", "Bangkok", "Dubai", "Honolulu", "Cartagena")
DRY_PLACES = ("Cairo", "Marrakech", "Windhoek", "Lima", "Phoenix", "Alice Springs")
WET_PLACES = ("Bergen", "Mumbai", "Singapore", "Bogotá", "Hilo", "Kuala Lumpur")
SNOW_PLACES = ("Zermatt", "Tromsø", "Sapporo", "Banff", "Queenstown", "Innsbruck")
BEACH_PLACES = ("Mombasa", "Zanzibar", "Honolulu", "Phuket", "Rio de Janeiro", "Malé")
DARK_SKY_PLACES = (
    "San Pedro de Atacama", "Windhoek", "Alice Springs", "Marrakech", "Flagstaff", "Lake Tekapo",
)
WINDY_PLACES = ("Wellington", "Cape Town", "Chicago", "Tarifa", "Punta Arenas", "Edinburgh")

HOT_QUESTIONS = (
    "Feeling the heat? See how chilly {place} is right now.",
    "Hot here — how many layers would you need in {place}?",
)
COLD_QUESTIONS = (
    "Dreaming of warmth? Check what {place} is basking in.",
    "Chilly here — would you need sunscreen in {place} today?",
)
WET_QUESTIONS = (
    "Tired of the rain? Find out if it's dry in {place}.",
    "Wet here — is anyone carrying an umbrella in {place}?",
)
CLEAR_QUESTIONS = (
    "Not much cloud here — wonder if it's pouring in {place}?",
    "Clear here — is {place} living up to its rainy reputation today?",
)
NIGHT_QUESTIONS = (
    "It's night here — is the sun up in {place}?",
    "While it's dark here, what kind of day is {place} having?",
)
DAY_QUESTIONS = (
    "Is it day or night in {place} right now? Take a guess, then check.",
)
ANYTIME_QUESTIONS = (
    "Take a guess: is it warmer in {place} than here? Tap to find out.",
    "Ever wondered what the weather does in {place}?",
    "What's the mood like in {place} today?",
    "Pick somewhere you've never been — how about {place}?",
    "If you teleported to {place} right now, what would you need to wear?",
    "Which is having the better day, here or {place}?",
)


def pick_places(
    places: tuple[str, ...],
    current_location: str,
    count: int,
    rng: random.Random | None = None
) -> list[str]:
    """Pick up to `count` different places, leaving out the one being viewed."""
    here = current_location.lower()
    elsewhere = [place for place in places if place.lower() not in here]
    return (rng or random).sample(elsewhere, min(count, len(elsewhere)))


def curiosity_prompts(
    location: str,
    condition: str,
    temperature_c: float,
    is_day: bool = True,
    count: int = 3,
    rng: random.Random | None = None,
    searched_as: str = ""
) -> list[CuriosityPrompt]:
    """
    Suggest other places to look up, starting with ones that contrast with here.

    Hot weather points to cold places, rain to dry ones, night to the other side
    of the world. General questions fill any remaining slots.

    `searched_as` is what the user typed, which can differ from the resolved
    name (Sapporo resolves to 札幌市) and is left out of the suggestions too.
    """
    rng = rng or random
    here = f"{location} {searched_as}"
    condition_lower = condition.lower()

    # (questions, places) that contrast with the current conditions
    themes: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    if temperature_c >= 28:
        themes.append((HOT_QUESTIONS, COLD_PLACES))
    elif temperature_c <= 12:
        themes.append((COLD_QUESTIONS, WARM_PLACES))
    if any(word in condition_lower for word in ("rain", "drizzle", "storm", "thunder")):
        themes.append((WET_QUESTIONS, DRY_PLACES))
    elif "clear" in condition_lower or "sunny" in condition_lower:
        themes.append((CLEAR_QUESTIONS, WET_PLACES))
    themes.append((DAY_QUESTIONS if is_day else NIGHT_QUESTIONS, WORLD_PLACES))
    rng.shuffle(themes)

    anytime = list(ANYTIME_QUESTIONS)
    rng.shuffle(anytime)
    themes += [((question,), WORLD_PLACES) for question in anytime]

    prompts: list[CuriosityPrompt] = []
    used: set[str] = set()
    for questions, places in themes:
        if len(prompts) == count:
            break
        fresh = tuple(place for place in places if place not in used)
        picked = pick_places(fresh, here, 1, rng)
        if not picked:
            continue
        used.add(picked[0])
        prompts.append({
            "question": rng.choice(questions).format(place=picked[0]),
            "location": picked[0],
        })

    return prompts

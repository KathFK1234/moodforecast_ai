"""Rule-based answers to "is this activity right for the weather, here?"."""

import random
import re
from typing import NamedTuple, TypedDict

from app.services import curiosity
from app.services.locality import LOCAL_FAVOURITES, Place, is_late_night, is_local, local_issue


class Activity(NamedTuple):
    """Something the user might want to do, and the words they might use for it."""
    name: str               # Reads naturally after "conditions for ..."
    category: str           # active, leisure, water, snow, sky, wind or indoor
    aliases: tuple[str, ...]
    night_ok: bool = False  # Just as good after dark
    needs: str = ""         # What the place must offer: coast, warm_coast, surf, snow, or a sport (see locality)
    prompt: str = ""        # How someone would ask about it, e.g. "Go for a run"


class ActivityCuriosity(TypedDict):
    """Other places to check the same activity."""
    question: str
    places: list[str]


class ActivityAdvice(TypedDict):
    """Output from the activity advisor."""
    activity: str
    recognised: bool
    verdict: str
    headline: str
    reasons: list[str]
    suggestion: str | None
    curiosity: ActivityCuriosity


ACTIVITIES = (
    Activity("running", "active", ("run", "running", "jog", "jogging"), prompt="Go for a run"),
    Activity("a walk", "active", ("walk", "walking", "stroll"), prompt="Take a walk"),
    Activity("cycling", "active", ("cycle", "cycling", "bike", "biking"), prompt="Ride a bike"),
    Activity("hiking", "active", ("hike", "hiking", "trek", "trekking"), prompt="Go hiking"),
    Activity("football", "active", ("football", "soccer"), prompt="Play football"),
    Activity("basketball", "active", ("basketball", "hoops"), prompt="Shoot some hoops"),
    Activity("tennis", "active", ("tennis", "padel"), prompt="Play tennis"),
    Activity("cricket", "active", ("cricket",), needs="cricket", prompt="Play cricket"),
    Activity("baseball", "active", ("baseball", "softball"), needs="baseball", prompt="Play baseball"),
    Activity("rugby", "active", ("rugby",), needs="rugby", prompt="Play rugby"),
    Activity("golf", "leisure", ("golf",), needs="golf", prompt="Play golf"),
    Activity("a picnic", "leisure", ("picnic",), prompt="Have a picnic"),
    Activity(
        "a barbecue", "leisure",
        ("barbecue", "bbq", "braai", "nyama choma", "asado", "cookout", "grill"),
        night_ok=True, prompt="Have a barbecue",
    ),
    Activity("gardening", "leisure", ("garden", "gardening", "planting"), prompt="Do some gardening"),
    Activity(
        "photography", "leisure",
        ("photo", "photos", "photography", "photograph"), prompt="Take photos",
    ),
    Activity("fishing", "leisure", ("fish", "fishing"), night_ok=True, prompt="Go fishing"),
    Activity("camping", "leisure", ("camp", "camping"), night_ok=True, prompt="Go camping"),
    Activity("swimming", "water", ("swim", "swimming", "pool"), prompt="Go swimming"),
    Activity(
        "a beach day", "water",
        ("beach", "seaside", "sunbathe", "sunbathing"), needs="coast", prompt="Go to the beach",
    ),
    Activity(
        "surfing", "water",
        ("surf", "surfing", "bodyboard", "bodyboarding"), needs="surf", prompt="Go surfing",
    ),
    Activity(
        "snorkelling", "water",
        ("snorkel", "snorkelling", "snorkeling", "scuba", "diving"),
        needs="warm_coast", prompt="Go snorkelling",
    ),
    Activity(
        "snow sports", "snow",
        ("ski", "skiing", "snowboard", "snowboarding", "sled", "sledding", "snowman", "snowball"),
        needs="snow", prompt="Go skiing",
    ),
    Activity(
        "stargazing", "sky",
        ("stargaze", "stargazing", "stars", "astronomy", "telescope", "moon"),
        night_ok=True, prompt="Stargaze",
    ),
    Activity("kite flying", "wind", ("kite", "kites"), prompt="Fly a kite"),
    Activity(
        "sailing", "wind",
        ("sail", "sailing", "windsurf", "windsurfing", "kitesurf", "kitesurfing"),
        needs="coast", prompt="Go sailing",
    ),
    Activity("reading", "indoor", ("read", "reading", "book"), prompt="Read a book"),
    Activity("a movie", "indoor", ("movie", "movies", "film", "cinema", "series"), prompt="Watch a movie"),
    Activity("cooking", "indoor", ("cook", "cooking", "bake", "baking"), prompt="Cook something new"),
    Activity(
        "games", "indoor",
        ("board game", "board games", "puzzle", "cards", "video game", "gaming"), prompt="Play a game",
    ),
    Activity(
        "an indoor workout", "indoor",
        ("yoga", "gym", "workout", "dance", "dancing", "pilates"), prompt="Work out indoors",
    ),
    Activity(
        "an indoor outing", "indoor",
        ("museum", "gallery", "library", "shopping", "mall", "cafe", "café", "coffee"),
        prompt="Visit a museum or café",
    ),
    Activity("a nap", "indoor", ("nap", "sleep"), prompt="Take a nap"),
)

# Longest alias first, so "board game" wins over a shorter word inside it
_ALIASES = sorted(
    ((alias, activity) for activity in ACTIVITIES for alias in activity.aliases),
    key=lambda pair: len(pair[0]),
    reverse=True,
)

GO_HEADLINES = (
    "Yes! Great conditions for {name}.",
    "Go for it — the weather in {place} is on your side for {name}.",
    "Green light for {name}. Enjoy!",
)
MAYBE_HEADLINES = (
    "Doable — {name} just needs a little planning.",
    "You can, with a caveat or two for {name}.",
    "{place} is so-so for {name} right now, but it can work.",
)
SKIP_HEADLINES = (
    "Not the moment for {name}.",
    "I'd hold off on {name} for now.",
    "{place} isn't playing along for {name} right now.",
)
HEADLINES = {"go": GO_HEADLINES, "maybe": MAYBE_HEADLINES, "skip": SKIP_HEADLINES}

RANDOM_HEADLINES = (
    "Today's pick for {place}: {name}.",
    "The dice have spoken: {name}!",
    "Why not {name}?",
    "{place} has the weather for {name} right now.",
)

# A nudge to go with each activity when it comes up as a random pick
PITCHES = {
    "running": "Lace up — even ten minutes counts.",
    "a walk": "No destination needed. Just pick a direction.",
    "cycling": "Pump up the tyres and find a road you haven't ridden.",
    "hiking": "Find a hill, bring water, earn the view.",
    "football": "Round up whoever's around for a kickabout.",
    "basketball": "First to eleven. Loser buys the drinks.",
    "tennis": "Grab a racket and a partner — rallying counts.",
    "cricket": "A bat, a ball and a few friends is a match.",
    "baseball": "Play catch, or find a diamond and a few innings.",
    "rugby": "Touch rugby counts — grab a ball and some space.",
    "golf": "A few holes, or a bucket of balls at the range.",
    "a picnic": "A blanket, some snacks and somewhere green.",
    "a barbecue": "Fire up the grill — it tastes better with company.",
    "gardening": "Repot, weed or plant something you can eat later.",
    "photography": "Give yourself a theme — doors, shadows, reflections — and find ten.",
    "fishing": "Patience, a line and a flask of something warm.",
    "camping": "Even one night under canvas resets the week.",
    "swimming": "A few lengths, or just float and look at the sky.",
    "a beach day": "Towel, sunscreen, something to read — the sea does the rest.",
    "surfing": "Check the break, wax the board and paddle out.",
    "snorkelling": "Mask on, face down — there's a whole world under there.",
    "snow sports": "Skis, a sled or a snowball — your call.",
    "stargazing": "Find a dark spot and see what you can name.",
    "kite flying": "Find an open field and let the wind do the work.",
    "sailing": "Catch the breeze while it's blowing.",
    "reading": "That book you've been meaning to start? Today.",
    "a movie": "Pick something you've never heard of.",
    "cooking": "Try a dish from a country you've never visited.",
    "games": "Dust off a board game or start a puzzle.",
    "an indoor workout": "Twenty minutes, your favourite playlist, done.",
    "an indoor outing": "A museum, a café or a library corner you haven't tried.",
    "a nap": "Twenty minutes. Set an alarm. No guilt.",
}

# Pitches in the local idiom, by (activity, country)
LOCAL_PITCHES = {
    ("a barbecue", "KE"): "Fire it up — nyama choma tastes better with company.",
    ("a barbecue", "TZ"): "Fire it up — nyama choma tastes better with company.",
    ("a barbecue", "UG"): "Get the muchomo going and call some friends.",
    ("a barbecue", "ZA"): "Light the braai and call the neighbours.",
    ("a barbecue", "NA"): "Light the braai and call the neighbours.",
    ("a barbecue", "AR"): "Time for an asado — low heat, no rush.",
    ("a barbecue", "UY"): "Time for an asado — low heat, no rush.",
    ("a barbecue", "AU"): "Throw something on the barbie.",
    ("a barbecue", "US"): "Fire up the grill for a cookout.",
    ("running", "KE"): "You're in the home of distance running — go and see why.",
    ("running", "ET"): "You're in the home of distance running — go and see why.",
    ("cricket", "IN"): "A bat, a tennis ball and a quiet street is all gully cricket needs.",
    ("cricket", "PK"): "A bat, a taped tennis ball and a quiet street is all you need.",
    ("cycling", "NL"): "You're in the right country for it — just follow the bike paths.",
}

# The only things suggested unprompted in the small hours
LATE_NIGHT_PICKS = ("stargazing", "reading", "a movie", "games")

# Offered when the answer is no. All indoors, so they hold in any weather.
INDOOR_SWAPS = (
    "Swap it for a new recipe, a board game or a film marathon.",
    "How about an indoor workout, some yoga or a dance break in the living room instead?",
    "Good moment for a book, a puzzle or a long call with a friend.",
    "Try a museum, a café or the library until conditions improve.",
)

CURIOSITY_PLACES = {
    "active": curiosity.WORLD_PLACES,
    "leisure": curiosity.WORLD_PLACES,
    "water": curiosity.BEACH_PLACES,
    "snow": curiosity.SNOW_PLACES,
    "sky": curiosity.DARK_SKY_PLACES,
    "wind": curiosity.WINDY_PLACES,
    "indoor": curiosity.WORLD_PLACES,
}


def find_activity(text: str) -> Activity | None:
    """Find the activity a question is about, e.g. "Can I go for a run?" -> running."""
    text_lower = text.strip().lower()
    for activity in ACTIVITIES:
        if text_lower == activity.name:
            return activity
    for alias, activity in _ALIASES:
        if re.search(rf"\b{re.escape(alias)}\b", text_lower):
            return activity
    return None


def _issues(
    activity: Activity,
    condition: str,
    temperature_c: float,
    humidity: float,
    wind_kph: float,
    is_day: bool,
    place: Place | None = None
) -> list[tuple[int, str]]:
    """
    List what stands in the way, as (severity, reason).

    Severity 1 is a caveat, 2 rules the activity out. With a `place`, an
    activity that can't be done there is ruled out before the weather is
    looked at, and one that is uncommon there gets a caveat.
    """
    category = activity.category
    if category == "indoor":
        return []

    local = None
    if place is not None and activity.needs:
        local = local_issue(activity.needs, activity.name, place, "snow" in condition.lower())
        if local and local[0] == 2:
            return [local]

    return ([local] if local else []) + _weather_issues(
        activity, condition, temperature_c, humidity, wind_kph, is_day, place
    )


def _weather_issues(
    activity: Activity,
    condition: str,
    temperature_c: float,
    humidity: float,
    wind_kph: float,
    is_day: bool,
    place: Place | None
) -> list[tuple[int, str]]:
    """What the weather puts in the way of an outdoor activity, as (severity, reason)."""
    category = activity.category

    issues: list[tuple[int, str]] = []
    condition_lower = condition.lower()
    temp = round(temperature_c)
    wind = round(wind_kph)

    storm = "storm" in condition_lower or "thunder" in condition_lower
    rain = "rain" in condition_lower
    snow = "snow" in condition_lower
    clear = "clear" in condition_lower or "sunny" in condition_lower

    if storm:
        return [(2, "There's a thunderstorm about — stay off open ground until it passes.")]

    # Sky: all that matters is darkness and cloud
    if category == "sky":
        if is_day and clear:
            issues.append((1, "It's still daytime — but skies are clear, so tonight could be a good one."))
        elif is_day:
            issues.append((2, f"It's daytime and {condition_lower} — check back after dark."))
        elif "partly" in condition_lower:
            issues.append((1, "There's some cloud about — you'll catch stars in the gaps."))
        elif not clear:
            issues.append((2, f"{condition.capitalize()} tonight, so the stars are hidden."))
        return issues

    # Precipitation and visibility
    if rain and category == "active":
        issues.append((1, "It's raining — dress for it and watch for slippery ground."))
    elif rain and category == "water":
        issues.append((1, "It's raining — fine once you're in the water, less fun on the shore."))
    elif rain:
        issues.append((2, "It's raining, which rather spoils it."))
    elif "drizzle" in condition_lower:
        issues.append((1, "There's drizzle in the air — pack a light waterproof."))
    elif snow and category != "snow":
        issues.append((1, "It's snowing — wrap up and take it slowly, it'll be slippery."))
    elif "fog" in condition_lower:
        issues.append((1, "Fog is cutting visibility — stay where you can be seen."))

    # Temperature
    if category == "snow":
        if not snow and temperature_c <= 0:
            issues.append((1, f"No snow is falling, but at {temp}°C whatever is on the ground will stay — check before you go."))
        elif not snow:
            issues.append((2, f"There's no snow falling and it's {temp}°C."))
    elif category == "water":
        if temperature_c < 15:
            issues.append((2, f"{temp}°C is too cold for a comfortable dip."))
        elif temperature_c < 22:
            issues.append((1, f"At {temp}°C it will feel bracing — keep it short."))
        elif temperature_c > 35:
            issues.append((1, f"It's {temp}°C — the water will be lovely, but cover up and find shade between dips."))
        # In the sea rather than a pool, the water has its own temperature
        sea = place.sea_temp_c if place is not None and activity.needs else None
        if sea is not None and sea < 17:
            issues.append((1, f"The sea is {round(sea)}°C — a wetsuit will make all the difference."))
    elif category == "active":
        if temperature_c > 35:
            issues.append((2, f"{temp}°C is heat-stress territory for anything energetic."))
        elif temperature_c > 30:
            issues.append((1, f"It's {temp}°C — go easy, seek shade and carry water."))
        elif temperature_c < 5:
            issues.append((1, f"It's {temp}°C — layer up and warm up properly first."))
        if humidity > 80 and temperature_c >= 26:
            issues.append((1, "Humid air makes effort feel harder — slow the pace and drink often."))
    else:
        if temperature_c > 35:
            issues.append((1, f"It's {temp}°C — find shade and bring plenty of water."))
        elif temperature_c < 0:
            issues.append((2, f"{temp}°C is too cold to be out for long."))
        elif temperature_c < 10:
            issues.append((1, f"At {temp}°C it's chilly for staying in one spot — bring warm layers."))

    # Wind
    if category == "wind":
        if wind_kph >= 50:
            issues.append((2, f"Winds of {wind} km/h are too strong to handle safely."))
        elif wind_kph >= 35:
            issues.append((1, f"It's blowing {wind} km/h — strong and gusty, best with experience."))
        elif wind_kph < 8:
            issues.append((2, f"Only {wind} km/h of wind — barely enough to ruffle a flag."))
        elif wind_kph < 12:
            issues.append((1, f"The breeze is light at {wind} km/h — it may take some patience."))
    elif wind_kph >= 60:
        issues.append((2, f"Winds of {wind} km/h are strong enough to be hazardous."))
    elif wind_kph >= 35:
        issues.append((1, f"It's blustery at {wind} km/h — hold on to your hat."))

    # Darkness
    if not is_day and not activity.night_ok:
        if category == "water":
            issues.append((1, "It's dark out — stick to a lit pool rather than open water."))
        elif category == "active":
            issues.append((1, "It's dark — choose lit routes and wear something visible."))
        else:
            issues.append((1, "It's dark — you'll want good lighting, or save it for daylight."))

    return issues


def _good_news(
    activity: Activity,
    condition: str,
    temperature_c: float,
    wind_kph: float,
    is_day: bool,
    place: Place | None = None
) -> str:
    """Say why the conditions suit the activity."""
    temp = round(temperature_c)
    wind = round(wind_kph)
    condition_lower = condition.lower()
    category = activity.category

    if category == "indoor":
        if any(word in condition_lower for word in ("rain", "drizzle", "storm", "thunder", "snow")):
            return f"It's {condition_lower} outside, so staying in is the smart call."
        if is_day and ("clear" in condition_lower or "sunny" in condition_lower) and 18 <= temperature_c <= 28:
            return f"Indoors always works — though at {temp}°C and {condition_lower} you could take it outside."
        return "Indoors, the weather can't touch you."
    if category == "sky":
        return "Clear skies and darkness — just what the stars need. Give your eyes a few minutes to adjust."
    if category == "snow":
        return f"Snow is falling at {temp}°C — wrap up and get out there."
    if category == "wind":
        return f"A steady {wind} km/h breeze — just right."
    if category == "water":
        if place is not None and activity.needs and place.sea_temp_c is not None:
            return f"{condition.capitalize()} and {temp}°C, with the sea at {round(place.sea_temp_c)}°C — good conditions for it."
        return f"{condition.capitalize()} and {temp}°C — good conditions for getting in the water."
    return f"{condition.capitalize()} and {temp}°C with {wind} km/h of wind — hard to ask for more."


def check_activity(
    question: str,
    location: str,
    condition: str,
    temperature_c: float,
    humidity: float,
    wind_kph: float,
    is_day: bool = True,
    rng: random.Random | None = None,
    searched_as: str = "",
    place: Place | None = None
) -> ActivityAdvice:
    """
    Main entry point: judge whether what the user wants to do suits the weather and the place.

    `question` is free text ("Can I go for a run?"). An activity that isn't
    recognised is judged as general time outdoors. `searched_as` is what the
    user typed for the location; it is left out of the places to compare.
    `place` holds the local facts (coast, height, country); without it only
    the weather is judged.

    Returns: activity, recognised, verdict (go, maybe or skip), headline, reasons,
    suggestion, curiosity.
    """
    found = find_activity(question)
    activity = found or Activity("time outdoors", "leisure", ())
    return _advise(
        activity, found is not None, location,
        condition, temperature_c, humidity, wind_kph, is_day, rng or random, searched_as, place
    )


def local_activities(place: Place | None, condition: str = "") -> list[Activity]:
    """
    The activities that are practical at a place, local favourites first.

    Leaves out anything the place can't offer or where it isn't commonly done.
    Without a `place`, every activity is returned.
    """
    if place is None:
        return list(ACTIVITIES)
    snowing = "snow" in condition.lower()
    favourites = LOCAL_FAVOURITES.get(place.country, ())
    practical = [a for a in ACTIVITIES if is_local(a.needs, place, snowing)]
    return sorted(practical, key=lambda a: a.name not in favourites)


def random_activity(
    location: str,
    condition: str,
    temperature_c: float,
    humidity: float,
    wind_kph: float,
    is_day: bool = True,
    rng: random.Random | None = None,
    searched_as: str = "",
    exclude: str = "",
    place: Place | None = None
) -> ActivityAdvice:
    """
    Pick something to try that suits the current weather and the place.

    Only activities with nothing standing in their way are picked, leaning
    towards outdoor ones when any qualify. Indoor activities always do, so
    there is always a pick. `exclude` is an activity name to leave out, so
    asking again gives something different.

    With a `place`, activities it can't offer or where they aren't commonly
    done are never picked, and local favourites come up more often. In the
    small hours there, only quiet picks are made.

    Returns the same shape as check_activity, with the verdict always "go".
    """
    rng = rng or random
    activity = _pick(condition, temperature_c, humidity, wind_kph, is_day, rng, exclude, place)

    advice = _advise(
        activity, True, location,
        condition, temperature_c, humidity, wind_kph, is_day, rng, searched_as, place
    )
    advice["headline"] = rng.choice(RANDOM_HEADLINES).format(
        name=activity.name, place=location.split(",")[0]
    )
    advice["reasons"].append(_pitch(activity, place))
    return advice


def _pitch(activity: Activity, place: Place | None) -> str:
    """The nudge for an activity, in the local idiom where there is one."""
    country = place.country if place is not None else ""
    return LOCAL_PITCHES.get((activity.name, country), PITCHES[activity.name])


def _pick(
    condition: str,
    temperature_c: float,
    humidity: float,
    wind_kph: float,
    is_day: bool,
    rng: random.Random,
    exclude: str,
    place: Place | None
) -> Activity:
    """Choose an activity with nothing in its way, favouring the outdoors and local favourites."""
    suited = [
        activity for activity in local_activities(place, condition)
        if activity.name != exclude
        and not _issues(activity, condition, temperature_c, humidity, wind_kph, is_day, place)
    ]
    # Nobody wants to be told to light a barbecue at 2am
    if place is not None and is_late_night(place):
        suited = [activity for activity in suited if activity.name in LATE_NIGHT_PICKS] or suited
    outdoor = [activity for activity in suited if activity.category != "indoor"]
    pool = outdoor if outdoor and rng.random() < 0.75 else suited
    favourites = LOCAL_FAVOURITES.get(place.country, ()) if place is not None else ()
    weights = [3 if activity.name in favourites else 1 for activity in pool]
    return rng.choices(pool, weights)[0]


def _advise(
    activity: Activity,
    recognised: bool,
    location: str,
    condition: str,
    temperature_c: float,
    humidity: float,
    wind_kph: float,
    is_day: bool,
    rng: random.Random,
    searched_as: str,
    place: Place | None = None
) -> ActivityAdvice:
    """Build the advice for one activity."""
    place_name = location.split(",")[0]

    issues = _issues(activity, condition, temperature_c, humidity, wind_kph, is_day, place)
    severity = max((level for level, _ in issues), default=0)
    verdict = ("go", "maybe", "skip")[severity]

    reasons = [reason for _, reason in issues]
    if not reasons:
        reasons.append(_good_news(activity, condition, temperature_c, wind_kph, is_day, place))

    suggestion = None
    if verdict == "skip" and place is not None and not is_local(activity.needs, place, "snow" in condition.lower()):
        # The place rules it out, not the weather: offer something that works here
        instead = _pick(condition, temperature_c, humidity, wind_kph, is_day, rng, activity.name, place)
        suggestion = f"Something that does work in {place_name} right now: {instead.name}. {_pitch(instead, place)}"
    elif verdict == "skip":
        suggestion = rng.choice(INDOOR_SWAPS)
    if not recognised:
        reasons.insert(0, "I don't know that one yet, so this is for being outdoors in general.")

    if activity.category == "indoor":
        curiosity_question = "Curious what the weather is doing elsewhere while you're inside? Peek at:"
    elif verdict == "go":
        curiosity_question = f"Curious how {activity.name} is looking elsewhere? Compare with:"
    else:
        curiosity_question = f"Wonder where it's better for {activity.name} right now? Check:"

    return {
        "activity": activity.name,
        "recognised": recognised,
        "verdict": verdict,
        "headline": rng.choice(HEADLINES[verdict]).format(name=activity.name, place=place_name),
        "reasons": reasons,
        "suggestion": suggestion,
        "curiosity": {
            "question": curiosity_question,
            "places": curiosity.pick_places(
                CURIOSITY_PLACES[activity.category], f"{location} {searched_as}", 3, rng
            ),
        },
    }

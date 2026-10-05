"""What is known about a place beyond its weather: country, coast, height."""

from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple


class Place(NamedTuple):
    """The local facts used to decide whether an activity is practical somewhere."""
    name: str = ""                    # Short name, e.g. "Nairobi"
    country: str = ""                 # ISO 3166-1 alpha-2, upper case; "" if unknown
    lat: float = 0.0
    elevation: float | None = None    # Metres above sea level
    coastal: bool | None = None       # Open sea within about 20 km; None if it could not be checked
    sea_temp_c: float | None = None
    local_hour: int | None = None     # Hour of the day there, 0-23; None if unknown


def country_of(display_name: str) -> str:
    """Country code from a display name such as 'Nairobi, KE'; "" if there is none."""
    parts = display_name.rsplit(",", 1)
    code = parts[-1].strip() if len(parts) == 2 else ""
    return code.upper() if len(code) == 2 and code.isalpha() else ""


def build_place(
    display_name: str,
    lat: float,
    forecast: dict[str, Any] | None = None,
    sea: dict[str, Any] | None = None,
    now_utc: datetime | None = None
) -> Place:
    """
    Put together what is known about a place.
    
    `forecast` is WeatherClient.get_forecast's result and `sea` is get_sea's;
    either can be missing, which leaves those facts unknown.
    """
    forecast = forecast or {}
    sea = sea or {}
    local_hour = None
    if forecast.get("utc_offset_seconds") is not None:
        now_utc = now_utc or datetime.now(timezone.utc)
        local_hour = (now_utc + timedelta(seconds=forecast["utc_offset_seconds"])).hour
    return Place(
        name=display_name.split(",")[0].strip(),
        country=country_of(display_name),
        lat=lat,
        elevation=forecast.get("elevation"),
        coastal=sea.get("coastal"),
        sea_temp_c=sea.get("sea_temp_c"),
        local_hour=local_hour,
    )


def is_late_night(place: Place) -> bool:
    """Whether it is the small hours there (23:00 to 05:00), when most people are winding down or asleep."""
    return place.local_hour is not None and (place.local_hour >= 23 or place.local_hour < 5)


# Where an activity is part of everyday life. These lists are judgement calls,
# kept deliberately short: a country is listed only where the activity is
# clearly common, and anywhere else it is treated as hard to find.
SNOW_COUNTRIES = frozenset({
    "NO", "SE", "FI", "IS", "CH", "AT", "FR", "IT", "DE", "AD", "LI", "SI", "SK", "CZ", "PL",
    "RO", "BG", "ES", "RU", "UA", "GE", "AM", "TR", "IR", "LB", "KZ", "KG", "CA", "US", "JP",
    "KR", "CN", "NZ", "AU", "CL", "AR",
})
CRICKET_COUNTRIES = frozenset({
    "IN", "PK", "BD", "LK", "AF", "NP", "AU", "NZ", "GB", "IE", "ZA", "ZW",
    "JM", "TT", "BB", "GY", "AG", "LC", "VC", "GD", "DM", "KN",
})
BASEBALL_COUNTRIES = frozenset({
    "US", "CA", "JP", "KR", "TW", "CU", "DO", "VE", "PR", "MX", "NI", "PA",
})
RUGBY_COUNTRIES = frozenset({
    "NZ", "AU", "ZA", "GB", "IE", "FR", "IT", "AR", "UY", "FJ", "WS", "TO", "JP", "GE", "RO", "NA", "KE",
})
GOLF_COUNTRIES = frozenset({
    "US", "CA", "GB", "IE", "AU", "NZ", "ZA", "JP", "KR", "SE", "DK", "NO", "FI", "DE", "FR",
    "ES", "PT", "NL", "TH", "AE", "MY", "SG",
})
SURF_COUNTRIES = frozenset({
    "AU", "NZ", "US", "MX", "CR", "NI", "SV", "PA", "PE", "CL", "EC", "BR", "PT", "ES", "FR",
    "GB", "IE", "MA", "SN", "ZA", "ID", "PH", "LK", "MV", "JP", "FJ",
})
SPORT_COUNTRIES = {
    "cricket": CRICKET_COUNTRIES,
    "baseball": BASEBALL_COUNTRIES,
    "rugby": RUGBY_COUNTRIES,
    "golf": GOLF_COUNTRIES,
}
# Needs that also require the sea; surfing needs a surfing country as well
COAST_NEEDS = ("coast", "warm_coast", "surf")

# Below this the sea is too cold for snorkelling without a thick wetsuit
WARM_SEA_C = 20

# Activities people in a country are especially likely to do, favoured in random picks
LOCAL_FAVOURITES = {
    "KE": ("running", "football", "a barbecue", "hiking", "rugby"),
    "ET": ("running", "football"),
    "UG": ("football", "a barbecue"),
    "TZ": ("football", "a barbecue"),
    "RW": ("football", "cycling", "hiking"),
    "NG": ("football",),
    "GH": ("football",),
    "SN": ("football",),
    "EG": ("football",),
    "MA": ("football",),
    "ZA": ("a barbecue", "rugby", "cricket", "hiking", "surfing"),
    "GB": ("football", "a walk", "cricket", "gardening"),
    "IE": ("rugby", "a walk", "golf"),
    "FR": ("cycling", "football", "a picnic"),
    "IT": ("football", "cycling"),
    "ES": ("football", "a beach day"),
    "PT": ("football", "surfing"),
    "DE": ("hiking", "cycling", "football"),
    "NL": ("cycling",),
    "DK": ("cycling",),
    "NO": ("snow sports", "hiking"),
    "SE": ("snow sports", "hiking"),
    "FI": ("snow sports", "hiking"),
    "CH": ("snow sports", "hiking"),
    "AT": ("snow sports", "hiking"),
    "US": ("baseball", "basketball", "a barbecue", "hiking"),
    "CA": ("hiking", "camping", "snow sports"),
    "MX": ("football", "baseball"),
    "BR": ("football", "a beach day", "a barbecue"),
    "AR": ("football", "a barbecue"),
    "IN": ("cricket",),
    "PK": ("cricket",),
    "BD": ("cricket",),
    "LK": ("cricket",),
    "JP": ("baseball", "hiking"),
    "KR": ("hiking", "baseball"),
    "AU": ("cricket", "surfing", "a barbecue", "a beach day"),
    "NZ": ("rugby", "hiking"),
}


def _near_slopes(place: Place) -> bool:
    """Whether a place is in snow country: a skiing nation, and far enough from the equator or high enough."""
    if place.country not in SNOW_COUNTRIES:
        return False
    return abs(place.lat) >= 36 or (place.elevation or 0) >= 1000


def local_issue(needs: str, activity: str, place: Place, snowing: bool = False) -> tuple[int, str] | None:
    """
    What makes an activity impractical at a place, as (severity, reason), or None.
    
    `needs` is the activity's requirement: coast, warm_coast, surf, snow, or a
    sport in SPORT_COUNTRIES. Severity 2 means it can't be done here; 1 means it is
    not commonly done, so it takes more effort. Anything unknown about the
    place is given the benefit of the doubt.
    """
    where = place.name or "this place"
    
    if needs in COAST_NEEDS:
        if place.coastal is False:
            return (2, f"{where} isn't on the coast, so {activity} would mean a trip to the sea first.")
        if needs == "warm_coast" and place.sea_temp_c is not None and place.sea_temp_c < WARM_SEA_C:
            return (2, f"The sea off {where} is {round(place.sea_temp_c)}°C — too cold for {activity} without serious kit.")
        if needs == "surf" and place.country and place.country not in SURF_COUNTRIES:
            return (1, f"{activity.capitalize()} isn't a big thing around {where}, so waves and board hire may be hard to find.")
    elif needs == "snow":
        if not snowing and place.country and not _near_slopes(place):
            return (2, f"{activity.capitalize()} aren't something people do around {where} — there are no slopes or reliable snow nearby.")
    elif needs in SPORT_COUNTRIES:
        if place.country and place.country not in SPORT_COUNTRIES[needs]:
            return (1, f"{activity.capitalize()} isn't widely played around {where}, so finding a game or somewhere to play may take some effort.")
    
    return None


def is_local(needs: str, place: Place, snowing: bool = False) -> bool:
    """
    Whether an activity is known to be practical at a place.
    
    Stricter than local_issue: used for suggestions nobody asked for, so
    anything that can't be confirmed (an unknown coast or country) is left out.
    """
    if needs in COAST_NEEDS:
        if place.coastal is not True:
            return False
        if needs == "surf":
            return place.country in SURF_COUNTRIES
        return needs == "coast" or place.sea_temp_c is None or place.sea_temp_c >= WARM_SEA_C
    if needs == "snow":
        return snowing or _near_slopes(place)
    if needs in SPORT_COUNTRIES:
        return place.country in SPORT_COUNTRIES[needs]
    return True

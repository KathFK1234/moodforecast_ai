"""What is known about a place beyond its weather: country, coast, height."""

from typing import Any, NamedTuple


class Place(NamedTuple):
    """The local facts used to decide whether an activity is practical somewhere."""
    name: str = ""                    # Short name, e.g. "Nairobi"
    country: str = ""                 # ISO 3166-1 alpha-2, upper case; "" if unknown
    lat: float = 0.0
    elevation: float | None = None    # Metres above sea level
    coastal: bool | None = None       # Open sea within about 20 km; None if it could not be checked
    sea_temp_c: float | None = None


def country_of(display_name: str) -> str:
    """Country code from a display name such as 'Nairobi, KE'; "" if there is none."""
    parts = display_name.rsplit(",", 1)
    code = parts[-1].strip() if len(parts) == 2 else ""
    return code.upper() if len(code) == 2 and code.isalpha() else ""


def build_place(
    display_name: str,
    lat: float,
    forecast: dict[str, Any] | None = None,
    sea: dict[str, Any] | None = None
) -> Place:
    """
    Put together what is known about a place.
    
    `forecast` is WeatherClient.get_forecast's result and `sea` is get_sea's;
    either can be missing, which leaves those facts unknown.
    """
    forecast = forecast or {}
    sea = sea or {}
    return Place(
        name=display_name.split(",")[0].strip(),
        country=country_of(display_name),
        lat=lat,
        elevation=forecast.get("elevation"),
        coastal=sea.get("coastal"),
        sea_temp_c=sea.get("sea_temp_c"),
    )

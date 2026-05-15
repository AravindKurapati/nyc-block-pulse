from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx

from ..config import settings
from ._utils import to_float

CENSUS_ACS_BASE = "https://api.census.gov/data"
TIGERWEB_TRACTS_BASE = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "TIGERweb/Tracts_Blocks/MapServer"
)

DEFAULT_ACS_YEAR = 2024
NYC_STATE = "36"
NYC_COUNTIES = {
    "005": "Bronx",
    "047": "Brooklyn",
    "061": "Manhattan",
    "081": "Queens",
    "085": "Staten Island",
}
TIGERWEB_ACS_TRACT_LAYER_BY_YEAR = {
    2024: 7,
    2025: 4,
}

ACS_VARIABLES = {
    "median_household_income": "B19013_001E",
    "occupied_housing_units": "B25003_001E",
    "renter_occupied_units": "B25003_003E",
    "education_25_plus": "B15003_001E",
    "bachelors": "B15003_022E",
    "masters": "B15003_023E",
    "professional": "B15003_024E",
    "doctorate": "B15003_025E",
    "total_population": "B01001_001E",
    "male_under_5": "B01001_003E",
    "female_under_5": "B01001_027E",
    "male_65_66": "B01001_020E",
    "male_67_69": "B01001_021E",
    "male_70_74": "B01001_022E",
    "male_75_79": "B01001_023E",
    "male_80_84": "B01001_024E",
    "male_85_plus": "B01001_025E",
    "female_65_66": "B01001_044E",
    "female_67_69": "B01001_045E",
    "female_70_74": "B01001_046E",
    "female_75_79": "B01001_047E",
    "female_80_84": "B01001_048E",
    "female_85_plus": "B01001_049E",
}

MISSING_ESTIMATES = {
    "-666666666",
    "-888888888",
    "-999999999",
    "-222222222",
    "-333333333",
}


def _estimate(value: Any) -> float | None:
    if value in MISSING_ESTIMATES:
        return None
    return to_float(value)


def _percent(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round((numerator / denominator) * 100, 2)


def _sum_values(row: dict[str, Any], keys: Iterable[str]) -> float | None:
    values = [_estimate(row.get(ACS_VARIABLES[key])) for key in keys]
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def normalize_acs_row(row: dict[str, Any], year: int) -> dict[str, Any]:
    state = str(row["state"])
    county = str(row["county"])
    tract = str(row["tract"])
    geoid = f"{state}{county}{tract}"

    occupied_units = _estimate(row.get(ACS_VARIABLES["occupied_housing_units"]))
    renter_units = _estimate(row.get(ACS_VARIABLES["renter_occupied_units"]))
    education_total = _estimate(row.get(ACS_VARIABLES["education_25_plus"]))
    total_population = _estimate(row.get(ACS_VARIABLES["total_population"]))
    bachelors_plus = _sum_values(
        row,
        ("bachelors", "masters", "professional", "doctorate"),
    )
    under_5 = _sum_values(row, ("male_under_5", "female_under_5"))
    over_65 = _sum_values(
        row,
        (
            "male_65_66",
            "male_67_69",
            "male_70_74",
            "male_75_79",
            "male_80_84",
            "male_85_plus",
            "female_65_66",
            "female_67_69",
            "female_70_74",
            "female_75_79",
            "female_80_84",
            "female_85_plus",
        ),
    )

    return {
        "geoid": geoid,
        "tract_name": row.get("NAME"),
        "borough": NYC_COUNTIES.get(county),
        "state": state,
        "county": county,
        "tract": tract,
        "year": year,
        "median_household_income": _estimate(row.get(ACS_VARIABLES["median_household_income"])),
        "renter_occupied_pct": _percent(renter_units, occupied_units),
        "bachelors_or_higher_pct": _percent(bachelors_plus, education_total),
        "under_5_pct": _percent(under_5, total_population),
        "over_65_pct": _percent(over_65, total_population),
        "density_change": 0,
        "raw_json": {"acs": row},
    }


def fetch_acs_estimates(
    year: int = DEFAULT_ACS_YEAR,
    counties: Iterable[str] = NYC_COUNTIES.keys(),
) -> dict[str, dict[str, Any]]:
    variables = ["NAME", *ACS_VARIABLES.values()]
    results: dict[str, dict[str, Any]] = {}

    for county in counties:
        params = {
            "get": ",".join(variables),
            "for": "tract:*",
            "in": f"state:{NYC_STATE} county:{county}",
        }
        if settings.census_api_key:
            params["key"] = settings.census_api_key

        response = httpx.get(f"{CENSUS_ACS_BASE}/{year}/acs/acs5", params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        if not payload:
            continue
        headers = payload[0]
        for values in payload[1:]:
            row = dict(zip(headers, values, strict=True))
            normalized = normalize_acs_row(row, year)
            results[normalized["geoid"]] = normalized

    return results


def _tract_layer(year: int) -> int:
    return TIGERWEB_ACS_TRACT_LAYER_BY_YEAR.get(year, 0)


def fetch_tract_geometries(
    year: int = DEFAULT_ACS_YEAR,
    counties: Iterable[str] = NYC_COUNTIES.keys(),
) -> dict[str, dict[str, Any]]:
    layer = _tract_layer(year)
    geometries: dict[str, dict[str, Any]] = {}

    for county in counties:
        params = {
            "where": f"STATE='{NYC_STATE}' AND COUNTY='{county}'",
            "outFields": "GEOID,NAME,BASENAME,STATE,COUNTY,TRACT",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        }
        response = httpx.get(f"{TIGERWEB_TRACTS_BASE}/{layer}/query", params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        for feature in payload.get("features", []):
            properties = feature.get("properties") or {}
            geoid = properties.get("GEOID")
            if not geoid:
                continue
            geometries[str(geoid)] = feature.get("geometry")

    return geometries


def _relative_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return ((current - previous) / abs(previous)) * 100


def calculate_density_change(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> float:
    if not previous:
        return 0

    changes = [
        _relative_change(current.get(metric), previous.get(metric))
        for metric in (
            "median_household_income",
            "renter_occupied_pct",
            "bachelors_or_higher_pct",
            "under_5_pct",
            "over_65_pct",
        )
    ]
    valid = [abs(change) for change in changes if change is not None]
    return round(max(valid), 2) if valid else 0


def collect_block_demographics(
    year: int = DEFAULT_ACS_YEAR,
    comparison_year: int | None = None,
) -> list[dict[str, Any]]:
    previous_year = comparison_year if comparison_year is not None else year - 5
    current = fetch_acs_estimates(year)
    previous = fetch_acs_estimates(previous_year)
    geometries = fetch_tract_geometries(year)

    rows: list[dict[str, Any]] = []
    for geoid, row in current.items():
        comparison = previous.get(geoid)
        row = {
            **row,
            "density_change": calculate_density_change(row, comparison),
            "geometry": geometries.get(geoid),
            "raw_json": {
                **row.get("raw_json", {}),
                "comparison_year": previous_year,
                "comparison": comparison.get("raw_json", {}) if comparison else None,
            },
        }
        rows.append(row)

    return rows

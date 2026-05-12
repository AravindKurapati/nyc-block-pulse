from __future__ import annotations

from typing import Any

import httpx

from ..config import settings

GEOCLIENT_BASE = "https://api.nyc.gov/geoclient/v2"
BOROUGH_TITLE = {
    "MANHATTAN": "Manhattan",
    "BRONX": "Bronx",
    "BROOKLYN": "Brooklyn",
    "QUEENS": "Queens",
    "STATEN IS": "Staten Island",
    "STATEN ISLAND": "Staten Island",
}


def resolve_address(address: str) -> dict[str, Any] | None:
    """Resolve an address, intersection, or place name via Geoclient v2 /search.

    /search does NLP parsing across all five boroughs, so the caller does not
    have to pre-disambiguate (e.g. '200 Atlantic Ave' resolves without a
    comma-borough suffix). When multiple `POSSIBLE_MATCH` results come back
    from different boroughs, the most-confident one is returned; the caller
    can re-run with an explicit comma-borough to override.
    """
    if not settings.nyc_geoclient_app_key:
        return None

    response = httpx.get(
        f"{GEOCLIENT_BASE}/search.json",
        params={"input": address},
        headers={"Ocp-Apim-Subscription-Key": settings.nyc_geoclient_app_key},
        timeout=10,
    )
    if response.status_code != 200:
        return None

    results = response.json().get("results") or []
    if not results:
        return None

    # Prefer EXACT_MATCH if present; else first POSSIBLE_MATCH.
    best = next((r for r in results if r.get("status") == "EXACT_MATCH"), results[0])
    data = best.get("response", {}) or {}

    lat = data.get("latitudeInternalLabel") or data.get("latitude")
    lon = data.get("longitudeInternalLabel") or data.get("longitude")
    if not lat or not lon:
        return None

    borough_raw = (data.get("firstBoroughName") or "").strip().upper()
    borough = BOROUGH_TITLE.get(borough_raw, borough_raw.title() or "Unknown")

    return {
        "lat": float(lat),
        "lon": float(lon),
        "bbl": data.get("bbl"),
        "bin": data.get("buildingIdentificationNumber"),
        "borough": borough,
    }

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

from nyc_pulse.config import settings

router = APIRouter(prefix="/api", tags=["search"])

GEOCLIENT_BASE = "https://api.nyc.gov/geoclient/v2"
BOROUGH_TITLE = {
    "MANHATTAN": "Manhattan",
    "BRONX": "Bronx",
    "BROOKLYN": "Brooklyn",
    "QUEENS": "Queens",
    "STATEN IS": "Staten Island",
    "STATEN ISLAND": "Staten Island",
}


def _borough(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    return BOROUGH_TITLE.get(raw.upper(), raw.title())


def _display(result: dict[str, Any], fallback: str) -> str:
    data = result.get("response") or {}
    direct = (
        data.get("displayName")
        or data.get("display")
        or data.get("address")
        or data.get("normalizedInput")
        or result.get("input")
    )
    if direct:
        return str(direct)

    house_number = data.get("houseNumber") or data.get("lowHouseNumber") or data.get("addressNumber")
    street = data.get("firstStreetNameNormalized") or data.get("streetName") or data.get("street")
    if house_number and street:
        return f"{house_number} {street}"
    if street:
        return str(street)
    return fallback


def _search_result(result: dict[str, Any], fallback: str) -> dict[str, Any] | None:
    data = result.get("response") or {}
    lat = data.get("latitudeInternalLabel") or data.get("latitude")
    lon = data.get("longitudeInternalLabel") or data.get("longitude")
    if not lat or not lon:
        return None

    return {
        "display": _display(result, fallback),
        "lat": float(lat),
        "lon": float(lon),
        "borough": _borough(data.get("firstBoroughName") or data.get("borough")),
    }


@router.get("/search")
def search(q: str = Query(..., min_length=1)) -> list[dict[str, Any]]:
    if not settings.nyc_geoclient_app_key:
        raise HTTPException(status_code=503, detail="NYC Geoclient credentials are not configured.")

    try:
        response = httpx.get(
            f"{GEOCLIENT_BASE}/search.json",
            params={"input": q},
            headers={"Ocp-Apim-Subscription-Key": settings.nyc_geoclient_app_key},
            timeout=10,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="NYC Geoclient request failed.") from exc

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="NYC Geoclient returned an error.")

    results = []
    for result in response.json().get("results") or []:
        parsed = _search_result(result, q)
        if parsed:
            results.append(parsed)
        if len(results) == 5:
            break

    return results

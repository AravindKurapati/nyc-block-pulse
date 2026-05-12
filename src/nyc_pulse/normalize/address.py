from __future__ import annotations

import re
from typing import Any

import httpx

from ..config import settings

GEOCLIENT_BASE = "https://api.nyc.gov/geo/geoclient/v2"
DEFAULT_BOROUGH = "Manhattan"


def resolve_address(address: str) -> dict[str, Any] | None:
    """Resolve an address or intersection to lat/lon and, when available, BBL/BIN."""
    if not settings.nyc_geoclient_app_key:
        return None

    if "&" in address or re.search(r"\band\b", address, flags=re.IGNORECASE):
        return _resolve_intersection(address)
    return _resolve_street(address)


def _resolve_street(address: str) -> dict[str, Any] | None:
    street_address, borough = _split_borough(address)
    parts = street_address.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    house_number, street = parts
    response = httpx.get(
        f"{GEOCLIENT_BASE}/address.json",
        params={
            "houseNumber": house_number,
            "street": street,
            "borough": borough,
        },
        headers={"Ocp-Apim-Subscription-Key": settings.nyc_geoclient_app_key},
        timeout=10,
    )
    if response.status_code != 200:
        return None
    data = response.json().get("address", {})
    lat = data.get("latitudeInternalLabel") or data.get("latitude")
    lon = data.get("longitudeInternalLabel") or data.get("longitude")
    if not lat or not lon:
        return None
    return {
        "lat": float(lat),
        "lon": float(lon),
        "bbl": data.get("bbl"),
        "bin": data.get("buildingIdentificationNumber"),
        "borough": borough,
    }


def _resolve_intersection(address: str) -> dict[str, Any] | None:
    intersection, borough = _split_borough(address)
    parts = [part.strip() for part in re.split(r"\s*(?:&|\band\b)\s*", intersection, flags=re.IGNORECASE)]
    if len(parts) != 2:
        return None
    response = httpx.get(
        f"{GEOCLIENT_BASE}/intersection.json",
        params={
            "crossStreetOne": parts[0],
            "crossStreetTwo": parts[1],
            "borough": borough,
        },
        headers={"Ocp-Apim-Subscription-Key": settings.nyc_geoclient_app_key},
        timeout=10,
    )
    if response.status_code != 200:
        return None
    data = response.json().get("intersection", {})
    lat = data.get("latitude")
    lon = data.get("longitude")
    if not lat or not lon:
        return None
    return {"lat": float(lat), "lon": float(lon), "bbl": None, "bin": None, "borough": borough}


def _split_borough(value: str) -> tuple[str, str]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return value.strip(), DEFAULT_BOROUGH


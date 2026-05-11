from __future__ import annotations

from typing import Any

import httpx

from ._utils import compact_summary, to_float

SLA_BASE = "https://data.ny.gov/resource/wg8y-fzsj.json"
NYC_COUNTIES = ("NEW YORK", "KINGS", "BRONX", "QUEENS", "RICHMOND")


def collect_liquor(limit: int = 10_000) -> list[dict]:
    county_where = " OR ".join(f"county='{county}'" for county in NYC_COUNTIES)
    response = httpx.get(SLA_BASE, params={"$limit": limit, "$where": county_where}, timeout=60)
    response.raise_for_status()
    rows = response.json()
    events = []
    for row in rows:
        serial = row.get("serial_number") or row.get("license_serial_number")
        if not serial:
            continue
        lat, lon = _coordinates(row.get("georeference"))
        dba = row.get("dba") or row.get("doing_business_as")
        license_type = row.get("license_type_name", "")
        events.append(
            {
                "id": f"sla_{serial}",
                "source": "liquor",
                "event_type": license_type,
                "occurred_at": row.get("effective_date"),
                "address": row.get("premises_address", ""),
                "bbl": None,
                "bin": None,
                "lat": lat,
                "lon": lon,
                "status": row.get("license_status"),
                "category": license_type,
                "summary": compact_summary(dba, license_type),
                "raw_json": row,
            }
        )
    return events


def _coordinates(georeference: Any) -> tuple[float | None, float | None]:
    if not isinstance(georeference, dict):
        return None, None
    coordinates = georeference.get("coordinates")
    if not coordinates or len(coordinates) < 2:
        return None, None
    lon = to_float(coordinates[0])
    lat = to_float(coordinates[1])
    return lat, lon


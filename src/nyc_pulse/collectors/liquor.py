from __future__ import annotations

from typing import Any

from ._utils import compact_summary, to_float
from .socrata import SOCRATA_NY_STATE_BASE, fetch_socrata

NYC_COUNTY_FILTER = (
    "upper(premisescounty) in ('NEW YORK','KINGS','QUEENS','BRONX','RICHMOND')"
)


def collect_liquor(limit: int = 10_000) -> list[dict]:
    rows = fetch_socrata(
        "9s3h-dpkz",
        where=NYC_COUNTY_FILTER,
        limit=limit,
        select="*",
        base_url=SOCRATA_NY_STATE_BASE,
    )
    events: list[dict] = []
    for row in rows:
        license_id = row.get("licensepermitid")
        if not license_id:
            continue
        lat, lon = _coordinates(row.get("georeference"))
        dba = row.get("dba") or row.get("legalname")
        description = row.get("description", "")
        events.append(
            {
                "id": f"sla_{license_id}",
                "source": "liquor",
                "event_type": description,
                "occurred_at": row.get("effectivedate"),
                "address": row.get("actualaddressofpremises", ""),
                "bbl": None,
                "bin": None,
                "lat": lat,
                "lon": lon,
                "status": "ACTIVE",
                "category": description,
                "summary": compact_summary(dba, description),
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

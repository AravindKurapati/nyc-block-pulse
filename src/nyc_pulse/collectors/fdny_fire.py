from __future__ import annotations

from ._utils import compact_summary, to_float
from .socrata import days_ago_filter, fetch_socrata


def collect_fdny_fire(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "erm2-nwe9",
        where=days_ago_filter("incident_datetime", days),
        select="starfire_incident_id,incident_datetime,incident_type_desc,latitude,longitude,borough_desc",
    )
    events = []
    for row in rows:
        incident_id = row.get("starfire_incident_id")
        if not incident_id:
            continue
        lat = to_float(row.get("latitude"))
        lon = to_float(row.get("longitude"))
        if lat is None or lon is None:
            continue
        events.append(
            {
                "id": f"fire_{incident_id}",
                "source": "fdny_fire",
                "event_type": "fire_incident",
                "occurred_at": row.get("incident_datetime"),
                "address": None,
                "bbl": None,
                "bin": None,
                "lat": lat,
                "lon": lon,
                "status": None,
                "category": row.get("incident_type_desc"),
                "summary": compact_summary(row.get("incident_type_desc"), row.get("borough_desc")),
                "raw_json": row,
            }
        )
    return events

from __future__ import annotations

from ._utils import compact_summary, to_float
from .socrata import days_ago_filter, fetch_socrata


def collect_311(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "erm2-nwe9",
        where=days_ago_filter("created_date", days),
        select=(
            "unique_key,complaint_type,descriptor,incident_address,bbl,latitude,"
            "longitude,created_date,status,borough"
        ),
    )
    events = []
    for row in rows:
        unique_key = row.get("unique_key")
        if not unique_key:
            continue
        events.append(
            {
                "id": f"311_{unique_key}",
                "source": "nyc_311",
                "event_type": row.get("complaint_type", ""),
                "occurred_at": row.get("created_date"),
                "address": row.get("incident_address", ""),
                "bbl": row.get("bbl"),
                "bin": None,
                "lat": to_float(row.get("latitude")),
                "lon": to_float(row.get("longitude")),
                "status": row.get("status"),
                "category": row.get("descriptor"),
                "summary": compact_summary(row.get("complaint_type"), row.get("descriptor")),
                "raw_json": row,
            }
        )
    return events


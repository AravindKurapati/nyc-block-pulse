from __future__ import annotations

from ._utils import compact_summary, to_float
from .socrata import days_ago_filter, fetch_socrata


def collect_evictions(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "6z8x-vjye",
        where=days_ago_filter("executed_date", days),
        select="court_index_number,executed_date,eviction_address,latitude,longitude,borough,residential_commercial_ind",
    )
    events = []
    for row in rows:
        court_index = row.get("court_index_number")
        executed_date = row.get("executed_date")
        if not court_index or not executed_date:
            continue
        lat = to_float(row.get("latitude"))
        lon = to_float(row.get("longitude"))
        if lat is None or lon is None:
            continue
        events.append(
            {
                "id": f"eviction_{court_index}_{executed_date[:10]}",
                "source": "evictions",
                "event_type": "eviction",
                "occurred_at": executed_date,
                "address": row.get("eviction_address"),
                "bbl": None,
                "bin": None,
                "lat": lat,
                "lon": lon,
                "status": None,
                "category": row.get("residential_commercial_ind"),
                "summary": compact_summary("Eviction", row.get("eviction_address")),
                "raw_json": row,
            }
        )
    return events

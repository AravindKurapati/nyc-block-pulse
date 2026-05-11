from __future__ import annotations

from ._utils import compact_summary, to_float
from .socrata import days_ago_filter, fetch_socrata


def collect_restaurants(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "43nn-pn8j",
        where=days_ago_filter("inspection_date", days),
        select=(
            "camis,dba,boro,building,street,cuisine_description,inspection_date,"
            "action,violation_code,violation_description,grade,latitude,longitude"
        ),
    )
    events = []
    for row in rows:
        camis = row.get("camis")
        if not camis:
            continue
        inspection_date = row.get("inspection_date", "")
        address = f"{row.get('building', '')} {row.get('street', '')}".strip()
        events.append(
            {
                "id": f"restaurant_{camis}_{inspection_date[:10]}",
                "source": "restaurants",
                "event_type": "inspection",
                "occurred_at": row.get("inspection_date"),
                "address": address,
                "bbl": None,
                "bin": None,
                "lat": to_float(row.get("latitude")),
                "lon": to_float(row.get("longitude")),
                "status": row.get("grade"),
                "category": row.get("cuisine_description"),
                "summary": compact_summary(row.get("dba"), row.get("action")),
                "raw_json": row,
            }
        )
    return events


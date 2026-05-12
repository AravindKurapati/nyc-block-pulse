from __future__ import annotations

from ._utils import compact_summary, to_float
from .socrata import days_ago_filter, fetch_socrata


def collect_hpd_complaints(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "ygpa-z7cr",
        where=days_ago_filter("received_date", days),
        select=(
            "complaint_id,problem_id,type,major_category,minor_category,"
            "problem_code,house_number,street_name,borough,bbl,bin,"
            "latitude,longitude,received_date,complaint_status,complaint_status_date"
        ),
    )
    events = []
    seen: set[str] = set()
    for row in rows:
        complaint_id = row.get("complaint_id")
        if not complaint_id:
            continue
        event_id = f"hpd_complaint_{complaint_id}"
        # The dataset has one row per problem; dedupe to one event per complaint.
        if event_id in seen:
            continue
        seen.add(event_id)
        address = f"{row.get('house_number', '')} {row.get('street_name', '')}".strip()
        events.append(
            {
                "id": event_id,
                "source": "hpd_complaints",
                "event_type": row.get("type", ""),
                "occurred_at": row.get("received_date"),
                "address": address,
                "bbl": row.get("bbl"),
                "bin": row.get("bin"),
                "lat": to_float(row.get("latitude")),
                "lon": to_float(row.get("longitude")),
                "status": row.get("complaint_status"),
                "category": row.get("major_category"),
                "summary": compact_summary(
                    row.get("major_category"),
                    row.get("minor_category"),
                    row.get("problem_code"),
                ),
                "raw_json": row,
            }
        )
    return events

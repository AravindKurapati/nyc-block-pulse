from __future__ import annotations

from ._utils import compact_summary, to_float
from .socrata import days_ago_filter, fetch_socrata


def collect_dob_permits(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "ipu4-2q9a",
        where=days_ago_filter("issuance_date", days),
        select=(
            "job__,job_type,work_type,building_type,house__,street_name,borough,"
            "bin__,bbl,latitude,longitude,issuance_date,job_status,estimated_job_costs"
        ),
    )
    events = []
    for row in rows:
        job_id = row.get("job__")
        if not job_id:
            continue
        address = f"{row.get('house__', '')} {row.get('street_name', '')}".strip()
        cost = row.get("estimated_job_costs") or "?"
        events.append(
            {
                "id": f"dob_permit_{job_id}",
                "source": "dob_permits",
                "event_type": row.get("job_type", ""),
                "occurred_at": row.get("issuance_date"),
                "address": address,
                "bbl": row.get("bbl"),
                "bin": row.get("bin__"),
                "lat": to_float(row.get("latitude")),
                "lon": to_float(row.get("longitude")),
                "status": row.get("job_status"),
                "category": row.get("work_type"),
                "summary": compact_summary(row.get("job_type"), row.get("work_type"), f"est. ${cost}"),
                "raw_json": row,
            }
        )
    return events


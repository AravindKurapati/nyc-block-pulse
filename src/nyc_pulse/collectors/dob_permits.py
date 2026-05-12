from __future__ import annotations

from ._utils import compact_summary, to_float
from .socrata import days_ago_filter, fetch_socrata


def collect_dob_permits(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "rbx6-tga4",
        where=days_ago_filter("issued_date", days),
        select=(
            "job_filing_number,work_permit,filing_reason,work_type,permit_status,"
            "house_no,street_name,borough,bin,bbl,latitude,longitude,"
            "issued_date,approved_date,expired_date,job_description,estimated_job_costs"
        ),
    )
    events = []
    for row in rows:
        permit_id = row.get("work_permit") or row.get("job_filing_number")
        if not permit_id:
            continue
        address = f"{row.get('house_no', '')} {row.get('street_name', '')}".strip()
        cost = row.get("estimated_job_costs") or "?"
        events.append(
            {
                "id": f"dob_permit_{permit_id}",
                "source": "dob_permits",
                "event_type": row.get("filing_reason", ""),
                "occurred_at": row.get("issued_date"),
                "address": address,
                "bbl": row.get("bbl"),
                "bin": row.get("bin"),
                "lat": to_float(row.get("latitude")),
                "lon": to_float(row.get("longitude")),
                "status": row.get("permit_status"),
                "category": row.get("work_type"),
                "summary": compact_summary(
                    row.get("filing_reason"),
                    row.get("work_type"),
                    f"est. ${cost}",
                ),
                "raw_json": row,
            }
        )
    return events

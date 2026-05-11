from __future__ import annotations

from .socrata import days_ago_filter, fetch_socrata


def collect_hpd_violations(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "wvxf-dwi5",
        where=days_ago_filter("inspectiondate", days),
        select=(
            "violationid,class,inspectiondate,approveddate,novdescription,currentstatus,"
            "housenumber,streetname,boro,zip"
        ),
    )
    events = []
    for row in rows:
        violation_id = row.get("violationid")
        if not violation_id:
            continue
        address = f"{row.get('housenumber', '')} {row.get('streetname', '')}".strip()
        events.append(
            {
                "id": f"hpd_violation_{violation_id}",
                "source": "hpd_violations",
                "event_type": row.get("class", ""),
                "occurred_at": row.get("inspectiondate") or row.get("approveddate"),
                "address": address,
                "bbl": None,
                "bin": None,
                "lat": None,
                "lon": None,
                "status": row.get("currentstatus"),
                "category": row.get("class"),
                "summary": row.get("novdescription", ""),
                "raw_json": row,
            }
        )
    return events


from __future__ import annotations

from ._utils import to_float
from .socrata import days_ago_filter, fetch_socrata


def collect_hpd_complaints(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "uwyv-629c",
        where=days_ago_filter("opendate", days),
        select=(
            "complaintid,type,majorcategoryid,minorcategoryid,codedescription,"
            "buildingnumber,streetname,boroughname,bbl,latitude,longitude,opendate,status"
        ),
    )
    events = []
    for row in rows:
        complaint_id = row.get("complaintid")
        if not complaint_id:
            continue
        address = f"{row.get('buildingnumber', '')} {row.get('streetname', '')}".strip()
        events.append(
            {
                "id": f"hpd_complaint_{complaint_id}",
                "source": "hpd_complaints",
                "event_type": row.get("type", ""),
                "occurred_at": row.get("opendate"),
                "address": address,
                "bbl": row.get("bbl"),
                "bin": None,
                "lat": to_float(row.get("latitude")),
                "lon": to_float(row.get("longitude")),
                "status": row.get("status"),
                "category": row.get("codedescription"),
                "summary": row.get("codedescription", ""),
                "raw_json": row,
            }
        )
    return events


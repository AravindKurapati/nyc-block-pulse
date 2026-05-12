from __future__ import annotations

from ._utils import compact_summary, to_float
from .socrata import days_ago_filter, fetch_socrata


def collect_nypd_crime(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "qgea-i56i",
        where=days_ago_filter("cmplnt_fr_dt", days),
        select="cmplnt_num,cmplnt_fr_dt,ofns_desc,law_cat_cd,latitude,longitude,boro_nm",
    )
    events = []
    for row in rows:
        cmplnt_num = row.get("cmplnt_num")
        if not cmplnt_num:
            continue
        lat = to_float(row.get("latitude"))
        lon = to_float(row.get("longitude"))
        if lat is None or lon is None:
            continue
        events.append(
            {
                "id": f"crime_{cmplnt_num}",
                "source": "nypd_crime",
                "event_type": (row.get("law_cat_cd") or "").lower(),
                "occurred_at": row.get("cmplnt_fr_dt"),
                "address": None,
                "bbl": None,
                "bin": None,
                "lat": lat,
                "lon": lon,
                "status": None,
                "category": row.get("ofns_desc"),
                "summary": compact_summary(row.get("ofns_desc"), row.get("law_cat_cd")),
                "raw_json": row,
            }
        )
    return events

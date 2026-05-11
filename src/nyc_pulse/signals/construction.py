from __future__ import annotations

from sqlalchemy.orm import Session

from ._common import evidence, fetch_nearby_events


def score_construction(lat: float, lon: float, radius_ft: int = 500, window_days: int = 90, session: Session | None = None) -> dict:
    rows = fetch_nearby_events(["dob_permits"], lat, lon, radius_ft, window_days, session=session)
    high_signal_terms = ("alteration", "alt", "new building", "nb", "demolition", "dm")
    high_value = [
        row
        for row in rows
        if any(term in f"{row.get('category') or ''} {row.get('event_type') or ''}".lower() for term in high_signal_terms)
    ]
    score = len(rows) + len(high_value) * 0.5
    return {
        "signal_type": "construction_pressure",
        "score": round(score, 2),
        "count": len(rows),
        "evidence": evidence(rows),
    }

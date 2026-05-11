from __future__ import annotations

from sqlalchemy.orm import Session

from ._common import evidence, fetch_nearby_events


def score_quality_of_life(lat: float, lon: float, radius_ft: int = 500, window_days: int = 90, session: Session | None = None) -> dict:
    rows = fetch_nearby_events(["nyc_311"], lat, lon, radius_ft, window_days, session=session)
    terms = (
        "noise",
        "sanitation",
        "rodent",
        "illegal parking",
        "blocked driveway",
        "sidewalk",
        "street condition",
        "graffiti",
    )
    relevant = [
        row
        for row in rows
        if any(term in f"{row.get('event_type') or ''} {row.get('category') or ''} {row.get('summary') or ''}".lower() for term in terms)
    ]
    score = len(relevant)
    return {
        "signal_type": "quality_of_life_drift",
        "score": round(score, 2),
        "count": len(relevant),
        "evidence": evidence(relevant),
    }

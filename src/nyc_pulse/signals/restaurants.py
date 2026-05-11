from __future__ import annotations

from sqlalchemy.orm import Session

from ._common import evidence, fetch_nearby_events


def score_restaurants(lat: float, lon: float, radius_ft: int = 500, window_days: int = 90, session: Session | None = None) -> dict:
    rows = fetch_nearby_events(["restaurants", "liquor", "dob_permits"], lat, lon, radius_ft, window_days, session=session)
    relevant = [
        row
        for row in rows
        if row.get("source") in {"restaurants", "liquor"}
        or "plumbing" in f"{row.get('category') or ''}".lower()
        or "alteration" in f"{row.get('event_type') or ''} {row.get('category') or ''}".lower()
    ]
    restaurant_count = sum(1 for row in relevant if row.get("source") == "restaurants")
    liquor_count = sum(1 for row in relevant if row.get("source") == "liquor")
    buildout_count = sum(1 for row in relevant if row.get("source") == "dob_permits")
    score = restaurant_count + liquor_count * 0.5 + buildout_count * 0.75
    return {
        "signal_type": "restaurant_turnover",
        "score": round(score, 2),
        "count": len(relevant),
        "evidence": evidence(relevant),
    }

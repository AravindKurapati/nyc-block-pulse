from __future__ import annotations

from sqlalchemy.orm import Session

from ._common import evidence, fetch_nearby_events


def score_crime(
    lat: float,
    lon: float,
    radius_ft: int = 500,
    window_days: int = 90,
    session: Session | None = None,
) -> dict:
    rows = fetch_nearby_events(["nypd_crime"], lat, lon, radius_ft, window_days, session=session)
    score = sum(
        2.0
        if row.get("event_type") == "felony"
        else 1.0
        if row.get("event_type") == "misdemeanor"
        else 0.5
        for row in rows
    )
    return {
        "signal_type": "crime_complaints",
        "score": round(score, 2),
        "count": len(rows),
        "evidence": evidence(rows),
    }

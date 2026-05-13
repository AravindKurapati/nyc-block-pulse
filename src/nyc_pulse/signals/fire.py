from __future__ import annotations

from sqlalchemy.orm import Session

from ._common import evidence, fetch_nearby_events


def score_fire(
    lat: float,
    lon: float,
    radius_ft: int = 500,
    window_days: int = 90,
    session: Session | None = None,
) -> dict:
    rows = fetch_nearby_events(["fdny_fire"], lat, lon, radius_ft, window_days, session=session)
    return {
        "signal_type": "fire_incidents",
        "score": round(float(len(rows)), 2),
        "count": len(rows),
        "evidence": evidence(rows),
    }

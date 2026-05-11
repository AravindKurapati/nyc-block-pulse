from __future__ import annotations

from ._common import evidence, fetch_nearby_events


def score_housing(lat: float, lon: float, radius_ft: int = 500, window_days: int = 90) -> dict:
    rows = fetch_nearby_events(["hpd_complaints", "hpd_violations", "nyc_311"], lat, lon, radius_ft, window_days)
    terms = ("heat", "hot water", "mold", "paint", "leak", "pest", "rodent", "elevator")
    relevant = [
        row
        for row in rows
        if row.get("source") != "nyc_311"
        or any(term in f"{row.get('event_type') or ''} {row.get('category') or ''} {row.get('summary') or ''}".lower() for term in terms)
    ]
    severe = [
        row
        for row in relevant
        if "class c" in f"{row.get('category') or ''} {row.get('event_type') or ''}".lower()
        or "open" in f"{row.get('status') or ''}".lower()
    ]
    score = len(relevant) + len(severe) * 0.5
    return {
        "signal_type": "housing_distress",
        "score": round(score, 2),
        "count": len(relevant),
        "evidence": evidence(relevant),
    }


from __future__ import annotations

from ._common import evidence, fetch_nearby_events


def score_nightlife(lat: float, lon: float, radius_ft: int = 500, window_days: int = 90) -> dict:
    rows = fetch_nearby_events(["liquor", "nyc_311", "restaurants"], lat, lon, radius_ft, window_days)
    relevant = [
        row
        for row in rows
        if row.get("source") != "nyc_311"
        or "noise" in f"{row.get('event_type') or ''} {row.get('category') or ''}".lower()
    ]
    liquor_count = sum(1 for row in relevant if row.get("source") == "liquor")
    noise_count = sum(1 for row in relevant if row.get("source") == "nyc_311")
    restaurant_count = sum(1 for row in relevant if row.get("source") == "restaurants")
    score = liquor_count * 1.5 + noise_count + restaurant_count * 0.4
    return {
        "signal_type": "nightlife_activity",
        "score": round(score, 2),
        "count": len(relevant),
        "evidence": evidence(relevant),
    }


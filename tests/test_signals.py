from __future__ import annotations

from nyc_pulse.signals import construction


def test_score_construction_scores_nearby_dob_events(monkeypatch):
    monkeypatch.setattr(construction, "fetch_nearby_events", lambda *args, **kwargs: [
        {
            "id": "dob_permit_1",
            "source": "dob_permits",
            "event_type": "ALT",
            "summary": "ALT - interior renovation",
            "occurred_at": "2026-05-01",
            "category": "Alteration",
            "status": "Issued",
            "raw_json": {},
        }
    ])

    result = construction.score_construction(40.7, -73.9)

    assert result["signal_type"] == "construction_pressure"
    assert result["score"] > 0
    assert result["count"] == 1
    assert result["evidence"][0]["id"] == "dob_permit_1"

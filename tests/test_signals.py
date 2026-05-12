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


def test_score_crime_weights_by_severity(monkeypatch):
    from nyc_pulse.signals import crime

    monkeypatch.setattr(
        crime,
        "fetch_nearby_events",
        lambda *args, **kwargs: [
            {
                "id": "crime_1",
                "source": "nypd_crime",
                "event_type": "felony",
                "summary": "ROBBERY",
                "occurred_at": "2026-05-01",
                "category": "ROBBERY",
                "status": None,
                "raw_json": {},
            },
            {
                "id": "crime_2",
                "source": "nypd_crime",
                "event_type": "misdemeanor",
                "summary": "ASSAULT",
                "occurred_at": "2026-05-02",
                "category": "ASSAULT",
                "status": None,
                "raw_json": {},
            },
            {
                "id": "crime_3",
                "source": "nypd_crime",
                "event_type": "violation",
                "summary": "DISORDERLY",
                "occurred_at": "2026-05-03",
                "category": "DISORDERLY",
                "status": None,
                "raw_json": {},
            },
        ],
    )

    result = crime.score_crime(40.7, -73.9)

    assert result["signal_type"] == "crime_complaints"
    assert result["score"] == 3.5
    assert result["count"] == 3
    assert len(result["evidence"]) == 3


def test_score_fire_flat_count(monkeypatch):
    from nyc_pulse.signals import fire

    monkeypatch.setattr(
        fire,
        "fetch_nearby_events",
        lambda *args, **kwargs: [
            {
                "id": "fire_1",
                "source": "fdny_fire",
                "event_type": "fire_incident",
                "summary": "111 - Building fire",
                "occurred_at": "2026-05-01",
                "category": "111 - Building fire",
                "status": None,
                "raw_json": {},
            },
            {
                "id": "fire_2",
                "source": "fdny_fire",
                "event_type": "fire_incident",
                "summary": "321 - EMS call",
                "occurred_at": "2026-05-02",
                "category": "321 - EMS call",
                "status": None,
                "raw_json": {},
            },
        ],
    )

    result = fire.score_fire(40.7, -73.9)

    assert result["signal_type"] == "fire_incidents"
    assert result["score"] == 2.0
    assert result["count"] == 2
    assert len(result["evidence"]) == 2

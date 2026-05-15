from __future__ import annotations

from nyc_pulse.signals import construction, demographics


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


class FakeMappingResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class FakeDemographicsSession:
    def __init__(self, row):
        self.row = row
        self.closed = False
        self.rolled_back = False

    def execute(self, statement, params):
        sql = str(statement)
        assert "block_demographics" in sql
        assert params == {"lat": 40.7, "lon": -73.9}
        return FakeMappingResult(self.row)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_score_density_change_returns_tract_signal():
    session = FakeDemographicsSession(
        {
            "geoid": "36061000100",
            "tract_name": "Census Tract 1",
            "borough": "Manhattan",
            "year": 2024,
            "median_household_income": 120000,
            "renter_occupied_pct": 82.4,
            "bachelors_or_higher_pct": 78.1,
            "under_5_pct": 3.2,
            "over_65_pct": 14.8,
            "density_change": 11.5,
        }
    )

    result = demographics.score_density_change(40.7, -73.9, session=session)

    assert result["signal_type"] == "density_change"
    assert result["score"] == 11.5
    assert result["count"] == 1
    assert result["evidence"][0]["id"] == "36061000100"
    assert "income $120,000" in result["evidence"][0]["summary"]
    assert session.rolled_back is True

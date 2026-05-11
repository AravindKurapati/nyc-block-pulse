from __future__ import annotations

from nyc_pulse.collectors import nyc_311
from nyc_pulse.collectors.socrata import days_ago_filter, fetch_socrata


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_fetch_socrata_passes_expected_request(monkeypatch):
    captured = {}

    def fake_get(url, params, headers, timeout):
        captured.update({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return FakeResponse([{"id": "1"}])

    monkeypatch.setattr("nyc_pulse.collectors.socrata.httpx.get", fake_get)

    rows = fetch_socrata("abcd-1234", "created_date >= '2026-01-01'", select="id")

    assert rows == [{"id": "1"}]
    assert captured["url"].endswith("/abcd-1234.json")
    assert captured["params"]["$where"] == "created_date >= '2026-01-01'"
    assert captured["params"]["$select"] == "id"
    assert captured["timeout"] == 60


def test_collect_311_normalizes_event_shape(monkeypatch):
    def fake_fetch(dataset_id, where, select, limit=50_000, offset=0):
        assert dataset_id == "erm2-nwe9"
        assert "created_date" in where
        return [
            {
                "unique_key": "42",
                "complaint_type": "Noise",
                "descriptor": "Loud Music",
                "incident_address": "1 MAIN ST",
                "bbl": "1000010001",
                "latitude": "40.7",
                "longitude": "-73.9",
                "created_date": "2026-05-01T00:00:00",
                "status": "Open",
            }
        ]

    monkeypatch.setattr(nyc_311, "fetch_socrata", fake_fetch)

    event = nyc_311.collect_311(days=7)[0]

    assert event["id"] == "311_42"
    assert event["source"] == "nyc_311"
    assert event["event_type"] == "Noise"
    assert event["lat"] == 40.7
    assert event["lon"] == -73.9
    assert event["raw_json"]["unique_key"] == "42"


def test_days_ago_filter_uses_requested_field():
    assert days_ago_filter("created_date", 7).startswith("created_date >= '")


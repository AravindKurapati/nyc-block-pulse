from __future__ import annotations

from nyc_pulse.db import upsert_events


class FakeResult:
    def __init__(self, rowcount):
        self.rowcount = rowcount


class FakeSession:
    def __init__(self):
        self.ids = set()
        self.commits = 0

    def execute(self, statement, params):
        # Support both single-dict (legacy) and list-of-dicts (batched) signatures.
        batch = params if isinstance(params, list) else [params]
        inserted = 0
        for p in batch:
            if p["id"] in self.ids:
                continue
            self.ids.add(p["id"])
            inserted += 1
        return FakeResult(inserted)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def test_upsert_events_is_idempotent_for_duplicate_ids():
    session = FakeSession()
    event = {
        "id": "311_42",
        "source": "nyc_311",
        "event_type": "Noise",
        "occurred_at": "2026-05-01T00:00:00",
        "address": "1 MAIN ST",
        "bbl": None,
        "bin": None,
        "lat": 40.7,
        "lon": -73.9,
        "status": "Open",
        "category": "Loud Music",
        "summary": "Noise - Loud Music",
        "raw_json": {"unique_key": "42"},
    }

    assert upsert_events(session, [event]) == 1
    assert upsert_events(session, [event]) == 0
    assert session.ids == {"311_42"}
    assert session.commits == 2


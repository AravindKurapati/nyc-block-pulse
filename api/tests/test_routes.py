from __future__ import annotations

from fastapi.testclient import TestClient

from api.deps import get_db_session
from api.main import app


class FakeSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_block_scores_all_signals_with_one_session(monkeypatch):
    fake_session = FakeSession()
    seen_sessions = []

    def override_session():
        try:
            yield fake_session
        finally:
            fake_session.close()

    def fake_score(lat, lon, radius_ft, window_days, session):
        seen_sessions.append(session)
        return {
            "signal_type": "test_signal",
            "score": 1.0,
            "count": 1,
            "evidence": [{"id": "event_1", "source": "nyc_311", "summary": "Noise", "date": "2026-05-01"}],
        }

    import api.routes.block as block_route

    for name in (
        "score_construction",
        "score_nightlife",
        "score_housing",
        "score_restaurants",
        "score_quality_of_life",
    ):
        monkeypatch.setattr(block_route, name, fake_score)

    app.dependency_overrides[get_db_session] = override_session
    try:
        response = TestClient(app).post("/api/block", json={"lat": 40.71978, "lon": -73.98877})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["location"]["lat"] == 40.71978
    assert body["window_days"] == 90
    assert set(body["signals"]) == {"construction", "nightlife", "housing", "restaurants", "quality_of_life"}
    assert seen_sessions == [fake_session] * 5
    assert fake_session.closed is True


class FakeRow:
    def __init__(self, **values):
        self._mapping = values


class FakeResult:
    def __init__(self, *, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one(self):
        return self._scalar

    def fetchall(self):
        return self._rows


class FakeEventsSession(FakeSession):
    def execute(self, statement, params):
        sql = str(statement)
        if "count(*)" in sql:
            return FakeResult(scalar=2)
        assert params["sources"] == ("nyc_311",)
        assert params["limit"] == 1
        assert "ORDER BY random()" in sql
        return FakeResult(
            rows=[
                FakeRow(
                    id="311_1",
                    source="nyc_311",
                    summary="Noise - Loud Music",
                    occurred_at="2026-05-09T12:00:00Z",
                    lon=-73.99,
                    lat=40.72,
                )
            ]
        )


def test_events_returns_sampled_feature_collection():
    fake_session = FakeEventsSession()

    def override_session():
        try:
            yield fake_session
        finally:
            fake_session.close()

    app.dependency_overrides[get_db_session] = override_session
    try:
        response = TestClient(app).get(
            "/api/events",
            params={
                "signal": "quality_of_life",
                "bbox": "-74.1,40.5,-73.7,40.9",
                "days": 90,
                "limit": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert body["sampled"] is True
    assert body["total_match"] == 2
    assert body["features"][0]["geometry"]["coordinates"] == [-73.99, 40.72]
    assert body["features"][0]["properties"]["id"] == "311_1"

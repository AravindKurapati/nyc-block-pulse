from __future__ import annotations

from fastapi.testclient import TestClient

from api.deps import get_db_session
from api.main import app
from nyc_pulse.normalize.address import GEOCLIENT_BASE


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
        "score_density_change",
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
    assert set(body["signals"]) == {
        "construction",
        "nightlife",
        "housing",
        "restaurants",
        "quality_of_life",
        "density_change",
    }
    assert seen_sessions == [fake_session] * 6
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


class FakeTrendSession(FakeSession):
    def execute(self, statement, params):
        sql = str(statement)
        assert "generate_series" in sql
        assert "ST_DWithin" in sql
        assert params["sources"] == ("dob_permits",)
        assert params["days"] == 3
        assert round(params["radius_m"], 2) == 152.4
        return FakeResult(
            rows=[
                FakeRow(date="2026-05-12", count=0),
                FakeRow(date="2026-05-13", count=2),
                FakeRow(date="2026-05-14", count=1),
            ]
        )


def test_signal_trend_returns_daily_counts():
    fake_session = FakeTrendSession()

    def override_session():
        try:
            yield fake_session
        finally:
            fake_session.close()

    app.dependency_overrides[get_db_session] = override_session
    try:
        response = TestClient(app).get(
            "/api/signal-trend",
            params={
                "signal": "construction",
                "lat": 40.7295,
                "lon": -73.998,
                "radius_ft": 500,
                "days": 3,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {"date": "2026-05-12", "count": 0},
        {"date": "2026-05-13", "count": 2},
        {"date": "2026-05-14", "count": 1},
    ]


class FakeDemographicsSession(FakeSession):
    def execute(self, statement, params):
        sql = str(statement)
        assert "block_demographics" in sql
        assert "ST_MakeEnvelope" in sql
        assert params["min_lon"] == -74.1
        assert params["limit"] == 10
        return FakeResult(
            rows=[
                FakeRow(
                    geoid="36061000100",
                    tract_name="Census Tract 1; New York County; New York",
                    borough="Manhattan",
                    year=2024,
                    median_household_income=120000,
                    renter_occupied_pct=82.4,
                    bachelors_or_higher_pct=78.1,
                    under_5_pct=3.2,
                    over_65_pct=14.8,
                    density_change=11.5,
                    geometry={
                        "type": "MultiPolygon",
                        "coordinates": [
                            [[[-74.0, 40.7], [-73.99, 40.7], [-73.99, 40.71], [-74.0, 40.7]]]
                        ],
                    },
                )
            ]
        )


def test_demographics_returns_tract_feature_collection():
    fake_session = FakeDemographicsSession()

    def override_session():
        try:
            yield fake_session
        finally:
            fake_session.close()

    app.dependency_overrides[get_db_session] = override_session
    try:
        response = TestClient(app).get(
            "/api/demographics",
            params={"bbox": "-74.1,40.5,-73.7,40.9", "limit": 10},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"][0]["geometry"]["type"] == "MultiPolygon"
    assert body["features"][0]["properties"]["geoid"] == "36061000100"
    assert body["features"][0]["properties"]["density_change"] == 11.5


class FakeHttpResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def test_search_returns_top_five_geoclient_results(monkeypatch):
    captured = {}
    payload = {
        "results": [
            {
                "status": "EXACT_MATCH",
                "response": {
                    "latitudeInternalLabel": "40.689813",
                    "longitudeInternalLabel": "-73.992842",
                    "houseNumber": "200",
                    "firstStreetNameNormalized": "ATLANTIC AVENUE",
                    "firstBoroughName": "BROOKLYN",
                },
            },
            {
                "status": "POSSIBLE_MATCH",
                "response": {
                    "latitude": "40.591643",
                    "longitude": "-74.091693",
                    "displayName": "200 Atlantic Ave",
                    "firstBoroughName": "STATEN IS",
                },
            },
            {"status": "POSSIBLE_MATCH", "response": {"latitude": "", "longitude": "-73.9"}},
            *[
                {
                    "status": "POSSIBLE_MATCH",
                    "response": {
                        "latitude": f"40.{index}",
                        "longitude": f"-73.{index}",
                        "displayName": f"Result {index}",
                        "firstBoroughName": "QUEENS",
                    },
                }
                for index in range(3, 8)
            ],
        ]
    }

    def fake_get(url, params, headers, timeout):
        captured.update({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return FakeHttpResponse(payload)

    import api.routes.search as search_route

    monkeypatch.setattr(search_route.settings, "nyc_geoclient_app_key", "key")
    monkeypatch.setattr(search_route.httpx, "get", fake_get)

    response = TestClient(app).get("/api/search", params={"q": "200 Atlantic Ave"})

    assert response.status_code == 200
    assert captured["url"] == f"{GEOCLIENT_BASE}/search.json"
    assert captured["params"] == {"input": "200 Atlantic Ave"}
    assert captured["headers"] == {"Ocp-Apim-Subscription-Key": "key"}
    body = response.json()
    assert len(body) == 5
    assert body[0] == {
        "display": "200 ATLANTIC AVENUE",
        "lat": 40.689813,
        "lon": -73.992842,
        "borough": "Brooklyn",
    }
    assert body[1]["borough"] == "Staten Island"


def test_search_returns_503_without_geoclient_credentials(monkeypatch):
    import api.routes.search as search_route

    monkeypatch.setattr(search_route.settings, "nyc_geoclient_app_key", "")

    response = TestClient(app).get("/api/search", params={"q": "200 Atlantic Ave"})

    assert response.status_code == 503
    assert response.json()["detail"] == "NYC Geoclient credentials are not configured."

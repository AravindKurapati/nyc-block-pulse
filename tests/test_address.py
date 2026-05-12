from __future__ import annotations

from nyc_pulse.normalize import address


def _search_response(status, response_body, *extra):
    """Build a Geoclient /search-shaped payload with one or more results."""
    results = [{"status": status, "response": response_body}, *extra]
    return {"id": "test", "status": "OK", "input": "x", "results": results}


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_resolve_address_returns_geoclient_fields(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout, headers=None):
        captured.update({"url": url, "params": params, "timeout": timeout, "headers": headers})
        return FakeResponse()

    monkeypatch.setattr(address.settings, "nyc_geoclient_app_key", "key")
    monkeypatch.setattr(address.httpx, "get", fake_get)

    result = address.resolve_address("123 Ludlow St")

    assert result == {
        "lat": 40.721,
        "lon": -73.987,
        "bbl": "1000010001",
        "bin": "1000001",
        "borough": "Manhattan",
    }
    assert captured["url"].endswith("/search.json")
    assert captured["params"]["input"] == "123 Ludlow St"


def test_resolve_address_prefers_exact_match_over_possible(monkeypatch):
    """When /search returns both EXACT and POSSIBLE matches, EXACT wins."""
    payload = _search_response(
        "POSSIBLE_MATCH",
        {
            "latitude": "40.0",
            "longitude": "-74.0",
            "firstBoroughName": "STATEN IS",
        },
        {
            "status": "EXACT_MATCH",
            "response": {
                "latitude": "40.689",
                "longitude": "-73.992",
                "firstBoroughName": "BROOKLYN",
                "bbl": "3002867505",
            },
        },
    )
    monkeypatch.setattr(address.settings, "nyc_geoclient_app_key", "key")
    monkeypatch.setattr(address.httpx, "get", lambda *a, **kw: FakeResponse(payload))

    result = address.resolve_address("200 Atlantic Ave")
    assert result["borough"] == "Brooklyn"
    assert result["lat"] == 40.689


def test_resolve_address_returns_first_possible_when_no_exact(monkeypatch):
    """Outer-borough addresses with no EXACT_MATCH should still resolve."""
    payload = _search_response(
        "POSSIBLE_MATCH",
        {
            "latitude": "40.689813",
            "longitude": "-73.992842",
            "firstBoroughName": "BROOKLYN",
        },
    )
    monkeypatch.setattr(address.settings, "nyc_geoclient_app_key", "key")
    monkeypatch.setattr(address.httpx, "get", lambda *a, **kw: FakeResponse(payload))

    result = address.resolve_address("200 Atlantic Ave, Brooklyn")
    assert result["borough"] == "Brooklyn"
    assert result["lat"] == 40.689813


def test_resolve_address_handles_no_results(monkeypatch):
    """Empty results list → None (not a crash)."""
    payload = {"id": "x", "status": "OK", "input": "nope", "results": []}
    monkeypatch.setattr(address.settings, "nyc_geoclient_app_key", "key")
    monkeypatch.setattr(address.httpx, "get", lambda *a, **kw: FakeResponse(payload))

    assert address.resolve_address("not a real place") is None


def test_resolve_address_without_credentials_returns_none(monkeypatch):
    monkeypatch.setattr(address.settings, "nyc_geoclient_app_key", "")

    assert address.resolve_address("123 Ludlow St") is None

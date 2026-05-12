from __future__ import annotations

from nyc_pulse.normalize import address


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "address": {
                "latitude": "40.721",
                "longitude": "-73.987",
                "bbl": "1000010001",
                "buildingIdentificationNumber": "1000001",
            }
        }


def test_resolve_address_returns_geoclient_fields(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured.update({"url": url, "params": params, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(address.settings, "nyc_geoclient_app_key", "key")
    monkeypatch.setattr(address.httpx, "get", fake_get)

    result = address.resolve_address("123 Ludlow St, Manhattan")

    assert result == {
        "lat": 40.721,
        "lon": -73.987,
        "bbl": "1000010001",
        "bin": "1000001",
        "borough": "Manhattan",
    }
    assert captured["url"].endswith("/address.json")
    assert captured["params"]["houseNumber"] == "123"
    assert captured["params"]["street"] == "Ludlow St"


def test_resolve_address_without_credentials_returns_none(monkeypatch):
    monkeypatch.setattr(address.settings, "nyc_geoclient_app_key", "")

    assert address.resolve_address("123 Ludlow St") is None


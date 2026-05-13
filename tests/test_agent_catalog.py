from __future__ import annotations


def test_has_geo_fields_true_when_lat_lon_present():
    from nyc_pulse.agent.catalog import has_geo_fields
    columns = ["incident_datetime", "latitude", "longitude", "borough"]
    assert has_geo_fields(columns) is True


def test_has_geo_fields_false_when_missing():
    from nyc_pulse.agent.catalog import has_geo_fields
    assert has_geo_fields(["date", "description", "borough"]) is False


def test_has_date_field_true():
    from nyc_pulse.agent.catalog import has_date_field
    assert has_date_field(["cmplnt_fr_dt", "latitude", "longitude"]) is True


def test_has_date_field_false():
    from nyc_pulse.agent.catalog import has_date_field
    assert has_date_field(["latitude", "longitude", "description"]) is False


def test_prefilter_skips_known_ids(monkeypatch):
    from nyc_pulse.agent import catalog

    pages = [
        {
            "results": [
                {
                    "resource": {
                        "id": "known-1111",
                        "name": "Known Dataset",
                        "description": "already evaluated",
                        "columns_name": ["date", "latitude", "longitude"],
                    }
                },
                {
                    "resource": {
                        "id": "new1-2222",
                        "name": "New Dataset",
                        "description": "fresh",
                        "columns_name": ["incident_date", "latitude", "longitude"],
                    }
                },
            ],
            "resultSetSize": 2,
        }
    ]
    call_count = 0

    def fake_get(url, params, headers, timeout):
        nonlocal call_count
        class R:
            def raise_for_status(self): pass
            def json(self): return pages[call_count - 1] if call_count <= len(pages) else {"results": [], "resultSetSize": 0}
        call_count += 1
        return R()

    monkeypatch.setattr(catalog.httpx, "get", fake_get)

    already_known = {"known-1111"}
    results = catalog.fetch_candidates(already_known)
    ids = [r["id"] for r in results]
    assert "known-1111" not in ids
    assert "new1-2222" in ids

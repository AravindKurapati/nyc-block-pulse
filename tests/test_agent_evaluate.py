from __future__ import annotations

import json


def test_evaluate_returns_result_on_high_score(monkeypatch):
    from nyc_pulse.agent import evaluate

    gemini_response = json.dumps({
        "score": 8,
        "rationale": "Geo-tagged noise complaints useful for nightlife signal",
        "signal_name": "noise_complaints",
        "date_field": "created_date",
        "id_field": "unique_key",
        "lat_field": "latitude",
        "lon_field": "longitude",
        "category_field": "complaint_type",
        "summary_fields": ["descriptor", "complaint_type"],
    })

    class FakeResponse:
        text = gemini_response

    class FakeModel:
        def generate_content(self, prompt):
            return FakeResponse()

    monkeypatch.setattr(evaluate, "_get_model", lambda: FakeModel())

    candidate = {
        "id": "fhrw-4uyv",
        "name": "311 Service Requests",
        "description": "All 311 service requests",
        "columns": ["unique_key", "created_date", "complaint_type", "descriptor", "latitude", "longitude"],
    }
    result = evaluate.evaluate_dataset(candidate)
    assert result is not None
    assert result["score"] == 8
    assert result["signal_name"] == "noise_complaints"
    assert result["dataset_id"] == "fhrw-4uyv"


def test_evaluate_returns_result_with_low_score(monkeypatch):
    """Low-score datasets return the dict (not None) so state.json retains score/rationale."""
    from nyc_pulse.agent import evaluate

    gemini_response = json.dumps({
        "score": 4,
        "rationale": "Aggregate statistics, no event-level data",
        "signal_name": "budget_data",
        "date_field": "fiscal_year",
        "id_field": "id",
        "lat_field": "latitude",
        "lon_field": "longitude",
        "category_field": None,
        "summary_fields": [],
    })

    class FakeResponse:
        text = gemini_response

    class FakeModel:
        def generate_content(self, prompt):
            return FakeResponse()

    monkeypatch.setattr(evaluate, "_get_model", lambda: FakeModel())

    candidate = {
        "id": "low1-scor",
        "name": "Budget Data",
        "description": "City budget aggregates",
        "columns": ["fiscal_year", "latitude", "longitude"],
    }
    result = evaluate.evaluate_dataset(candidate)
    assert result is not None
    assert result["score"] == 4
    assert result["rationale"] == "Aggregate statistics, no event-level data"


def test_evaluate_returns_none_on_malformed_json(monkeypatch):
    from nyc_pulse.agent import evaluate

    class FakeResponse:
        text = "not valid json at all"

    class FakeModel:
        def generate_content(self, prompt):
            return FakeResponse()

    monkeypatch.setattr(evaluate, "_get_model", lambda: FakeModel())

    result = evaluate.evaluate_dataset({
        "id": "bad1-json",
        "name": "Bad",
        "description": "bad",
        "columns": ["date", "latitude", "longitude"],
    })
    assert result is None

from __future__ import annotations


def test_parse_generated_files_extracts_three_blocks():
    from nyc_pulse.agent.codegen import parse_generated_files

    llm_output = """
# FILE: src/nyc_pulse/collectors/noise.py
def collect_noise(days=90):
    return []

# FILE: src/nyc_pulse/signals/noise.py
def score_noise(lat, lon, radius_ft=500, window_days=90, session=None):
    return {"signal_type": "noise", "score": 0.0, "count": 0, "evidence": []}

# FILE: tests/test_agent_noise.py
def test_noise_uses_correct_dataset(monkeypatch):
    pass
"""
    files = parse_generated_files(llm_output)
    assert "src/nyc_pulse/collectors/noise.py" in files
    assert "src/nyc_pulse/signals/noise.py" in files
    assert "tests/test_agent_noise.py" in files
    assert "def collect_noise" in files["src/nyc_pulse/collectors/noise.py"]


def test_parse_generated_files_returns_empty_on_no_blocks():
    from nyc_pulse.agent.codegen import parse_generated_files
    result = parse_generated_files("no file markers here")
    assert result == {}


def test_generate_files_returns_three_files(monkeypatch):
    from nyc_pulse.agent import codegen

    fake_collector = "def collect_noise(days=90):\n    return []\n"
    fake_scorer = "def score_noise(lat, lon, radius_ft=500, window_days=90, session=None):\n    return {}\n"
    fake_test = "def test_noise_uses_correct_dataset(monkeypatch):\n    pass\n"

    fake_output = (
        f"# FILE: src/nyc_pulse/collectors/noise.py\n{fake_collector}\n"
        f"# FILE: src/nyc_pulse/signals/noise.py\n{fake_scorer}\n"
        f"# FILE: tests/test_agent_noise.py\n{fake_test}\n"
    )

    class FakeResponse:
        text = fake_output

    class FakeModel:
        def generate_content(self, prompt):
            return FakeResponse()

    monkeypatch.setattr(codegen, "_get_model", lambda: FakeModel())

    eval_result = {
        "dataset_id": "fhrw-4uyv",
        "score": 8,
        "rationale": "Good signal",
        "signal_name": "noise",
        "date_field": "created_date",
        "id_field": "unique_key",
        "lat_field": "latitude",
        "lon_field": "longitude",
        "category_field": "complaint_type",
        "summary_fields": ["descriptor"],
    }
    files = codegen.generate_files(eval_result)
    assert "src/nyc_pulse/collectors/noise.py" in files
    assert "src/nyc_pulse/signals/noise.py" in files
    assert "tests/test_agent_noise.py" in files

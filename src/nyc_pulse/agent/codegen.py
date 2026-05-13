from __future__ import annotations

import os
import re
from pathlib import Path

import google.generativeai as genai

_PACKAGE_DIR = Path(__file__).resolve().parents[1]
_COLLECTORS_DIR = _PACKAGE_DIR / "collectors"
_SIGNALS_DIR = _PACKAGE_DIR / "signals"

_EXAMPLE_COLLECTOR_PATH = _COLLECTORS_DIR / "nyc_311.py"
_EXAMPLE_SCORER_PATH = _SIGNALS_DIR / "quality_of_life.py"
_EXAMPLE_COLLECTOR2_PATH = _COLLECTORS_DIR / "restaurants.py"

_SYSTEM_PROMPT = """You are a Python code generator for the nyc-block-pulse project.
You will be given examples of existing collectors and scorers, plus metadata about a new dataset.
Generate three Python files that follow the exact same patterns as the examples.
Each file must be preceded by a comment line: # FILE: path/to/file.py
Output nothing else - no explanations, no markdown fences, just the FILE comments and code."""


def _get_model():
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    return genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=_SYSTEM_PROMPT,
    )


def parse_generated_files(llm_output: str) -> dict[str, str]:
    pattern = re.compile(r"^# FILE: (.+)$", re.MULTILINE)
    matches = list(pattern.finditer(llm_output))
    if not matches:
        return {}
    files = {}
    for i, match in enumerate(matches):
        path = match.group(1).strip()
        start = match.end() + 1
        end = matches[i + 1].start() if i + 1 < len(matches) else len(llm_output)
        files[path] = llm_output[start:end].strip()
    return files


def generate_files(eval_result: dict) -> dict[str, str]:
    signal_name = eval_result["signal_name"]
    collector_example = _EXAMPLE_COLLECTOR_PATH.read_text()
    scorer_example = _EXAMPLE_SCORER_PATH.read_text()
    collector2_example = _EXAMPLE_COLLECTOR2_PATH.read_text()

    prompt = f"""Generate three files for a new signal called '{signal_name}'.

EXAMPLE COLLECTOR 1 (src/nyc_pulse/collectors/nyc_311.py):
{collector_example}

EXAMPLE COLLECTOR 2 (src/nyc_pulse/collectors/restaurants.py):
{collector2_example}

EXAMPLE SCORER (src/nyc_pulse/signals/quality_of_life.py):
{scorer_example}

NEW DATASET METADATA:
- Dataset ID: {eval_result['dataset_id']}
- Signal name: {signal_name}
- Date field: {eval_result['date_field']}
- ID field: {eval_result['id_field']}
- Lat field: {eval_result['lat_field']}
- Lon field: {eval_result['lon_field']}
- Category field: {eval_result['category_field']}
- Summary fields: {eval_result['summary_fields']}

Generate exactly these three files, each preceded by its # FILE: comment:
# FILE: src/nyc_pulse/collectors/{signal_name}.py
# FILE: src/nyc_pulse/signals/{signal_name}.py
# FILE: tests/test_agent_{signal_name}.py

The collector must follow the exact pattern of the examples.
The scorer must use fetch_nearby_events(['{signal_name}'], ...) and return a flat count score.
The test must mock fetch_socrata and assert dataset_id == '{eval_result['dataset_id']}'.
"""

    try:
        model = _get_model()
        response = model.generate_content(prompt)
        return parse_generated_files(response.text)
    except Exception:
        return {}

from __future__ import annotations

import json
import os
from typing import Any

import google.generativeai as genai

_SYSTEM_PROMPT = """You are evaluating NYC Open Data datasets for relevance to a block-level urban intelligence tool.
The tool scores city blocks on signals like construction pressure, crime, nightlife, housing distress, and quality of life.
Each dataset becomes a data collector that ingests geo-tagged events by location and time window.

A good dataset (score 7-10):
- Has events tied to specific lat/lon locations (not aggregated statistics)
- Has a timestamp field so events can be filtered by recency
- Represents something a person walking a NYC block would notice or care about
- Has a unique identifier per event for deduplication

Respond with valid JSON only. No markdown fences, no explanation outside the JSON."""


def _get_model() -> Any:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    return genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config={"response_mime_type": "application/json"},
        system_instruction=_SYSTEM_PROMPT,
    )


def evaluate_dataset(candidate: dict) -> dict | None:
    """Return the eval dict for parseable responses; callers decide score thresholds."""
    user_prompt = f"""Dataset ID: {candidate['id']}
Name: {candidate['name']}
Description: {candidate['description']}
Columns: {', '.join(candidate['columns'])}

Evaluate this dataset and respond with:
{{
  "score": <0-10 integer>,
  "rationale": "<one sentence>",
  "signal_name": "<snake_case name, e.g. noise_complaints>",
  "date_field": "<exact column name for date/time filter>",
  "id_field": "<exact column name for unique event ID>",
  "lat_field": "<exact column name for latitude>",
  "lon_field": "<exact column name for longitude>",
  "category_field": "<exact column name for event category/type, or null>",
  "summary_fields": ["<field1>", "<field2>"]
}}"""

    try:
        model = _get_model()
        response = model.generate_content(user_prompt)
        data = json.loads(response.text)
    except Exception:
        return None

    if not isinstance(data.get("score"), int):
        return None

    return {
        "dataset_id": candidate["id"],
        "score": data["score"],
        "rationale": data.get("rationale", ""),
        "signal_name": data.get("signal_name", ""),
        "date_field": data.get("date_field", ""),
        "id_field": data.get("id_field", ""),
        "lat_field": data.get("lat_field", ""),
        "lon_field": data.get("lon_field", ""),
        "category_field": data.get("category_field"),
        "summary_fields": data.get("summary_fields", []),
    }

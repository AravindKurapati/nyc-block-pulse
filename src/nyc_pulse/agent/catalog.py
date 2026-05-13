from __future__ import annotations

import re
from pathlib import Path

import httpx

CATALOG_URL = "https://data.cityofnewyork.us/api/catalog/v1"
PAGE_SIZE = 100

_DATE_KEYWORDS = {"date", "time", "at", "dt", "datetime"}
_COLLECTORS_DIR = Path(__file__).resolve().parents[1] / "collectors"


def has_geo_fields(columns: list[str]) -> bool:
    lower = [c.lower() for c in columns]
    has_lat = any("lat" in c or "latitude" in c for c in lower)
    has_lon = any("lon" in c or "longitude" in c for c in lower)
    return has_lat and has_lon


def has_date_field(columns: list[str]) -> bool:
    for col in columns:
        tokens = [token for token in re.split(r"[^a-z0-9]+", col.lower()) if token]
        if any(token in _DATE_KEYWORDS for token in tokens):
            return True
    return False


def _id_in_collectors(dataset_id: str) -> bool:
    for path in _COLLECTORS_DIR.glob("*.py"):
        if dataset_id in path.read_text():
            return True
    return False


def fetch_candidates(already_evaluated: set[str]) -> list[dict]:
    candidates = []
    offset = 0
    while True:
        resp = httpx.get(
            CATALOG_URL,
            params={"only": "datasets", "limit": PAGE_SIZE, "offset": offset},
            headers={"Accept": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        results = page.get("results", [])
        if not results:
            break
        for entry in results:
            resource = entry.get("resource", {})
            dataset_id = resource.get("id", "")
            if not dataset_id or dataset_id in already_evaluated:
                continue
            if _id_in_collectors(dataset_id):
                continue
            columns = resource.get("columns_name") or []
            if not has_geo_fields(columns) or not has_date_field(columns):
                continue
            candidates.append({
                "id": dataset_id,
                "name": resource.get("name", ""),
                "description": resource.get("description", ""),
                "columns": columns,
            })
        if len(results) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return candidates

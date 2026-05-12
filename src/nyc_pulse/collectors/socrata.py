from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ..config import settings

SOCRATA_BASE = "https://data.cityofnewyork.us/resource"
SOCRATA_NY_STATE_BASE = "https://data.ny.gov/resource"


def fetch_socrata(
    dataset_id: str,
    where: str,
    limit: int = 50_000,
    offset: int = 0,
    select: str = "*",
    base_url: str = SOCRATA_BASE,
) -> list[dict[str, Any]]:
    url = f"{base_url}/{dataset_id}.json"
    headers = {}
    if settings.nyc_open_data_app_token:
        headers["X-App-Token"] = settings.nyc_open_data_app_token

    all_rows: list[dict[str, Any]] = []
    current_offset = offset
    while True:
        params = {
            "$where": where,
            "$limit": limit,
            "$offset": current_offset,
            "$select": select,
        }
        response = httpx.get(url, params=params, headers=headers, timeout=60)
        response.raise_for_status()
        page: list[dict[str, Any]] = response.json()
        all_rows.extend(page)
        if len(page) < limit:
            break
        current_offset += limit
    return all_rows


def days_ago_filter(field: str, days: int) -> str:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{field} >= '{cutoff}'"


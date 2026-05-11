from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ..config import settings

SOCRATA_BASE = "https://data.cityofnewyork.us/resource"


def fetch_socrata(
    dataset_id: str,
    where: str,
    limit: int = 50_000,
    offset: int = 0,
    select: str = "*",
) -> list[dict[str, Any]]:
    url = f"{SOCRATA_BASE}/{dataset_id}.json"
    headers = {}
    if settings.nyc_open_data_app_token:
        headers["X-App-Token"] = settings.nyc_open_data_app_token

    params = {
        "$where": where,
        "$limit": limit,
        "$offset": offset,
        "$select": select,
    }
    response = httpx.get(url, params=params, headers=headers, timeout=60)
    response.raise_for_status()
    return response.json()


def days_ago_filter(field: str, days: int) -> str:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{field} >= '{cutoff}'"


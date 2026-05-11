from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import bindparam, text

from ..db import get_session
from ..normalize.geography import feet_to_meters


def fetch_nearby_events(
    sources: Iterable[str],
    lat: float,
    lon: float,
    radius_ft: int,
    window_days: int,
) -> list[dict[str, Any]]:
    session = get_session()
    try:
        statement = (
            text(
                """
                SELECT id, source, event_type, summary, occurred_at, category, status, raw_json
                FROM events
                WHERE source IN :sources
                  AND occurred_at >= now() - (:window_days * interval '1 day')
                  AND geom IS NOT NULL
                  AND ST_DWithin(
                      geom::geography,
                      ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                      :radius_m
                  )
                ORDER BY occurred_at DESC NULLS LAST
                """
            )
            .bindparams(bindparam("sources", expanding=True))
        )
        rows = session.execute(
            statement,
            {
                "sources": tuple(sources),
                "lat": lat,
                "lon": lon,
                "radius_m": feet_to_meters(radius_ft),
                "window_days": window_days,
            },
        ).fetchall()
    finally:
        session.close()
    return [dict(row._mapping) for row in rows]


def evidence(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, str | None]]:
    return [
        {
            "id": row.get("id"),
            "source": row.get("source"),
            "summary": row.get("summary"),
            "date": str(row.get("occurred_at")) if row.get("occurred_at") is not None else "",
        }
        for row in rows[:limit]
    ]


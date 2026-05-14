from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from api.deps import get_db_session
from nyc_pulse.normalize.geography import feet_to_meters

router = APIRouter(prefix="/api", tags=["events"])

SignalName = Literal["construction", "nightlife", "housing", "restaurants", "quality_of_life"]

SIGNAL_SOURCES: dict[str, tuple[str, ...]] = {
    "construction": ("dob_permits",),
    "nightlife": ("liquor", "nyc_311", "restaurants"),
    "housing": ("hpd_complaints", "hpd_violations", "nyc_311"),
    "restaurants": ("restaurants", "liquor", "dob_permits"),
    "quality_of_life": ("nyc_311",),
}


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    try:
        min_lon, min_lat, max_lon, max_lat = [float(part.strip()) for part in value.split(",")]
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="bbox must be four comma-separated numbers: min_lon,min_lat,max_lon,max_lat.",
        ) from exc

    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(status_code=400, detail="bbox min values must be less than max values.")
    if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180 and -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise HTTPException(status_code=400, detail="bbox coordinates are outside valid longitude/latitude ranges.")

    return min_lon, min_lat, max_lon, max_lat


def _base_params(
    signal: str,
    bbox: tuple[float, float, float, float],
    days: int,
    limit: int,
) -> dict[str, Any]:
    min_lon, min_lat, max_lon, max_lat = bbox
    return {
        "sources": SIGNAL_SOURCES[signal],
        "min_lon": min_lon,
        "min_lat": min_lat,
        "max_lon": max_lon,
        "max_lat": max_lat,
        "days": days,
        "limit": limit,
    }


def _count_events(session: Session, params: dict[str, Any]) -> int:
    statement = (
        text(
            """
            SELECT count(*) AS total
            FROM events
            WHERE source IN :sources
              AND occurred_at >= now() - (:days * interval '1 day')
              AND geom IS NOT NULL
              AND ST_Intersects(
                  geom,
                  ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
              )
            """
        )
        .bindparams(bindparam("sources", expanding=True))
    )
    return int(session.execute(statement, params).scalar_one())


def _fetch_events(session: Session, params: dict[str, Any], sampled: bool) -> list[dict[str, Any]]:
    if sampled:
        statement = (
            text(
                """
                WITH sampled AS (
                    SELECT
                        id,
                        source,
                        summary,
                        occurred_at,
                        ST_X(geom) AS lon,
                        ST_Y(geom) AS lat
                    FROM events
                    WHERE source IN :sources
                      AND occurred_at >= now() - (:days * interval '1 day')
                      AND geom IS NOT NULL
                      AND ST_Intersects(
                          geom,
                          ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
                      )
                    ORDER BY random()
                    LIMIT :limit
                )
                SELECT *
                FROM sampled
                ORDER BY occurred_at DESC NULLS LAST
                """
            )
            .bindparams(bindparam("sources", expanding=True))
        )
    else:
        statement = (
            text(
                """
                SELECT
                    id,
                    source,
                    summary,
                    occurred_at,
                    ST_X(geom) AS lon,
                    ST_Y(geom) AS lat
                FROM events
                WHERE source IN :sources
                  AND occurred_at >= now() - (:days * interval '1 day')
                  AND geom IS NOT NULL
                  AND ST_Intersects(
                      geom,
                      ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
                  )
                ORDER BY occurred_at DESC NULLS LAST
                LIMIT :limit
                """
            )
            .bindparams(bindparam("sources", expanding=True))
        )

    rows = session.execute(statement, params).fetchall()
    return [dict(row._mapping) for row in rows]


def _feature(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
        "properties": {
            "id": row["id"],
            "source": row["source"],
            "summary": row.get("summary"),
            "occurred_at": row.get("occurred_at"),
        },
    }


@router.get("/signal-trend")
def signal_trend(
    signal: SignalName,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_ft: int = Query(default=500, gt=0),
    days: int = Query(default=90, ge=1, le=366),
    session: Session = Depends(get_db_session),
) -> list[dict[str, Any]]:
    statement = (
        text(
            """
            WITH day_series AS (
                SELECT generate_series(
                    (current_date - ((:days - 1) * interval '1 day'))::date,
                    current_date,
                    interval '1 day'
                )::date AS day
            ),
            event_counts AS (
                SELECT occurred_at::date AS day, count(*)::integer AS count
                FROM events
                WHERE source IN :sources
                  AND occurred_at >= now() - (:days * interval '1 day')
                  AND geom IS NOT NULL
                  AND ST_DWithin(
                      geom::geography,
                      ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                      :radius_m
                  )
                GROUP BY occurred_at::date
            )
            SELECT
                to_char(day_series.day, 'YYYY-MM-DD') AS date,
                COALESCE(event_counts.count, 0)::integer AS count
            FROM day_series
            LEFT JOIN event_counts ON event_counts.day = day_series.day
            ORDER BY day_series.day
            """
        )
        .bindparams(bindparam("sources", expanding=True))
    )
    rows = session.execute(
        statement,
        {
            "sources": SIGNAL_SOURCES[signal],
            "lat": lat,
            "lon": lon,
            "radius_m": feet_to_meters(radius_ft),
            "days": days,
        },
    ).fetchall()
    return [dict(row._mapping) for row in rows]


@router.get("/events")
def events(
    signal: SignalName,
    bbox: str = Query(...),
    days: int = Query(default=90, ge=1),
    limit: int = Query(default=5000, ge=1, le=10000),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    parsed_bbox = _parse_bbox(bbox)
    params = _base_params(signal, parsed_bbox, days, limit)
    total_match = _count_events(session, params)
    sampled = total_match > limit
    rows = _fetch_events(session, params, sampled)

    return {
        "type": "FeatureCollection",
        "features": [_feature(row) for row in rows],
        "sampled": sampled,
        "total_match": total_match,
    }

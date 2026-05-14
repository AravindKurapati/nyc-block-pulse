from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.deps import get_db_session
from api.routes.events import _parse_bbox

router = APIRouter(prefix="/api", tags=["demographics"])


def _geometry(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return value


def _feature(row: dict[str, Any]) -> dict[str, Any] | None:
    geometry = _geometry(row.get("geometry"))
    if not geometry:
        return None
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "geoid": row["geoid"],
            "tract_name": row.get("tract_name"),
            "borough": row.get("borough"),
            "year": row.get("year"),
            "median_household_income": row.get("median_household_income"),
            "renter_occupied_pct": row.get("renter_occupied_pct"),
            "bachelors_or_higher_pct": row.get("bachelors_or_higher_pct"),
            "under_5_pct": row.get("under_5_pct"),
            "over_65_pct": row.get("over_65_pct"),
            "density_change": row.get("density_change"),
        },
    }


@router.get("/demographics")
def demographics(
    bbox: str = Query(...),
    limit: int = Query(default=2000, ge=1, le=5000),
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    min_lon, min_lat, max_lon, max_lat = _parse_bbox(bbox)
    rows = session.execute(
        text(
            """
            SELECT
                geoid,
                tract_name,
                borough,
                year,
                median_household_income,
                renter_occupied_pct,
                bachelors_or_higher_pct,
                under_5_pct,
                over_65_pct,
                density_change,
                ST_AsGeoJSON(geom)::json AS geometry
            FROM block_demographics
            WHERE geom IS NOT NULL
              AND ST_Intersects(
                  geom,
                  ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
              )
            ORDER BY density_change DESC, geoid
            LIMIT :limit
            """
        ),
        {
            "min_lon": min_lon,
            "min_lat": min_lat,
            "max_lon": max_lon,
            "max_lat": max_lat,
            "limit": limit,
        },
    ).fetchall()
    features = [
        feature
        for feature in (_feature(dict(row._mapping)) for row in rows)
        if feature is not None
    ]
    return {"type": "FeatureCollection", "features": features}

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_session


def _format_pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.1f}%"


def _format_income(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"${float(value):,.0f}"


def _summary(row: dict[str, Any]) -> str:
    return (
        f"{row.get('tract_name') or row.get('geoid')}: "
        f"income {_format_income(row.get('median_household_income'))}, "
        f"renters {_format_pct(row.get('renter_occupied_pct'))}, "
        f"bachelor's+ {_format_pct(row.get('bachelors_or_higher_pct'))}, "
        f"under 5 {_format_pct(row.get('under_5_pct'))}, "
        f"over 65 {_format_pct(row.get('over_65_pct'))}"
    )


def score_density_change(
    lat: float,
    lon: float,
    radius_ft: int = 500,
    window_days: int = 90,
    session: Session | None = None,
) -> dict:
    _session = session or get_session()
    _owned = session is None
    try:
        row = _session.execute(
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
                    density_change
                FROM block_demographics
                WHERE geom IS NOT NULL
                  AND ST_Intersects(
                      geom,
                      ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                  )
                ORDER BY year DESC
                LIMIT 1
                """
            ),
            {"lat": lat, "lon": lon},
        ).mappings().first()
    finally:
        if _owned:
            _session.close()
        else:
            try:
                _session.rollback()
            except Exception:
                pass

    if not row:
        return {
            "signal_type": "density_change",
            "score": 0,
            "count": 0,
            "evidence": [],
        }

    values = dict(row)
    return {
        "signal_type": "density_change",
        "score": round(float(values.get("density_change") or 0), 2),
        "count": 1,
        "evidence": [
            {
                "id": values.get("geoid"),
                "source": "census_acs",
                "summary": _summary(values),
                "date": str(values.get("year") or ""),
            }
        ],
    }

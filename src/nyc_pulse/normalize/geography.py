from __future__ import annotations


def feet_to_meters(feet: int | float) -> float:
    return float(feet) * 0.3048


def point_area_key(lat: float, lon: float, precision: int = 5) -> str:
    return f"point:{round(lat, precision)},{round(lon, precision)}"


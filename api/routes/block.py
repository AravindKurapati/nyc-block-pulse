from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from api.deps import get_db_session
from nyc_pulse.normalize.address import resolve_address
from nyc_pulse.signals.construction import score_construction
from nyc_pulse.signals.housing import score_housing
from nyc_pulse.signals.nightlife import score_nightlife
from nyc_pulse.signals.quality_of_life import score_quality_of_life
from nyc_pulse.signals.restaurants import score_restaurants

router = APIRouter(prefix="/api", tags=["block"])


class BlockRequest(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    address: str | None = None
    days: int = Field(default=90, ge=1)
    radius_ft: int = Field(default=500, gt=0)

    @model_validator(mode="after")
    def require_location(self) -> "BlockRequest":
        if self.address and self.address.strip():
            self.address = self.address.strip()
            return self
        if self.lat is None or self.lon is None:
            raise ValueError("Provide either address or both lat and lon.")
        return self


def _location_from_request(payload: BlockRequest) -> dict[str, Any]:
    if payload.address:
        location = resolve_address(payload.address)
        if not location:
            raise HTTPException(status_code=404, detail="Could not resolve address.")
        return location

    return {
        "lat": payload.lat,
        "lon": payload.lon,
        "borough": None,
        "bbl": None,
        "bin": None,
    }


@router.post("/block")
def block_report(payload: BlockRequest, session: Session = Depends(get_db_session)) -> dict[str, Any]:
    location = _location_from_request(payload)
    lat = float(location["lat"])
    lon = float(location["lon"])

    signals = {
        "construction": score_construction(lat, lon, payload.radius_ft, payload.days, session=session),
        "nightlife": score_nightlife(lat, lon, payload.radius_ft, payload.days, session=session),
        "housing": score_housing(lat, lon, payload.radius_ft, payload.days, session=session),
        "restaurants": score_restaurants(lat, lon, payload.radius_ft, payload.days, session=session),
        "quality_of_life": score_quality_of_life(lat, lon, payload.radius_ft, payload.days, session=session),
    }

    return {
        "location": {
            "lat": lat,
            "lon": lon,
            "borough": location.get("borough"),
            "bbl": location.get("bbl"),
            "bin": location.get("bin"),
        },
        "window_days": payload.days,
        "radius_ft": payload.radius_ft,
        "signals": signals,
    }

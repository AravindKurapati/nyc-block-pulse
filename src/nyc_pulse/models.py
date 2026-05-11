from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NormalizedEvent(BaseModel):
    id: str
    source: str
    event_type: str = ""
    occurred_at: str | None = None
    address: str = ""
    bbl: str | None = None
    bin: str | None = None
    lat: float | None = None
    lon: float | None = None
    status: str | None = None
    category: str | None = None
    summary: str | None = None
    raw_json: dict[str, Any] = Field(default_factory=dict)


from __future__ import annotations

from typing import Any


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compact_summary(*parts: Any, separator: str = " - ") -> str:
    return separator.join(str(part) for part in parts if part not in (None, ""))


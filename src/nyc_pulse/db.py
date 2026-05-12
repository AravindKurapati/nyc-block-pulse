from __future__ import annotations

import json
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

_engine: Engine | None = None
SessionLocal = sessionmaker()


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        if not settings.database_url:
            raise RuntimeError("Set DATABASE_URL before using database-backed commands.")
        # executemany_mode='values_plus_batch' makes psycopg2 rewrite executemany
        # INSERTs into multi-row VALUES (...) form, collapsing a chunk into one
        # statement. Falls back gracefully on non-psycopg2 drivers.
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            executemany_mode="values_plus_batch",
        )
        SessionLocal.configure(bind=_engine)
    return _engine


def get_session() -> Session:
    get_engine()
    return SessionLocal()


CHUNK_SIZE = 500


def upsert_events(session: Session, events: list[dict[str, Any]]) -> int:
    """Insert normalized event rows idempotently in chunked batches.

    Each chunk is one multi-row INSERT (via SQLAlchemy executemany), committed
    before the next chunk so partial progress survives mid-run failures and we
    stay well under transaction-pooler statement_timeout limits.

    Returns the total number of rows actually inserted. Existing event ids are
    ignored via ON CONFLICT DO NOTHING.
    """
    if not events:
        return 0

    statement = text(
        """
        INSERT INTO events (
            id, source, event_type, occurred_at, address, bbl, bin,
            lat, lon, status, category, summary, raw_json, ingested_at, geom
        )
        VALUES (
            :id, :source, :event_type, :occurred_at, :address, :bbl, :bin,
            :lat, :lon, :status, :category, :summary, CAST(:raw_json AS JSONB), now(),
            CASE
                WHEN :lat IS NOT NULL AND :lon IS NOT NULL THEN
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                ELSE NULL
            END
        )
        ON CONFLICT (id) DO NOTHING
        """
    )

    params_list = [
        {
            "id": event["id"],
            "source": event["source"],
            "event_type": event.get("event_type") or "",
            "occurred_at": event.get("occurred_at"),
            "address": event.get("address") or "",
            "bbl": event.get("bbl"),
            "bin": event.get("bin"),
            "lat": event.get("lat"),
            "lon": event.get("lon"),
            "status": event.get("status"),
            "category": event.get("category"),
            "summary": event.get("summary"),
            "raw_json": json.dumps(event.get("raw_json") or {}),
        }
        for event in events
    ]

    inserted = 0
    for start in range(0, len(params_list), CHUNK_SIZE):
        chunk = params_list[start : start + CHUNK_SIZE]
        result = session.execute(statement, chunk)
        if result.rowcount and result.rowcount > 0:
            inserted += result.rowcount
        session.commit()
    return inserted


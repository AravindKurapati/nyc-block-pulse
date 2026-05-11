"""Initial PostGIS-backed schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-11
"""

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS properties (
            bbl TEXT PRIMARY KEY,
            bin TEXT,
            address TEXT,
            borough TEXT,
            block TEXT,
            lot TEXT,
            lat DOUBLE PRECISION,
            lon DOUBLE PRECISION,
            building_class TEXT,
            land_use TEXT,
            raw_json JSONB,
            geom geometry(Point, 4326)
        );

        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            event_type TEXT NOT NULL,
            occurred_at TIMESTAMPTZ,
            address TEXT,
            bbl TEXT,
            bin TEXT,
            lat DOUBLE PRECISION,
            lon DOUBLE PRECISION,
            status TEXT,
            category TEXT,
            summary TEXT,
            raw_json JSONB,
            ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            geom geometry(Point, 4326)
        );

        CREATE TABLE IF NOT EXISTS signals (
            id TEXT PRIMARY KEY,
            area_key TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            score DOUBLE PRECISION NOT NULL,
            window_days INTEGER NOT NULL,
            evidence_json JSONB NOT NULL,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            query TEXT NOT NULL,
            area_key TEXT,
            report_md TEXT NOT NULL,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS ingest_runs (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ,
            status TEXT,
            rows_fetched INTEGER DEFAULT 0,
            rows_inserted INTEGER DEFAULT 0,
            error TEXT
        );

        CREATE INDEX IF NOT EXISTS events_geom_idx ON events USING GIST(geom);
        CREATE INDEX IF NOT EXISTS events_source_idx ON events(source);
        CREATE INDEX IF NOT EXISTS events_occurred_at_idx ON events(occurred_at DESC);
        CREATE INDEX IF NOT EXISTS properties_geom_idx ON properties USING GIST(geom);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS ingest_runs;
        DROP TABLE IF EXISTS reports;
        DROP TABLE IF EXISTS signals;
        DROP TABLE IF EXISTS events;
        DROP TABLE IF EXISTS properties;
        """
    )


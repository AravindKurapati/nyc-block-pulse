"""Add Census ACS tract demographics.

Revision ID: 0002_block_demographics
Revises: 0001_initial_schema
Create Date: 2026-05-14
"""

from alembic import op

revision = "0002_block_demographics"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS block_demographics (
            geoid TEXT PRIMARY KEY,
            tract_name TEXT,
            borough TEXT,
            state TEXT NOT NULL,
            county TEXT NOT NULL,
            tract TEXT NOT NULL,
            year INTEGER NOT NULL,
            median_household_income DOUBLE PRECISION,
            renter_occupied_pct DOUBLE PRECISION,
            bachelors_or_higher_pct DOUBLE PRECISION,
            under_5_pct DOUBLE PRECISION,
            over_65_pct DOUBLE PRECISION,
            density_change DOUBLE PRECISION NOT NULL DEFAULT 0,
            raw_json JSONB,
            geom geometry(MultiPolygon, 4326),
            centroid geometry(Point, 4326),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS block_demographics_geom_idx
            ON block_demographics USING GIST(geom);
        CREATE INDEX IF NOT EXISTS block_demographics_density_change_idx
            ON block_demographics(density_change DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS block_demographics;")

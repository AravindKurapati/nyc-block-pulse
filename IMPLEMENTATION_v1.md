# NYC Block Pulse — v1 Implementation Spec
**Status:** Ready for Codex implementation
**Storage:** Supabase Postgres (not SQLite)
**Compute:** Local CLI + GitHub Actions cron (no Modal yet)

---

## What Codex needs to build

Greenfield project. Nothing exists yet except `ARCHITECTURE.md`. Build the full v1 in order.

---

## 1. Project setup

### `pyproject.toml`

```toml
[project]
name = "nyc-block-pulse"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "typer[all]>=0.12",
    "httpx>=0.27",
    "psycopg2-binary>=2.9",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "alembic>=1.13",
    "sqlalchemy>=2.0",
    "rich>=13.0",
    "python-dotenv>=1.0",
    "polars>=0.20",
]

[project.scripts]
nyc-pulse = "nyc_pulse.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### `.env.example`

```
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
DATABASE_URL_DIRECT=postgresql://postgres.[ref]:[password]@aws-0-us-east-1.pooler.supabase.com:5432/postgres
NYC_OPEN_DATA_APP_TOKEN=
NYC_GEOCLIENT_APP_ID=
NYC_GEOCLIENT_APP_KEY=
```

### Repo structure to create

```
nyc-block-pulse/
  pyproject.toml
  .env.example
  .env                          # not committed
  alembic.ini
  migrations/
    env.py
    versions/
      0001_initial_schema.py
  src/nyc_pulse/
    __init__.py
    cli.py
    config.py
    db.py
    models.py
    collectors/
      __init__.py
      socrata.py
      nyc_311.py
      dob_permits.py
      hpd_complaints.py
      hpd_violations.py
      restaurants.py
      liquor.py
    normalize/
      __init__.py
      address.py
      geography.py
    signals/
      __init__.py
      construction.py
      nightlife.py
      housing.py
      restaurants.py
      quality_of_life.py
    reports/
      __init__.py
      block_report.py
  tests/
  .github/
    workflows/
      daily_update.yml
```

---

## 2. Config

### `src/nyc_pulse/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    database_url_direct: str = ""
    nyc_open_data_app_token: str = ""
    nyc_geoclient_app_id: str = ""
    nyc_geoclient_app_key: str = ""
    default_radius_ft: int = 500
    default_window_days: int = 90

settings = Settings()
```

---

## 3. Database

### Supabase setup (manual, one-time)

1. Create project at supabase.com
2. Enable PostGIS: Dashboard → Database → Extensions → enable `postgis`
3. Copy connection strings into `.env`
4. Use **pooled** URL (port 6543) as `DATABASE_URL` for CLI and GitHub Actions
5. Use **direct** URL (port 5432) as `DATABASE_URL_DIRECT` for Alembic migrations only

### `src/nyc_pulse/db.py`

```python
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

def get_session() -> Session:
    return SessionLocal()
```

### Alembic migration: `migrations/versions/0001_initial_schema.py`

```python
def upgrade():
    op.execute("""
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
    """)

def downgrade():
    op.execute("""
        DROP TABLE IF EXISTS ingest_runs;
        DROP TABLE IF EXISTS reports;
        DROP TABLE IF EXISTS signals;
        DROP TABLE IF EXISTS events;
        DROP TABLE IF EXISTS properties;
    """)
```

### `alembic.ini` — set `sqlalchemy.url`

In `migrations/env.py`, read from settings:

```python
from nyc_pulse.config import settings
config.set_main_option("sqlalchemy.url", settings.database_url_direct)
```

Run migrations with:

```bash
alembic upgrade head
```

---

## 4. Socrata client

### `src/nyc_pulse/collectors/socrata.py`

Generic client for all NYC Open Data / Socrata endpoints.

```python
import httpx
from datetime import datetime, timedelta
from ..config import settings

SOCRATA_BASE = "https://data.cityofnewyork.us/resource"

def fetch_socrata(
    dataset_id: str,
    where: str,
    limit: int = 50_000,
    offset: int = 0,
    select: str = "*",
) -> list[dict]:
    url = f"{SOCRATA_BASE}/{dataset_id}.json"
    headers = {}
    if settings.nyc_open_data_app_token:
        headers["X-App-Token"] = settings.nyc_open_data_app_token

    params = {
        "$where": where,
        "$limit": limit,
        "$offset": offset,
        "$select": select,
    }
    resp = httpx.get(url, params=params, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()

def days_ago_filter(field: str, days: int) -> str:
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{field} >= '{cutoff}'"
```

---

## 5. Collectors

Each collector returns a list of normalized dicts ready to upsert into `events`.

All share this shape:

```python
{
    "id": str,           # stable unique key per source
    "source": str,       # "nyc_311" | "dob_permits" | "hpd_complaints" | etc
    "event_type": str,
    "occurred_at": str,  # ISO 8601
    "address": str,
    "bbl": str | None,
    "bin": str | None,
    "lat": float | None,
    "lon": float | None,
    "status": str | None,
    "category": str | None,
    "summary": str | None,
    "raw_json": dict,
}
```

### `src/nyc_pulse/collectors/nyc_311.py`

Dataset ID: `erm2-nwe9`

```python
from .socrata import fetch_socrata, days_ago_filter

def collect_311(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "erm2-nwe9",
        where=days_ago_filter("created_date", days),
        select="unique_key,complaint_type,descriptor,incident_address,bbl,latitude,longitude,created_date,status,borough",
    )
    return [
        {
            "id": f"311_{r['unique_key']}",
            "source": "nyc_311",
            "event_type": r.get("complaint_type", ""),
            "occurred_at": r.get("created_date"),
            "address": r.get("incident_address", ""),
            "bbl": r.get("bbl"),
            "bin": None,
            "lat": float(r["latitude"]) if r.get("latitude") else None,
            "lon": float(r["longitude"]) if r.get("longitude") else None,
            "status": r.get("status"),
            "category": r.get("descriptor"),
            "summary": f"{r.get('complaint_type')} — {r.get('descriptor')}",
            "raw_json": r,
        }
        for r in rows if r.get("unique_key")
    ]
```

### `src/nyc_pulse/collectors/dob_permits.py`

Dataset ID: `ipu4-2q9a`

```python
from .socrata import fetch_socrata, days_ago_filter

def collect_dob_permits(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "ipu4-2q9a",
        where=days_ago_filter("issuance_date", days),
        select="job__,job_type,work_type,building_type,house__,street_name,borough,bin__,bbl,latitude,longitude,issuance_date,job_status,estimated_job_costs",
    )
    return [
        {
            "id": f"dob_permit_{r['job__']}",
            "source": "dob_permits",
            "event_type": r.get("job_type", ""),
            "occurred_at": r.get("issuance_date"),
            "address": f"{r.get('house__', '')} {r.get('street_name', '')}".strip(),
            "bbl": r.get("bbl"),
            "bin": r.get("bin__"),
            "lat": float(r["latitude"]) if r.get("latitude") else None,
            "lon": float(r["longitude"]) if r.get("longitude") else None,
            "status": r.get("job_status"),
            "category": r.get("work_type"),
            "summary": f"{r.get('job_type')} / {r.get('work_type')} — est. ${r.get('estimated_job_costs', '?')}",
            "raw_json": r,
        }
        for r in rows if r.get("job__")
    ]
```

### `src/nyc_pulse/collectors/hpd_complaints.py`

Dataset ID: `uwyv-629c`

```python
from .socrata import fetch_socrata, days_ago_filter

def collect_hpd_complaints(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "uwyv-629c",
        where=days_ago_filter("opendate", days),
        select="complaintid,type,majorcategoryid,minorcategoryid,codedescription,buildingnumber,streetname,boroughname,bbl,latitude,longitude,opendate,status",
    )
    return [
        {
            "id": f"hpd_complaint_{r['complaintid']}",
            "source": "hpd_complaints",
            "event_type": r.get("type", ""),
            "occurred_at": r.get("opendate"),
            "address": f"{r.get('buildingnumber', '')} {r.get('streetname', '')}".strip(),
            "bbl": r.get("bbl"),
            "bin": None,
            "lat": float(r["latitude"]) if r.get("latitude") else None,
            "lon": float(r["longitude"]) if r.get("longitude") else None,
            "status": r.get("status"),
            "category": r.get("codedescription"),
            "summary": r.get("codedescription", ""),
            "raw_json": r,
        }
        for r in rows if r.get("complaintid")
    ]
```

### `src/nyc_pulse/collectors/restaurants.py`

Dataset ID: `43nn-pn8j`

```python
from .socrata import fetch_socrata, days_ago_filter

def collect_restaurants(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "43nn-pn8j",
        where=days_ago_filter("inspection_date", days),
        select="camis,dba,boro,building,street,cuisine_description,inspection_date,action,violation_code,violation_description,grade,latitude,longitude",
    )
    return [
        {
            "id": f"restaurant_{r['camis']}_{r.get('inspection_date', '')[:10]}",
            "source": "restaurants",
            "event_type": "inspection",
            "occurred_at": r.get("inspection_date"),
            "address": f"{r.get('building', '')} {r.get('street', '')}".strip(),
            "bbl": None,
            "bin": None,
            "lat": float(r["latitude"]) if r.get("latitude") else None,
            "lon": float(r["longitude"]) if r.get("longitude") else None,
            "status": r.get("grade"),
            "category": r.get("cuisine_description"),
            "summary": f"{r.get('dba')} — {r.get('action')}",
            "raw_json": r,
        }
        for r in rows if r.get("camis")
    ]
```

### `src/nyc_pulse/collectors/liquor.py`

NY State Liquor Authority. Dataset: `wg8y-fzsj` on data.ny.gov.

```python
import httpx

SLA_BASE = "https://data.ny.gov/resource/wg8y-fzsj.json"

def collect_liquor(limit: int = 10_000) -> list[dict]:
    resp = httpx.get(SLA_BASE, params={"$limit": limit, "$where": "county='NEW YORK' OR county='KINGS' OR county='BRONX' OR county='QUEENS' OR county='RICHMOND'"}, timeout=60)
    resp.raise_for_status()
    rows = resp.json()
    return [
        {
            "id": f"sla_{r.get('serial_number', r.get('license_serial_number', ''))}",
            "source": "liquor",
            "event_type": r.get("license_type_name", ""),
            "occurred_at": r.get("effective_date"),
            "address": r.get("premises_address", ""),
            "bbl": None,
            "bin": None,
            "lat": float(r["georeference"]["coordinates"][1]) if r.get("georeference") else None,
            "lon": float(r["georeference"]["coordinates"][0]) if r.get("georeference") else None,
            "status": r.get("license_status"),
            "category": r.get("license_type_name"),
            "summary": f"{r.get('dba', r.get('doing_business_as', ''))} — {r.get('license_type_name')}",
            "raw_json": r,
        }
        for r in rows
    ]
```

---

## 6. Address resolver

### `src/nyc_pulse/normalize/address.py`

Use NYC Geoclient API. Register free at: https://api.cityofnewyork.us/geoclient

```python
import httpx
from ..config import settings

GEOCLIENT_BASE = "https://api.cityofnewyork.us/geoclient/v2"

def resolve_address(address: str) -> dict | None:
    """
    Returns {"lat": float, "lon": float, "bbl": str, "bin": str} or None.
    Accepts free-text address or intersection like "Ludlow St & Rivington St".
    """
    if "&" in address or " and " in address.lower():
        return _resolve_intersection(address)
    return _resolve_street(address)

def _resolve_street(address: str) -> dict | None:
    parts = address.strip().rsplit(" ", 3)
    if len(parts) < 2:
        return None
    house_number = parts[0]
    street = " ".join(parts[1:])
    resp = httpx.get(
        f"{GEOCLIENT_BASE}/address.json",
        params={
            "houseNumber": house_number,
            "street": street,
            "borough": "Manhattan",  # TODO: detect borough from address
            "app_id": settings.nyc_geoclient_app_id,
            "app_key": settings.nyc_geoclient_app_key,
        },
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    data = resp.json().get("address", {})
    lat = data.get("latitudeInternalLabel") or data.get("latitude")
    lon = data.get("longitudeInternalLabel") or data.get("longitude")
    if not lat or not lon:
        return None
    return {
        "lat": float(lat),
        "lon": float(lon),
        "bbl": data.get("bbl"),
        "bin": data.get("buildingIdentificationNumber"),
    }

def _resolve_intersection(address: str) -> dict | None:
    parts = [p.strip() for p in address.replace(" and ", "&").split("&")]
    if len(parts) != 2:
        return None
    resp = httpx.get(
        f"{GEOCLIENT_BASE}/intersection.json",
        params={
            "crossStreetOne": parts[0],
            "crossStreetTwo": parts[1],
            "borough": "Manhattan",
            "app_id": settings.nyc_geoclient_app_id,
            "app_key": settings.nyc_geoclient_app_key,
        },
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    data = resp.json().get("intersection", {})
    lat = data.get("latitude")
    lon = data.get("longitude")
    if not lat or not lon:
        return None
    return {"lat": float(lat), "lon": float(lon), "bbl": None, "bin": None}
```

---

## 7. Ingest pipeline

### `src/nyc_pulse/db.py` — upsert helper

```python
def upsert_events(session: Session, events: list[dict]) -> int:
    from sqlalchemy import text
    inserted = 0
    for e in events:
        geom = None
        if e.get("lat") and e.get("lon"):
            geom = f"ST_SetSRID(ST_MakePoint({e['lon']}, {e['lat']}), 4326)"

        session.execute(text(f"""
            INSERT INTO events (id, source, event_type, occurred_at, address, bbl, bin,
                lat, lon, status, category, summary, raw_json, ingested_at
                {', geom' if geom else ''})
            VALUES (:id, :source, :event_type, :occurred_at, :address, :bbl, :bin,
                :lat, :lon, :status, :category, :summary, :raw_json::jsonb, now()
                {', ' + geom if geom else ''})
            ON CONFLICT (id) DO NOTHING
        """), {**e, "raw_json": __import__("json").dumps(e["raw_json"])})
        inserted += 1
    session.commit()
    return inserted
```

---

## 8. Signals

### Construction pressure: `src/nyc_pulse/signals/construction.py`

```python
from sqlalchemy import text
from ..db import get_session

def score_construction(lat: float, lon: float, radius_ft: int = 500, window_days: int = 90) -> dict:
    session = get_session()
    rows = session.execute(text("""
        SELECT id, summary, occurred_at, category, raw_json
        FROM events
        WHERE source = 'dob_permits'
          AND occurred_at >= now() - interval ':window days'
          AND ST_DWithin(
              geom::geography,
              ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
              :radius_m
          )
    """), {"lat": lat, "lon": lon, "radius_m": radius_ft * 0.3048, "window": window_days}).fetchall()

    score = len(rows)
    high_value = [r for r in rows if "alteration" in (r.category or "").lower()
                  or "new building" in (r.category or "").lower()]
    score += len(high_value) * 0.5  # boost for high-signal permit types

    return {
        "signal_type": "construction_pressure",
        "score": round(score, 2),
        "count": len(rows),
        "evidence": [{"id": r.id, "summary": r.summary, "date": str(r.occurred_at)} for r in rows[:10]],
    }
```

Build the same pattern for `nightlife.py`, `housing.py`, `restaurants.py`, `quality_of_life.py` — each queries the relevant sources and returns `{signal_type, score, count, evidence}`.

---

## 9. CLI

### `src/nyc_pulse/cli.py`

```python
import typer
from rich.console import Console
from rich.markdown import Markdown

app = typer.Typer()
console = Console()

@app.command("init")
def init():
    """Run alembic migrations to set up the database."""
    import subprocess
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    console.print("[green]Database ready.[/green]")

@app.command("update")
def update(
    days: int = typer.Option(7, help="Lookback window in days"),
    source: str = typer.Option("all", help="Source to update: all|311|dob|hpd|restaurants|liquor"),
):
    """Pull recent records from NYC Open Data into Postgres."""
    from .collectors.nyc_311 import collect_311
    from .collectors.dob_permits import collect_dob_permits
    from .collectors.hpd_complaints import collect_hpd_complaints
    from .collectors.restaurants import collect_restaurants
    from .collectors.liquor import collect_liquor
    from .db import get_session, upsert_events

    session = get_session()
    collectors = {
        "311": collect_311,
        "dob": collect_dob_permits,
        "hpd": collect_hpd_complaints,
        "restaurants": collect_restaurants,
        "liquor": collect_liquor,
    }
    targets = collectors if source == "all" else {source: collectors[source]}

    for name, fn in targets.items():
        with console.status(f"Fetching {name}..."):
            events = fn(days=days) if name != "liquor" else fn()
        inserted = upsert_events(session, events)
        console.print(f"[cyan]{name}:[/cyan] {len(events)} fetched, {inserted} new rows")

@app.command("block")
def block_report(
    query: str = typer.Argument(..., help="Address or intersection, e.g. 'Ludlow St & Rivington St'"),
    days: int = typer.Option(90),
    radius: int = typer.Option(500, help="Radius in feet"),
):
    """Generate a block report for an address or intersection."""
    from .normalize.address import resolve_address
    from .signals.construction import score_construction
    from .reports.block_report import render_report

    with console.status("Resolving location..."):
        loc = resolve_address(query)
    if not loc:
        console.print("[red]Could not resolve location.[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]Resolved: {loc['lat']:.5f}, {loc['lon']:.5f}[/dim]")

    signals = {}
    with console.status("Scoring signals..."):
        signals["construction"] = score_construction(loc["lat"], loc["lon"], radius, days)
        # add nightlife, housing, restaurants, quality_of_life here

    report = render_report(query, loc, signals, days)
    console.print(Markdown(report))

if __name__ == "__main__":
    app()
```

---

## 10. Block report renderer

### `src/nyc_pulse/reports/block_report.py`

```python
from datetime import datetime

def render_report(query: str, loc: dict, signals: dict, window_days: int) -> str:
    lines = [
        f"# Block Report: {query}",
        f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  ",
        f"**Window:** last {window_days} days  ",
        f"**Data as of:** NYC Open Data (24–48h lag)  ",
        "",
    ]
    for signal_type, result in signals.items():
        lines += [
            f"## {signal_type.replace('_', ' ').title()}",
            f"**Score:** {result['score']} ({result['count']} events)",
            "",
            "**Evidence:**",
        ]
        for e in result.get("evidence", [])[:5]:
            lines.append(f"- {e['date'][:10]} — {e['summary']}")
        lines.append("")
    return "\n".join(lines)
```

---

## 11. GitHub Actions daily update

### `.github/workflows/daily_update.yml`

```yaml
name: Daily NYC Data Update

on:
  schedule:
    - cron: "0 11 * * *"   # 6 AM ET
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - run: pip install -e .

      - name: Run ingest
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          NYC_OPEN_DATA_APP_TOKEN: ${{ secrets.NYC_OPEN_DATA_APP_TOKEN }}
        run: nyc-pulse update --days 7
```

Add `DATABASE_URL` and `NYC_OPEN_DATA_APP_TOKEN` as GitHub repository secrets.

---

## 12. Tests (minimum to write)

```
tests/
  test_socrata.py         - mock httpx, assert normalized event shape
  test_address.py         - mock Geoclient, assert lat/lon/bbl returned
  test_signals.py         - seed DB with fixture events, assert score > 0
  test_upsert.py          - upsert same row twice, assert no duplicate
```

---

## Implementation order for Codex

1. `pyproject.toml` + `.env.example`
2. `config.py`
3. `db.py` (engine, session, upsert_events)
4. Alembic setup + `0001_initial_schema.py`
5. `collectors/socrata.py` (generic client)
6. Each collector: `nyc_311.py`, `dob_permits.py`, `hpd_complaints.py`, `restaurants.py`, `liquor.py`
7. `normalize/address.py`
8. `signals/construction.py` (one signal first, prove the pattern)
9. `reports/block_report.py`
10. `cli.py`
11. `.github/workflows/daily_update.yml`
12. Tests

Do not build the frontend. Do not add the LLM layer. Stop at step 12.

---

## Notes for Codex

- Run `alembic upgrade head` with `DATABASE_URL_DIRECT` (port 5432), not the pooled URL
- PostGIS must be enabled on the Supabase project before running migrations
- All radius queries use `ST_DWithin(...geography, ...geography, meters)` — convert feet to meters (× 0.3048)
- Socrata field names vary by dataset — check the dataset page if a field is missing
- NYC Geoclient requires a free account + app credentials — the resolver will return None gracefully if not configured; the CLI should warn but not crash
- `ON CONFLICT (id) DO NOTHING` on upsert makes all ingests idempotent
- Do NOT read, print, or log `.env` contents

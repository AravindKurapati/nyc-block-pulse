# NYC Block Pulse

Local-first / free-hosted alternative data scout for NYC blocks, buildings, and neighborhood change.

## Product idea

NYC Block Pulse answers one question:

> What is changing on this block, and what public evidence supports that story?

The app ingests official NYC and NY State public datasets, normalizes them around addresses, BBLs, BINs, blocks, and neighborhoods, then generates evidence-backed signals such as construction pressure, nightlife churn, housing distress, restaurant turnover, and quality-of-life drift.

Example user query:

```text
Ludlow St and Rivington St
```

Example output:

```text
Signal: hospitality/commercial churn

Evidence:
- 4 DOB alteration permits within 500 ft in the last 90 days
- 2 liquor-license records nearby
- 311 noise complaints up 31% versus the prior 90 days
- 3 restaurant inspection records show new or changed establishments

Thesis:
This block appears to be shifting toward higher-foot-traffic hospitality use, with rising nighttime activity and interior renovation work.
```

## Official data sources

Most NYC datasets are accessible through NYC Open Data, which runs on Socrata. Queries can be made over HTTPS and returned as JSON or CSV. The MVP should use official sources only.

Core sources:

| Source | What it provides | Use |
|---|---|---|
| NYC 311 Service Requests | Complaints, agency routing, status, location | Noise, sanitation, heat, sidewalk, rodent, quality-of-life trends |
| DOB Permit Issuance | Building permits, job type, work type, dates, BIN/location | Construction pressure, renovation activity, commercial buildouts |
| DOB Violations | Building code violations | Safety/compliance signal |
| HPD Complaints | Housing maintenance complaints | Tenant distress signal |
| HPD Violations | Housing maintenance violations | Serious building-risk signal |
| ACRIS | Property transactions, deeds, mortgages | Ownership and transaction churn |
| PLUTO / MapPLUTO | Land use, zoning, BBL, building class, lot facts | Property context and block baseline |
| DOHMH Restaurant Inspections | Establishments, inspections, grades, violations | Restaurant turnover and operating risk |
| NY State Liquor Authority data | Licenses and license status | Nightlife / hospitality activity |
| MTA GTFS real-time and alerts | Subway/bus service state | Optional transit disruption layer |

The v0 should avoid scraping private websites. Public city datasets are enough.

## Core entities

The hard part is not fetching data. The hard part is resolving messy city records into stable entities.

Primary keys:

```text
BBL = borough-block-lot, property tax lot identifier
BIN = building identification number
address = human-readable street address
lat/lon = point geometry
block_id = derived geographic block or buffered area
neighborhood_id = NTA/CD/council district/etc.
```

The entity resolver should support:

```text
address -> lat/lon
address -> BBL/BIN when possible
BBL/BIN -> property profile
lat/lon -> nearby events within radius
intersection -> nearby block/event search
```

## MVP scope

Start narrow:

```text
Input:
  address or intersection

Output:
  block report for last 90 days

Datasets:
  311
  DOB permits
  HPD complaints/violations
  restaurant inspections
  liquor licenses
  PLUTO, if easy

Signals:
  construction pressure
  nightlife activity
  housing distress
  restaurant turnover
  quality-of-life drift
```

Do not start with a full map-heavy app. Build the data spine first.

## Data storage

### Local development

Use SQLite first.

```text
data/
  raw/
    nyc_311/
    dob_permits/
    hpd/
    restaurants/
    liquor/
  cache/
  nyc_block_pulse.sqlite
```

SQLite tables:

```sql
properties
  bbl TEXT PRIMARY KEY
  bin TEXT
  address TEXT
  borough TEXT
  block TEXT
  lot TEXT
  lat REAL
  lon REAL
  building_class TEXT
  land_use TEXT
  raw_json TEXT

events
  id TEXT PRIMARY KEY
  source TEXT NOT NULL
  event_type TEXT NOT NULL
  occurred_at TEXT
  address TEXT
  bbl TEXT
  bin TEXT
  lat REAL
  lon REAL
  status TEXT
  category TEXT
  summary TEXT
  raw_json TEXT
  ingested_at TEXT NOT NULL

signals
  id TEXT PRIMARY KEY
  area_key TEXT NOT NULL
  signal_type TEXT NOT NULL
  score REAL NOT NULL
  window_days INTEGER NOT NULL
  evidence_json TEXT NOT NULL
  generated_at TEXT NOT NULL

reports
  id TEXT PRIMARY KEY
  query TEXT NOT NULL
  area_key TEXT
  report_md TEXT NOT NULL
  generated_at TEXT NOT NULL

ingest_runs
  id TEXT PRIMARY KEY
  source TEXT NOT NULL
  started_at TEXT NOT NULL
  completed_at TEXT
  status TEXT
  rows_fetched INTEGER DEFAULT 0
  rows_inserted INTEGER DEFAULT 0
  error TEXT
```

### Hosted database

Use Supabase or Neon when the app needs hosted state.

Recommended:

```text
Supabase:
  better if you want auth, dashboard, storage, quick app APIs

Neon:
  better if you want clean serverless Postgres and PostGIS
```

For a demo, keep hosted storage small:

```text
Store:
  normalized recent events
  computed signals
  generated reports

Do not store:
  all 311 history since 2010
  huge raw CSV dumps
  every historical city record
```

If Postgres is used, add PostGIS later for radius/geospatial queries.

## Architecture without Modal

This is the cheapest and simplest path.

### Use when

Use the non-Modal path if the goal is:

```text
local demo
small hosted demo
manual updates
no cloud compute dependency
zero spend
```

### Stack

```text
Python 3.11+
Typer CLI
SQLite locally
DuckDB for large local CSV exploration
Polars or Pandas
Pydantic
httpx
Rich terminal output
FastAPI optional
Next.js optional
Leaflet or MapLibre optional
Supabase/Neon optional hosted DB
GitHub Actions optional daily update
```

### Flow

```text
User runs:
  nyc-pulse update --days 7

App:
  pulls updated records from NYC Open Data
  normalizes them into SQLite
  computes signals
  writes reports

User runs:
  nyc-pulse block "Ludlow St & Rivington St"

App:
  resolves location
  fetches nearby events from SQLite
  scores signals
  prints evidence-backed report
```

### Scheduled updates without Modal

Options:

```text
Local:
  Windows Task Scheduler
  cron on macOS/Linux

Hosted:
  GitHub Actions scheduled workflow
  Vercel Cron if using Next.js
  Supabase scheduled jobs if using Supabase
```

Suggested v0:

```text
GitHub Actions daily at 6 AM ET
  -> run Python ingest
  -> write to hosted Postgres
  -> optionally save generated markdown reports as artifacts
```

### Pros

```text
lowest cost
simple mental model
easy to debug locally
no cloud runtime lock-in
good for a portfolio MVP
```

### Cons

```text
GitHub Actions has runtime limits
no easy bursty compute
less convenient for long/heavy jobs
not ideal for model inference
scheduled web endpoints require extra platform
```

## Architecture with Modal

Modal should be used for compute, not as the database.

Modal is useful for:

```text
daily ETL jobs
scheduled data refresh
heavier Polars/Pandas jobs
geocoding batches
LLM report generation
parallel block scans
optional web API
```

Use Supabase or Neon for durable hosted data.

### Use when

Use Modal if the goal is:

```text
hosted daily updates
clean scheduled compute
parallel data processing
LLM/thesis generation later
no always-on server
using the $30/month free compute credits
```

### Stack

```text
Python 3.11+
Modal
FastAPI on Modal web endpoint
Supabase or Neon Postgres
SQLAlchemy or asyncpg
Pydantic
httpx
Polars
DuckDB for local/raw exploration
Next.js frontend on Vercel
Leaflet or MapLibre map UI
```

### Flow

```text
Modal daily cron
  -> fetch latest records from NYC Open Data / NY State Open Data
  -> normalize addresses, BBLs, BINs
  -> compute block-level signals
  -> write compact tables to Supabase/Neon

Frontend on Vercel
  -> calls Modal FastAPI endpoint
  -> endpoint reads Supabase/Neon
  -> returns block report and evidence cards
```

### Modal app shape

```text
jobs/daily_update.py
  @modal.function(schedule=modal.Cron("0 6 * * *"))
  def daily_update():
      ingest_recent_311()
      ingest_recent_dob_permits()
      ingest_recent_hpd()
      ingest_recent_restaurants()
      ingest_recent_liquor()
      compute_signals()

api/main.py
  @modal.asgi_app()
  def fastapi_app():
      return app
```

### Hosted DB responsibilities

Postgres stores:

```text
normalized event rows
properties
signals
reports
ingest run metadata
```

Modal stores:

```text
no durable primary data
optional cache in Modal Volume
logs and metrics
```

### Pros

```text
great use of free Modal credits
no always-on server cost
scheduled jobs are clean
easy to scale bursty ETL
can add LLM/model steps later
professional architecture story
```

### Cons

```text
more moving parts
requires Modal account/config/secrets
must set budget limits to avoid surprise charges
web endpoints/crons are limited on Starter
database still needs Supabase/Neon
```

## Cost model

Expected v0 cost:

```text
$0/month
```

Free components:

```text
NYC Open Data / Socrata for reasonable use
NY State Open Data for liquor data
MTA public feeds
SQLite local DB
GitHub Actions free tier
Vercel free tier
Supabase free tier or Neon free tier
Modal Starter credits for compute
```

Potential paid components later:

```text
hosted DB beyond free storage
map tiles at higher public traffic
LLM API calls for polished narrative reports
geocoding API if free city geocoding is insufficient
Modal compute beyond free credits
```

Cost controls:

```text
limit ingest windows to last 7/30/90 days
store compact normalized rows, not raw full history
cache raw API responses locally, not hosted
batch updates daily, not continuously
set Modal workspace budget
avoid LLM calls by default
```

## Signal engine

Signals should be deterministic first. Add LLM narrative later.

### Construction pressure

Inputs:

```text
DOB permits
DOB job type / work type
permit issue date
estimated cost if present
distance from block
```

Scoring idea:

```text
score = weighted count of permits in last 90 days
boost for alteration/interior/demo/new-building work
boost for high estimated cost
compare against prior 90-day baseline
```

### Nightlife activity

Inputs:

```text
liquor license records
311 noise complaints
restaurant records
DOB commercial alteration permits
```

Scoring idea:

```text
score = liquor activity + after-hours noise complaint trend + restaurant turnover
```

### Housing distress

Inputs:

```text
HPD complaints
HPD violations
311 heat/hot water/pests/mold complaints
DOB violations
```

Scoring idea:

```text
score = severity-weighted HPD violations + repeat complaint trend
boost for open Class C violations
```

### Restaurant turnover

Inputs:

```text
DOHMH restaurant inspections
new CAMIS records
inspection grade changes
SLA license activity
DOB interior permits
```

Scoring idea:

```text
score = new/changed restaurant records + license activity + recent buildout permits
```

### Quality-of-life drift

Inputs:

```text
311 sanitation
rodent
noise
blocked sidewalk
illegal parking
street condition
```

Scoring idea:

```text
compare last 30/90 days to prior period and borough/neighborhood baseline
```

## LLM layer

Do not let the LLM invent facts. The LLM only turns computed evidence into readable narrative.

Prompt contract:

```text
Input:
  structured evidence rows
  source names
  timestamps
  computed scores

Output:
  short thesis
  confidence
  evidence bullets
  caveats

Rules:
  no claims without evidence row
  cite source and date for every claim
  say "insufficient evidence" when weak
```

The non-LLM fallback should still work:

```text
template-based report from evidence rows
```

## Frontend

Do frontend after the CLI and signal engine work.

MVP frontend:

```text
Next.js
search box for address/intersection
MapLibre or Leaflet map
block report panel
evidence cards
signal chips
timeline
source links
```

Avoid a marketing landing page. The first screen should be the actual NYC block intelligence tool.

## Suggested implementation order

1. Create Python package and CLI.
2. Add SQLite schema.
3. Implement Socrata client.
4. Implement 311 collector for recent records.
5. Implement DOB permits collector.
6. Implement HPD complaints/violations collector.
7. Implement DOHMH restaurant collector.
8. Implement basic address/intersection resolver.
9. Implement block report command.
10. Add deterministic signals.
11. Add hosted DB option.
12. Add Modal daily job option.
13. Add FastAPI endpoint.
14. Add Next.js map UI.
15. Add optional LLM report writer.

## CLI design

```bash
nyc-pulse init
nyc-pulse update --days 7
nyc-pulse update --source 311 --days 30
nyc-pulse block "Ludlow St & Rivington St"
nyc-pulse property "123 Ludlow St"
nyc-pulse signals --neighborhood "Lower East Side"
nyc-pulse export-report "Ludlow St & Rivington St" --format md
```

## Repo structure

```text
nyc-block-pulse/
  README.md
  ARCHITECTURE.md
  pyproject.toml
  .env.example

  src/nyc_pulse/
    cli.py
    config.py
    db.py
    models.py

    collectors/
      socrata.py
      nyc_311.py
      dob_permits.py
      dob_violations.py
      hpd_complaints.py
      hpd_violations.py
      restaurants.py
      liquor.py
      pluto.py

    normalize/
      address.py
      bbl_bin.py
      geography.py
      event_schema.py

    signals/
      construction.py
      nightlife.py
      housing.py
      restaurants.py
      quality_of_life.py

    reports/
      block_report.py
      templates.py
      llm_writer.py

    api/
      main.py

    jobs/
      daily_update.py

  frontend/
    # optional Next.js app later

  tests/
```

## Recommendation

Build the first version without Modal:

```text
CLI + SQLite + Socrata collectors + deterministic reports
```

Then add Modal once the signal engine has real value:

```text
Modal daily job + Supabase/Neon + Vercel frontend
```

This avoids spending time on cloud plumbing before the core question is answered:

> Can the system produce a useful, evidence-backed story about a NYC block?


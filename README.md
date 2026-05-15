# NYC BLOCK PULSE

**Live demo:** *(coming soon — Vercel)*

I kept walking past construction scaffolding in the East Village and wondering: is this block actually changing, or does it just feel like it? StreetEasy tells you what's listed. Zillow tells you what sold. Nothing tells you what's *happening* on the block right now — the permits, the noise complaints, the new liquor licenses, the inspection failures.

So I built this. NYC Block Pulse pulls from ten public NYC datasets and scores any city block on seven signals — construction, nightlife, housing distress, restaurants, quality of life, crime, fire incidents — backed by the actual events behind each score.

Click a block. See what's changing. See the evidence.

---

## What it does

Type an address (or click the map). The right panel returns a block report scoring seven signals over the last 90 days within a 500 ft radius. Every score is backed by event-level evidence — the specific DOB permits, 311 complaints, NYPD incidents, eviction filings, restaurant inspections that drove the number.

The map heatmap is multi-select: toggle multiple signals at once and the heat overlays merge.

The idle state isn't empty either — it has Aru's Picks (Washington Sq Park, Apollo Bagels, NYU Langone, DUMBO, Domino Park, Hunters Point, etc.), all eight NYU campus buildings I cared about, and a Your Saves section backed by localStorage.

---

## Why agentic?

The interesting part lives behind a CLI command, not the UI.

NYC Open Data has ~3,000 datasets. A human can't evaluate them all to find which ones are worth ingesting. So I built `nyc-pulse agent discover` — a weekly GitHub Actions cron that:

1. Pages through the Socrata catalog API, pre-filters for datasets with lat/lon + a timestamp column
2. Sends each candidate to Gemini 2.0 Flash for a 0–10 relevance score against the project's signal model
3. For approved datasets (score ≥ 7), prompts Gemini again with two existing collectors as examples to generate a new collector + scorer + pytest contract test
4. Writes the files, runs the test in a subprocess — if it fails, deletes everything and marks the dataset `validation_failed` in `agent/state.json`
5. If it passes, wires the new signal into the CLI + API via regex anchors, opens a labeled PR, and enables auto-merge
6. CI is the safety rail — bad generated code can't land because the existing pytest suite has to pass

A second command, `nyc-pulse agent monitor`, queries the DB weekly and opens a GitHub Issue if any source has stopped ingesting rows.

Evaluated datasets persist in `agent/state.json` so subsequent runs never re-evaluate the same ID. The whole loop costs $0 — Gemini 2.0 Flash has 1500 free requests/day.

---

## Stack

- **App + API:** Next.js 14 (App Router, Route Handlers, TypeScript), Tailwind, MapLibre GL JS
- **CLI:** Typer (Python 3.11)
- **DB:** Supabase Postgres + PostGIS
- **Ingestion:** Socrata NYC Open Data API
- **Agent:** Gemini 2.0 Flash via `google-generativeai`, GitHub Actions cron, `gh` CLI for PR + Issue creation
- **Tests:** pytest, 45 tests across collectors, signals, API routes, and agent modules

---

## Vercel API

The production API now runs inside `web/` as Next.js Route Handlers on Vercel:

- `/api/health`
- `/api/events`
- `/api/signal-trend`
- `/api/block`
- `/api/demographics`
- `/api/search`

Fly.io deployment is no longer needed. Set one `DATABASE_URL` environment variable in Vercel project settings; the route handlers use it directly through `pg` against Supabase Postgres/PostGIS.

---

## Data sources

10 datasets, all official NYC Open Data / Socrata:

| Signal | Datasets |
|---|---|
| construction | DOB permits, DOB violations |
| nightlife | NY State liquor licenses, 311 noise complaints |
| housing | HPD complaints, HPD violations, evictions |
| restaurants | DOHMH inspections |
| quality_of_life | 311 service requests |
| crime | NYPD complaint data (`qgea-i56i`) |
| fire | FDNY incidents (`erm2-nwe9`) |

New signals get auto-added by the agent — see `agent/state.json` for what's been evaluated.

---

## Running locally

```bash
git clone https://github.com/AravindKurapati/nyc-block-pulse
cd nyc-block-pulse

# CLI / ingestion
pip install -e ".[dev]"
cp .env.example .env   # fill in DATABASE_URL, NYC_OPEN_DATA_APP_TOKEN
nyc-pulse update all   # ingest the last 90 days for every collector

# Web app + API
cd web
npm install
cp .env.local.example .env.local   # fill in DATABASE_URL
npm run dev
```

Open `http://localhost:3000`. Click anywhere on the map. The frontend and API both run from the same Next.js dev server.

---

## CLI

```bash
nyc-pulse update all                    # ingest all collectors, last 90 days
nyc-pulse update <collector> --days 30  # one collector, custom window
nyc-pulse block "Ludlow St and Rivington St" --days 90 --radius-ft 500
nyc-pulse agent discover --dry-run      # agent loop without git/PR
nyc-pulse agent monitor                 # source health check
```

---

## Tests

```bash
python -m pytest tests/ api/tests/ -v   # 45 passing
cd web && npx tsc --noEmit              # frontend typecheck
```

---

## Environment variables

See `.env.example`.

- `DATABASE_URL` — Supabase Postgres connection string (required)
- `NYC_OPEN_DATA_APP_TOKEN` — Socrata app token (required for production rate limits, optional locally)
- `GEMINI_API_KEY` — Gemini 2.0 Flash key from [aistudio.google.com](https://aistudio.google.com) (required only for the agent commands; free tier covers 1500 req/day)
- `GH_TOKEN` — used by `agent discover` to open PRs and `agent monitor` to open Issues (GitHub Actions provides this automatically)

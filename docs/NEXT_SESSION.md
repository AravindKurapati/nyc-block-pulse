# Next Session Handoff — NYC Block Pulse

## Status at end of this session

- PR #3 (FastAPI backend) — merged to master
- PR #4 (Next.js frontend) — **merged to master** (squash commit `be3e06d`)
- master is now stable with the full frontend

## What landed in PR #4

- Next.js 14 + Tailwind + MapLibre frontend
- Signal toggle, search autocomplete, block report panel
- Animated scores, color-coded bars, Web Audio ping on click
- Idle panel: Aru's Picks (11 spots), NYU Buildings (8 incl. NYU Langone), localStorage Your Saves
- Bookmark toggle on block reports — persists in `localStorage` key `"nbp_saves"`
- Review fixes: maplibre-gl pinned to `^4.7.0`, search `onBlur`, `pendingSignalRef` for signal-before-map-load

## Aru's Favorite Spots (for hardcoded "Aru's Picks" feature)

User-provided:
| Name | Location |
|------|----------|
| Washington Square Park | 40.73082, -73.99763 — Greenwich Village |
| Apollo Bagels | 40.72941, -74.00277 — West Village |
| DUMBO | 40.70338, -73.98930 — Brooklyn |
| NYU 404 | 40.72952, -73.99585 — likely 404 Lafayette St |
| Lafayette Bakery | need to confirm exact location |
| Bensonhurst Park | 40.60526, -74.00910 — Brooklyn |
| Domino Park | 40.71503, -73.96590 — Williamsburg |
| Hunters Point | 40.74480, -73.94860 — LIC, Queens |

Suggested additions (spread across boroughs):
| Name | Location |
|------|----------|
| The High Line (Chelsea) | 40.74800, -74.00480 |
| Smorgasburg (Prospect Park) | 40.66040, -73.96910 |
| Astoria Park | 40.77800, -73.93040 — Queens |
| Arthur Avenue | 40.85460, -73.89030 — The Bronx |
| Snug Harbor | 40.64360, -74.10080 — Staten Island |
| Katz's Delicatessen | 40.72228, -73.98737 — LES |

## NYU Buildings layer (special purple markers)

Build a hardcoded NYU layer with torch/purple pins, always visible on the map.

Key buildings:
| Building | Address | Lat/Lon |
|----------|---------|---------|
| Bobst Library | 70 Washington Sq S | 40.72950, -73.99800 |
| Stern School of Business | 44 W 4th St | 40.72939, -73.99695 |
| Kimmel Center | 60 Washington Sq S | 40.72972, -73.99842 |
| Silver Center | 100 Washington Sq E | 40.72997, -73.99682 |
| Courant Institute | 251 Mercer St | 40.72874, -73.99560 |
| Tandon (Brooklyn) | 6 MetroTech Center | 40.69440, -73.98650 |
| NYU Langone | 550 1st Ave | 40.74220, -73.97440 |
| Casa Italiana | 24 W 12th St | 40.73560, -73.99650 |

## New data signals to add (backend work)

All three use the existing Socrata pipeline — same pattern as current collectors:

### 1. Crime (NYPD Complaint Data)
- Dataset: `qgea-i56i` (NYPD Complaint Data Current YTD) on data.cityofnewyork.us
- Fields: `cmplnt_fr_dt`, `ofns_desc`, `law_cat_cd` (FELONY/MISDEMEANOR/VIOLATION), `latitude`, `longitude`, `boro_nm`
- New collector: `src/nyc_pulse/collectors/nypd_crime.py`
- New scorer: `src/nyc_pulse/signals/crime.py`
- Score weight: felony × 2, misdemeanor × 1, violation × 0.5

### 2. Fire Incidents (FDNY)
- Dataset: `erm2-nwe9` on data.cityofnewyork.us (FDNY Incident Dispatch Data)
- Fields: `incident_datetime`, `incident_type_desc`, `latitude`, `longitude`, `borough_desc`
- New collector: `src/nyc_pulse/collectors/fdny_fire.py`
- New scorer: `src/nyc_pulse/signals/fire.py`

### 3. Evictions
- Dataset: `6z8x-vjye` on data.cityofnewyork.us (NYC Evictions)
- Fields: `executed_date`, `eviction_address`, `latitude`, `longitude`, `borough`, `residential_commercial_ind`
- New collector: `src/nyc_pulse/collectors/evictions.py`
- Fold into existing `housing` scorer (strong housing distress signal)

### 4. Demographics (Census ACS) — bigger lift, separate PR
- Source: Census Bureau ACS 5-year estimates
- Requires polygon rendering (choropleth), not event points
- Needs a new `block_demographics` table or Census API proxy
- Suggested v2 after crime/fire/evictions land

## Frontend features to build

1. **Aru's Picks panel** — hardcoded favorite spots in the BlockPanel sidebar with one-click fly-to
2. **NYU buildings layer** — purple markers always on map, click to score that building's block
3. **localStorage bookmarks** — save/unsave button on each block report, persists in browser

## Popular open source projects to integrate

- **deck.gl** (Uber) — GPU-accelerated layers, would replace MapLibre heatmap with ScatterplotLayer or HeatmapLayer. Massive perf improvement at scale.
- **H3** (Uber) — hexagonal grid indexing; enables choropleth signal views (v2 Approach B from the spec)
- **Recharts** — add a small sparkline/bar chart to each signal card showing score trend over time
- **Turf.js** — client-side geo math; could compute "walk score"-style radius rings visually on the map

## Current branch state

- `master` — stable, all PRs merged except #4
- `nextjs-frontend` — PR #4 open, has local uncommitted changes (BlockPanel + Map) that need to be pushed
- `docs/frontend-v1-spec` — stale, can be deleted

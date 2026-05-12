# Crime, Fire & Evictions Signals — Design Spec
_Date: 2026-05-12_

## Problem

NYC Block Pulse currently scores five signals (construction, nightlife, housing, restaurants, quality of life). Three high-value public datasets are unused: NYPD complaint data, FDNY incident dispatch, and NYC evictions. The signal toggle is single-select, so users can only view one heatmap at a time.

## Goal

Add crime and fire as two new scored signals, fold evictions into the existing housing signal, and upgrade the frontend to multi-select so users can layer any combination of heatmaps simultaneously.

## Out of scope

- Demographics / Census ACS (v2, requires choropleth rendering)
- Separate heatmap colors per signal (single merged heatmap for now)
- Any schema changes (all new data goes into the existing `events` table)

---

## Backend

### New collectors

All three follow the existing `collect_X(days: int = 90) -> list[dict]` pattern and use `fetch_socrata` + `to_float` + `compact_summary` from existing utilities.

#### `src/nyc_pulse/collectors/nypd_crime.py`

- Dataset: `qgea-i56i` (NYPD Complaint Data Current YTD) on data.cityofnewyork.us
- Filter: `cmplnt_fr_dt` within last `days` days
- Select: `cmplnt_num`, `cmplnt_fr_dt`, `ofns_desc`, `law_cat_cd`, `latitude`, `longitude`, `boro_nm`
- Event ID: `f"crime_{row['cmplnt_num']}"`
- `source`: `"nypd_crime"`
- `event_type`: value of `law_cat_cd` lowercased (`"felony"`, `"misdemeanor"`, `"violation"`)
- `occurred_at`: `cmplnt_fr_dt`
- `category`: `ofns_desc`
- `summary`: `compact_summary(ofns_desc, law_cat_cd)`
- Skip rows missing `cmplnt_num`, `latitude`, or `longitude`

#### `src/nyc_pulse/collectors/fdny_fire.py`

- Dataset: `erm2-nwe9` (FDNY Incident Dispatch Data) on data.cityofnewyork.us
- Filter: `incident_datetime` within last `days` days
- Select: `starfire_incident_id`, `incident_datetime`, `incident_type_desc`, `latitude`, `longitude`, `borough_desc`
- Event ID: `f"fire_{row['starfire_incident_id']}"`
- `source`: `"fdny_fire"`
- `event_type`: `"fire_incident"`
- `occurred_at`: `incident_datetime`
- `category`: `incident_type_desc`
- `summary`: `compact_summary(incident_type_desc, row.get('borough_desc'))`
- Skip rows missing `starfire_incident_id`, `latitude`, or `longitude`

#### `src/nyc_pulse/collectors/evictions.py`

- Dataset: `6z8x-vjye` (NYC Evictions) on data.cityofnewyork.us
- Filter: `executed_date` within last `days` days
- Select: `court_index_number`, `executed_date`, `eviction_address`, `latitude`, `longitude`, `borough`, `residential_commercial_ind`
- Event ID: `f"eviction_{row['court_index_number']}_{row.get('executed_date', '')[:10]}"`
- `source`: `"evictions"`
- `event_type`: `"eviction"`
- `occurred_at`: `executed_date`
- `address`: `eviction_address`
- `category`: `residential_commercial_ind`
- `summary`: `compact_summary("Eviction", eviction_address)`
- Skip rows missing `court_index_number` or `executed_date`

### New scorers

#### `src/nyc_pulse/signals/crime.py`

```python
def score_crime(lat, lon, radius_ft=500, window_days=90, session=None) -> dict:
    rows = fetch_nearby_events(["nypd_crime"], lat, lon, radius_ft, window_days, session=session)
    score = sum(
        2.0 if r.get("event_type") == "felony"
        else 1.0 if r.get("event_type") == "misdemeanor"
        else 0.5
        for r in rows
    )
    return {
        "signal_type": "crime_complaints",
        "score": round(score, 2),
        "count": len(rows),
        "evidence": evidence(rows),
    }
```

#### `src/nyc_pulse/signals/fire.py`

```python
def score_fire(lat, lon, radius_ft=500, window_days=90, session=None) -> dict:
    rows = fetch_nearby_events(["fdny_fire"], lat, lon, radius_ft, window_days, session=session)
    return {
        "signal_type": "fire_incidents",
        "score": round(float(len(rows)), 2),
        "count": len(rows),
        "evidence": evidence(rows),
    }
```

### Updated scorer: housing

`src/nyc_pulse/signals/housing.py` — add `"evictions"` to the source list passed to `fetch_nearby_events`. Each eviction counts as 1 toward the housing distress score (no extra weight needed beyond its presence).

### CLI wiring (`src/nyc_pulse/cli.py`)

`update` command: import and call `collect_nypd_crime`, `collect_fdny_fire`, `collect_evictions` alongside existing collectors, pass results to `upsert_events`.

`block` command: import and call `score_crime`, `score_fire`, add their results to the signals dict returned in the block report. The response now has 7 signals.

---

## API layer

### FastAPI `/block` endpoint

Returns 7 signals. The `SignalName` literal type (defined in `api/models.py` or equivalent) gains `"crime"` and `"fire"`. No structural change to the response — it's already a dict keyed by signal name.

### FastAPI `/events` endpoint

No change. Accepts a single `signal: SignalName`. The frontend handles multi-select by making parallel requests.

---

## Frontend

### Type changes (`web/lib/types.ts`)

```ts
// Before
export type SignalName =
  | "construction" | "nightlife" | "housing" | "restaurants" | "quality_of_life";

// After
export type SignalName =
  | "construction" | "nightlife" | "housing" | "restaurants" | "quality_of_life"
  | "crime" | "fire";
```

### `web/components/SignalToggle.tsx`

Props change from single-select to multi-select:

```ts
// Before
type SignalToggleProps = {
  signal: SignalName;
  onChange: (signal: SignalName) => void;
};

// After
type SignalToggleProps = {
  signals: SignalName[];
  onChange: (signals: SignalName[]) => void;
};
```

Add `"crime"` and `"fire"` to the `SIGNALS` array.

Toggle logic: clicking an active signal removes it from the array (unless it's the last one — no-op if `signals.length === 1`). Clicking an inactive signal adds it. A button is visually active if its value is in the `signals` array.

### `web/app/page.tsx`

State changes:
```ts
// Before
const [signal, setSignal] = useState<SignalName>(DEFAULT_SIGNAL);

// After
const [signals, setSignals] = useState<SignalName[]>([DEFAULT_SIGNAL]);
```

`requestEvents` fires one `fetchEvents` call per selected signal in parallel, merges all returned feature arrays into a single `EventsGeoJSON` before calling `setHeatmapGeoJSON`. Merged collection: `features` = all arrays concatenated, `total_match` = sum across responses, `sampled` = `true` if any response was sampled.

The `scrollIntoView` call that highlights a signal card adapts: if exactly one signal is selected, scroll to that card. If multiple signals are selected, skip the scroll entirely.

Pass `signals` (array) to `SignalToggle` and `BlockPanel`.

### `web/components/BlockPanel.tsx`

Prop rename:
```ts
// Before
selectedSignal?: SignalName;

// After
selectedSignals?: SignalName[];
```

A signal card is highlighted (dark border) if its key is in `selectedSignals`. Add `"crime"` and `"fire"` to `SIGNAL_LABELS` and `SIGNAL_ORDER`.

Signal label additions:
```ts
crime: "Crime",
fire: "Fire Incidents",
```

`SIGNAL_ORDER` — insert crime and fire after quality_of_life:
```ts
["construction", "nightlife", "housing", "restaurants", "quality_of_life", "crime", "fire"]
```

---

## Data flow (end to end)

```
GitHub Actions cron
  → nyc-pulse update --days 7
    → collect_nypd_crime()  → upsert_events()
    → collect_fdny_fire()   → upsert_events()
    → collect_evictions()   → upsert_events()

User clicks map at (lat, lon)
  → GET /api/block?lat=...&lon=...
    → score_crime() → { signal_type: "crime_complaints", score, count, evidence }
    → score_fire()  → { signal_type: "fire_incidents",  score, count, evidence }
    → 7-signal response → BlockPanel renders all 7 cards

User selects [crime, construction] in SignalToggle
  → parallel: GET /api/events?signal=crime   → GeoJSON A
  → parallel: GET /api/events?signal=construction → GeoJSON B
  → merge features A + B → single heatmap layer
```

---

## Testing

Manual verification:
1. `nyc-pulse update --days 7` runs without error; `events` table has rows with `source IN ('nypd_crime', 'fdny_fire', 'evictions')`
2. `nyc-pulse block 40.73082 -73.99763` returns 7 signals including `crime` and `fire`
3. Frontend: block report panel shows 7 signal cards
4. Selecting "Crime" + "Construction" in toggle shows merged heatmap; deselecting one removes those events
5. Selecting all 7 signals works; clicking the last active signal is a no-op (stays selected)
6. Housing score increases in areas with recent evictions vs. without

---

## Files changed

| File | Change |
|------|--------|
| `src/nyc_pulse/collectors/nypd_crime.py` | New |
| `src/nyc_pulse/collectors/fdny_fire.py` | New |
| `src/nyc_pulse/collectors/evictions.py` | New |
| `src/nyc_pulse/signals/crime.py` | New |
| `src/nyc_pulse/signals/fire.py` | New |
| `src/nyc_pulse/signals/housing.py` | Add evictions source |
| `src/nyc_pulse/cli.py` | Wire new collectors + scorers |
| `api/` (FastAPI models/routes) | Add crime + fire to SignalName |
| `web/lib/types.ts` | Add crime + fire to SignalName |
| `web/components/SignalToggle.tsx` | Multi-select, add crime + fire |
| `web/app/page.tsx` | signals[] state, parallel fetch, merge |
| `web/components/BlockPanel.tsx` | selectedSignals[], add crime + fire labels |

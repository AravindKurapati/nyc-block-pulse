# Crime, Fire & Evictions Signals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add NYPD crime, FDNY fire, and NYC evictions signals to the backend, expose crime + fire as new API signals, and upgrade the frontend signal toggle to multi-select with parallel heatmap fetching.

**Architecture:** Three new collectors follow the existing `collect_X(days) -> list[dict]` pattern using `fetch_socrata`. Two new scorers follow `score_X(lat, lon, radius_ft, window_days, session) -> dict` using `fetch_nearby_events`. Evictions fold into the existing housing scorer. The frontend `SignalToggle` switches from single-value to array state; `page.tsx` fires parallel `fetchEvents` calls and merges results into one heatmap GeoJSON.

**Tech Stack:** Python, SQLAlchemy, Socrata API, FastAPI, Next.js 14, TypeScript, Tailwind CSS

---

## File Map

| File | Change |
|------|--------|
| `src/nyc_pulse/collectors/nypd_crime.py` | New — Socrata `qgea-i56i` collector |
| `src/nyc_pulse/collectors/fdny_fire.py` | New — Socrata `erm2-nwe9` collector |
| `src/nyc_pulse/collectors/evictions.py` | New — Socrata `6z8x-vjye` collector |
| `src/nyc_pulse/signals/crime.py` | New — weighted felony/misdemeanor/violation scorer |
| `src/nyc_pulse/signals/fire.py` | New — flat count scorer |
| `src/nyc_pulse/signals/housing.py` | Add `"evictions"` to source list |
| `src/nyc_pulse/cli.py` | Wire 3 collectors into `update`, 2 scorers into `block` |
| `api/routes/events.py` | Add `"crime"` + `"fire"` to `SignalName` + `SIGNAL_SOURCES` |
| `api/routes/block.py` | Add `score_crime` + `score_fire` to block endpoint |
| `api/tests/test_routes.py` | Update block test to expect 7 signals |
| `tests/test_collectors_schema.py` | Add contract tests for 3 new collectors |
| `tests/test_signals.py` | Add unit tests for crime + fire scorers |
| `web/lib/types.ts` | Add `"crime"` + `"fire"` to `SignalName` |
| `web/components/SignalToggle.tsx` | Multi-select props + logic + new buttons |
| `web/app/page.tsx` | `signals: SignalName[]` state, parallel fetch, merged GeoJSON |
| `web/components/BlockPanel.tsx` | `selectedSignals: SignalName[]`, add crime + fire labels |

---

### Task 1: NYPD Crime collector

**Files:**
- Create: `src/nyc_pulse/collectors/nypd_crime.py`
- Modify: `tests/test_collectors_schema.py`

- [ ] **Step 1: Write the failing contract test**

Open `tests/test_collectors_schema.py`. Add at the bottom:

```python
def test_nypd_crime_uses_correct_dataset_and_fields(monkeypatch):
    captured = {}

    def fake_fetch(dataset_id, where, select, limit=50_000, offset=0):
        captured["dataset_id"] = dataset_id
        captured["where"] = where
        captured["select"] = select
        return []

    from nyc_pulse.collectors import nypd_crime
    monkeypatch.setattr(nypd_crime, "fetch_socrata", fake_fetch)
    nypd_crime.collect_nypd_crime(days=7)

    assert captured["dataset_id"] == "qgea-i56i"
    assert "cmplnt_fr_dt" in captured["where"]
    select_fields = {f.strip() for f in captured["select"].split(",")}
    for required in ("cmplnt_num", "cmplnt_fr_dt", "ofns_desc", "law_cat_cd", "latitude", "longitude"):
        assert required in select_fields, f"Missing field: {required}"


def test_nypd_crime_normalizes_row(monkeypatch):
    from nyc_pulse.collectors import nypd_crime

    def fake_fetch(*a, **k):
        return [
            {
                "cmplnt_num": "123456789",
                "cmplnt_fr_dt": "2026-05-01T00:00:00",
                "ofns_desc": "ASSAULT 3 & RELATED OFFENSES",
                "law_cat_cd": "MISDEMEANOR",
                "latitude": "40.73082",
                "longitude": "-73.99763",
                "boro_nm": "MANHATTAN",
            }
        ]

    monkeypatch.setattr(nypd_crime, "fetch_socrata", fake_fetch)
    events = nypd_crime.collect_nypd_crime(days=7)

    assert len(events) == 1
    e = events[0]
    assert e["id"] == "crime_123456789"
    assert e["source"] == "nypd_crime"
    assert e["event_type"] == "misdemeanor"
    assert e["lat"] == 40.73082
    assert e["lon"] == -73.99763
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd D:\Aru\NYU\nyc-block-pulse
python -m pytest tests/test_collectors_schema.py::test_nypd_crime_uses_correct_dataset_and_fields tests/test_collectors_schema.py::test_nypd_crime_normalizes_row -v
```

Expected: `ModuleNotFoundError` or `ImportError` — file doesn't exist yet.

- [ ] **Step 3: Create the collector**

Create `src/nyc_pulse/collectors/nypd_crime.py`:

```python
from __future__ import annotations

from ._utils import compact_summary, to_float
from .socrata import days_ago_filter, fetch_socrata


def collect_nypd_crime(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "qgea-i56i",
        where=days_ago_filter("cmplnt_fr_dt", days),
        select="cmplnt_num,cmplnt_fr_dt,ofns_desc,law_cat_cd,latitude,longitude,boro_nm",
    )
    events = []
    for row in rows:
        cmplnt_num = row.get("cmplnt_num")
        if not cmplnt_num:
            continue
        lat = to_float(row.get("latitude"))
        lon = to_float(row.get("longitude"))
        if lat is None or lon is None:
            continue
        events.append({
            "id": f"crime_{cmplnt_num}",
            "source": "nypd_crime",
            "event_type": (row.get("law_cat_cd") or "").lower(),
            "occurred_at": row.get("cmplnt_fr_dt"),
            "address": None,
            "bbl": None,
            "bin": None,
            "lat": lat,
            "lon": lon,
            "status": None,
            "category": row.get("ofns_desc"),
            "summary": compact_summary(row.get("ofns_desc"), row.get("law_cat_cd")),
            "raw_json": row,
        })
    return events
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/test_collectors_schema.py::test_nypd_crime_uses_correct_dataset_and_fields tests/test_collectors_schema.py::test_nypd_crime_normalizes_row -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nyc_pulse/collectors/nypd_crime.py tests/test_collectors_schema.py
git commit -m "feat: NYPD crime collector (qgea-i56i)"
```

---

### Task 2: FDNY Fire collector

**Files:**
- Create: `src/nyc_pulse/collectors/fdny_fire.py`
- Modify: `tests/test_collectors_schema.py`

- [ ] **Step 1: Write the failing contract tests**

Append to `tests/test_collectors_schema.py`:

```python
def test_fdny_fire_uses_correct_dataset_and_fields(monkeypatch):
    captured = {}

    def fake_fetch(dataset_id, where, select, limit=50_000, offset=0):
        captured["dataset_id"] = dataset_id
        captured["where"] = where
        captured["select"] = select
        return []

    from nyc_pulse.collectors import fdny_fire
    monkeypatch.setattr(fdny_fire, "fetch_socrata", fake_fetch)
    fdny_fire.collect_fdny_fire(days=7)

    assert captured["dataset_id"] == "erm2-nwe9"
    assert "incident_datetime" in captured["where"]
    select_fields = {f.strip() for f in captured["select"].split(",")}
    for required in ("starfire_incident_id", "incident_datetime", "incident_type_desc", "latitude", "longitude"):
        assert required in select_fields, f"Missing field: {required}"


def test_fdny_fire_normalizes_row(monkeypatch):
    from nyc_pulse.collectors import fdny_fire

    def fake_fetch(*a, **k):
        return [
            {
                "starfire_incident_id": "987654",
                "incident_datetime": "2026-05-02T14:30:00",
                "incident_type_desc": "300 - Rescue, EMS incident, other",
                "latitude": "40.74220",
                "longitude": "-73.97440",
                "borough_desc": "3 - Manhattan",
            }
        ]

    monkeypatch.setattr(fdny_fire, "fetch_socrata", fake_fetch)
    events = fdny_fire.collect_fdny_fire(days=7)

    assert len(events) == 1
    e = events[0]
    assert e["id"] == "fire_987654"
    assert e["source"] == "fdny_fire"
    assert e["event_type"] == "fire_incident"
    assert e["lat"] == 40.74220
    assert e["lon"] == -73.97440
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_collectors_schema.py::test_fdny_fire_uses_correct_dataset_and_fields tests/test_collectors_schema.py::test_fdny_fire_normalizes_row -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create the collector**

Create `src/nyc_pulse/collectors/fdny_fire.py`:

```python
from __future__ import annotations

from ._utils import compact_summary, to_float
from .socrata import days_ago_filter, fetch_socrata


def collect_fdny_fire(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "erm2-nwe9",
        where=days_ago_filter("incident_datetime", days),
        select="starfire_incident_id,incident_datetime,incident_type_desc,latitude,longitude,borough_desc",
    )
    events = []
    for row in rows:
        incident_id = row.get("starfire_incident_id")
        if not incident_id:
            continue
        lat = to_float(row.get("latitude"))
        lon = to_float(row.get("longitude"))
        if lat is None or lon is None:
            continue
        events.append({
            "id": f"fire_{incident_id}",
            "source": "fdny_fire",
            "event_type": "fire_incident",
            "occurred_at": row.get("incident_datetime"),
            "address": None,
            "bbl": None,
            "bin": None,
            "lat": lat,
            "lon": lon,
            "status": None,
            "category": row.get("incident_type_desc"),
            "summary": compact_summary(row.get("incident_type_desc"), row.get("borough_desc")),
            "raw_json": row,
        })
    return events
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/test_collectors_schema.py::test_fdny_fire_uses_correct_dataset_and_fields tests/test_collectors_schema.py::test_fdny_fire_normalizes_row -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nyc_pulse/collectors/fdny_fire.py tests/test_collectors_schema.py
git commit -m "feat: FDNY fire collector (erm2-nwe9)"
```

---

### Task 3: Evictions collector

**Files:**
- Create: `src/nyc_pulse/collectors/evictions.py`
- Modify: `tests/test_collectors_schema.py`

- [ ] **Step 1: Write the failing contract tests**

Append to `tests/test_collectors_schema.py`:

```python
def test_evictions_uses_correct_dataset_and_fields(monkeypatch):
    captured = {}

    def fake_fetch(dataset_id, where, select, limit=50_000, offset=0):
        captured["dataset_id"] = dataset_id
        captured["where"] = where
        captured["select"] = select
        return []

    from nyc_pulse.collectors import evictions
    monkeypatch.setattr(evictions, "fetch_socrata", fake_fetch)
    evictions.collect_evictions(days=7)

    assert captured["dataset_id"] == "6z8x-vjye"
    assert "executed_date" in captured["where"]
    select_fields = {f.strip() for f in captured["select"].split(",")}
    for required in ("court_index_number", "executed_date", "eviction_address", "latitude", "longitude"):
        assert required in select_fields, f"Missing field: {required}"


def test_evictions_normalizes_row(monkeypatch):
    from nyc_pulse.collectors import evictions

    def fake_fetch(*a, **k):
        return [
            {
                "court_index_number": "LT-001234-26/BX",
                "executed_date": "2026-04-15T00:00:00",
                "eviction_address": "100 MAIN ST",
                "latitude": "40.85460",
                "longitude": "-73.89030",
                "borough": "BRONX",
                "residential_commercial_ind": "Residential",
            }
        ]

    monkeypatch.setattr(evictions, "fetch_socrata", fake_fetch)
    events = evictions.collect_evictions(days=7)

    assert len(events) == 1
    e = events[0]
    assert e["id"] == "eviction_LT-001234-26/BX_2026-04-15"
    assert e["source"] == "evictions"
    assert e["event_type"] == "eviction"
    assert e["address"] == "100 MAIN ST"
    assert e["lat"] == 40.85460
    assert e["lon"] == -73.89030
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_collectors_schema.py::test_evictions_uses_correct_dataset_and_fields tests/test_collectors_schema.py::test_evictions_normalizes_row -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create the collector**

Create `src/nyc_pulse/collectors/evictions.py`:

```python
from __future__ import annotations

from ._utils import compact_summary, to_float
from .socrata import days_ago_filter, fetch_socrata


def collect_evictions(days: int = 90) -> list[dict]:
    rows = fetch_socrata(
        "6z8x-vjye",
        where=days_ago_filter("executed_date", days),
        select="court_index_number,executed_date,eviction_address,latitude,longitude,borough,residential_commercial_ind",
    )
    events = []
    for row in rows:
        court_index = row.get("court_index_number")
        executed_date = row.get("executed_date")
        if not court_index or not executed_date:
            continue
        lat = to_float(row.get("latitude"))
        lon = to_float(row.get("longitude"))
        if lat is None or lon is None:
            continue
        events.append({
            "id": f"eviction_{court_index}_{executed_date[:10]}",
            "source": "evictions",
            "event_type": "eviction",
            "occurred_at": executed_date,
            "address": row.get("eviction_address"),
            "bbl": None,
            "bin": None,
            "lat": lat,
            "lon": lon,
            "status": None,
            "category": row.get("residential_commercial_ind"),
            "summary": compact_summary("Eviction", row.get("eviction_address")),
            "raw_json": row,
        })
    return events
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/test_collectors_schema.py::test_evictions_uses_correct_dataset_and_fields tests/test_collectors_schema.py::test_evictions_normalizes_row -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nyc_pulse/collectors/evictions.py tests/test_collectors_schema.py
git commit -m "feat: evictions collector (6z8x-vjye)"
```

---

### Task 4: Crime scorer

**Files:**
- Create: `src/nyc_pulse/signals/crime.py`
- Modify: `tests/test_signals.py`

- [ ] **Step 1: Write the failing unit test**

Open `tests/test_signals.py`. Add at the bottom:

```python
def test_score_crime_weights_by_severity(monkeypatch):
    from nyc_pulse.signals import crime

    monkeypatch.setattr(crime, "fetch_nearby_events", lambda *args, **kwargs: [
        {"id": "crime_1", "source": "nypd_crime", "event_type": "felony",
         "summary": "ROBBERY", "occurred_at": "2026-05-01", "category": "ROBBERY", "status": None, "raw_json": {}},
        {"id": "crime_2", "source": "nypd_crime", "event_type": "misdemeanor",
         "summary": "ASSAULT", "occurred_at": "2026-05-02", "category": "ASSAULT", "status": None, "raw_json": {}},
        {"id": "crime_3", "source": "nypd_crime", "event_type": "violation",
         "summary": "DISORDERLY", "occurred_at": "2026-05-03", "category": "DISORDERLY", "status": None, "raw_json": {}},
    ])

    result = crime.score_crime(40.7, -73.9)

    assert result["signal_type"] == "crime_complaints"
    # felony(2.0) + misdemeanor(1.0) + violation(0.5) = 3.5
    assert result["score"] == 3.5
    assert result["count"] == 3
    assert len(result["evidence"]) == 3
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python -m pytest tests/test_signals.py::test_score_crime_weights_by_severity -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create the scorer**

Create `src/nyc_pulse/signals/crime.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from ._common import evidence, fetch_nearby_events


def score_crime(lat: float, lon: float, radius_ft: int = 500, window_days: int = 90, session: Session | None = None) -> dict:
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

- [ ] **Step 4: Run test to confirm it passes**

```bash
python -m pytest tests/test_signals.py::test_score_crime_weights_by_severity -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nyc_pulse/signals/crime.py tests/test_signals.py
git commit -m "feat: crime scorer with felony/misdemeanor/violation weighting"
```

---

### Task 5: Fire scorer

**Files:**
- Create: `src/nyc_pulse/signals/fire.py`
- Modify: `tests/test_signals.py`

- [ ] **Step 1: Write the failing unit test**

Append to `tests/test_signals.py`:

```python
def test_score_fire_flat_count(monkeypatch):
    from nyc_pulse.signals import fire

    monkeypatch.setattr(fire, "fetch_nearby_events", lambda *args, **kwargs: [
        {"id": "fire_1", "source": "fdny_fire", "event_type": "fire_incident",
         "summary": "111 - Building fire", "occurred_at": "2026-05-01", "category": "111 - Building fire", "status": None, "raw_json": {}},
        {"id": "fire_2", "source": "fdny_fire", "event_type": "fire_incident",
         "summary": "321 - EMS call", "occurred_at": "2026-05-02", "category": "321 - EMS call", "status": None, "raw_json": {}},
    ])

    result = fire.score_fire(40.7, -73.9)

    assert result["signal_type"] == "fire_incidents"
    assert result["score"] == 2.0
    assert result["count"] == 2
    assert len(result["evidence"]) == 2
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python -m pytest tests/test_signals.py::test_score_fire_flat_count -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create the scorer**

Create `src/nyc_pulse/signals/fire.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from ._common import evidence, fetch_nearby_events


def score_fire(lat: float, lon: float, radius_ft: int = 500, window_days: int = 90, session: Session | None = None) -> dict:
    rows = fetch_nearby_events(["fdny_fire"], lat, lon, radius_ft, window_days, session=session)
    return {
        "signal_type": "fire_incidents",
        "score": round(float(len(rows)), 2),
        "count": len(rows),
        "evidence": evidence(rows),
    }
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
python -m pytest tests/test_signals.py::test_score_fire_flat_count -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nyc_pulse/signals/fire.py tests/test_signals.py
git commit -m "feat: fire scorer (flat incident count)"
```

---

### Task 6: Update housing scorer to include evictions

**Files:**
- Modify: `src/nyc_pulse/signals/housing.py`
- Modify: `tests/test_signals.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_signals.py`:

```python
def test_score_housing_includes_evictions(monkeypatch):
    from nyc_pulse.signals import housing

    called_with_sources = []

    def fake_fetch(sources, lat, lon, radius_ft, window_days, session=None):
        called_with_sources.extend(sources)
        return [
            {"id": "eviction_1", "source": "evictions", "event_type": "eviction",
             "summary": "Eviction - 123 Main St", "occurred_at": "2026-05-01",
             "category": "Residential", "status": None, "raw_json": {}},
        ]

    monkeypatch.setattr(housing, "fetch_nearby_events", fake_fetch)
    result = housing.score_housing(40.7, -73.9)

    assert "evictions" in called_with_sources
    assert result["signal_type"] == "housing_distress"
    assert result["count"] >= 1
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python -m pytest tests/test_signals.py::test_score_housing_includes_evictions -v
```

Expected: FAIL — `"evictions" not in called_with_sources`.

- [ ] **Step 3: Update housing scorer**

Open `src/nyc_pulse/signals/housing.py`. Find:

```python
    rows = fetch_nearby_events(["hpd_complaints", "hpd_violations", "nyc_311"], lat, lon, radius_ft, window_days, session=session)
```

Replace with:

```python
    rows = fetch_nearby_events(["hpd_complaints", "hpd_violations", "nyc_311", "evictions"], lat, lon, radius_ft, window_days, session=session)
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
python -m pytest tests/test_signals.py::test_score_housing_includes_evictions -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/nyc_pulse/signals/housing.py tests/test_signals.py
git commit -m "feat: fold evictions into housing scorer"
```

---

### Task 7: Wire new collectors and scorers into the CLI

**Files:**
- Modify: `src/nyc_pulse/cli.py`

- [ ] **Step 1: Add collector imports**

Open `src/nyc_pulse/cli.py`. The existing imports start at line 9. Add three new import lines after the existing collector imports:

```python
from .collectors.dob_permits import collect_dob_permits
from .collectors.evictions import collect_evictions          # new
from .collectors.fdny_fire import collect_fdny_fire          # new
from .collectors.hpd_complaints import collect_hpd_complaints
from .collectors.hpd_violations import collect_hpd_violations
from .collectors.liquor import collect_liquor
from .collectors.nypd_crime import collect_nypd_crime        # new
from .collectors.nyc_311 import collect_311
from .collectors.restaurants import collect_restaurants
```

- [ ] **Step 2: Register the three new collectors in the `update` command's `collectors` dict**

Find the `collectors` dict in the `update` command (currently has 6 entries). Replace the entire dict:

```python
    collectors = {
        "311": collect_311,
        "dob": collect_dob_permits,
        "evictions": collect_evictions,
        "fire": collect_fdny_fire,
        "hpd": collect_hpd_complaints,
        "hpd_violations": collect_hpd_violations,
        "crime": collect_nypd_crime,
        "restaurants": collect_restaurants,
        "liquor": collect_liquor,
    }
```

Also update the help text for `source`:

```python
    source: str = typer.Option(
        "all",
        help="Source to update: all|311|dob|evictions|fire|hpd|hpd_violations|crime|restaurants|liquor",
    ),
```

- [ ] **Step 3: Add scorer imports and wire into the `block` command**

At the top of the `block_report` function body, add imports for the two new scorers alongside the existing ones:

```python
    from .signals.construction import score_construction
    from .signals.crime import score_crime                    # new
    from .signals.fire import score_fire                      # new
    from .signals.housing import score_housing
    from .signals.nightlife import score_nightlife
    from .signals.quality_of_life import score_quality_of_life
    from .signals.restaurants import score_restaurants
```

Replace the `signals` dict in `block_report`:

```python
        signals = {
            "construction": score_construction(loc["lat"], loc["lon"], radius, days, session=session),
            "nightlife": score_nightlife(loc["lat"], loc["lon"], radius, days, session=session),
            "housing": score_housing(loc["lat"], loc["lon"], radius, days, session=session),
            "restaurants": score_restaurants(loc["lat"], loc["lon"], radius, days, session=session),
            "quality_of_life": score_quality_of_life(loc["lat"], loc["lon"], radius, days, session=session),
            "crime": score_crime(loc["lat"], loc["lon"], radius, days, session=session),
            "fire": score_fire(loc["lat"], loc["lon"], radius, days, session=session),
        }
```

- [ ] **Step 4: Verify no import errors**

```bash
python -c "from nyc_pulse.cli import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/nyc_pulse/cli.py
git commit -m "feat: wire crime/fire/evictions collectors and scorers into CLI"
```

---

### Task 8: Update FastAPI events route

**Files:**
- Modify: `api/routes/events.py`

- [ ] **Step 1: Update `SignalName` Literal and `SIGNAL_SOURCES`**

Open `api/routes/events.py`. Find:

```python
SignalName = Literal["construction", "nightlife", "housing", "restaurants", "quality_of_life"]

SIGNAL_SOURCES: dict[str, tuple[str, ...]] = {
    "construction": ("dob_permits",),
    "nightlife": ("liquor", "nyc_311", "restaurants"),
    "housing": ("hpd_complaints", "hpd_violations", "nyc_311"),
    "restaurants": ("restaurants", "liquor", "dob_permits"),
    "quality_of_life": ("nyc_311",),
}
```

Replace with:

```python
SignalName = Literal["construction", "nightlife", "housing", "restaurants", "quality_of_life", "crime", "fire"]

SIGNAL_SOURCES: dict[str, tuple[str, ...]] = {
    "construction": ("dob_permits",),
    "nightlife": ("liquor", "nyc_311", "restaurants"),
    "housing": ("hpd_complaints", "hpd_violations", "nyc_311", "evictions"),
    "restaurants": ("restaurants", "liquor", "dob_permits"),
    "quality_of_life": ("nyc_311",),
    "crime": ("nypd_crime",),
    "fire": ("fdny_fire",),
}
```

- [ ] **Step 2: Verify the API starts cleanly**

```bash
python -c "from api.routes.events import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add api/routes/events.py
git commit -m "feat: add crime + fire to API events SignalName and SIGNAL_SOURCES"
```

---

### Task 9: Update FastAPI block route

**Files:**
- Modify: `api/routes/block.py`

- [ ] **Step 1: Add imports for new scorers**

Open `api/routes/block.py`. Find the existing scorer imports:

```python
from nyc_pulse.signals.construction import score_construction
from nyc_pulse.signals.housing import score_housing
from nyc_pulse.signals.nightlife import score_nightlife
from nyc_pulse.signals.quality_of_life import score_quality_of_life
from nyc_pulse.signals.restaurants import score_restaurants
```

Replace with:

```python
from nyc_pulse.signals.construction import score_construction
from nyc_pulse.signals.crime import score_crime
from nyc_pulse.signals.fire import score_fire
from nyc_pulse.signals.housing import score_housing
from nyc_pulse.signals.nightlife import score_nightlife
from nyc_pulse.signals.quality_of_life import score_quality_of_life
from nyc_pulse.signals.restaurants import score_restaurants
```

- [ ] **Step 2: Add crime + fire to the signals dict**

Find the `signals` dict in `block_report`:

```python
    signals = {
        "construction": score_construction(lat, lon, payload.radius_ft, payload.days, session=session),
        "nightlife": score_nightlife(lat, lon, payload.radius_ft, payload.days, session=session),
        "housing": score_housing(lat, lon, payload.radius_ft, payload.days, session=session),
        "restaurants": score_restaurants(lat, lon, payload.radius_ft, payload.days, session=session),
        "quality_of_life": score_quality_of_life(lat, lon, payload.radius_ft, payload.days, session=session),
    }
```

Replace with:

```python
    signals = {
        "construction": score_construction(lat, lon, payload.radius_ft, payload.days, session=session),
        "nightlife": score_nightlife(lat, lon, payload.radius_ft, payload.days, session=session),
        "housing": score_housing(lat, lon, payload.radius_ft, payload.days, session=session),
        "restaurants": score_restaurants(lat, lon, payload.radius_ft, payload.days, session=session),
        "quality_of_life": score_quality_of_life(lat, lon, payload.radius_ft, payload.days, session=session),
        "crime": score_crime(lat, lon, payload.radius_ft, payload.days, session=session),
        "fire": score_fire(lat, lon, payload.radius_ft, payload.days, session=session),
    }
```

- [ ] **Step 3: Commit**

```bash
git add api/routes/block.py
git commit -m "feat: add crime + fire signals to API block route"
```

---

### Task 10: Update API block route test

**Files:**
- Modify: `api/tests/test_routes.py`

- [ ] **Step 1: Update the existing block test**

Open `api/tests/test_routes.py`. Find `test_block_scores_all_signals_with_one_session`. It currently patches 5 scorer names and asserts 5 signals. Update it to patch 7 and assert 7:

Find:
```python
    for name in (
        "score_construction",
        "score_nightlife",
        "score_housing",
        "score_restaurants",
        "score_quality_of_life",
    ):
        monkeypatch.setattr(block_route, name, fake_score)
```

Replace with:
```python
    for name in (
        "score_construction",
        "score_nightlife",
        "score_housing",
        "score_restaurants",
        "score_quality_of_life",
        "score_crime",
        "score_fire",
    ):
        monkeypatch.setattr(block_route, name, fake_score)
```

Find:
```python
    assert set(body["signals"]) == {"construction", "nightlife", "housing", "restaurants", "quality_of_life"}
    assert seen_sessions == [fake_session] * 5
```

Replace with:
```python
    assert set(body["signals"]) == {"construction", "nightlife", "housing", "restaurants", "quality_of_life", "crime", "fire"}
    assert seen_sessions == [fake_session] * 7
```

- [ ] **Step 2: Run the full API test suite**

```bash
python -m pytest api/tests/ -v
```

Expected: all pass.

- [ ] **Step 3: Run the full backend test suite**

```bash
python -m pytest tests/ api/tests/ -v
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add api/tests/test_routes.py
git commit -m "test: update block route test to expect 7 signals"
```

---

### Task 11: Update frontend types and BlockPanel labels

**Files:**
- Modify: `web/lib/types.ts`
- Modify: `web/components/BlockPanel.tsx`

- [ ] **Step 1: Add `"crime"` and `"fire"` to `SignalName` in types.ts**

Open `web/lib/types.ts`. Find:

```ts
export type SignalName =
  | "construction"
  | "nightlife"
  | "housing"
  | "restaurants"
  | "quality_of_life";
```

Replace with:

```ts
export type SignalName =
  | "construction"
  | "nightlife"
  | "housing"
  | "restaurants"
  | "quality_of_life"
  | "crime"
  | "fire";
```

- [ ] **Step 2: Add crime + fire to `SIGNAL_LABELS` and `SIGNAL_ORDER` in BlockPanel**

Open `web/components/BlockPanel.tsx`. Find:

```ts
const SIGNAL_LABELS: Record<SignalName, string> = {
  construction: "Construction",
  nightlife: "Nightlife",
  housing: "Housing",
  restaurants: "Restaurants",
  quality_of_life: "Quality of life",
};
```

Replace with:

```ts
const SIGNAL_LABELS: Record<SignalName, string> = {
  construction: "Construction",
  nightlife: "Nightlife",
  housing: "Housing",
  restaurants: "Restaurants",
  quality_of_life: "Quality of life",
  crime: "Crime",
  fire: "Fire Incidents",
};
```

Find:

```ts
const SIGNAL_ORDER: SignalName[] = [
  "construction",
  "nightlife",
  "housing",
  "restaurants",
  "quality_of_life",
];
```

Replace with:

```ts
const SIGNAL_ORDER: SignalName[] = [
  "construction",
  "nightlife",
  "housing",
  "restaurants",
  "quality_of_life",
  "crime",
  "fire",
];
```

- [ ] **Step 3: Update `selectedSignal` prop to `selectedSignals` (array)**

Find:

```ts
type BlockPanelProps = {
  report: BlockReport | null;
  isLoading?: boolean;
  error?: string | null;
  selectedSignal?: SignalName;
  onFlyTo: (lat: number, lon: number) => void;
};
```

Replace with:

```ts
type BlockPanelProps = {
  report: BlockReport | null;
  isLoading?: boolean;
  error?: string | null;
  selectedSignals?: SignalName[];
  onFlyTo: (lat: number, lon: number) => void;
};
```

Update the function signature destructure to match:

```ts
export default function BlockPanel({
  report,
  isLoading = false,
  error,
  selectedSignals,
  onFlyTo,
}: BlockPanelProps) {
```

Update the card highlight check. Find:

```ts
          const active = key === selectedSignal;
```

Replace with:

```ts
          const active = selectedSignals?.includes(key) ?? false;
```

- [ ] **Step 4: Verify TypeScript compiles (one expected error — page.tsx not updated yet)**

```bash
cd web && npx tsc --noEmit 2>&1
```

Expected: one error about `selectedSignal` prop missing in `page.tsx`. That's fine — fixed in Task 13.

- [ ] **Step 5: Commit**

```bash
git add web/lib/types.ts web/components/BlockPanel.tsx
git commit -m "feat: add crime + fire to frontend SignalName and BlockPanel"
```

---

### Task 12: Update SignalToggle to multi-select

**Files:**
- Modify: `web/components/SignalToggle.tsx`

- [ ] **Step 1: Replace the entire file**

Open `web/components/SignalToggle.tsx` and replace its full contents with:

```tsx
"use client";

import type { SignalName } from "@/lib/types";

const SIGNALS: Array<{ value: SignalName; label: string }> = [
  { value: "quality_of_life", label: "Quality of life" },
  { value: "nightlife", label: "Nightlife" },
  { value: "construction", label: "Construction" },
  { value: "housing", label: "Housing" },
  { value: "restaurants", label: "Restaurants" },
  { value: "crime", label: "Crime" },
  { value: "fire", label: "Fire Incidents" },
];

type SignalToggleProps = {
  signals: SignalName[];
  onChange: (signals: SignalName[]) => void;
};

export default function SignalToggle({ signals, onChange }: SignalToggleProps) {
  function toggle(value: SignalName) {
    if (signals.includes(value)) {
      if (signals.length === 1) return;
      onChange(signals.filter((s) => s !== value));
    } else {
      onChange([...signals, value]);
    }
  }

  return (
    <div className="w-[min(600px,calc(100vw-2rem))] rounded border border-neutral-200 bg-white/95 p-3 shadow-sm backdrop-blur">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Signals
      </div>
      <div className="flex flex-wrap gap-2">
        {SIGNALS.map((item) => {
          const active = signals.includes(item.value);
          return (
            <button
              key={item.value}
              type="button"
              onClick={() => toggle(item.value)}
              className={[
                "min-h-9 rounded border px-3 text-sm font-medium transition",
                active
                  ? "border-neutral-950 bg-neutral-950 text-white"
                  : "border-neutral-200 bg-white text-neutral-700 hover:border-neutral-400",
              ].join(" ")}
              aria-pressed={active}
            >
              {item.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles (still the one page.tsx error)**

```bash
cd web && npx tsc --noEmit 2>&1
```

Expected: still only the `page.tsx` prop mismatch error.

- [ ] **Step 3: Commit**

```bash
git add web/components/SignalToggle.tsx
git commit -m "feat: SignalToggle multi-select with crime + fire"
```

---

### Task 13: Update page.tsx for multi-signal state and parallel fetch

**Files:**
- Modify: `web/app/page.tsx`

- [ ] **Step 1: Replace the entire page.tsx**

Open `web/app/page.tsx` and replace its full contents with:

```tsx
"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";

import BlockPanel from "@/components/BlockPanel";
import SearchBar from "@/components/SearchBar";
import SignalToggle from "@/components/SignalToggle";
import { fetchBlock, fetchEvents } from "@/lib/api";
import type {
  BBox,
  BlockReport,
  EventsGeoJSON,
  SearchResult,
  SignalName,
} from "@/lib/types";

const Map = dynamic(() => import("@/components/Map"), { ssr: false });

const DEFAULT_SIGNAL: SignalName = "quality_of_life";
const DEFAULT_DAYS = 90;
const DEFAULT_RADIUS_FT = 500;

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

export default function Home() {
  const [signals, setSignals] = useState<SignalName[]>([DEFAULT_SIGNAL]);
  const [heatmapGeoJSON, setHeatmapGeoJSON] = useState<EventsGeoJSON | null>(null);
  const [report, setReport] = useState<BlockReport | null>(null);
  const [selectedLocation, setSelectedLocation] = useState<{
    lat: number;
    lon: number;
  } | null>(null);
  const [isBlockLoading, setIsBlockLoading] = useState(false);
  const [blockError, setBlockError] = useState<string | null>(null);
  const [eventError, setEventError] = useState<string | null>(null);
  const panelError = blockError ?? eventError;

  const signalsRef = useRef(signals);
  const bboxRef = useRef<BBox | null>(null);
  const eventAbortRef = useRef<AbortController | null>(null);
  const blockAbortRef = useRef<AbortController | null>(null);
  const boundsDebounceRef = useRef<number | null>(null);
  const pendingSignalsRef = useRef<SignalName[] | null>(null);

  useEffect(() => {
    signalsRef.current = signals;
  }, [signals]);

  const requestEvents = useCallback((nextSignals: SignalName[], bbox: BBox) => {
    eventAbortRef.current?.abort();
    const controller = new AbortController();
    eventAbortRef.current = controller;
    setEventError(null);

    Promise.all(
      nextSignals.map((sig) =>
        fetchEvents(
          { signal: sig, bbox, days: DEFAULT_DAYS, limit: 5000 },
          controller.signal,
        )
      )
    )
      .then((results) => {
        const merged: EventsGeoJSON = {
          type: "FeatureCollection",
          features: results.flatMap((r) => r.features),
          sampled: results.some((r) => r.sampled),
          total_match: results.reduce((sum, r) => sum + r.total_match, 0),
        };
        setHeatmapGeoJSON(merged);
      })
      .catch((error: unknown) => {
        if (isAbortError(error)) return;
        setEventError(
          error instanceof Error ? error.message : "Could not load map events.",
        );
      });
  }, []);

  const handleBoundsChange = useCallback(
    (bbox: BBox) => {
      bboxRef.current = bbox;
      const pendingSignals = pendingSignalsRef.current;
      if (pendingSignals) {
        pendingSignalsRef.current = null;
        requestEvents(pendingSignals, bbox);
        return;
      }
      if (boundsDebounceRef.current) {
        window.clearTimeout(boundsDebounceRef.current);
      }
      boundsDebounceRef.current = window.setTimeout(() => {
        requestEvents(signalsRef.current, bbox);
      }, 300);
    },
    [requestEvents],
  );

  useEffect(() => {
    const bbox = bboxRef.current;
    if (bbox) {
      requestEvents(signals, bbox);
    } else {
      pendingSignalsRef.current = signals;
    }
    if (signals.length === 1) {
      document
        .getElementById(`signal-${signals[0]}`)
        ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [requestEvents, signals]);

  const loadBlock = useCallback((lat: number, lon: number) => {
    blockAbortRef.current?.abort();
    const controller = new AbortController();
    blockAbortRef.current = controller;
    setSelectedLocation({ lat, lon });
    setBlockError(null);
    setIsBlockLoading(true);

    fetchBlock(
      { lat, lon, days: DEFAULT_DAYS, radius_ft: DEFAULT_RADIUS_FT },
      controller.signal,
    )
      .then((data) => setReport(data))
      .catch((error: unknown) => {
        if (isAbortError(error)) return;
        setBlockError(
          error instanceof Error ? error.message : "Could not load block report.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsBlockLoading(false);
        }
      });
  }, []);

  const handleSearchSelect = useCallback(
    (result: SearchResult) => {
      loadBlock(result.lat, result.lon);
    },
    [loadBlock],
  );

  useEffect(() => {
    return () => {
      eventAbortRef.current?.abort();
      blockAbortRef.current?.abort();
      if (boundsDebounceRef.current) {
        window.clearTimeout(boundsDebounceRef.current);
      }
    };
  }, []);

  return (
    <main className="flex min-h-screen flex-col bg-neutral-100 text-neutral-950">
      <header className="z-20 flex min-h-16 items-center gap-4 border-b border-neutral-200 bg-white px-4 py-3 shadow-sm md:px-6">
        <div className="shrink-0 text-lg font-semibold tracking-tight">
          NYC Block Pulse
        </div>
        <div className="min-w-0 flex-1">
          <SearchBar onSelect={handleSearchSelect} />
        </div>
      </header>

      <div className="grid flex-1 lg:grid-cols-[minmax(0,65fr)_minmax(360px,35fr)]">
        <section className="relative min-h-[calc(100vh-4rem)] bg-neutral-200">
          <Map
            heatmapGeoJSON={heatmapGeoJSON}
            selectedLocation={selectedLocation}
            onMapClick={loadBlock}
            onBoundsChange={handleBoundsChange}
          />
          <div className="pointer-events-none absolute bottom-4 left-4 z-10">
            <div className="pointer-events-auto">
              <SignalToggle signals={signals} onChange={setSignals} />
            </div>
          </div>
        </section>

        <div className="min-h-[520px] lg:h-[calc(100vh-4rem)]">
          <BlockPanel
            report={report}
            isLoading={isBlockLoading}
            error={panelError}
            selectedSignals={signals}
            onFlyTo={loadBlock}
          />
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Verify TypeScript is now clean**

```bash
cd web && npx tsc --noEmit 2>&1
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add web/app/page.tsx
git commit -m "feat: multi-signal state and parallel heatmap fetch in page.tsx"
```

---

### Task 14: Final verification and PR

- [ ] **Step 1: Run full backend test suite**

```bash
cd D:\Aru\NYU\nyc-block-pulse
python -m pytest tests/ api/tests/ -v
```

Expected: all pass.

- [ ] **Step 2: Run frontend build**

```bash
cd web && npm run build 2>&1
```

Expected: no errors.

- [ ] **Step 3: Manual smoke test**

Start the dev server:
```bash
cd web && npm run dev
```

Open `http://localhost:3000` and verify:
- Signal toggle shows 7 buttons: Quality of life, Nightlife, Construction, Housing, Restaurants, Crime, Fire Incidents
- Clicking a second signal adds it (both filled dark)
- Clicking an active signal removes it (unless it's the last one — no-op)
- Clicking the map loads a block report with 7 signal cards including Crime and Fire Incidents
- Score bars and animated counts appear for all 7 signals

- [ ] **Step 4: Push and open PR**

```bash
git push origin nextjs-frontend
gh pr create --title "feat: crime, fire, evictions signals + multi-select toggle" --body "$(cat <<'EOF'
## Summary

- Add NYPD crime collector (Socrata qgea-i56i) with felony×2 / misdemeanor×1 / violation×0.5 scoring
- Add FDNY fire collector (Socrata erm2-nwe9) with flat incident count scoring
- Add NYC evictions collector (Socrata 6z8x-vjye), folded into housing distress scorer
- Expose crime + fire as new signals in FastAPI /block and /events endpoints
- Upgrade frontend SignalToggle from single-select to multi-select (min 1 always active)
- page.tsx fires parallel fetchEvents calls per selected signal, merges into single heatmap GeoJSON
- BlockPanel shows all 7 signal cards; active cards highlighted for all selected signals

## Test Plan

- [ ] `python -m pytest tests/ api/tests/ -v` — all pass
- [ ] `npm run build` — no errors
- [ ] Signal toggle shows 7 buttons; multi-select works, last button is no-op when clicked
- [ ] Block report shows 7 signals including Crime and Fire Incidents with scores and evidence
- [ ] Selecting Crime + Construction layers both heatmaps on the map
- [ ] `nyc-pulse update --days 7` runs without error (requires live DB + API token)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

# TWEAK: Collector schema fixes (DOB / HPD complaints / liquor)

## Problem

Three of the six Socrata collectors are broken against the **current** dataset schemas:

1. **DOB Permit Issuance (`ipu4-2q9a`) — HTTP 400 + dataset frozen.** The `$select` references field names that don't exist in the live schema. Double-trailing-underscore fields (`job__`, `house__`, `bin__`) are **correct** — those weren't the problem. The actual culprits:

   | Code uses             | Dataset has           |
   |-----------------------|-----------------------|
   | `building_type`       | `bldg_type`           |
   | `latitude`            | `gis_latitude`        |
   | `longitude`           | `gis_longitude`       |
   | `job_status`          | `permit_status`       |
   | `bbl`                 | *(field does not exist)* |
   | `estimated_job_costs` | *(field does not exist)* |

   Socrata returns 400 for the entire request when any one `$select` field is unknown.

   **Additional finding during smoke testing:** even after fixing `$select`, `ipu4-2q9a` returned 0 rows. The dataset's most recent `issuance_date` is **2020-06-05** — the dataset is frozen. Per the official description: *"This dataset only includes permits issued in the Buildings Information System (BIS); most current permits are now issued in DOB NOW."* The collector must instead use **DOB NOW: Build – Approved Permits = `rbx6-tga4`**, which has a similar but cleaner schema (`job_filing_number`, `work_permit`, `filing_reason`, `work_type`, `permit_status`, `house_no`, `street_name`, `borough`, `bin`, `bbl`, `latitude`, `longitude`, `issued_date`, `estimated_job_costs`).

2. **HPD Complaints — HTTP 403.** The hardcoded dataset ID `uwyv-629c` has been retired; Socrata returns 403 (not 404) for deprecated datasets. The current replacement is **`ygpa-z7cr`** ("Housing Maintenance Code Complaints and Problems"). The schema is also entirely different: current dataset uses `complaint_id`, `received_date`, `borough`, `house_number`, `street_name`, `major_category`, `minor_category`, `type`, `problem_code`, `complaint_status`, `complaint_status_date`, `latitude`, `longitude`, `bbl`, `bin` — *not* `complaintid`, `opendate`, `buildingnumber`, `boroughname`, `codedescription`, `status`, etc.

3. **NY State SLA liquor licenses — HTTP 403.** Dataset `wg8y-fzsj` has been retired. The current replacement is **`9s3h-dpkz`** ("Current Liquor Authority Active Licenses") on `data.ny.gov`. New schema:

   - Unique ID: `licensepermitid` (not `serial_number`)
   - County: `premisescounty` (mixed case — `"New York"`, `"Kings"`, `"Queens"`, `"Bronx"`, `"Richmond"`)
   - Type/description: `description` (e.g. "Restaurant", "Liquor Store"), `class`, `type`
   - Names: `legalname`, `dba`
   - Address: `actualaddressofpremises`, `city`, `statename`, `zipcode`
   - Dates: `originalissuedate`, `lastissuedate`, `effectivedate`, `expirationdate`
   - Geo: `georeference` (still `{coordinates: [lon, lat], type: "Point"}`)
   - **No** `license_status` field — every row in this dataset is active by definition.

   The collector also currently sends **no `X-App-Token`** to `data.ny.gov`. Socrata accepts the same NYC app token across portals; we should pass it for politeness and to avoid throttling. (The 403 is the deprecated-dataset issue, not the missing token — but sending it is the right hygiene fix.)

311 (`erm2-nwe9`), HPD violations (`wvxf-dwi5`), and restaurants (`43nn-pn8j`) are all still on current IDs and need no changes.

## Approach

### 1. DOB collector — switch to DOB NOW dataset

In `collectors/dob_permits.py`:

- Dataset ID: `rbx6-tga4`.
- Date filter field: `issued_date` (was `issuance_date` in BIS).
- `$select`: `job_filing_number,work_permit,filing_reason,work_type,permit_status,house_no,street_name,borough,bin,bbl,latitude,longitude,issued_date,approved_date,expired_date,job_description,estimated_job_costs`
- Unique ID: `work_permit` (fall back to `job_filing_number` if absent) → `dob_permit_{work_permit}`.
- Address: `{house_no} {street_name}`.
- `lat`/`lon` read from `latitude`/`longitude` (no more `gis_` prefix).
- `bbl` and `bin` populated from the live fields.
- `status` reads `permit_status`.
- `event_type` reads `filing_reason`.
- `category` reads `work_type`.
- `summary` is `compact_summary(filing_reason, work_type, "est. $<cost>")`.

### 2. HPD complaints collector — switch dataset + rewrite field mapping

In `collectors/hpd_complaints.py`:

- Dataset ID: `ygpa-z7cr`.
- `$where` date field: `received_date` (not `opendate`).
- `$select`: `complaint_id,problem_id,type,major_category,minor_category,problem_code,house_number,street_name,borough,bbl,bin,latitude,longitude,received_date,complaint_status,complaint_status_date`.
- ID dedup key: `complaint_id` (note underscore; was `complaintid`).
- Address: `{house_number} {street_name}`.
- `bbl`, `bin` populated from the live fields.
- `event_type` → `type` (`EMERGENCY` / `NON EMERGENCY` / `HAZARDOUS` / `IMMEDIATE EMERGENCY`).
- `category` → `major_category`.
- `summary` → `compact_summary(major_category, minor_category, problem_code)`.
- `status` → `complaint_status`.
- `occurred_at` → `received_date`.

### 3. SLA liquor collector — switch dataset + rewrite

In `collectors/liquor.py`:

- Base URL: `https://data.ny.gov/resource/9s3h-dpkz.json`.
- County filter (case-insensitive against mixed case in the new dataset):
  `upper(premisescounty) in ('NEW YORK','KINGS','QUEENS','BRONX','RICHMOND')`
- Pass `X-App-Token` header from `settings.nyc_open_data_app_token` when set (same token works on `data.ny.gov`).
- Unique ID: `licensepermitid` → `sla_{licensepermitid}`.
- Address: `actualaddressofpremises`.
- DBA: `dba` (fall back to `legalname`).
- Type/category: `description`.
- Coordinates: `georeference.coordinates` → `[lon, lat]` (same as before, just on new field).
- `status`: set to `"ACTIVE"` (this dataset is active licenses only).
- `occurred_at`: `effectivedate`.

### 4. Hygiene: extract `data.ny.gov` access through the shared Socrata helper

Optional but clean: add an optional `base_url` parameter to `fetch_socrata` (default `https://data.cityofnewyork.us/resource`) so the liquor collector can reuse the paginate-and-token-send plumbing instead of its bespoke `httpx.get` loop. This is a small refactor that drops ~25 lines from `liquor.py` and gives us free `X-App-Token` headers. Recommended.

## Files touched

- `src/nyc_pulse/collectors/dob_permits.py`
- `src/nyc_pulse/collectors/hpd_complaints.py`
- `src/nyc_pulse/collectors/liquor.py`
- `src/nyc_pulse/collectors/socrata.py` — accept optional `base_url`, optional rate-limit headers param if needed.
- `tests/test_collectors_schema.py` — new contract tests asserting each broken collector sends the right dataset ID + `$select` to a captured `fetch_socrata`.
- `tests/test_socrata.py` — existing `test_collect_liquor_paginates` becomes wrong (different field names + URL). Rewrite to use new schema.

## Database impact

**None.** Schema unchanged. The `events` table accepts all of these via the existing `upsert_events` mapping. `category`, `event_type`, `status`, `summary` are free-text fields. `bbl`/`bin` remain optional. No migration. `SCHEMA.md` does not need updating.

## Risks / caveats

- DOB doesn't expose `bbl` directly; we lose BBL on DOB events. Acceptable — `geom` is still populated from `gis_latitude`/`gis_longitude`, and downstream block scoring uses the geometry, not BBL.
- The new SLA dataset is *active-only* — we no longer see inactive/expired licenses. That matches the previous filter intent (current nightlife signal), so this is a wash.
- The HPD complaints dataset is "Complaints and Problems" (one row per problem, not per complaint). We dedupe on `complaint_id`; multiple problem rows per complaint collapse to one event. Acceptable for block-level signal scoring; if we ever want per-problem granularity, we'd switch the dedup key to `problem_id`.

## Rollout

- `pytest -q` must pass.
- Smoke: `nyc-pulse update --source dob --days 7`, `--source hpd`, `--source liquor` each must complete and report fetched/inserted counts > 0.

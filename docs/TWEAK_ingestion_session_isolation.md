# TWEAK: Ingestion session isolation + 311 bulk-insert batching

## Problem

Two related bugs in `nyc-pulse update --source all`:

1. **311 statement timeout.** `upsert_events` (in `src/nyc_pulse/db.py`) loops `session.execute()` once per row inside a single transaction, then commits at the end. For a 90-day 311 pull (hundreds of thousands of rows) this is hundreds of thousands of round-trips through Supabase's transaction pooler (port 6543), which enforces a ~60s statement_timeout. The transaction is killed mid-loop.

2. **Cascade poisoning.** When step 1 raises, `cli.py update` catches the exception and prints a warning, but never calls `session.rollback()`. The shared `Session` stays in `InFailedSqlTransaction`, so every subsequent collector (`hpd_violations`, `restaurants`, …) fails with *"current transaction is aborted, commands ignored until end of transaction block."* That looks like five broken collectors when really only one is broken.

A prior fix (`a18194e`) added `rollback()` to the **signal scorers** for `block` reports, but the **`update` path** was never patched.

## Approach

Two surgical changes, both in the data layer / CLI — no schema changes.

### 1. `cli.py update`: rollback on collector failure

In the per-collector `except` block, call `session.rollback()` before logging the warning. Safe in both cases:

- If the failure happened during fetch (HTTP error before any SQL), rollback is a harmless no-op.
- If it happened mid-loop in `upsert_events`, rollback clears the aborted-tx state so the next collector starts clean.

### 2. `db.py upsert_events`: chunked bulk insert with per-chunk commit

Replace the per-row `for event in events: session.execute(statement, params)` + single final `commit()` with:

- Build a list of param dicts (no per-row execute).
- Process in chunks of **500 rows**.
- For each chunk: one `session.execute(statement, chunk_params_list)` call (SQLAlchemy turns this into psycopg2 `executemany`), followed by `session.commit()`.
- Track total `rowcount` across chunks; return the sum.

Engine config: also pass `executemany_mode="values_plus_batch"` to `create_engine`, which makes psycopg2 rewrite executemany of an `INSERT ... VALUES (...)` into multi-row `INSERT ... VALUES (...), (...), …` — a single SQL statement per chunk. Falls back gracefully on non-psycopg2 drivers.

**Why 500:** A multi-row INSERT of 500 rows of ~14 columns each fits well within Supabase's tx-pooler statement_timeout and PostgreSQL's parameter limit (32k). Chunking also lets partial progress survive a mid-run failure (earlier chunks are already committed).

### Why not switch to the session pooler (port 5432)?

That was the user's alt suggestion. Rejected because:

- The per-row loop is still O(N) round trips even without the timeout — ingest stays slow.
- It bakes pooler choice into CLI ergonomics; the project already has `DATABASE_URL_DIRECT` for that purpose and we shouldn't conflate the two.
- Chunked bulk insert fixes the root cause (too many round trips), not the symptom (timeout on tx pooler).

## Files touched

- `src/nyc_pulse/cli.py` — add `session.rollback()` to the per-collector `except` in `update`.
- `src/nyc_pulse/db.py` — refactor `upsert_events`; add `executemany_mode` to `create_engine`.
- `tests/test_upsert.py` — existing `FakeSession.execute` signature changes (param becomes `list[dict]`); update assertions.
- `tests/test_cli.py` — existing cascade test is a false negative because it mocks `upsert_events`; rewrite to use a `FakeSession` whose `execute` raises mid-stream so the rollback path is actually exercised.
- New: `tests/test_upsert_batching.py` — verify chunking + per-chunk commit.

## Database impact

**None.** Schema unchanged. The SQL statement is the same `INSERT ... ON CONFLICT (id) DO NOTHING` — only the parameter-passing pattern and chunk boundaries change. No migration needed; `SCHEMA.md` does not need updating.

## Rollout

- Local: `pytest -q` must pass (including the two new tests + the updated existing ones).
- Smoke: `nyc-pulse update --source 311 --days 7` should complete; `nyc-pulse update --source all --days 7` should run every collector to completion and report per-source counts.

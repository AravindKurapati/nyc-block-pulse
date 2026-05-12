"""upsert_events must chunk inserts and commit per chunk.

Issue: 311 returns hundreds of thousands of rows per 90-day pull. The previous
implementation looped session.execute() once per row inside one transaction
and committed at the end, exceeding Supabase's tx-pooler statement_timeout.

Fix: chunk rows into batches and pass each batch as a list to execute() so
SQLAlchemy/psycopg2 can emit a multi-row INSERT. Commit per chunk so partial
progress survives a mid-run failure.
"""
from __future__ import annotations

from nyc_pulse.db import upsert_events


class FakeResult:
    def __init__(self, rowcount):
        self.rowcount = rowcount


class BatchingFakeSession:
    """Records every execute call along with the size of the params batch.

    Supports both single-dict and list-of-dict params (executemany style).
    """

    def __init__(self):
        self.execute_calls: list[int] = []  # batch sizes
        self.commits = 0

    def execute(self, statement, params):
        if isinstance(params, list):
            self.execute_calls.append(len(params))
            return FakeResult(len(params))
        else:
            self.execute_calls.append(1)
            return FakeResult(1)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def _event(i: int) -> dict:
    return {
        "id": f"311_{i}",
        "source": "nyc_311",
        "event_type": "Noise",
        "occurred_at": "2026-05-01T00:00:00",
        "address": f"{i} MAIN ST",
        "bbl": None,
        "bin": None,
        "lat": 40.7,
        "lon": -73.9,
        "status": "Open",
        "category": "Loud Music",
        "summary": "Noise",
        "raw_json": {"unique_key": str(i)},
    }


def test_upsert_events_batches_rows_in_chunks():
    """1500 rows should produce 3 chunked execute calls of 500 each (not 1500)."""
    session = BatchingFakeSession()
    events = [_event(i) for i in range(1500)]

    inserted = upsert_events(session, events)

    assert inserted == 1500
    # Must be <<1500 round trips. Asserting <= 10 is generous and proves we
    # are NOT doing per-row execute.
    assert len(session.execute_calls) <= 10, (
        f"expected batched execute calls, got {len(session.execute_calls)} "
        f"(per-row execute is the bug)"
    )
    # Each batch is bounded — no single batch swallows everything (which could
    # exceed PostgreSQL parameter limits at high row counts).
    assert max(session.execute_calls) <= 1000


def test_upsert_events_commits_per_chunk():
    """Commits should occur per chunk so partial progress survives failures."""
    session = BatchingFakeSession()
    events = [_event(i) for i in range(1500)]

    upsert_events(session, events)

    # At least one commit per chunk (could be == number of chunks, or chunks+1
    # if there's a trailing commit; either is fine).
    assert session.commits >= len(session.execute_calls), (
        f"commits={session.commits} chunks={len(session.execute_calls)}: "
        f"must commit per chunk for crash-safety"
    )


def test_upsert_events_handles_empty_list():
    session = BatchingFakeSession()
    assert upsert_events(session, []) == 0
    assert session.execute_calls == []

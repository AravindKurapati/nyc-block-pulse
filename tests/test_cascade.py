"""Regression test for the update-command cascade bug.

When one collector's upsert raises (e.g. statement timeout), the shared session
is left in a failed-transaction state. The CLI must call session.rollback() in
the except block so subsequent collectors aren't poisoned.

The existing test_update_continues_when_one_collector_fails mocks upsert_events
entirely, so it never exercises the real session-state path. This test uses a
fake session whose execute() raises mid-stream the first time and records
whether rollback() was called before the next collector runs.
"""
from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from nyc_pulse.cli import app

runner = CliRunner()


class TrackingSession:
    """Simulates a SQLAlchemy session that goes into a failed-tx state.

    The first execute() raises (mimicking Supabase tx-pooler statement_timeout).
    After that, every execute() raises InFailedSqlTransaction until rollback()
    is called. We record the order of operations to assert rollback happens
    between collectors.
    """

    def __init__(self):
        self.in_failed_tx = False
        self.first_execute_done = False
        self.events: list[str] = []

    def execute(self, statement, params):
        self.events.append("execute")
        if self.in_failed_tx:
            raise RuntimeError("current transaction is aborted, commands ignored")
        if not self.first_execute_done:
            self.first_execute_done = True
            self.in_failed_tx = True
            raise RuntimeError("statement timeout exceeded")

        class R:
            rowcount = 1

        return R()

    def commit(self):
        self.events.append("commit")

    def rollback(self):
        self.events.append("rollback")
        self.in_failed_tx = False

    def close(self):
        self.events.append("close")


def test_update_rolls_back_session_after_collector_failure():
    session = TrackingSession()

    # Collectors each return one trivial event; the real db.upsert_events
    # will be called with the shared session above.
    def one_event(days=None):
        return [
            {
                "id": f"x_{days}",
                "source": "test",
                "event_type": "",
                "occurred_at": None,
                "address": "",
                "bbl": None,
                "bin": None,
                "lat": None,
                "lon": None,
                "status": None,
                "category": None,
                "summary": None,
                "raw_json": {},
            }
        ]

    with (
        patch("nyc_pulse.cli.collect_311", lambda days: one_event(days)),
        patch("nyc_pulse.cli.collect_dob_permits", lambda days: one_event(days)),
        patch("nyc_pulse.cli.collect_hpd_complaints", lambda days: one_event(days)),
        patch("nyc_pulse.cli.collect_hpd_violations", lambda days: one_event(days)),
        patch("nyc_pulse.cli.collect_restaurants", lambda days: one_event(days)),
        patch("nyc_pulse.cli.collect_liquor", lambda: one_event(0)),
        patch("nyc_pulse.cli.get_session", return_value=session),
    ):
        result = runner.invoke(app, ["update", "--source", "all"])

    assert result.exit_code == 0, result.output

    # Cascade-protection contract: after the first execute raises, a rollback
    # must happen before the next execute. Otherwise InFailedSqlTransaction
    # cascades across collectors.
    first_execute_idx = session.events.index("execute")
    assert "rollback" in session.events, (
        "session.rollback() was never called after the first collector failed — "
        "this is the cascade bug"
    )
    rollback_idx = session.events.index("rollback")
    later_executes = [
        i for i, e in enumerate(session.events) if e == "execute" and i > first_execute_idx
    ]
    assert later_executes, "no further execute() calls after the failure"
    assert rollback_idx < later_executes[0], (
        "rollback() happened too late — subsequent collectors ran on a poisoned session"
    )

from __future__ import annotations

import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from nyc_pulse.cli import app

runner = CliRunner()


def test_update_continues_when_one_collector_fails():
    calls = []

    def failing_311(days):
        raise RuntimeError("Socrata timeout")

    def ok_dob(days):
        calls.append("dob")
        return []

    with (
        patch("nyc_pulse.cli.collect_311", failing_311),
        patch("nyc_pulse.cli.collect_dob_permits", ok_dob),
        patch("nyc_pulse.cli.collect_hpd_complaints", lambda days: []),
        patch("nyc_pulse.cli.collect_hpd_violations", lambda days: []),
        patch("nyc_pulse.cli.collect_restaurants", lambda days: []),
        patch("nyc_pulse.cli.collect_liquor", lambda: []),
        patch("nyc_pulse.cli.get_session", return_value=MagicMock()),
        patch("nyc_pulse.cli.upsert_events", return_value=0),
    ):
        result = runner.invoke(app, ["update", "--source", "all"])

    assert "dob" in calls, "dob collector should have run despite 311 failure"
    assert result.exit_code == 0
    assert "311: skipped" in result.output
    assert "Socrata timeout" in result.output

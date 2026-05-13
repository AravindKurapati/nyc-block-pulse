from __future__ import annotations

import subprocess

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_session
from .state import DEFAULT_STATE_PATH, load_state

_KNOWN_SOURCES = [
    "dob_permits",
    "hpd_complaints",
    "hpd_violations",
    "nyc_311",
    "restaurants",
    "liquor",
]


def get_expected_sources(state_path=DEFAULT_STATE_PATH) -> list[str]:
    state = load_state(state_path)
    agent_sources = [
        v["signal_name"]
        for v in state.get("evaluated", {}).values()
        if v.get("status") == "approved" and "signal_name" in v
    ]
    return _KNOWN_SOURCES + agent_sources


def check_sources(session: Session, state_path=DEFAULT_STATE_PATH) -> list[str]:
    result = session.execute(
        text("""
            SELECT source, COUNT(*) AS new_rows
            FROM events
            WHERE ingested_at >= now() - interval '7 days'
            GROUP BY source
        """)
    )
    counts = {row.source: row.new_rows for row in result}
    dead = []
    for source in get_expected_sources(state_path):
        if counts.get(source, 0) == 0:
            dead.append(source)
    return dead


def _issue_already_open(source: str) -> bool:
    result = subprocess.run(
        ["gh", "issue", "list", "--label", "data-health", "--state", "open", "--json", "title"],
        capture_output=True,
        text=True,
    )
    return f"[monitor] {source}" in result.stdout


def create_health_issue(source: str) -> None:
    if _issue_already_open(source):
        return
    subprocess.run(
        [
            "gh", "issue", "create",
            "--title", f"[monitor] {source} has no new rows in 7 days",
            "--body", (
                f"Source `{source}` had 0 rows ingested in the last 7 days.\n\n"
                "Possible causes:\n"
                "- The upstream Socrata dataset was updated/retired\n"
                "- The collector is filtering too aggressively\n"
                "- The daily ingest job failed\n\n"
                "Check the collector file and the latest daily update workflow run."
            ),
            "--label", "data-health",
        ],
        check=False,
    )


def run_monitor(dry_run: bool = False) -> list[str]:
    session = get_session()
    try:
        dead = check_sources(session)
    finally:
        session.close()

    for source in dead:
        if dry_run:
            print(f"[dry-run] Would create issue for dead source: {source}")
        else:
            create_health_issue(source)
    return dead

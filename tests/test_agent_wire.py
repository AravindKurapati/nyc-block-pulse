from __future__ import annotations

import tempfile
from pathlib import Path


_FAKE_CLI = '''from .collectors.restaurants import collect_restaurants
from .collectors.liquor import collect_liquor

collectors = {
    "restaurants": collect_restaurants,
    "liquor": collect_liquor,
}

signals = {
    "restaurants": score_restaurants(lat, lon, radius, days, session=session),
    "fire": score_fire(lat, lon, radius, days, session=session),
}
'''

_FAKE_EVENTS = '''SignalName = Literal["construction", "fire"]

SIGNAL_SOURCES: dict[str, tuple[str, ...]] = {
    "construction": ("dob_permits",),
    "fire": ("fdny_fire",),
}
'''

_FAKE_BLOCK = '''from nyc_pulse.signals.fire import score_fire

signals = {
    "construction": score_construction(lat, lon, payload.radius_ft, payload.days, session=session),
    "fire": score_fire(lat, lon, payload.radius_ft, payload.days, session=session),
}
'''


def test_wire_cli_adds_collector_import_and_entry(tmp_path):
    from nyc_pulse.agent.wire import wire_cli

    cli_file = tmp_path / "cli.py"
    cli_file.write_text(_FAKE_CLI)

    wire_cli("noise", cli_file)
    content = cli_file.read_text()

    assert "from .collectors.noise import collect_noise" in content
    assert '"noise": collect_noise,' in content
    assert '"noise": score_noise(' in content


def test_wire_events_adds_signal_name_and_sources(tmp_path):
    from nyc_pulse.agent.wire import wire_events

    events_file = tmp_path / "events.py"
    events_file.write_text(_FAKE_EVENTS)

    wire_events("noise", "fhrw-4uyv", events_file)
    content = events_file.read_text()

    assert '"noise"' in content
    assert '"noise": ("noise",' in content


def test_wire_block_adds_import_and_signal(tmp_path):
    from nyc_pulse.agent.wire import wire_block

    block_file = tmp_path / "block.py"
    block_file.write_text(_FAKE_BLOCK)

    wire_block("noise", block_file)
    content = block_file.read_text()

    assert "from nyc_pulse.signals.noise import score_noise" in content
    assert '"noise": score_noise(' in content

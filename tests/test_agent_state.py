from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_state(tmp_path):
    p = tmp_path / "state.json"
    p.write_text('{"evaluated": {}}')
    return p


def test_load_returns_empty_evaluated_on_fresh_file(tmp_state):
    from nyc_pulse.agent.state import load_state
    state = load_state(tmp_state)
    assert state == {"evaluated": {}}


def test_save_and_reload(tmp_state):
    from nyc_pulse.agent.state import load_state, save_state
    state = load_state(tmp_state)
    state["evaluated"]["abc1-2345"] = {"status": "rejected", "score": 3}
    save_state(state, tmp_state)
    reloaded = load_state(tmp_state)
    assert reloaded["evaluated"]["abc1-2345"]["status"] == "rejected"


def test_is_evaluated_true_for_known_id(tmp_state):
    from nyc_pulse.agent.state import is_evaluated, load_state, save_state
    state = load_state(tmp_state)
    state["evaluated"]["xyz9-1234"] = {"status": "approved"}
    save_state(state, tmp_state)
    assert is_evaluated("xyz9-1234", tmp_state) is True


def test_is_evaluated_false_for_unknown_id(tmp_state):
    from nyc_pulse.agent.state import is_evaluated
    assert is_evaluated("brand-new1", tmp_state) is False

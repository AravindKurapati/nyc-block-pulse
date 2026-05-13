from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STATE_PATH = _REPO_ROOT / "agent" / "state.json"


def load_state(path: Path = DEFAULT_STATE_PATH) -> dict:
    if not path.exists():
        return {"evaluated": {}}
    return json.loads(path.read_text())


def save_state(state: dict, path: Path = DEFAULT_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def is_evaluated(dataset_id: str, path: Path = DEFAULT_STATE_PATH) -> bool:
    return dataset_id in load_state(path).get("evaluated", {})

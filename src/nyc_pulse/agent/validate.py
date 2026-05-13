from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def validate_generated(signal_name: str, files: dict[str, str]) -> bool:
    test_key = f"tests/test_agent_{signal_name}.py"
    collector_key = f"src/nyc_pulse/collectors/{signal_name}.py"
    scorer_key = f"src/nyc_pulse/signals/{signal_name}.py"

    if test_key not in files or collector_key not in files or scorer_key not in files:
        return False

    written: list[Path] = []
    passed = False
    try:
        for key in (collector_key, scorer_key, test_key):
            dest = _REPO_ROOT / key
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(files[key])
            written.append(dest)

        result = subprocess.run(
            ["python", "-m", "pytest", str(_REPO_ROOT / test_key), "-v", "--tb=short", "-x"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        passed = result.returncode == 0
    except Exception:
        passed = False
    finally:
        if not passed:
            for p in written:
                if p.exists():
                    p.unlink()
    return passed

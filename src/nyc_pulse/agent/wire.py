from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLI_PATH = _REPO_ROOT / "src" / "nyc_pulse" / "cli.py"
_EVENTS_PATH = _REPO_ROOT / "api" / "routes" / "events.py"
_BLOCK_PATH = _REPO_ROOT / "api" / "routes" / "block.py"


def _insert_after_import_block(content: str, import_pattern: str, import_line: str) -> str:
    if import_line in content:
        return content
    return re.sub(
        import_pattern,
        lambda m: m.group(0) + import_line + "\n",
        content,
        count=1,
        flags=re.MULTILINE,
    )


def _append_dict_entry(content: str, dict_name: str, entry: str) -> str:
    if entry in content:
        return content

    pattern = re.compile(
        rf"(?ms)(?P<start>^(?P<indent>\s*){re.escape(dict_name)}(?:\s*:[^=]+)?\s*=\s*\{{)"
        rf"(?P<body>.*?)"
        rf"(?P<end>^\s*\}})"
    )

    def replace(match: re.Match[str]) -> str:
        indent = match.group("indent") + "    "
        body = match.group("body")
        separator = "" if body.endswith("\n") else "\n"
        return f"{match.group('start')}{body}{separator}{indent}{entry}\n{match.group('end')}"

    return pattern.sub(replace, content, count=1)


def wire_cli(signal_name: str, cli_path: Path = _CLI_PATH) -> None:
    content = cli_path.read_text()

    import_line = f"from .collectors.{signal_name} import collect_{signal_name}"
    content = _insert_after_import_block(
        content,
        r"(?:^from \.collectors\.\w+ import collect_\w+\n)+",
        import_line,
    )

    collector_entry = f'"{signal_name}": collect_{signal_name},'
    content = _append_dict_entry(content, "collectors", collector_entry)

    scorer_import = f"    from .signals.{signal_name} import score_{signal_name}"
    content = _insert_after_import_block(
        content,
        r"(?:^    from \.signals\.\w+ import score_\w+\n)+",
        scorer_import,
    )

    signal_entry = f'"{signal_name}": score_{signal_name}(loc["lat"], loc["lon"], radius, days, session=session),'
    content = _append_dict_entry(content, "signals", signal_entry)

    cli_path.write_text(content)


def wire_events(signal_name: str, dataset_id: str, events_path: Path = _EVENTS_PATH) -> None:
    content = events_path.read_text()

    literal_pattern = re.compile(r'(SignalName\s*=\s*Literal\[)(?P<body>[^\]]*)(\])', re.DOTALL)

    def add_literal(match: re.Match[str]) -> str:
        body = match.group("body")
        if f'"{signal_name}"' in body:
            return match.group(0)
        separator = ", " if body.strip() else ""
        return f'{match.group(1)}{body.rstrip()}{separator}"{signal_name}"{match.group(3)}'

    content = literal_pattern.sub(add_literal, content, count=1)

    source_entry = f'"{signal_name}": ("{signal_name}",),'
    content = _append_dict_entry(content, "SIGNAL_SOURCES", source_entry)

    events_path.write_text(content)


def wire_block(signal_name: str, block_path: Path = _BLOCK_PATH) -> None:
    content = block_path.read_text()

    import_line = f"from nyc_pulse.signals.{signal_name} import score_{signal_name}"
    content = _insert_after_import_block(
        content,
        r"(?:^from nyc_pulse\.signals\.\w+ import score_\w+\n)+",
        import_line,
    )

    signal_entry = f'"{signal_name}": score_{signal_name}(lat, lon, payload.radius_ft, payload.days, session=session),'
    content = _append_dict_entry(content, "signals", signal_entry)

    block_path.write_text(content)


def wire_all(signal_name: str, dataset_id: str) -> None:
    wire_cli(signal_name)
    wire_events(signal_name, dataset_id)
    wire_block(signal_name)

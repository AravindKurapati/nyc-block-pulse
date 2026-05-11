from __future__ import annotations

from datetime import datetime, timezone


def render_report(query: str, loc: dict, signals: dict, window_days: int) -> str:
    lines = [
        f"# Block Report: {query}",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ",
        f"**Window:** last {window_days} days  ",
        "**Data as of:** NYC Open Data / NY State Open Data, subject to source update lag  ",
        f"**Location:** {loc['lat']:.5f}, {loc['lon']:.5f}  ",
        "",
    ]
    for signal_type, result in signals.items():
        lines.extend(
            [
                f"## {signal_type.replace('_', ' ').title()}",
                f"**Score:** {result['score']} ({result['count']} events)",
                "",
                "**Evidence:**",
            ]
        )
        signal_evidence = result.get("evidence", [])[:5]
        if not signal_evidence:
            lines.append("- No nearby evidence found in this window.")
        for item in signal_evidence:
            date = (item.get("date") or "")[:10] or "unknown date"
            source = item.get("source") or "source"
            summary = item.get("summary") or item.get("id") or "event"
            lines.append(f"- {date} [{source}] {summary}")
        lines.append("")
    return "\n".join(lines)


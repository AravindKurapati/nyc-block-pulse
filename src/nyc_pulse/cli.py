from __future__ import annotations

import subprocess

import typer
from rich.console import Console
from rich.markdown import Markdown

app = typer.Typer()
console = Console()


@app.command("init")
def init() -> None:
    """Run alembic migrations to set up the database."""
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    console.print("[green]Database ready.[/green]")


@app.command("update")
def update(
    days: int = typer.Option(7, help="Lookback window in days"),
    source: str = typer.Option(
        "all",
        help="Source to update: all|311|dob|hpd|hpd_violations|restaurants|liquor",
    ),
) -> None:
    """Pull recent records from public datasets into Postgres."""
    from .collectors.dob_permits import collect_dob_permits
    from .collectors.hpd_complaints import collect_hpd_complaints
    from .collectors.hpd_violations import collect_hpd_violations
    from .collectors.liquor import collect_liquor
    from .collectors.nyc_311 import collect_311
    from .collectors.restaurants import collect_restaurants
    from .db import get_session, upsert_events

    collectors = {
        "311": collect_311,
        "dob": collect_dob_permits,
        "hpd": collect_hpd_complaints,
        "hpd_violations": collect_hpd_violations,
        "restaurants": collect_restaurants,
        "liquor": collect_liquor,
    }
    source_key = source.lower().replace("-", "_")
    if source_key != "all" and source_key not in collectors:
        console.print(f"[red]Unknown source:[/red] {source}")
        raise typer.Exit(1)

    targets = collectors if source_key == "all" else {source_key: collectors[source_key]}
    session = get_session()
    try:
        for name, collector in targets.items():
            with console.status(f"Fetching {name}..."):
                events = collector(days=days) if name != "liquor" else collector()
            inserted = upsert_events(session, events)
            console.print(f"[cyan]{name}:[/cyan] {len(events)} fetched, {inserted} new rows")
    finally:
        session.close()


@app.command("block")
def block_report(
    query: str = typer.Argument(..., help="Address or intersection, e.g. 'Ludlow St & Rivington St'"),
    days: int = typer.Option(90),
    radius: int = typer.Option(500, help="Radius in feet"),
) -> None:
    """Generate a block report for an address or intersection."""
    from .normalize.address import resolve_address
    from .reports.block_report import render_report
    from .signals.construction import score_construction
    from .signals.housing import score_housing
    from .signals.nightlife import score_nightlife
    from .signals.quality_of_life import score_quality_of_life
    from .signals.restaurants import score_restaurants

    with console.status("Resolving location..."):
        loc = resolve_address(query)
    if not loc:
        console.print("[red]Could not resolve location. Check the query and NYC Geoclient credentials.[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]Resolved: {loc['lat']:.5f}, {loc['lon']:.5f}[/dim]")

    with console.status("Scoring signals..."):
        signals = {
            "construction": score_construction(loc["lat"], loc["lon"], radius, days),
            "nightlife": score_nightlife(loc["lat"], loc["lon"], radius, days),
            "housing": score_housing(loc["lat"], loc["lon"], radius, days),
            "restaurants": score_restaurants(loc["lat"], loc["lon"], radius, days),
            "quality_of_life": score_quality_of_life(loc["lat"], loc["lon"], radius, days),
        }

    report = render_report(query, loc, signals, days)
    console.print(Markdown(report))


if __name__ == "__main__":
    app()

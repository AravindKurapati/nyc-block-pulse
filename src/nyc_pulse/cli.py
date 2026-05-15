from __future__ import annotations

import subprocess

import typer
from rich.console import Console
from rich.markdown import Markdown

from .collectors.dob_permits import collect_dob_permits
from .collectors.census_acs import DEFAULT_ACS_YEAR, collect_block_demographics
from .collectors.hpd_complaints import collect_hpd_complaints
from .collectors.hpd_violations import collect_hpd_violations
from .collectors.liquor import collect_liquor
from .collectors.nyc_311 import collect_311
from .collectors.restaurants import collect_restaurants
from .config import settings
from .db import get_session, upsert_demographics, upsert_events

app = typer.Typer()
agent_app = typer.Typer(help="Autonomous dataset discovery and monitoring.")
app.add_typer(agent_app, name="agent")
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
            try:
                with console.status(f"Fetching {name}..."):
                    events = collector(days=days) if name != "liquor" else collector()
                inserted = upsert_events(session, events)
                console.print(f"[cyan]{name}:[/cyan] {len(events)} fetched, {inserted} new rows")
            except Exception as exc:
                session.rollback()
                console.print(f"[yellow]{name}: skipped — {exc}[/yellow]")
    finally:
        session.close()


@app.command("update-demographics")
def update_demographics(
    year: int = typer.Option(DEFAULT_ACS_YEAR, help="ACS 5-year estimate year"),
    comparison_year: int | None = typer.Option(None, help="Prior ACS year for density_change"),
) -> None:
    """Pull Census ACS tract demographics and TIGERweb tract polygons."""
    session = get_session()
    try:
        with console.status(f"Fetching ACS {year} demographics..."):
            rows = collect_block_demographics(year=year, comparison_year=comparison_year)
        inserted = upsert_demographics(session, rows)
        console.print(f"[cyan]demographics:[/cyan] {len(rows)} fetched, {inserted} upserted")
    except Exception:
        session.rollback()
        raise
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
    from .signals.demographics import score_density_change
    from .signals.housing import score_housing
    from .signals.nightlife import score_nightlife
    from .signals.quality_of_life import score_quality_of_life
    from .signals.restaurants import score_restaurants

    with console.status("Resolving location..."):
        loc = resolve_address(query)
    if not loc:
        if not settings.nyc_geoclient_app_id or not settings.nyc_geoclient_app_key:
            console.print("[red]NYC Geoclient credentials not set. Add NYC_GEOCLIENT_APP_ID and NYC_GEOCLIENT_APP_KEY to .env[/red]")
        else:
            console.print("[red]Could not resolve location. Check the address format (e.g. '123 Main St, Brooklyn' or 'Ludlow St & Rivington St').[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]Resolved: {loc['lat']:.5f}, {loc['lon']:.5f}[/dim]")

    session = get_session()
    try:
        with console.status("Scoring signals..."):
            signals = {
                "construction": score_construction(loc["lat"], loc["lon"], radius, days, session=session),
                "nightlife": score_nightlife(loc["lat"], loc["lon"], radius, days, session=session),
                "housing": score_housing(loc["lat"], loc["lon"], radius, days, session=session),
                "restaurants": score_restaurants(loc["lat"], loc["lon"], radius, days, session=session),
                "quality_of_life": score_quality_of_life(loc["lat"], loc["lon"], radius, days, session=session),
                "density_change": score_density_change(loc["lat"], loc["lon"], radius, days, session=session),
            }
    finally:
        session.close()

    report = render_report(query, loc, signals, days)
    console.print(Markdown(report))


@agent_app.command("discover")
def agent_discover(
    dry_run: bool = typer.Option(False, "--dry-run", help="Run all steps except git/PR operations."),
) -> None:
    """Scan NYC Open Data catalog, evaluate datasets, generate collectors, open PRs."""
    from .agent.catalog import fetch_candidates
    from .agent.codegen import generate_files
    from .agent.evaluate import evaluate_dataset
    from .agent.pr import create_pr
    from .agent.state import load_state, save_state
    from .agent.validate import validate_generated
    from .agent.wire import wire_all

    state = load_state()
    already_evaluated = set(state["evaluated"].keys())

    console.print(f"[cyan]Fetching catalog candidates (skipping {len(already_evaluated)} known IDs)...[/cyan]")
    candidates = fetch_candidates(already_evaluated)
    console.print(f"[cyan]Found {len(candidates)} pre-filtered candidates.[/cyan]")

    for candidate in candidates:
        dataset_id = candidate["id"]
        console.print(f"\n[dim]Evaluating {dataset_id}: {candidate['name'][:60]}[/dim]")

        eval_result = evaluate_dataset(candidate)
        if eval_result is None:
            state["evaluated"][dataset_id] = {"status": "rejected", "score": 0, "rationale": "parse_failure"}
            save_state(state)
            console.print("  [red]Parse failure - skipping.[/red]")
            continue

        if eval_result["score"] < 7:
            state["evaluated"][dataset_id] = {
                "status": "rejected",
                "score": eval_result["score"],
                "rationale": eval_result["rationale"],
            }
            save_state(state)
            console.print(f"  [yellow]Rejected (score {eval_result['score']}/10): {eval_result['rationale']}[/yellow]")
            continue

        console.print(f"  [green]Score {eval_result['score']}/10 - {eval_result['signal_name']}[/green]")
        console.print("  Generating code...")
        files = generate_files(eval_result)
        if not files:
            state["evaluated"][dataset_id] = {"status": "codegen_failed", "score": eval_result["score"]}
            save_state(state)
            console.print("  [red]Code generation failed.[/red]")
            continue

        console.print("  Validating generated tests...")
        passed = validate_generated(eval_result["signal_name"], files)
        if not passed:
            state["evaluated"][dataset_id] = {
                "status": "validation_failed",
                "score": eval_result["score"],
                "signal_name": eval_result["signal_name"],
            }
            save_state(state)
            console.print("  [red]Validation failed - skipping PR.[/red]")
            continue

        if not dry_run:
            wire_all(eval_result["signal_name"], dataset_id)

        pr_url = create_pr(eval_result["signal_name"], dataset_id, eval_result, files, dry_run=dry_run)
        state["evaluated"][dataset_id] = {
            "status": "approved",
            "score": eval_result["score"],
            "signal_name": eval_result["signal_name"],
            "pr": pr_url,
        }
        save_state(state)
        console.print(f"  [green]PR opened: {pr_url or '(dry-run)'}[/green]")

    if not dry_run:
        import subprocess
        subprocess.run(["git", "push", "origin", "HEAD:master"], capture_output=True)

    console.print("\n[green]Done.[/green]")


@agent_app.command("monitor")
def agent_monitor(
    dry_run: bool = typer.Option(False, "--dry-run", help="Print issues without creating them."),
) -> None:
    """Check data source health and open GitHub issues for dead sources."""
    from .agent.monitor import run_monitor

    dead = run_monitor(dry_run=dry_run)
    if dead:
        console.print(f"[yellow]Dead sources: {', '.join(dead)}[/yellow]")
    else:
        console.print("[green]All sources healthy.[/green]")


if __name__ == "__main__":
    app()

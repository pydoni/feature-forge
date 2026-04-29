"""feature-forge CLI application."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from feature_forge import __version__

app = typer.Typer(
    name="feature-forge",
    help="Lightweight feature store for small and medium teams.",
    no_args_is_help=True,
)
console = Console()


def _resolve_repo(repo: str | None) -> Path:
    path = Path(repo) if repo else Path.cwd()
    if not path.is_dir():
        console.print(f"[red]Error:[/red] '{path}' is not a directory")
        raise typer.Exit(1)
    return path


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"feature-forge {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit",
        callback=_version_callback, is_eager=True,
    ),
) -> None:
    pass


@app.command()
def init(
    path: str = typer.Argument(".", help="Directory to initialize the feature repo in"),
) -> None:
    """Create a new feature repo with scaffold YAML files."""
    repo = Path(path)
    repo.mkdir(parents=True, exist_ok=True)

    entities_yml = repo / "entities.yml"
    sources_yml = repo / "sources.yml"
    features_yml = repo / "features.yml"

    if entities_yml.exists() or sources_yml.exists() or features_yml.exists():
        console.print(
            "[yellow]Warning:[/yellow] YAML files already exist in this directory. "
            "Skipping existing files."
        )

    if not entities_yml.exists():
        entities_yml.write_text(
            "entities:\n"
            "  - name: customer\n"
            "    join_keys:\n"
            "      - customer_id\n"
            '    description: "A customer entity"\n'
        )

    if not sources_yml.exists():
        sources_yml.write_text(
            "sources:\n"
            "  - name: transactions\n"
            "    backend: parquet\n"
            "    path: data/transactions.parquet\n"
            "    entity: customer\n"
            "    timestamp_column: event_timestamp\n"
            "    columns:\n"
            "      - { name: customer_id, dtype: int64 }\n"
            "      - { name: amount, dtype: float64 }\n"
            "      - { name: event_timestamp, dtype: timestamp }\n"
        )

    if not features_yml.exists():
        features_yml.write_text(
            "feature_views:\n"
            "  - name: customer_features\n"
            "    entity: customer\n"
            "    source: transactions\n"
            "    features:\n"
            "      - name: transaction_count_7d\n"
            "        dtype: int64\n"
            '        description: "Transactions in the last 7 days"\n'
            "        aggregation:\n"
            "          function: count\n"
            "          column: amount\n"
            "          window: 7d\n"
        )

    console.print(f"[green]Initialized feature repo at {repo.resolve()}[/green]")
    console.print("  entities.yml")
    console.print("  sources.yml")
    console.print("  features.yml")
    console.print("\nEdit these files to define your features, then run:")
    console.print("  [bold]feature-forge validate[/bold]")


@app.command()
def validate(
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="Path to feature repo"),
) -> None:
    """Validate the feature registry (schema, cross-references, sources)."""
    from feature_forge.registry.loader import load_registry
    from feature_forge.registry.validator import validate_registry

    repo_path = _resolve_repo(repo)

    try:
        registry = load_registry(repo_path)
    except Exception as e:
        console.print(f"[red]Error loading registry:[/red] {e}")
        raise typer.Exit(1)

    result = validate_registry(registry, str(repo_path))

    if result.is_valid:
        console.print("[green]Registry is valid.[/green]")
        warnings = [i for i in result.issues if i.level == "warning"]
        if warnings:
            console.print(f"\n[yellow]{len(warnings)} warning(s):[/yellow]")
            for w in warnings:
                console.print(f"  [{w.source_name}] {w.message}")
    else:
        errors = [i for i in result.issues if i.level == "error"]
        warnings = [i for i in result.issues if i.level == "warning"]
        console.print(f"[red]{len(errors)} error(s) found:[/red]")
        for e in errors:
            console.print(f"  [red]ERROR[/red] [{e.source_name}] {e.message}")
        if warnings:
            console.print(f"\n[yellow]{len(warnings)} warning(s):[/yellow]")
            for w in warnings:
                console.print(f"  [yellow]WARN[/yellow] [{w.source_name}] {w.message}")
        raise typer.Exit(1)


@app.command(name="list")
def list_items(
    kind: str = typer.Argument(
        ..., help="What to list: entities, sources, or features"
    ),
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="Path to feature repo"),
) -> None:
    """List registered entities, sources, or feature views."""
    from feature_forge.registry.loader import load_registry

    repo_path = _resolve_repo(repo)

    try:
        registry = load_registry(repo_path)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if kind == "entities":
        table = Table(title="Entities")
        table.add_column("Name", style="cyan")
        table.add_column("Join Keys")
        table.add_column("Description")
        for entity in registry.entities:
            table.add_row(entity.name, ", ".join(entity.join_keys), entity.description)
        console.print(table)

    elif kind == "sources":
        table = Table(title="Sources")
        table.add_column("Name", style="cyan")
        table.add_column("Backend")
        table.add_column("Entity")
        table.add_column("Columns", justify="right")
        for source in registry.sources:
            table.add_row(
                source.name,
                source.backend.value,
                source.entity,
                str(len(source.columns)),
            )
        console.print(table)

    elif kind == "features":
        table = Table(title="Feature Views")
        table.add_column("Name", style="cyan")
        table.add_column("Entity")
        table.add_column("Source")
        table.add_column("Features", justify="right")
        for fv in registry.feature_views:
            table.add_row(fv.name, fv.entity, fv.source, str(len(fv.features)))
        console.print(table)

    else:
        console.print(
            f"[red]Unknown kind '{kind}'. Use: entities, sources, or features[/red]"
        )
        raise typer.Exit(1)


@app.command()
def describe(
    feature_view: str = typer.Argument(..., help="Name of the feature view to describe"),
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="Path to feature repo"),
) -> None:
    """Show detailed info about a feature view."""
    from feature_forge.registry.loader import load_registry

    repo_path = _resolve_repo(repo)

    try:
        registry = load_registry(repo_path)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    fv = registry.get_feature_view(feature_view)
    if fv is None:
        console.print(f"[red]Feature view '{feature_view}' not found[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]{fv.name}[/bold]")
    console.print(f"  Entity: {fv.entity}")
    console.print(f"  Source: {fv.source}")
    if fv.timestamp_column:
        console.print(f"  Timestamp: {fv.timestamp_column}")

    table = Table(title="Features")
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("Mode")
    table.add_column("Detail")
    table.add_column("Description")

    for f in fv.features:
        if f.column:
            mode = "passthrough"
            detail = f"column={f.column}"
        elif f.aggregation:
            mode = "aggregation"
            detail = f"{f.aggregation.function}({f.aggregation.column}, {f.aggregation.window})"
        else:
            mode = "?"
            detail = ""
        table.add_row(f.name, f.dtype.value, mode, detail, f.description)

    console.print(table)


@app.command()
def materialize(
    feature_view: str = typer.Argument(..., help="Feature view to materialize"),
    start: str = typer.Option(..., "--start", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option(..., "--end", help="End date (YYYY-MM-DD)"),
    entity_key: str = typer.Option(
        ..., "--entity-key", help="Entity key name (e.g. customer_id)"
    ),
    entity_values: str = typer.Option(
        ..., "--entity-values", help="Comma-separated entity values"
    ),
    interval: str = typer.Option("1d", "--interval", help="Time interval (e.g. 1d, 7d, 1h)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output Parquet path"),
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="Path to feature repo"),
    engine: str = typer.Option("duckdb", "--engine", help="Query engine (duckdb or spark)"),
) -> None:
    """Materialize a feature view to a Parquet file."""
    from feature_forge.sdk.store import FeatureStore

    repo_path = _resolve_repo(repo)

    # Parse entity values
    values = [v.strip() for v in entity_values.split(",")]
    # Try to parse as int
    try:
        parsed_values = [int(v) for v in values]
    except ValueError:
        parsed_values = values

    try:
        with FeatureStore(repo_path, engine=engine) as store:
            output_path = store.materialize(
                feature_views=[feature_view],
                entity_ids={entity_key: parsed_values},
                start_date=start,
                end_date=end,
                interval=interval,
                output_path=output,
            )
        console.print(f"[green]Materialized to {output_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

"""CLI entry point for swagger-loadgen."""

from __future__ import annotations

import asyncio
import sys
from typing import Annotated

import typer
from rich.console import Console

from swagger_loadgen.config import load_config
from swagger_loadgen.parser import SpecSource, parse_spec, parse_swagger_config
from swagger_loadgen.reporter import print_summary, stream_results
from swagger_loadgen.runner import RequestResult, run_load

app = typer.Typer(
    name="swagger-loadgen",
    help="Load generator driven by OpenAPI/Swagger specs.",
    no_args_is_help=True,
)
console = Console()


def _parse_header(raw: str) -> tuple[str, str]:
    """Parse 'Key: Value' header string."""
    if ":" not in raw:
        console.print(
            f"[red]Invalid header format (expected 'Key: Value'): {raw}[/red]"
        )
        raise typer.Exit(1)
    key, _, value = raw.partition(":")
    return key.strip(), value.strip()


def _parse_definition_filters(raw: list[str]) -> set[str]:
    """Parse definition filters from repeatable/comma-separated CLI inputs."""
    parsed: set[str] = set()
    for item in raw:
        for name in item.split(","):
            stripped = name.strip()
            if stripped:
                parsed.add(stripped)
    return parsed


def _deduplicate_sources(sources: list[SpecSource]) -> list[SpecSource]:
    """Deduplicate source list while preserving order."""
    seen: set[tuple[str, str]] = set()
    result: list[SpecSource] = []
    for src in sources:
        key = (src.name, src.url)
        if key in seen:
            continue
        seen.add(key)
        result.append(src)
    return result


async def _run(
    url: str | None,
    url_name: str,
    swagger_config_url: str | None,
    raw_definitions: list[str],
    tps: float,
    duration: float,
    config_path: str | None,
    raw_headers: list[str],
    base_url: str | None,
) -> None:
    """Async orchestrator: parse → filter → run → report."""
    # Load config
    cfg = load_config(config_path)

    # Merge CLI headers into config headers
    for raw in raw_headers:
        k, v = _parse_header(raw)
        cfg.headers[k] = v

    sources: list[SpecSource] = []
    if url:
        sources.append(SpecSource(name=url_name, url=url))

    if swagger_config_url:
        console.print(f"[bold]Fetching swagger config:[/bold] {swagger_config_url}")
        try:
            sources.extend(parse_swagger_config(swagger_config_url))
        except Exception as exc:
            console.print(f"[red]Failed to parse swagger config: {exc}[/red]")
            raise typer.Exit(1) from exc

    sources = _deduplicate_sources(sources)
    definition_filters = _parse_definition_filters(raw_definitions)
    if definition_filters:
        filtered = [src for src in sources if src.name in definition_filters]
        if not filtered:
            available = ", ".join(src.name for src in sources) or "(none)"
            console.print(
                "[red]No matching definitions found.[/red] "
                f"Requested: {', '.join(sorted(definition_filters))} / "
                f"Available: {available}"
            )
            raise typer.Exit(1)
        sources = filtered

    # Parse specs (multi source)
    endpoints = []
    failed_sources: list[tuple[str, str]] = []
    for source in sources:
        console.print(f"[bold]Fetching spec:[/bold] [{source.name}] {source.url}")
        try:
            parsed = parse_spec(
                source.url,
                base_url_override=base_url,
                source_name=source.name,
            )
        except Exception as exc:
            failed_sources.append((source.name, str(exc)))
            continue
        endpoints.extend(parsed)

    if failed_sources:
        console.print("[yellow]Some specs failed and were skipped:[/yellow]")
        for source_name, reason in failed_sources:
            console.print(f"  - [{source_name}] {reason}")

    if not endpoints:
        if failed_sources:
            console.print(
                "[red]No runnable GET endpoints after parsing failures.[/red]"
            )
            raise typer.Exit(1)
        console.print("[yellow]No GET endpoints found in sources.[/yellow]")
        raise typer.Exit(0)

    # Filter
    endpoints = cfg.filter_endpoints(endpoints)
    if not endpoints:
        console.print("[yellow]All endpoints filtered out by config.[/yellow]")
        raise typer.Exit(0)

    console.print(f"[bold]Endpoints:[/bold] {len(endpoints)} GET paths")
    for ep in endpoints:
        console.print(f"  [{ep.source_name}] {ep.path}")
    console.print(f"[bold]TPS:[/bold] {tps}  [bold]Duration:[/bold] {duration}s")
    console.rule()

    # Run with streaming output
    queue: asyncio.Queue[RequestResult] = asyncio.Queue()
    streamer = asyncio.create_task(stream_results(queue))

    stats = await run_load(
        endpoints=endpoints,
        tps=tps,
        duration=duration,
        headers=cfg.headers or None,
        param_values=cfg.params or None,
        on_result=queue,
    )

    # Drain remaining items and stop streamer
    await queue.join()
    streamer.cancel()

    print_summary(stats)


@app.command()
def main(
    url: Annotated[
        str | None,
        typer.Option("--url", help="OpenAPI/Swagger spec URL (single source)"),
    ] = None,
    url_name: Annotated[
        str,
        typer.Option(
            "--url-name",
            help="Logical definition name to use with --url",
        ),
    ] = "single",
    swagger_config_url: Annotated[
        str | None,
        typer.Option(
            "--swagger-config-url",
            help="Swagger UI config URL that contains multiple definitions",
        ),
    ] = None,
    definition: Annotated[
        list[str] | None,
        typer.Option(
            "--definition",
            "-d",
            help="Definition filter (repeatable or comma-separated)",
        ),
    ] = None,
    tps: Annotated[float, typer.Option("--tps", help="Requests per second")] = 1.0,
    duration: Annotated[
        float, typer.Option("--duration", help="Test duration in seconds")
    ] = 30.0,
    config: Annotated[
        str | None, typer.Option("--config", help="YAML config file path")
    ] = None,
    header: Annotated[
        list[str] | None,
        typer.Option("--header", help="HTTP header (repeatable, 'Key: Value')"),
    ] = None,
    base_url: Annotated[
        str | None,
        typer.Option("--base-url", help="Override base URL from spec"),
    ] = None,
) -> None:
    """Parse OpenAPI sources and fire GET requests at a fixed TPS."""
    if url is None and swagger_config_url is None:
        console.print("[red]Either --url or --swagger-config-url is required.[/red]")
        raise typer.Exit(1)

    try:
        asyncio.run(
            _run(
                url=url,
                url_name=url_name,
                swagger_config_url=swagger_config_url,
                raw_definitions=definition or [],
                tps=tps,
                duration=duration,
                config_path=config,
                raw_headers=header or [],
                base_url=base_url,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(130)

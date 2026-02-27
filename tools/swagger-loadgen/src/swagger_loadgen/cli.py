"""CLI entry point for swagger-loadgen."""

from __future__ import annotations

import asyncio
import sys
from typing import Annotated

import typer
from rich.console import Console

from swagger_loadgen.config import load_config
from swagger_loadgen.parser import parse_spec
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


async def _run(
    url: str,
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

    # Parse spec
    console.print(f"[bold]Fetching spec:[/bold] {url}")
    try:
        endpoints = parse_spec(url, base_url_override=base_url)
    except Exception as exc:
        console.print(f"[red]Failed to parse spec: {exc}[/red]")
        raise typer.Exit(1) from exc

    if not endpoints:
        console.print("[yellow]No GET endpoints found in spec.[/yellow]")
        raise typer.Exit(0)

    # Filter
    endpoints = cfg.filter_endpoints(endpoints)
    if not endpoints:
        console.print("[yellow]All endpoints filtered out by config.[/yellow]")
        raise typer.Exit(0)

    console.print(f"[bold]Endpoints:[/bold] {len(endpoints)} GET paths")
    for ep in endpoints:
        console.print(f"  {ep.path}")
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
    url: Annotated[str, typer.Option("--url", help="OpenAPI/Swagger spec URL")],
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
    """Parse an OpenAPI spec and fire GET requests at a fixed TPS."""
    try:
        asyncio.run(_run(url, tps, duration, config, header or [], base_url))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(130)

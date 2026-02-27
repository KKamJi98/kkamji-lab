"""Real-time console output and summary statistics."""

from __future__ import annotations

import asyncio
import statistics
from collections import defaultdict

from rich.console import Console
from rich.table import Table

from swagger_loadgen.runner import RequestResult, RunStats

console = Console()


async def stream_results(queue: asyncio.Queue[RequestResult]) -> None:
    """Print each request result as it arrives."""
    while True:
        result = await queue.get()
        if result.error:
            console.print(
                f"  GET {result.path}  [red]{result.error}[/red]  "
                f"{result.latency_ms:.0f}ms"
            )
        else:
            color = "green" if result.status < 400 else "yellow"
            console.print(
                f"  GET {result.path}  [{color}]{result.status}[/{color}]  "
                f"{result.latency_ms:.0f}ms"
            )
        queue.task_done()


def _percentile(data: list[float], pct: float) -> float:
    """Calculate percentile from sorted data."""
    if not data:
        return 0.0
    k = (len(data) - 1) * (pct / 100)
    f = int(k)
    c = f + 1
    if c >= len(data):
        return data[f]
    return data[f] + (k - f) * (data[c] - data[f])


def print_summary(stats: RunStats) -> None:
    """Print final summary table with latency percentiles and per-endpoint stats."""
    if not stats.results:
        console.print("\n[yellow]No requests were made.[/yellow]")
        return

    latencies = sorted(r.latency_ms for r in stats.results)
    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)

    console.print()
    console.rule("[bold]Summary")

    overview = Table(show_header=False, box=None, padding=(0, 2))
    overview.add_row("Total requests", str(stats.total))
    overview.add_row("Success", f"[green]{stats.success_count}[/green]")
    overview.add_row("Failure", f"[red]{stats.failure_count}[/red]")
    overview.add_row(
        "Success rate",
        f"{stats.success_count / stats.total * 100:.1f}%",
    )
    overview.add_row("p50 latency", f"{p50:.1f}ms")
    overview.add_row("p95 latency", f"{p95:.1f}ms")
    overview.add_row("p99 latency", f"{p99:.1f}ms")
    console.print(overview)

    # Per-endpoint breakdown
    by_path: dict[str, list[RequestResult]] = defaultdict(list)
    for r in stats.results:
        by_path[r.path].append(r)

    if len(by_path) > 1:
        console.print()
        ep_table = Table(title="Per-Endpoint Stats")
        ep_table.add_column("Path")
        ep_table.add_column("Count", justify="right")
        ep_table.add_column("Success %", justify="right")
        ep_table.add_column("Avg (ms)", justify="right")
        ep_table.add_column("p95 (ms)", justify="right")

        for path, results in sorted(by_path.items()):
            count = len(results)
            ok = sum(1 for r in results if r.error is None and r.status < 400)
            lats = sorted(r.latency_ms for r in results)
            avg = statistics.mean(lats) if lats else 0
            ep_p95 = _percentile(lats, 95)
            ep_table.add_row(
                path,
                str(count),
                f"{ok / count * 100:.0f}%",
                f"{avg:.1f}",
                f"{ep_p95:.1f}",
            )

        console.print(ep_table)

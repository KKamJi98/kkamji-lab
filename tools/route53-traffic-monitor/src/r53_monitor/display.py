"""Rich Live 실시간 대시보드 모듈."""

from __future__ import annotations

import asyncio

from rich.console import Group
from rich.live import Live
from rich.table import Table
from rich.text import Text

from .aws import WeightedRecord
from .stats import Stats, StatsSnapshot

BAR_WIDTH = 25


def _format_duration(seconds: float) -> str:
    """초를 MM:SS 형식으로 변환."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _make_bar(ratio: float, width: int = BAR_WIDTH) -> str:
    """비율에 따른 바 차트 문자열."""
    filled = int(ratio * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def build_dashboard(
    record_name: str,
    records: list[WeightedRecord],
    snapshot: StatsSnapshot,
) -> Group:
    """대시보드 레이아웃을 구성한다."""
    total_weight = sum(r.weight for r in records)

    # 제목
    title = Text(
        f"\n\U0001f680 Route53 Weighted Traffic Monitor \u2014 {record_name}", style="bold"
    )

    separator = Text("\u2501" * 64, style="dim")

    # Route53 설정 테이블
    weight_table = Table(
        title="\U0001f4cb Route53 Configured Weights",
        show_header=True,
        header_style="bold",
        padding=(0, 1),
    )
    weight_table.add_column("SetIdentifier", style="cyan")
    weight_table.add_column("Weight", justify="right")
    weight_table.add_column("Ratio", justify="right")

    weight_ratios: dict[str, float] = {}
    for rec in records:
        ratio = rec.weight / total_weight if total_weight > 0 else 0
        weight_ratios[rec.set_identifier] = ratio
        weight_table.add_row(
            rec.set_identifier,
            str(rec.weight),
            f"{ratio * 100:.1f}%",
        )

    # 실제 트래픽 분포 테이블
    traffic_table = Table(
        title=f"\U0001f4ca Actual Traffic Distribution (Total: {snapshot.total_requests:,})",
        show_header=True,
        header_style="bold",
        padding=(0, 1),
    )
    traffic_table.add_column("SetIdentifier", style="cyan")
    traffic_table.add_column("Count", justify="right")
    traffic_table.add_column("Ratio", justify="right")
    traffic_table.add_column("Diff", justify="right")
    traffic_table.add_column("Distribution")

    total = snapshot.total_requests - snapshot.errors
    for rec in records:
        count = snapshot.distribution.get(rec.set_identifier, 0)
        actual_ratio = count / total if total > 0 else 0
        configured_ratio = weight_ratios.get(rec.set_identifier, 0)
        diff = actual_ratio - configured_ratio

        if diff > 0:
            diff_text = Text(f"+{diff * 100:.1f}%", style="green")
        elif diff < 0:
            diff_text = Text(f"{diff * 100:.1f}%", style="red")
        else:
            diff_text = Text("0.0%", style="dim")

        bar = _make_bar(actual_ratio)

        traffic_table.add_row(
            rec.set_identifier,
            f"{count:,}",
            f"{actual_ratio * 100:.1f}%",
            diff_text,
            bar,
        )

    # 상태 바
    latency_str = f"{snapshot.avg_latency_ms:.0f}ms" if snapshot.avg_latency_ms else "N/A"
    status_line = Text(
        f"\u23f1  TPS: {snapshot.current_tps:.1f}  \u2502  "
        f"Uptime: {_format_duration(snapshot.elapsed_seconds)}  \u2502  "
        f"Errors: {snapshot.errors}  \u2502  "
        f"Avg Latency: {latency_str}",
        style="dim",
    )

    return Group(
        title,
        separator,
        Text(),
        weight_table,
        Text(),
        traffic_table,
        Text(),
        status_line,
        separator,
    )


async def run_display(
    record_name: str,
    records_ref: list[list[WeightedRecord]],
    stats: Stats,
    refresh_interval: float = 0.5,
) -> None:
    """Rich Live 대시보드를 주기적으로 갱신한다."""
    with Live(refresh_per_second=2, screen=False) as live:
        while True:
            snapshot = stats.get_snapshot()
            dashboard = build_dashboard(record_name, records_ref[0], snapshot)
            live.update(dashboard)
            await asyncio.sleep(refresh_interval)

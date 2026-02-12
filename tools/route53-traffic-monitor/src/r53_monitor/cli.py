"""Typer CLI entry point."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from . import __version__
from .aws import (
    AwsAuthError,
    Route53ApiError,
    WeightedRecord,
    get_weighted_records,
    get_zone_nameservers,
    validate_credentials,
)
from .config import build_config
from .display import run_display
from .resolver import AliasResolution, WeightedResolver, resolve_alias_targets
from .sender import TrafficSender, poll_route53
from .stats import Stats

app = typer.Typer(
    name="r53mon",
    help="Route53 Weighted Traffic Monitor",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"route53-traffic-monitor v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = False,
):
    """Route53 Weighted Traffic Monitor."""


@app.command()
def watch(
    endpoint: Annotated[
        str,
        typer.Option("--endpoint", "-e", help="모니터링 대상 URL (예: https://example.com)"),
    ] = None,
    zone_id: Annotated[
        str,
        typer.Option("--zone-id", "-z", help="Route53 Hosted Zone ID"),
    ] = None,
    record_name: Annotated[
        str | None,
        typer.Option("--record-name", "-r", help="레코드명 (생략 시 endpoint에서 추출)"),
    ] = None,
    tps: Annotated[
        int | None,
        typer.Option("--tps", "-t", help="초당 DNS 조회 횟수 (기본: 10)"),
    ] = None,
    no_http: Annotated[
        bool,
        typer.Option("--no-http", help="HTTP 트래픽 생성 비활성화"),
    ] = False,
    config_file: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="TOML 설정 파일 경로"),
    ] = None,
    env_file: Annotated[
        Path | None,
        typer.Option("--env-file", help=".env 파일 경로"),
    ] = None,
):
    """Route53 가중치 레코드의 설정 비율 vs 실제 트래픽 분포를 실시간 모니터링합니다."""
    try:
        cfg = build_config(
            endpoint=endpoint,
            zone_id=zone_id,
            record_name=record_name,
            tps=tps,
            no_http=no_http,
            config_file=config_file,
            env_file=env_file,
        )
    except ValueError as e:
        console.print(f"[red]설정 오류: {e}[/red]")
        raise typer.Exit(1) from e

    console.print(f"[bold green]대상: {cfg.record_name}[/bold green]")
    console.print(
        f"[dim]Zone: {cfg.hosted_zone_id} | TPS: {cfg.tps} | HTTP: {cfg.http_enabled}[/dim]"
    )

    # AWS 자격증명 사전 검증
    with console.status("[bold green]AWS 자격증명 확인 중..."):
        try:
            validate_credentials()
        except AwsAuthError as e:
            console.print(f"[red]AWS 인증 오류: {e}[/red]")
            raise typer.Exit(1) from e

    # Route53 가중치 레코드 조회
    with console.status("[bold green]Route53 가중치 레코드 조회 중..."):
        try:
            records = get_weighted_records(cfg.hosted_zone_id, cfg.record_name)
        except AwsAuthError as e:
            console.print(f"[red]AWS 인증 오류: {e}[/red]")
            raise typer.Exit(1) from e
        except Route53ApiError as e:
            console.print(f"[red]Route53 API 오류: {e}[/red]")
            raise typer.Exit(1) from e

    if not records:
        console.print("[red]가중치 레코드를 찾을 수 없습니다.[/red]")
        console.print(
            f"[dim]{cfg.record_name} 에 Weighted 레코드가 설정되어 있는지 확인하세요.[/dim]"
        )
        raise typer.Exit(1)

    console.print(f"[green]{len(records)}개 가중치 레코드 발견[/green]")
    for rec in records:
        console.print(
            f"  [cyan]{rec.set_identifier}[/cyan]: weight={rec.weight}, type={rec.record_type}"
        )

    # NS 조회
    with console.status("[bold green]Hosted Zone NS 조회 중..."):
        try:
            nameservers = get_zone_nameservers(cfg.hosted_zone_id)
        except AwsAuthError as e:
            console.print(f"[red]AWS 인증 오류: {e}[/red]")
            raise typer.Exit(1) from e
        except Route53ApiError as e:
            console.print(f"[red]NS 조회 실패: {e}[/red]")
            raise typer.Exit(1) from e

    # DNS Resolver 초기화
    record_type = records[0].record_type
    try:
        resolver = WeightedResolver(nameservers, cfg.record_name, record_type)
    except ValueError as e:
        console.print(f"[red]DNS Resolver 초기화 실패: {e}[/red]")
        raise typer.Exit(1) from e

    # ALIAS 레코드 해석
    alias_resolution = AliasResolution()
    has_alias = any(r.record_type == "ALIAS" for r in records)
    if has_alias:
        with console.status("[bold green]ALIAS 대상 IP 해석 중..."):
            alias_resolution = resolve_alias_targets(records)

        console.print("[bold]ALIAS 대상 해석 결과:[/bold]")
        for sid, target in alias_resolution.targets.items():
            ips_str = ", ".join(target.ips) if target.ips else "[red]해석 실패[/red]"
            console.print(f"  [cyan]{sid}[/cyan]: {target.alias_dns}")
            console.print(f"    IPs: {ips_str}")

        for warning in alias_resolution.warnings:
            console.print(f"  [yellow]WARNING: {warning}[/yellow]")

        if alias_resolution.indistinguishable:
            console.print(
                "[red]ALIAS 대상들이 동일한 IP로 해석되어 "
                "DNS 기반 트래픽 분포 측정이 불가능합니다.[/red]"
            )
            console.print(
                "[dim]다른 ALB/NLB를 사용하거나, "
                "ALIAS 대상이 서로 다른 IP를 가지는지 확인하세요.[/dim]"
            )
            raise typer.Exit(1)

    # 시작 전 권한 NS 테스트 조회 (10회)
    console.print("[bold]권한 NS 테스트 조회 (10회):[/bold]")
    test_hits: dict[str, int] = {}
    test_unknown: list[str] = []
    from .aws import build_value_to_identifier_map

    value_map = build_value_to_identifier_map(records)
    for _ in range(10):
        ips = resolver.resolve_once()
        if not ips:
            test_unknown.append("(조회 실패)")
            continue
        ips_str = ", ".join(ips)
        # 매핑 시도
        matched = None
        first_ip = ips[0]
        if first_ip in value_map:
            matched = value_map[first_ip]
        elif has_alias:
            ip_set = frozenset(ips)
            if ip_set in alias_resolution.ip_set_map:
                matched = alias_resolution.ip_set_map[ip_set]
            elif first_ip in alias_resolution.ip_map:
                matched = alias_resolution.ip_map[first_ip]
        if matched:
            test_hits[matched] = test_hits.get(matched, 0) + 1
            console.print(f"  [{ips_str}] → [cyan]{matched}[/cyan]")
        else:
            test_unknown.append(ips_str)
            console.print(f"  [{ips_str}] → [red]매핑 실패[/red]")

    if test_hits:
        console.print(f"  결과: {test_hits}")
    if test_unknown:
        console.print(f"  [yellow]매핑 실패 {len(test_unknown)}건[/yellow]")
        console.print("  [dim]권한 NS 응답 IP가 ALIAS 대상 해석 IP와 다를 수 있습니다.[/dim]")

    console.print("[green]모니터링을 시작합니다...[/green]\n")

    # 비동기 이벤트 루프 실행
    stats = Stats()
    records_ref: list[list[WeightedRecord]] = [records]
    sender = TrafficSender(cfg, stats, records, resolver, alias_resolution)

    async def _run():
        tasks = [
            asyncio.create_task(sender.run()),
            asyncio.create_task(poll_route53(cfg, sender, records_ref)),
            asyncio.create_task(run_display(cfg.record_name, records_ref, stats)),
        ]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        sender.stop()
        # 최종 통계 출력
        snapshot = stats.get_snapshot()
        console.print("\n[bold]최종 통계[/bold]")
        console.print(f"  총 요청: {snapshot.total_requests:,}")
        console.print(f"  에러: {snapshot.errors}")
        total = snapshot.total_requests - snapshot.errors
        for sid, count in sorted(snapshot.distribution.items()):
            ratio = count / total * 100 if total > 0 else 0
            console.print(f"  [cyan]{sid}[/cyan]: {count:,} ({ratio:.1f}%)")


if __name__ == "__main__":
    app()

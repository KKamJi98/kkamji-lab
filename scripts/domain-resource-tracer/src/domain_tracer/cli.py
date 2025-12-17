"""CLI 인터페이스."""

import json
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from . import __version__
from .tracer import trace_domain

app = typer.Typer(
    name="drt",
    help="AWS 도메인 기반 리소스 추적 도구",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"domain-resource-tracer v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = False,
):
    """AWS 도메인 기반 리소스 추적 도구."""


@app.command()
def trace(
    pattern: Annotated[
        str,
        typer.Argument(help="도메인 검색 패턴 (정규표현식 지원)"),
    ],
    region: Annotated[
        str,
        typer.Option("--region", "-r", help="AWS 리전 (기본: ap-northeast-2)"),
    ] = "ap-northeast-2",
    output_json: Annotated[
        bool,
        typer.Option("--json", "-j", help="JSON 형식으로 출력"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-V", help="상세 출력"),
    ] = False,
):
    """도메인 패턴으로 AWS 리소스 체인을 추적합니다.

    예시:
        drt trace "api\\.example\\.com"
        drt trace ".*\\.example\\.com"
        drt trace "prod-.*"
    """
    with console.status(f"[bold green]'{pattern}' 패턴으로 검색 중..."):
        try:
            results = trace_domain(pattern, region)
        except ValueError as e:
            console.print(f"[red]오류: {e}[/red]")
            raise typer.Exit(1) from e
        except Exception as e:
            console.print(f"[red]AWS API 오류: {e}[/red]")
            raise typer.Exit(1) from e

    if not results:
        console.print(f"[yellow]'{pattern}' 패턴과 일치하는 도메인을 찾지 못했습니다.[/yellow]")
        raise typer.Exit(0)

    if output_json:
        console.print_json(json.dumps(results, indent=2, ensure_ascii=False, default=str))
        return

    # 결과 출력
    console.print(f"\n[bold green]검색 결과: {len(results)}개 도메인[/bold green]\n")

    for result in results:
        render_result(result, verbose)


def render_result(result: dict, verbose: bool = False):
    """결과를 트리 형태로 렌더링."""
    domain = result["domain"]
    target_type = result["target_type"]

    # 메인 트리
    tree = Tree(f"[bold cyan]{domain}[/bold cyan] [dim]({result['hosted_zone']['name']})[/dim]")

    # DNS 레코드 정보
    record_branch = tree.add("[bold]DNS 레코드[/bold]")
    record_branch.add(f"Type: {result['record']['type']}")
    record_branch.add(f"Value: [green]{result['record']['value']}[/green]")
    record_branch.add(f"Target: [yellow]{target_type}[/yellow]")

    details = result.get("details", {})

    # CloudFront 정보
    if "cloudfront" in details:
        cf = details["cloudfront"]
        cf_branch = tree.add("[bold magenta]CloudFront[/bold magenta]")
        cf_branch.add(f"Distribution ID: {cf.get('distribution_id')}")
        cf_branch.add(f"Status: {cf.get('status')}")

        if cf.get("origins"):
            origins_branch = cf_branch.add("[bold]Origins[/bold]")
            for origin in cf["origins"]:
                origin_text = f"[{origin['type']}] {origin['domain']}"
                if "bucket" in origin:
                    origin_text += f" (Bucket: {origin['bucket']})"
                origins_branch.add(origin_text)

        if verbose and cf.get("behaviors"):
            behaviors_branch = cf_branch.add("[bold]Cache Behaviors[/bold]")
            for behavior in cf["behaviors"]:
                behaviors_branch.add(f"{behavior['path_pattern']} → {behavior['target_origin']}")

    # Load Balancer 정보
    if "load_balancer" in details:
        lb = details["load_balancer"]
        lb_type = (lb.get("lb_type") or "unknown").upper()
        lb_branch = tree.add(f"[bold blue]Load Balancer ({lb_type})[/bold blue]")
        lb_branch.add(f"Name: {lb.get('lb_name')}")
        lb_branch.add(f"Scheme: {lb.get('scheme')}")
        lb_branch.add(f"VPC: {lb.get('vpc_id')}")

        if lb.get("state"):
            lb_branch.add(f"State: {lb.get('state')}")

        # Listeners
        if verbose and lb.get("listeners"):
            listeners_branch = lb_branch.add("[bold]Listeners[/bold]")
            for listener in lb["listeners"]:
                listener_text = f":{listener['port']} ({listener['protocol']})"
                listeners_branch.add(listener_text)

        # Target Groups
        if lb.get("target_groups"):
            tg_branch = lb_branch.add("[bold]Target Groups[/bold]")
            for tg in lb["target_groups"]:
                tg_item = tg_branch.add(f"[cyan]{tg['name']}[/cyan]")
                tg_item.add(f"Type: {tg['target_type']}")
                tg_item.add(f"Port: {tg.get('port')}")

                if tg.get("targets"):
                    targets_item = tg_item.add("[bold]Targets[/bold]")
                    for target in tg["targets"]:
                        health_color = "green" if target["health_state"] == "healthy" else "red"
                        targets_item.add(
                            f"{target['id']}:{target.get('port')} "
                            f"[{health_color}]({target['health_state']})[/{health_color}]"
                        )

    # EC2 인스턴스 정보
    if "ec2_instances" in details and details["ec2_instances"]:
        ec2_branch = tree.add("[bold yellow]EC2 Instances[/bold yellow]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Instance ID")
        table.add_column("Name")
        table.add_column("State")
        table.add_column("Type")
        table.add_column("Private IP")
        table.add_column("AZ")

        for instance in details["ec2_instances"]:
            if "error" in instance:
                ec2_branch.add(f"[red]Error: {instance['error']}[/red]")
                continue

            state_color = "green" if instance["state"] == "running" else "red"
            table.add_row(
                instance["instance_id"],
                instance.get("name", "-"),
                f"[{state_color}]{instance['state']}[/{state_color}]",
                instance["instance_type"],
                instance.get("private_ip", "-"),
                instance.get("availability_zone", "-"),
            )

        ec2_branch.add(table)

    console.print(Panel(tree, border_style="dim"))
    console.print()


@app.command()
def list_zones():
    """Route53 Hosted Zone 목록을 조회합니다."""
    from .aws_clients import get_route53_client

    client = get_route53_client()

    with console.status("[bold green]Hosted Zone 조회 중..."):
        paginator = client.get_paginator("list_hosted_zones")
        zones = []
        for page in paginator.paginate():
            zones.extend(page["HostedZones"])

    if not zones:
        console.print("[yellow]등록된 Hosted Zone이 없습니다.[/yellow]")
        return

    table = Table(title="Route53 Hosted Zones", show_header=True, header_style="bold")
    table.add_column("Zone ID")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Record Count")

    for zone in zones:
        zone_id = zone["Id"].replace("/hostedzone/", "")
        zone_type = "Private" if zone.get("Config", {}).get("PrivateZone") else "Public"
        table.add_row(
            zone_id,
            zone["Name"].rstrip("."),
            zone_type,
            str(zone["ResourceRecordSetCount"]),
        )

    console.print(table)


@app.command()
def list_records(
    zone_id: Annotated[
        str,
        typer.Argument(help="Hosted Zone ID"),
    ],
    pattern: Annotated[
        str,
        typer.Option("--pattern", "-p", help="필터링 패턴 (정규표현식)"),
    ] = None,
):
    """특정 Hosted Zone의 레코드를 조회합니다."""
    import re

    from .aws_clients import get_route53_client

    client = get_route53_client()

    regex = None
    if pattern:
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            console.print(f"[red]잘못된 정규표현식: {e}[/red]")
            raise typer.Exit(1) from e

    with console.status("[bold green]레코드 조회 중..."):
        paginator = client.get_paginator("list_resource_record_sets")
        records = []
        for page in paginator.paginate(HostedZoneId=zone_id):
            for record in page["ResourceRecordSets"]:
                if regex and not regex.search(record["Name"]):
                    continue
                records.append(record)

    if not records:
        console.print("[yellow]레코드를 찾지 못했습니다.[/yellow]")
        return

    table = Table(title=f"Records in {zone_id}", show_header=True, header_style="bold")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Value / Alias Target")

    for record in records:
        name = record["Name"].rstrip(".")
        record_type = record["Type"]

        if "AliasTarget" in record:
            value = f"[dim]Alias →[/dim] {record['AliasTarget']['DNSName'].rstrip('.')}"
        elif "ResourceRecords" in record:
            values = [r["Value"] for r in record["ResourceRecords"]]
            value = "\n".join(values[:3])
            if len(values) > 3:
                value += f"\n[dim]... +{len(values) - 3} more[/dim]"
        else:
            value = "-"

        table.add_row(name, record_type, value)

    console.print(table)


if __name__ == "__main__":
    app()

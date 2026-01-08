"""CLI 인터페이스."""

import json
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from . import __version__
from .tracer import (
    InputType,
    identify_input_type,
    reverse_trace_auto,
    trace_domain,
)

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


@app.command(name="reverse-trace")
def reverse_trace(
    identifier: Annotated[
        str,
        typer.Argument(help="LB DNS, EC2 Instance ID, EC2 IP, 또는 EC2 Name (자동 감지)"),
    ],
    region: Annotated[
        str,
        typer.Option("--region", "-r", help="AWS 리전 (자동 감지, 미지정시 ap-northeast-2)"),
    ] = None,
    output_json: Annotated[
        bool,
        typer.Option("--json", "-j", help="JSON 형식으로 출력"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-V", help="상세 출력"),
    ] = False,
):
    """LB DNS 또는 EC2로부터 역방향 추적을 수행합니다.

    입력 형식에 따라 자동으로 추적 방향을 결정합니다:
    - LB DNS (*.elb.amazonaws.com) → Route53, CloudFront, Target Groups
    - EC2 Instance ID (i-xxx) → Target Group → LB → Route53, CloudFront
    - EC2 IP (x.x.x.x) → Target Group → LB → Route53, CloudFront
    - EC2 Private DNS (ip-x-x-x-x.*.compute.internal) → Target Group → LB
    - EC2 Name (문자열) → Target Group → LB → Route53, CloudFront

    예시:
        drt reverse-trace "k8s-xxx.elb.ap-northeast-2.amazonaws.com"
        drt reverse-trace "i-1234567890abcdef0"
        drt reverse-trace "10.0.1.100"
        drt reverse-trace "ip-172-30-65-89.ap-northeast-2.compute.internal"
        drt reverse-trace "prod-web-server"
    """
    input_type = identify_input_type(identifier)
    type_desc = {
        InputType.LB_DNS: "Load Balancer DNS",
        InputType.EC2_INSTANCE_ID: "EC2 Instance ID",
        InputType.EC2_IP: "EC2 IP",
        InputType.EC2_PRIVATE_DNS: "EC2 Private DNS",
        InputType.EC2_NAME: "EC2 Name",
    }.get(input_type, "Unknown")

    console.print(f"[dim]입력 타입: {type_desc}[/dim]")

    with console.status(f"[bold green]'{identifier}' 역추적 중..."):
        try:
            result = reverse_trace_auto(identifier, region)
        except Exception as e:
            console.print(f"[red]AWS API 오류: {e}[/red]")
            raise typer.Exit(1) from e

    if output_json:
        console.print_json(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return

    # 입력 타입에 따라 다른 렌더링 함수 호출
    if input_type == InputType.LB_DNS:
        render_reverse_lb_result(result, verbose)
    else:
        render_reverse_ec2_result(result, verbose)


def render_reverse_lb_result(result: dict, verbose: bool = False):
    """LB 역추적 결과를 트리 형태로 렌더링."""
    lb_dns = result["lb_dns"]
    lb = result.get("load_balancer", {})

    # 메인 트리
    tree = Tree(f"[bold cyan]{lb_dns}[/bold cyan]")

    # Load Balancer 정보
    lb_type = (lb.get("lb_type") or "unknown").upper()
    if lb.get("lb_name"):
        lb_branch = tree.add(f"[bold blue]Load Balancer ({lb_type})[/bold blue]")
        lb_branch.add(f"Name: {lb.get('lb_name')}")
        lb_branch.add(f"Scheme: {lb.get('scheme')}")
        lb_branch.add(f"VPC: {lb.get('vpc_id')}")
        if lb.get("state"):
            lb_branch.add(f"State: {lb.get('state')}")
    else:
        tree.add("[yellow]Load Balancer 정보를 찾을 수 없습니다[/yellow]")

    # Route53 역추적 결과
    route53_records = result.get("route53_records", [])
    if route53_records:
        r53_branch = tree.add(
            f"[bold magenta]← Route53 레코드 ({len(route53_records)}개)[/bold magenta]"
        )
        for r53 in route53_records:
            r53_item = r53_branch.add(f"[cyan]{r53['domain']}[/cyan]")
            r53_item.add(f"Hosted Zone: {r53['hosted_zone_name']} ({r53['hosted_zone_id']})")
            r53_item.add(f"Type: {r53['record_type']}")
    else:
        tree.add("[dim]← Route53: 이 LB를 가리키는 레코드 없음[/dim]")

    # CloudFront 역추적 결과
    cf_distributions = result.get("cloudfront_distributions", [])
    if cf_distributions:
        cf_branch = tree.add(
            f"[bold magenta]← CloudFront ({len(cf_distributions)}개)[/bold magenta]"
        )
        for cf in cf_distributions:
            status_color = "green" if cf["status"] == "Deployed" else "yellow"
            cf_item = cf_branch.add(
                f"[cyan]{cf['distribution_dns']}[/cyan] ({cf['distribution_id']})"
            )
            cf_item.add(f"Status: [{status_color}]{cf['status']}[/{status_color}]")
            cf_item.add(f"Enabled: {cf['enabled']}")
            if verbose and cf.get("matching_origins"):
                origins_item = cf_item.add("[bold]Matching Origins[/bold]")
                for origin in cf["matching_origins"]:
                    origins_item.add(f"{origin['id']}: {origin['domain']}")
    else:
        tree.add("[dim]← CloudFront: 이 LB를 Origin으로 사용하는 Distribution 없음[/dim]")

    # Target Groups
    if lb.get("target_groups"):
        tg_branch = tree.add("[bold green]→ Target Groups[/bold green]")
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
    ec2_instances = result.get("ec2_instances", [])
    if ec2_instances:
        ec2_branch = tree.add("[bold yellow]→ EC2 Instances[/bold yellow]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Instance ID")
        table.add_column("Name")
        table.add_column("State")
        table.add_column("Type")
        table.add_column("Private IP")
        table.add_column("AZ")

        for instance in ec2_instances:
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

    # Verbose 모드일 때 Listeners 표시
    if verbose and lb.get("listeners"):
        listeners_branch = tree.add("[bold]Listeners[/bold]")
        for listener in lb["listeners"]:
            listener_text = f":{listener['port']} ({listener['protocol']})"
            listener_item = listeners_branch.add(listener_text)

            for rule in listener.get("rules", []):
                if rule.get("conditions"):
                    conditions_text = ", ".join(
                        f"{c['type']}={c['values']}" for c in rule["conditions"]
                    )
                    listener_item.add(f"Rule {rule['priority']}: {conditions_text}")

    console.print(Panel(tree, title="[bold]Reverse Trace Result[/bold]", border_style="dim"))
    console.print()


def render_reverse_ec2_result(result: dict, verbose: bool = False):
    """EC2 역추적 결과를 트리 형태로 렌더링."""
    identifier = result["identifier"]
    input_type = result.get("input_type", "unknown")
    ec2_instances = result.get("ec2_instances", [])

    # 메인 트리
    tree = Tree(f"[bold cyan]{identifier}[/bold cyan] [dim]({input_type})[/dim]")

    # EC2 인스턴스 정보
    if not ec2_instances:
        tree.add("[yellow]EC2 인스턴스를 찾을 수 없습니다[/yellow]")
    elif "error" in ec2_instances[0]:
        tree.add(f"[red]오류: {ec2_instances[0]['error']}[/red]")
    else:
        for ec2 in ec2_instances:
            if "error" in ec2:
                continue

            state_color = "green" if ec2["state"] == "running" else "red"
            ec2_branch = tree.add(
                f"[bold yellow]EC2: {ec2['instance_id']}[/bold yellow] "
                f"[dim]({ec2.get('name', 'N/A')})[/dim]"
            )
            ec2_branch.add(f"State: [{state_color}]{ec2['state']}[/{state_color}]")
            ec2_branch.add(f"Type: {ec2['instance_type']}")
            ec2_branch.add(f"Primary IP: {ec2.get('private_ip', '-')}")
            all_ips = ec2.get("all_private_ips", [])
            if all_ips:
                ec2_branch.add(f"ENI IPs: {len(all_ips)}개 (Pod IP 포함)")
            if ec2.get("public_ip"):
                ec2_branch.add(f"Public IP: {ec2['public_ip']}")
            ec2_branch.add(f"AZ: {ec2.get('availability_zone', '-')}")
            ec2_branch.add(f"VPC: {ec2.get('vpc_id', '-')}")

    # Target Groups
    target_groups = result.get("target_groups", [])
    if target_groups:
        tg_branch = tree.add(f"[bold green]→ Target Groups ({len(target_groups)}개)[/bold green]")
        for tg in target_groups:
            if "error" in tg:
                continue
            health_color = "green" if tg["health_state"] == "healthy" else "red"
            tg_item = tg_branch.add(f"[cyan]{tg['target_group_name']}[/cyan]")
            tg_item.add(f"Type: {tg['target_type']}")
            tg_item.add(f"Port: {tg.get('port')}")
            tg_item.add(
                f"Target: {tg['target_id']}:{tg.get('target_port')} "
                f"[{health_color}]({tg['health_state']})[/{health_color}]"
            )
    else:
        tree.add("[dim]→ Target Group: 등록된 Target Group 없음[/dim]")

    # Load Balancers
    load_balancers = result.get("load_balancers", [])
    if load_balancers:
        lb_branch = tree.add(f"[bold blue]→ Load Balancers ({len(load_balancers)}개)[/bold blue]")
        for lb in load_balancers:
            lb_type = (lb.get("lb_type") or "unknown").upper()
            lb_item = lb_branch.add(f"[cyan]{lb['lb_name']}[/cyan] ({lb_type})")
            lb_item.add(f"DNS: {lb['dns_name']}")
            lb_item.add(f"Scheme: {lb.get('scheme')}")
            lb_item.add(f"VPC: {lb.get('vpc_id')}")
            if lb.get("state"):
                lb_item.add(f"State: {lb['state']}")
    else:
        tree.add("[dim]→ Load Balancer: 연결된 LB 없음[/dim]")

    # Route53 역추적 결과
    route53_records = result.get("route53_records", [])
    if route53_records:
        r53_branch = tree.add(
            f"[bold magenta]← Route53 레코드 ({len(route53_records)}개)[/bold magenta]"
        )
        for r53 in route53_records:
            r53_item = r53_branch.add(f"[cyan]{r53['domain']}[/cyan]")
            r53_item.add(f"Hosted Zone: {r53['hosted_zone_name']} ({r53['hosted_zone_id']})")
            r53_item.add(f"Type: {r53['record_type']}")
    else:
        tree.add("[dim]← Route53: 연결된 레코드 없음[/dim]")

    # CloudFront 역추적 결과
    cf_distributions = result.get("cloudfront_distributions", [])
    if cf_distributions:
        cf_branch = tree.add(
            f"[bold magenta]← CloudFront ({len(cf_distributions)}개)[/bold magenta]"
        )
        for cf in cf_distributions:
            status_color = "green" if cf["status"] == "Deployed" else "yellow"
            cf_item = cf_branch.add(
                f"[cyan]{cf['distribution_dns']}[/cyan] ({cf['distribution_id']})"
            )
            cf_item.add(f"Status: [{status_color}]{cf['status']}[/{status_color}]")
            cf_item.add(f"Enabled: {cf['enabled']}")
            if verbose and cf.get("matching_origins"):
                origins_item = cf_item.add("[bold]Matching Origins[/bold]")
                for origin in cf["matching_origins"]:
                    origins_item.add(f"{origin['id']}: {origin['domain']}")
    else:
        tree.add("[dim]← CloudFront: 연결된 Distribution 없음[/dim]")

    console.print(Panel(tree, title="[bold]EC2 Reverse Trace Result[/bold]", border_style="dim"))
    console.print()


if __name__ == "__main__":
    app()

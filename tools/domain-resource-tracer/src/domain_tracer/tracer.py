"""AWS 리소스 추적 핵심 로직."""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from botocore.exceptions import ClientError

from .aws_clients import (
    get_cloudfront_client,
    get_ec2_client,
    get_elb_client,
    get_elbv2_client,
    get_route53_client,
)


class RecordType(Enum):
    """DNS 레코드 타입."""

    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    ALIAS = "ALIAS"


class TargetType(Enum):
    """타겟 리소스 타입."""

    CLOUDFRONT = "CloudFront"
    ALB = "ALB"
    NLB = "NLB"
    CLB = "CLB (Classic)"
    EC2 = "EC2"
    S3 = "S3"
    API_GATEWAY = "API Gateway"
    UNKNOWN = "Unknown"


@dataclass
class TraceResult:
    """추적 결과."""

    domain: str
    hosted_zone_id: str | None = None
    hosted_zone_name: str | None = None
    record_type: str | None = None
    record_value: str | None = None
    target_type: TargetType = TargetType.UNKNOWN
    resources: list[dict[str, Any]] = field(default_factory=list)
    chain: list[str] = field(default_factory=list)


def extract_region_from_elb_dns(dns_name: str) -> str:
    """ELB DNS 이름에서 리전 추출."""
    # 패턴: name-1234567890.ap-northeast-2.elb.amazonaws.com
    match = re.search(r"\.([a-z]{2}-[a-z]+-\d)\.elb\.amazonaws\.com", dns_name)
    if match:
        return match.group(1)
    return "ap-northeast-2"


def search_route53_records(pattern: str) -> list[TraceResult]:
    """정규표현식 패턴으로 Route53 레코드 검색."""
    client = get_route53_client()
    results: list[TraceResult] = []

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise ValueError(f"잘못된 정규표현식: {e}") from e

    # 모든 Hosted Zone 조회
    paginator = client.get_paginator("list_hosted_zones")
    for zones_page in paginator.paginate():
        for zone in zones_page["HostedZones"]:
            zone_id = zone["Id"].replace("/hostedzone/", "")
            zone_name = zone["Name"].rstrip(".")

            # 각 Zone의 레코드 조회
            record_paginator = client.get_paginator("list_resource_record_sets")
            for records_page in record_paginator.paginate(HostedZoneId=zone_id):
                for record in records_page["ResourceRecordSets"]:
                    record_name = record["Name"].rstrip(".")

                    # 패턴 매칭
                    if regex.search(record_name):
                        result = TraceResult(
                            domain=record_name,
                            hosted_zone_id=zone_id,
                            hosted_zone_name=zone_name,
                            record_type=record["Type"],
                        )

                        # Alias 레코드 처리
                        if "AliasTarget" in record:
                            result.record_type = f"{record['Type']} (Alias)"
                            result.record_value = record["AliasTarget"]["DNSName"].rstrip(".")
                            result.chain.append(f"Route53: {record_name}")
                            result.chain.append(f"→ Alias: {result.record_value}")
                        # 일반 레코드 처리
                        elif "ResourceRecords" in record:
                            values = [r["Value"] for r in record["ResourceRecords"]]
                            result.record_value = ", ".join(values)
                            result.chain.append(f"Route53: {record_name}")
                            result.chain.append(f"→ {record['Type']}: {result.record_value}")

                        # 타겟 타입 판별
                        if result.record_value:
                            result.target_type = identify_target_type(result.record_value)

                        results.append(result)

    return results


def identify_target_type(dns_value: str) -> TargetType:
    """DNS 값으로 타겟 타입 판별."""
    dns_lower = dns_value.lower()

    if ".cloudfront.net" in dns_lower:
        return TargetType.CLOUDFRONT
    elif ".elb.amazonaws.com" in dns_lower:
        if dns_lower.startswith("internal-") or "-internal-" in dns_lower:
            pass  # internal도 ALB/NLB/CLB일 수 있음
        # ALB/NLB는 이름 패턴으로 구분 어려움, 실제 조회 필요
        return TargetType.ALB  # 기본값, 추후 정확히 판별
    elif ".s3" in dns_lower and ".amazonaws.com" in dns_lower:
        return TargetType.S3
    elif ".execute-api." in dns_lower:
        return TargetType.API_GATEWAY
    elif re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", dns_value):
        return TargetType.EC2

    return TargetType.UNKNOWN


def trace_cloudfront(distribution_dns: str) -> dict[str, Any]:
    """CloudFront 배포 정보 추적."""
    client = get_cloudfront_client()
    result = {
        "type": "CloudFront",
        "distribution_dns": distribution_dns,
        "distribution_id": None,
        "origins": [],
        "behaviors": [],
    }

    # distribution_dns에서 ID 추출 또는 전체 목록에서 검색
    paginator = client.get_paginator("list_distributions")

    for page in paginator.paginate():
        if "DistributionList" not in page or "Items" not in page["DistributionList"]:
            continue

        for dist in page["DistributionList"]["Items"]:
            if dist["DomainName"].lower() == distribution_dns.lower():
                result["distribution_id"] = dist["Id"]
                result["status"] = dist["Status"]
                result["enabled"] = dist["Enabled"]

                # Origins 정보
                for origin in dist.get("Origins", {}).get("Items", []):
                    origin_info = {
                        "id": origin["Id"],
                        "domain": origin["DomainName"],
                    }

                    # S3 Origin 확인
                    if ".s3." in origin["DomainName"] or origin["DomainName"].endswith(
                        ".s3.amazonaws.com"
                    ):
                        origin_info["type"] = "S3"
                        # 버킷 이름 추출
                        bucket_match = re.match(r"([^.]+)\.s3[.-]", origin["DomainName"])
                        if bucket_match:
                            origin_info["bucket"] = bucket_match.group(1)
                    elif ".elb." in origin["DomainName"]:
                        origin_info["type"] = "ELB"
                    else:
                        origin_info["type"] = "Custom"

                    if "S3OriginConfig" in origin:
                        origin_info["origin_access_identity"] = origin["S3OriginConfig"].get(
                            "OriginAccessIdentity", ""
                        )
                    if "CustomOriginConfig" in origin:
                        origin_info["protocol_policy"] = origin["CustomOriginConfig"].get(
                            "OriginProtocolPolicy", ""
                        )

                    result["origins"].append(origin_info)

                # Cache Behaviors
                default_behavior = dist.get("DefaultCacheBehavior", {})
                result["behaviors"].append(
                    {
                        "path_pattern": "*",
                        "target_origin": default_behavior.get("TargetOriginId"),
                        "viewer_protocol_policy": default_behavior.get("ViewerProtocolPolicy"),
                    }
                )

                for behavior in dist.get("CacheBehaviors", {}).get("Items", []):
                    result["behaviors"].append(
                        {
                            "path_pattern": behavior.get("PathPattern"),
                            "target_origin": behavior.get("TargetOriginId"),
                            "viewer_protocol_policy": behavior.get("ViewerProtocolPolicy"),
                        }
                    )

                return result

    return result


def normalize_elb_dns(dns_name: str) -> str:
    """ELB DNS 이름 정규화 (dualstack. prefix 제거)."""
    if dns_name.lower().startswith("dualstack."):
        return dns_name[len("dualstack.") :]
    return dns_name


def trace_load_balancer(lb_dns: str, region: str | None = None) -> dict[str, Any]:
    """Load Balancer 정보 추적 (ALB/NLB/CLB)."""
    # dualstack. prefix 제거
    lb_dns = normalize_elb_dns(lb_dns)

    if region is None:
        region = extract_region_from_elb_dns(lb_dns)

    result = {
        "type": "LoadBalancer",
        "dns_name": lb_dns,
        "lb_type": None,
        "lb_arn": None,
        "lb_name": None,
        "vpc_id": None,
        "scheme": None,
        "listeners": [],
        "target_groups": [],
        "targets": [],
    }

    # ALB/NLB 조회 (ELBv2)
    elbv2 = get_elbv2_client(region)
    try:
        paginator = elbv2.get_paginator("describe_load_balancers")
        for page in paginator.paginate():
            for lb in page["LoadBalancers"]:
                if lb["DNSName"].lower() == lb_dns.lower():
                    result["lb_type"] = lb["Type"]  # 'application' or 'network'
                    result["lb_arn"] = lb["LoadBalancerArn"]
                    result["lb_name"] = lb["LoadBalancerName"]
                    result["vpc_id"] = lb["VpcId"]
                    result["scheme"] = lb["Scheme"]
                    result["state"] = lb["State"]["Code"]

                    # Listeners 조회
                    listeners_resp = elbv2.describe_listeners(LoadBalancerArn=lb["LoadBalancerArn"])
                    for listener in listeners_resp["Listeners"]:
                        listener_info = {
                            "port": listener["Port"],
                            "protocol": listener["Protocol"],
                            "listener_arn": listener["ListenerArn"],
                            "rules": [],
                        }

                        # Listener Rules 조회
                        rules_resp = elbv2.describe_rules(ListenerArn=listener["ListenerArn"])
                        for rule in rules_resp["Rules"]:
                            rule_info = {
                                "priority": rule["Priority"],
                                "conditions": [],
                                "actions": [],
                            }

                            for condition in rule.get("Conditions", []):
                                if "HostHeaderConfig" in condition:
                                    rule_info["conditions"].append(
                                        {
                                            "type": "host-header",
                                            "values": condition["HostHeaderConfig"]["Values"],
                                        }
                                    )
                                elif "PathPatternConfig" in condition:
                                    rule_info["conditions"].append(
                                        {
                                            "type": "path-pattern",
                                            "values": condition["PathPatternConfig"]["Values"],
                                        }
                                    )

                            for action in rule.get("Actions", []):
                                action_info = {"type": action["Type"]}
                                if action["Type"] == "forward":
                                    if "TargetGroupArn" in action:
                                        action_info["target_group_arn"] = action["TargetGroupArn"]
                                    elif "ForwardConfig" in action:
                                        action_info["target_groups"] = [
                                            tg["TargetGroupArn"]
                                            for tg in action["ForwardConfig"]["TargetGroups"]
                                        ]
                                rule_info["actions"].append(action_info)

                            listener_info["rules"].append(rule_info)

                        result["listeners"].append(listener_info)

                    # Target Groups 수집
                    target_group_arns = set()
                    for listener in result["listeners"]:
                        for rule in listener["rules"]:
                            for action in rule["actions"]:
                                if "target_group_arn" in action:
                                    target_group_arns.add(action["target_group_arn"])
                                elif "target_groups" in action:
                                    target_group_arns.update(action["target_groups"])

                    # Target Groups 상세 정보
                    if target_group_arns:
                        tg_resp = elbv2.describe_target_groups(
                            TargetGroupArns=list(target_group_arns)
                        )
                        for tg in tg_resp["TargetGroups"]:
                            tg_info = {
                                "arn": tg["TargetGroupArn"],
                                "name": tg["TargetGroupName"],
                                "protocol": tg.get("Protocol"),
                                "port": tg.get("Port"),
                                "target_type": tg["TargetType"],
                                "vpc_id": tg.get("VpcId"),
                                "health_check": {
                                    "protocol": tg.get("HealthCheckProtocol"),
                                    "path": tg.get("HealthCheckPath"),
                                    "port": tg.get("HealthCheckPort"),
                                },
                                "targets": [],
                            }

                            # Target Health 조회
                            health_resp = elbv2.describe_target_health(
                                TargetGroupArn=tg["TargetGroupArn"]
                            )
                            for target in health_resp["TargetHealthDescriptions"]:
                                target_info = {
                                    "id": target["Target"]["Id"],
                                    "port": target["Target"].get("Port"),
                                    "health_state": target["TargetHealth"]["State"],
                                    "health_reason": target["TargetHealth"].get("Reason"),
                                }
                                tg_info["targets"].append(target_info)

                                # EC2 인스턴스 정보 수집
                                if target["Target"]["Id"].startswith("i-"):
                                    result["targets"].append(target["Target"]["Id"])

                            result["target_groups"].append(tg_info)

                    return result

    except ClientError:
        pass

    # Classic ELB 조회
    elb = get_elb_client(region)
    try:
        resp = elb.describe_load_balancers()
        for lb in resp["LoadBalancerDescriptions"]:
            if lb["DNSName"].lower() == lb_dns.lower():
                result["lb_type"] = "classic"
                result["lb_name"] = lb["LoadBalancerName"]
                result["vpc_id"] = lb.get("VPCId")
                result["scheme"] = lb["Scheme"]

                for listener in lb["ListenerDescriptions"]:
                    cfg = listener["Listener"]
                    result["listeners"].append(
                        {
                            "protocol": cfg["Protocol"],
                            "port": cfg["LoadBalancerPort"],
                            "instance_protocol": cfg["InstanceProtocol"],
                            "instance_port": cfg["InstancePort"],
                        }
                    )

                result["targets"] = lb.get("Instances", [])
                if result["targets"]:
                    result["targets"] = [i["InstanceId"] for i in result["targets"]]

                return result

    except ClientError:
        pass

    return result


def get_ec2_details(instance_ids: list[str], region: str = "ap-northeast-2") -> list[dict]:
    """EC2 인스턴스 상세 정보 조회."""
    if not instance_ids:
        return []

    ec2 = get_ec2_client(region)
    results = []

    try:
        resp = ec2.describe_instances(InstanceIds=instance_ids)
        for reservation in resp["Reservations"]:
            for instance in reservation["Instances"]:
                name = ""
                for tag in instance.get("Tags", []):
                    if tag["Key"] == "Name":
                        name = tag["Value"]
                        break

                results.append(
                    {
                        "instance_id": instance["InstanceId"],
                        "name": name,
                        "state": instance["State"]["Name"],
                        "instance_type": instance["InstanceType"],
                        "private_ip": instance.get("PrivateIpAddress"),
                        "public_ip": instance.get("PublicIpAddress"),
                        "availability_zone": instance["Placement"]["AvailabilityZone"],
                    }
                )
    except ClientError as e:
        results.append({"error": str(e)})

    return results


def trace_domain(pattern: str, region: str | None = None) -> list[dict[str, Any]]:
    """도메인 패턴으로 전체 리소스 체인 추적."""
    results = []

    # Route53에서 매칭되는 레코드 검색
    route53_results = search_route53_records(pattern)

    for r53_result in route53_results:
        trace_data = {
            "domain": r53_result.domain,
            "hosted_zone": {
                "id": r53_result.hosted_zone_id,
                "name": r53_result.hosted_zone_name,
            },
            "record": {
                "type": r53_result.record_type,
                "value": r53_result.record_value,
            },
            "target_type": r53_result.target_type.value,
            "chain": r53_result.chain,
            "details": {},
        }

        # CloudFront 추적
        if r53_result.target_type == TargetType.CLOUDFRONT and r53_result.record_value:
            cf_details = trace_cloudfront(r53_result.record_value)
            trace_data["details"]["cloudfront"] = cf_details
            trace_data["chain"].append(f"→ CloudFront ID: {cf_details.get('distribution_id')}")

            # CloudFront Origin 추가 추적
            for origin in cf_details.get("origins", []):
                trace_data["chain"].append(f"  → Origin ({origin['type']}): {origin['domain']}")

                # ELB Origin이면 추가 추적
                if origin["type"] == "ELB":
                    lb_details = trace_load_balancer(origin["domain"], region)
                    trace_data["details"]["load_balancer"] = lb_details
                    if lb_details.get("targets"):
                        target_region = region or "ap-northeast-2"
                        ec2_details = get_ec2_details(lb_details["targets"], target_region)
                        trace_data["details"]["ec2_instances"] = ec2_details

        # Load Balancer 추적
        elif r53_result.target_type == TargetType.ALB and r53_result.record_value:
            lb_details = trace_load_balancer(r53_result.record_value, region)
            trace_data["details"]["load_balancer"] = lb_details

            if lb_details.get("lb_type"):
                trace_data["chain"].append(
                    f"→ {lb_details['lb_type'].upper()}: {lb_details.get('lb_name')}"
                )

            # Target Groups
            for tg in lb_details.get("target_groups", []):
                trace_data["chain"].append(f"  → Target Group: {tg['name']}")
                for target in tg.get("targets", []):
                    trace_data["chain"].append(
                        f"    → Target: {target['id']} ({target['health_state']})"
                    )

            # EC2 상세 정보
            if lb_details.get("targets"):
                target_region = region or extract_region_from_elb_dns(r53_result.record_value)
                ec2_details = get_ec2_details(lb_details["targets"], target_region)
                trace_data["details"]["ec2_instances"] = ec2_details

        results.append(trace_data)

    return results


def reverse_trace_route53(target_dns: str) -> list[dict[str, Any]]:
    """특정 DNS 값을 가리키는 Route53 레코드 역추적."""
    client = get_route53_client()
    results: list[dict[str, Any]] = []

    # 정규화: 소문자 + trailing dot 제거 + dualstack. 제거
    target_normalized = normalize_elb_dns(target_dns.lower().rstrip("."))

    # 모든 Hosted Zone 순회
    zone_paginator = client.get_paginator("list_hosted_zones")
    for zones_page in zone_paginator.paginate():
        for zone in zones_page["HostedZones"]:
            zone_id = zone["Id"].replace("/hostedzone/", "")
            zone_name = zone["Name"].rstrip(".")

            # 각 Zone의 레코드 순회
            record_paginator = client.get_paginator("list_resource_record_sets")
            for records_page in record_paginator.paginate(HostedZoneId=zone_id):
                for record in records_page["ResourceRecordSets"]:
                    # Alias 레코드 확인
                    if "AliasTarget" in record:
                        alias_dns = record["AliasTarget"]["DNSName"].lower().rstrip(".")
                        alias_normalized = normalize_elb_dns(alias_dns)

                        if alias_normalized == target_normalized:
                            results.append(
                                {
                                    "domain": record["Name"].rstrip("."),
                                    "hosted_zone_id": zone_id,
                                    "hosted_zone_name": zone_name,
                                    "record_type": f"{record['Type']} (Alias)",
                                    "is_alias": True,
                                }
                            )

                    # CNAME 레코드 확인
                    elif record["Type"] == "CNAME" and "ResourceRecords" in record:
                        for rr in record["ResourceRecords"]:
                            cname_normalized = normalize_elb_dns(rr["Value"].lower().rstrip("."))
                            if cname_normalized == target_normalized:
                                results.append(
                                    {
                                        "domain": record["Name"].rstrip("."),
                                        "hosted_zone_id": zone_id,
                                        "hosted_zone_name": zone_name,
                                        "record_type": "CNAME",
                                        "is_alias": False,
                                    }
                                )

    return results


def reverse_trace_cloudfront(origin_dns: str) -> list[dict[str, Any]]:
    """특정 DNS를 Origin으로 사용하는 CloudFront Distribution 역추적."""
    client = get_cloudfront_client()
    results: list[dict[str, Any]] = []

    origin_normalized = normalize_elb_dns(origin_dns.lower())

    paginator = client.get_paginator("list_distributions")
    for page in paginator.paginate():
        if "DistributionList" not in page or "Items" not in page["DistributionList"]:
            continue

        for dist in page["DistributionList"]["Items"]:
            matching_origins = []

            for origin in dist.get("Origins", {}).get("Items", []):
                origin_domain = origin["DomainName"].lower()
                origin_domain_normalized = normalize_elb_dns(origin_domain)

                if origin_domain_normalized == origin_normalized:
                    matching_origins.append(
                        {
                            "id": origin["Id"],
                            "domain": origin["DomainName"],
                        }
                    )

            if matching_origins:
                results.append(
                    {
                        "distribution_id": dist["Id"],
                        "distribution_dns": dist["DomainName"],
                        "status": dist["Status"],
                        "enabled": dist["Enabled"],
                        "matching_origins": matching_origins,
                    }
                )

    return results


def reverse_trace_lb(lb_dns: str, region: str | None = None) -> dict[str, Any]:
    """LB DNS로부터 역방향 추적 (Route53, CloudFront, EC2)."""
    # 리전 자동 감지
    if region is None:
        region = extract_region_from_elb_dns(lb_dns)

    result: dict[str, Any] = {
        "lb_dns": lb_dns,
        "region": region,
        "route53_records": [],
        "load_balancer": {},
        "ec2_instances": [],
        "cloudfront_distributions": [],
        "chain": [],
    }

    # 1. LB -> Target Group -> EC2 정방향 추적 (기존 로직 재사용)
    lb_details = trace_load_balancer(lb_dns, region)
    result["load_balancer"] = lb_details
    result["chain"].append(f"LB: {lb_dns}")

    if lb_details.get("lb_name"):
        result["chain"].append(f"  Type: {lb_details.get('lb_type', 'unknown').upper()}")
        result["chain"].append(f"  Name: {lb_details['lb_name']}")

    # EC2 인스턴스 조회
    if lb_details.get("targets"):
        ec2_details = get_ec2_details(lb_details["targets"], region)
        result["ec2_instances"] = ec2_details
        for tg in lb_details.get("target_groups", []):
            result["chain"].append(f"  → Target Group: {tg['name']}")
            for target in tg.get("targets", []):
                result["chain"].append(f"    → {target['id']} ({target['health_state']})")

    # 2. Route53 역추적 - 이 LB를 가리키는 도메인 찾기
    route53_records = reverse_trace_route53(lb_dns)
    result["route53_records"] = route53_records
    if route53_records:
        result["chain"].append("← Route53 레코드:")
        for r53 in route53_records:
            result["chain"].append(f"  ← {r53['domain']} ({r53['hosted_zone_name']})")

    # 3. CloudFront 역추적 - 이 LB를 Origin으로 사용하는 Distribution 찾기
    cf_distributions = reverse_trace_cloudfront(lb_dns)
    result["cloudfront_distributions"] = cf_distributions
    if cf_distributions:
        result["chain"].append("← CloudFront Distributions:")
        for cf in cf_distributions:
            result["chain"].append(f"  ← {cf['distribution_dns']} ({cf['distribution_id']})")

    return result


class InputType(Enum):
    """입력 타입."""

    LB_DNS = "lb_dns"
    EC2_INSTANCE_ID = "ec2_instance_id"
    EC2_IP = "ec2_ip"
    EC2_PRIVATE_DNS = "ec2_private_dns"  # ip-x-x-x-x.region.compute.internal
    EC2_NAME = "ec2_name"
    UNKNOWN = "unknown"


# EC2 Private DNS 패턴: ip-172-30-65-89.ap-northeast-2.compute.internal
EC2_PRIVATE_DNS_PATTERN = re.compile(
    r"^ip-(\d{1,3})-(\d{1,3})-(\d{1,3})-(\d{1,3})\..*\.compute\.internal$", re.IGNORECASE
)


def extract_ip_from_private_dns(private_dns: str) -> str | None:
    """EC2 Private DNS에서 IP 주소 추출."""
    match = EC2_PRIVATE_DNS_PATTERN.match(private_dns)
    if match:
        return f"{match.group(1)}.{match.group(2)}.{match.group(3)}.{match.group(4)}"
    return None


def identify_input_type(identifier: str) -> InputType:
    """입력 값의 타입을 자동 감지."""
    identifier = identifier.strip()

    # LB DNS 패턴
    if ".elb.amazonaws.com" in identifier.lower():
        return InputType.LB_DNS

    # EC2 Instance ID 패턴
    if identifier.startswith("i-") and len(identifier) >= 10:
        return InputType.EC2_INSTANCE_ID

    # IP 주소 패턴 (Private/Public IP)
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", identifier):
        return InputType.EC2_IP

    # EC2 Private DNS 패턴 (ip-x-x-x-x.region.compute.internal)
    if EC2_PRIVATE_DNS_PATTERN.match(identifier):
        return InputType.EC2_PRIVATE_DNS

    # 그 외는 EC2 Name 태그로 간주
    return InputType.EC2_NAME


def find_ec2_by_identifier(identifier: str, region: str = "ap-northeast-2") -> list[dict[str, Any]]:
    """식별자로 EC2 인스턴스 검색 (Instance ID, IP, Name 태그)."""
    ec2 = get_ec2_client(region)
    results: list[dict[str, Any]] = []

    input_type = identify_input_type(identifier)

    try:
        if input_type == InputType.EC2_INSTANCE_ID:
            # Instance ID로 직접 조회
            resp = ec2.describe_instances(InstanceIds=[identifier])
        elif input_type == InputType.EC2_IP:
            # Private IP 또는 Public IP로 조회
            resp = ec2.describe_instances(
                Filters=[
                    {
                        "Name": "private-ip-address",
                        "Values": [identifier],
                    }
                ]
            )
            # Private IP로 못 찾으면 Public IP로 재시도
            if not resp["Reservations"]:
                resp = ec2.describe_instances(
                    Filters=[
                        {
                            "Name": "ip-address",
                            "Values": [identifier],
                        }
                    ]
                )
        elif input_type == InputType.EC2_PRIVATE_DNS:
            # Private DNS에서 IP 추출 후 조회
            extracted_ip = extract_ip_from_private_dns(identifier)
            if extracted_ip:
                resp = ec2.describe_instances(
                    Filters=[
                        {
                            "Name": "private-ip-address",
                            "Values": [extracted_ip],
                        }
                    ]
                )
            else:
                # IP 추출 실패 시 빈 결과
                resp = {"Reservations": []}
        else:
            # Name 태그로 조회 (정규표현식 지원을 위해 와일드카드 사용)
            # AWS Filter는 와일드카드(*)만 지원하므로 일단 전체 조회 후 필터링
            resp = ec2.describe_instances(
                Filters=[
                    {
                        "Name": "tag:Name",
                        "Values": [f"*{identifier}*"] if "*" not in identifier else [identifier],
                    }
                ]
            )

        for reservation in resp.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                name = ""
                for tag in instance.get("Tags", []):
                    if tag["Key"] == "Name":
                        name = tag["Value"]
                        break

                # ENI에서 모든 Private IP 수집 (primary + secondary)
                all_private_ips: list[str] = []
                for eni in instance.get("NetworkInterfaces", []):
                    for private_ip_info in eni.get("PrivateIpAddresses", []):
                        ip = private_ip_info.get("PrivateIpAddress")
                        if ip:
                            all_private_ips.append(ip)

                results.append(
                    {
                        "instance_id": instance["InstanceId"],
                        "name": name,
                        "state": instance["State"]["Name"],
                        "instance_type": instance["InstanceType"],
                        "private_ip": instance.get("PrivateIpAddress"),
                        "public_ip": instance.get("PublicIpAddress"),
                        "all_private_ips": all_private_ips,  # ENI의 모든 IP (Pod IP 포함)
                        "availability_zone": instance["Placement"]["AvailabilityZone"],
                        "vpc_id": instance.get("VpcId"),
                        "subnet_id": instance.get("SubnetId"),
                    }
                )

    except ClientError as e:
        results.append({"error": str(e), "identifier": identifier})

    return results


def find_target_groups_for_ec2(
    instance_id: str,
    all_private_ips: list[str] | None = None,
    region: str = "ap-northeast-2",
) -> list[dict[str, Any]]:
    """EC2 인스턴스가 등록된 Target Group 검색.

    Args:
        instance_id: EC2 인스턴스 ID
        all_private_ips: ENI의 모든 Private IP (primary + secondary, Pod IP 포함)
        region: AWS 리전
    """
    elbv2 = get_elbv2_client(region)
    results: list[dict[str, Any]] = []

    # 매칭할 IP 집합 생성
    match_ips = set(all_private_ips) if all_private_ips else set()

    try:
        # 모든 Target Group 조회
        tg_paginator = elbv2.get_paginator("describe_target_groups")
        for tg_page in tg_paginator.paginate():
            for tg in tg_page["TargetGroups"]:
                # 각 Target Group의 타겟 상태 조회
                health_resp = elbv2.describe_target_health(TargetGroupArn=tg["TargetGroupArn"])

                for target_health in health_resp["TargetHealthDescriptions"]:
                    target_id = target_health["Target"]["Id"]

                    # Instance ID 또는 ENI의 모든 IP로 매칭 (Pod IP 포함)
                    is_match = target_id == instance_id or target_id in match_ips

                    if is_match:
                        results.append(
                            {
                                "target_group_arn": tg["TargetGroupArn"],
                                "target_group_name": tg["TargetGroupName"],
                                "target_type": tg["TargetType"],
                                "protocol": tg.get("Protocol"),
                                "port": tg.get("Port"),
                                "vpc_id": tg.get("VpcId"),
                                "load_balancer_arns": tg.get("LoadBalancerArns", []),
                                "target_id": target_id,
                                "target_port": target_health["Target"].get("Port"),
                                "health_state": target_health["TargetHealth"]["State"],
                                "health_reason": target_health["TargetHealth"].get("Reason"),
                            }
                        )

    except ClientError as e:
        results.append({"error": str(e)})

    return results


def reverse_trace_ec2(identifier: str, region: str = "ap-northeast-2") -> dict[str, Any]:
    """EC2 (Instance ID/IP/Name)로부터 역방향 추적."""
    result: dict[str, Any] = {
        "identifier": identifier,
        "input_type": identify_input_type(identifier).value,
        "region": region,
        "ec2_instances": [],
        "target_groups": [],
        "load_balancers": [],
        "route53_records": [],
        "cloudfront_distributions": [],
        "chain": [],
    }

    # 1. EC2 인스턴스 찾기
    ec2_instances = find_ec2_by_identifier(identifier, region)
    result["ec2_instances"] = ec2_instances

    if not ec2_instances or "error" in ec2_instances[0]:
        result["chain"].append(f"EC2: {identifier} - 찾을 수 없음")
        return result

    # 2. 각 EC2에 대해 Target Group 검색
    all_lb_arns: set[str] = set()

    for ec2 in ec2_instances:
        if "error" in ec2:
            continue

        instance_id = ec2["instance_id"]
        private_ip = ec2.get("private_ip")
        all_private_ips = ec2.get("all_private_ips", [])
        result["chain"].append(f"EC2: {instance_id} ({ec2.get('name', 'N/A')})")
        result["chain"].append(f"  Primary IP: {private_ip}")
        result["chain"].append(f"  ENI IPs: {len(all_private_ips)}개 (Pod IP 포함)")

        # Target Group 검색 (ENI의 모든 IP로 매칭)
        target_groups = find_target_groups_for_ec2(instance_id, all_private_ips, region)

        for tg in target_groups:
            if "error" in tg:
                continue

            result["target_groups"].append(tg)
            result["chain"].append(f"  → Target Group: {tg['target_group_name']}")
            result["chain"].append(
                f"    Target: {tg['target_id']}:{tg['target_port']} ({tg['health_state']})"
            )

            # Load Balancer ARN 수집
            all_lb_arns.update(tg.get("load_balancer_arns", []))

    # 3. Load Balancer 정보 조회
    if all_lb_arns:
        elbv2 = get_elbv2_client(region)
        try:
            lb_resp = elbv2.describe_load_balancers(LoadBalancerArns=list(all_lb_arns))
            for lb in lb_resp["LoadBalancers"]:
                lb_info = {
                    "lb_arn": lb["LoadBalancerArn"],
                    "lb_name": lb["LoadBalancerName"],
                    "lb_type": lb["Type"],
                    "dns_name": lb["DNSName"],
                    "scheme": lb["Scheme"],
                    "vpc_id": lb["VpcId"],
                    "state": lb["State"]["Code"],
                }
                result["load_balancers"].append(lb_info)
                result["chain"].append(f"  → LB: {lb['LoadBalancerName']} ({lb['Type']})")
                result["chain"].append(f"    DNS: {lb['DNSName']}")

                # 4. Route53 역추적
                r53_records = reverse_trace_route53(lb["DNSName"])
                for r53 in r53_records:
                    if r53 not in result["route53_records"]:
                        result["route53_records"].append(r53)
                        result["chain"].append(
                            f"    ← Route53: {r53['domain']} ({r53['hosted_zone_name']})"
                        )

                # 5. CloudFront 역추적
                cf_dists = reverse_trace_cloudfront(lb["DNSName"])
                for cf in cf_dists:
                    if cf not in result["cloudfront_distributions"]:
                        result["cloudfront_distributions"].append(cf)
                        result["chain"].append(
                            f"    ← CloudFront: {cf['distribution_dns']} ({cf['distribution_id']})"
                        )

        except ClientError as e:
            result["chain"].append(f"  LB 조회 오류: {e}")

    return result


def reverse_trace_auto(identifier: str, region: str | None = None) -> dict[str, Any]:
    """입력 타입을 자동 감지하여 역추적 수행."""
    input_type = identify_input_type(identifier)

    if input_type == InputType.LB_DNS:
        return reverse_trace_lb(identifier, region)
    else:
        # EC2 관련 (Instance ID, IP, Name)
        if region is None:
            region = "ap-northeast-2"
        return reverse_trace_ec2(identifier, region)

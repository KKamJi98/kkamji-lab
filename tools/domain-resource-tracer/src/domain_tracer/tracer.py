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

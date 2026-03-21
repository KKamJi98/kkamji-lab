"""domain_tracer.tracer 핵심 함수 단위 테스트."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from domain_tracer.tracer import (
    TargetType,
    identify_target_type,
    normalize_elb_dns,
    trace_cloudfront,
    trace_load_balancer,
)

# ---------------------------------------------------------------------------
# identify_target_type
# ---------------------------------------------------------------------------


def test_identify_target_type_cloudfront():
    """CloudFront DNS는 CLOUDFRONT 타입을 반환해야 한다."""
    assert identify_target_type("abc123.cloudfront.net") == TargetType.CLOUDFRONT


def test_identify_target_type_alb():
    """.elb.amazonaws.com DNS는 ALB 타입을 반환해야 한다."""
    assert identify_target_type("my-alb-123.ap-northeast-2.elb.amazonaws.com") == TargetType.ALB


def test_identify_target_type_s3():
    """S3 endpoint DNS는 S3 타입을 반환해야 한다."""
    assert identify_target_type("my-bucket.s3.amazonaws.com") == TargetType.S3


def test_identify_target_type_api_gateway():
    """API Gateway DNS는 API_GATEWAY 타입을 반환해야 한다."""
    assert (
        identify_target_type("abc.execute-api.ap-northeast-2.amazonaws.com")
        == TargetType.API_GATEWAY
    )


def test_identify_target_type_ec2_ip():
    """IPv4 주소는 EC2 타입을 반환해야 한다."""
    assert identify_target_type("192.0.2.10") == TargetType.EC2


def test_identify_target_type_unknown():
    """알 수 없는 DNS는 UNKNOWN 타입을 반환해야 한다."""
    assert identify_target_type("some.random.hostname.example.com") == TargetType.UNKNOWN


# ---------------------------------------------------------------------------
# normalize_elb_dns
# ---------------------------------------------------------------------------


def test_normalize_elb_dns_removes_dualstack_prefix():
    """dualstack. prefix가 있으면 제거돼야 한다."""
    result = normalize_elb_dns("dualstack.my-alb-123.ap-northeast-2.elb.amazonaws.com")
    assert result == "my-alb-123.ap-northeast-2.elb.amazonaws.com"


def test_normalize_elb_dns_passthrough_without_prefix():
    """dualstack. prefix가 없으면 원본 문자열이 그대로 반환돼야 한다."""
    dns = "my-alb-123.ap-northeast-2.elb.amazonaws.com"
    assert normalize_elb_dns(dns) == dns


def test_normalize_elb_dns_case_insensitive_prefix():
    """dualstack. prefix 비교는 대소문자를 무시해야 한다."""
    result = normalize_elb_dns("Dualstack.my-alb-123.ap-northeast-2.elb.amazonaws.com")
    assert result == "my-alb-123.ap-northeast-2.elb.amazonaws.com"


# ---------------------------------------------------------------------------
# trace_cloudfront
# ---------------------------------------------------------------------------


def _make_cloudfront_paginator(pages: list[dict]) -> MagicMock:
    """CloudFront paginator mock을 생성한다."""
    paginator = MagicMock()
    paginator.paginate.return_value = iter(pages)
    return paginator


@patch("domain_tracer.tracer.get_cloudfront_client")
def test_trace_cloudfront_found_distribution(mock_get_client):
    """매칭되는 CloudFront 배포가 있으면 distribution_id가 채워져야 한다."""
    dist = {
        "Id": "EDFDVBD6EXAMPLE",
        "DomainName": "abc123.cloudfront.net",
        "Status": "Deployed",
        "Enabled": True,
        "Origins": {"Items": []},
        "DefaultCacheBehavior": {
            "TargetOriginId": "origin-1",
            "ViewerProtocolPolicy": "redirect-to-https",
        },
        "CacheBehaviors": {"Items": []},
    }
    page = {"DistributionList": {"Items": [dist]}}

    client = MagicMock()
    client.get_paginator.return_value = _make_cloudfront_paginator([page])
    mock_get_client.return_value = client

    result = trace_cloudfront("abc123.cloudfront.net")

    assert result["distribution_id"] == "EDFDVBD6EXAMPLE"


@patch("domain_tracer.tracer.get_cloudfront_client")
def test_trace_cloudfront_empty_distribution_list(mock_get_client):
    """Items가 없는 DistributionList 페이지에서 오류 없이 빈 결과를 반환해야 한다."""
    page = {"DistributionList": {"Items": []}}

    client = MagicMock()
    client.get_paginator.return_value = _make_cloudfront_paginator([page])
    mock_get_client.return_value = client

    result = trace_cloudfront("not-found.cloudfront.net")

    assert result["distribution_id"] is None
    assert result["origins"] == []


@patch("domain_tracer.tracer.get_cloudfront_client")
def test_trace_cloudfront_none_distribution_list(mock_get_client):
    """DistributionList 키 자체가 없는 페이지에서 오류 없이 빈 결과를 반환해야 한다."""
    page = {}  # DistributionList 키 없음

    client = MagicMock()
    client.get_paginator.return_value = _make_cloudfront_paginator([page])
    mock_get_client.return_value = client

    result = trace_cloudfront("x.cloudfront.net")

    assert result["distribution_id"] is None


@patch("domain_tracer.tracer.get_cloudfront_client")
def test_trace_cloudfront_s3_origin_parsed(mock_get_client):
    """S3 Origin이 있으면 type='S3'로 파싱되어야 한다."""
    dist = {
        "Id": "DIST001",
        "DomainName": "abc.cloudfront.net",
        "Status": "Deployed",
        "Enabled": True,
        "Origins": {
            "Items": [
                {
                    "Id": "s3-origin",
                    "DomainName": "my-bucket.s3.amazonaws.com",
                    "S3OriginConfig": {"OriginAccessIdentity": ""},
                }
            ]
        },
        "DefaultCacheBehavior": {
            "TargetOriginId": "s3-origin",
            "ViewerProtocolPolicy": "https-only",
        },
        "CacheBehaviors": {"Items": []},
    }
    page = {"DistributionList": {"Items": [dist]}}

    client = MagicMock()
    client.get_paginator.return_value = _make_cloudfront_paginator([page])
    mock_get_client.return_value = client

    result = trace_cloudfront("abc.cloudfront.net")

    assert result["origins"][0]["type"] == "S3"


# ---------------------------------------------------------------------------
# trace_load_balancer
# ---------------------------------------------------------------------------


def _client_error(code: str, message: str = "error") -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": message}},
        "DescribeLoadBalancers",
    )


@patch("domain_tracer.tracer.get_elb_client")
@patch("domain_tracer.tracer.get_elbv2_client")
def test_trace_load_balancer_alb_found(mock_elbv2, mock_elb):
    """ALB가 매칭되면 lb_type과 lb_name이 채워져야 한다."""
    lb = {
        "DNSName": "my-alb.ap-northeast-2.elb.amazonaws.com",
        "Type": "application",
        "LoadBalancerArn": "arn:aws:elasticloadbalancing:ap-northeast-2:123:loadbalancer/app/my-alb/abc",
        "LoadBalancerName": "my-alb",
        "VpcId": "vpc-0001",
        "Scheme": "internet-facing",
        "State": {"Code": "active"},
    }
    paginator = MagicMock()
    paginator.paginate.return_value = iter([{"LoadBalancers": [lb]}])

    elbv2_client = MagicMock()
    elbv2_client.get_paginator.return_value = paginator
    elbv2_client.describe_listeners.return_value = {"Listeners": []}
    mock_elbv2.return_value = elbv2_client

    result = trace_load_balancer("my-alb.ap-northeast-2.elb.amazonaws.com", region="ap-northeast-2")

    assert result["lb_type"] == "application"
    assert result["lb_name"] == "my-alb"


@patch("domain_tracer.tracer.get_elb_client")
@patch("domain_tracer.tracer.get_elbv2_client")
def test_trace_load_balancer_access_denied_logs_warning(mock_elbv2, mock_elb, caplog):
    """AccessDeniedException 발생 시 warning 로그가 기록돼야 한다."""
    elbv2_client = MagicMock()
    elbv2_client.get_paginator.side_effect = _client_error(
        "AccessDeniedException", "User is not authorized"
    )
    mock_elbv2.return_value = elbv2_client

    elb_client = MagicMock()
    elb_client.describe_load_balancers.return_value = {"LoadBalancerDescriptions": []}
    mock_elb.return_value = elb_client

    with caplog.at_level(logging.WARNING, logger="domain_tracer.tracer"):
        trace_load_balancer("my-alb.ap-northeast-2.elb.amazonaws.com", region="ap-northeast-2")

    assert any("권한 없음" in r.message for r in caplog.records)


@patch("domain_tracer.tracer.get_elb_client")
@patch("domain_tracer.tracer.get_elbv2_client")
def test_trace_load_balancer_throttling_logs_warning(mock_elbv2, mock_elb, caplog):
    """Throttling 발생 시 warning 로그가 기록돼야 한다."""
    elbv2_client = MagicMock()
    elbv2_client.get_paginator.side_effect = _client_error("Throttling", "Rate exceeded")
    mock_elbv2.return_value = elbv2_client

    elb_client = MagicMock()
    elb_client.describe_load_balancers.return_value = {"LoadBalancerDescriptions": []}
    mock_elb.return_value = elb_client

    with caplog.at_level(logging.WARNING, logger="domain_tracer.tracer"):
        trace_load_balancer("my-alb.ap-northeast-2.elb.amazonaws.com", region="ap-northeast-2")

    assert any("스로틀링" in r.message for r in caplog.records)

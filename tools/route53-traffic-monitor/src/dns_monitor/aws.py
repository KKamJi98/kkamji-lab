"""Route53 API - 가중치 레코드 및 NS 조회."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    TokenRetrievalError,
)


class AwsAuthError(Exception):
    """AWS 인증/자격증명 오류."""


class Route53ApiError(Exception):
    """Route53 API 호출 오류."""


@lru_cache
def get_route53_client():
    """Route53 클라이언트 반환."""
    return boto3.client("route53")


def validate_credentials() -> None:
    """AWS 자격증명이 유효한지 검증한다.

    Raises:
        AwsAuthError: 자격증명이 없거나 만료된 경우
    """
    try:
        sts = boto3.client("sts")
        sts.get_caller_identity()
    except NoCredentialsError as e:
        raise AwsAuthError(
            "AWS 자격증명을 찾을 수 없습니다. 'aws configure' 또는 'aws sso login'을 실행하세요."
        ) from e
    except TokenRetrievalError as e:
        raise AwsAuthError("AWS SSO 토큰이 만료되었습니다. 'aws sso login'을 실행하세요.") from e
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("ExpiredToken", "ExpiredTokenException", "InvalidClientTokenId"):
            raise AwsAuthError(f"AWS 토큰이 만료되었습니다 ({code}). 재인증을 실행하세요.") from e
        raise AwsAuthError(f"AWS 인증 오류: {e}") from e
    except BotoCoreError as e:
        raise AwsAuthError(f"AWS 자격증명 확인 실패: {e}") from e


@dataclass
class WeightedRecord:
    """가중치 레코드 정보."""

    set_identifier: str
    weight: int
    record_type: str  # A, CNAME, ALIAS
    values: list[str] = field(default_factory=list)


def get_weighted_records(zone_id: str, record_name: str) -> list[WeightedRecord]:
    """해당 record_name의 Weighted 레코드 목록을 조회한다.

    Raises:
        AwsAuthError: 자격증명 문제
        Route53ApiError: API 호출 실패
    """
    try:
        client = get_route53_client()

        # record_name을 FQDN으로 정규화
        fqdn = record_name if record_name.endswith(".") else record_name + "."

        paginator = client.get_paginator("list_resource_record_sets")
        records: list[WeightedRecord] = []

        for page in paginator.paginate(
            HostedZoneId=zone_id,
            StartRecordName=fqdn,
            StartRecordType="A",
        ):
            for rrs in page["ResourceRecordSets"]:
                # 이름이 다르면 중단
                if rrs["Name"] != fqdn:
                    break

                # Weighted 레코드만 필터
                if rrs.get("SetIdentifier") is None or rrs.get("Weight") is None:
                    continue

                record_type = rrs["Type"]
                values: list[str] = []

                if "AliasTarget" in rrs:
                    values.append(rrs["AliasTarget"]["DNSName"].rstrip("."))
                    record_type = "ALIAS"
                elif "ResourceRecords" in rrs:
                    values = [r["Value"] for r in rrs["ResourceRecords"]]

                records.append(
                    WeightedRecord(
                        set_identifier=rrs["SetIdentifier"],
                        weight=rrs["Weight"],
                        record_type=record_type,
                        values=values,
                    )
                )

        return records
    except (NoCredentialsError, TokenRetrievalError) as e:
        raise AwsAuthError(
            "AWS 자격증명을 찾을 수 없거나 만료되었습니다. "
            "'aws configure' 또는 'aws sso login'을 실행하세요."
        ) from e
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        msg = e.response.get("Error", {}).get("Message", str(e))
        if code in ("ExpiredToken", "ExpiredTokenException", "InvalidClientTokenId"):
            raise AwsAuthError(f"AWS 토큰 만료 ({code}). 재인증하세요.") from e
        if code == "NoSuchHostedZone":
            raise Route53ApiError(f"Hosted Zone을 찾을 수 없습니다: {zone_id}") from e
        if code == "AccessDenied":
            raise AwsAuthError(f"Route53 접근 권한이 없습니다: {msg}") from e
        raise Route53ApiError(f"Route53 API 오류 ({code}): {msg}") from e
    except BotoCoreError as e:
        raise AwsAuthError(f"AWS 자격증명 확인 실패: {e}") from e


def get_zone_nameservers(zone_id: str) -> list[str]:
    """Hosted Zone의 NS 레코드를 조회한다.

    Raises:
        AwsAuthError: 자격증명 문제
        Route53ApiError: API 호출 실패
    """
    try:
        client = get_route53_client()
        resp = client.get_hosted_zone(Id=zone_id)
        delegation_set = resp.get("DelegationSet", {})
        nameservers = delegation_set.get("NameServers", [])
        return nameservers
    except (NoCredentialsError, TokenRetrievalError) as e:
        raise AwsAuthError(
            "AWS 자격증명을 찾을 수 없거나 만료되었습니다. "
            "'aws configure' 또는 'aws sso login'을 실행하세요."
        ) from e
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        msg = e.response.get("Error", {}).get("Message", str(e))
        if code in ("ExpiredToken", "ExpiredTokenException", "InvalidClientTokenId"):
            raise AwsAuthError(f"AWS 토큰 만료 ({code}). 재인증하세요.") from e
        raise Route53ApiError(f"Route53 API 오류 ({code}): {msg}") from e
    except BotoCoreError as e:
        raise AwsAuthError(f"AWS 자격증명 확인 실패: {e}") from e


def build_value_to_identifier_map(
    records: list[WeightedRecord],
) -> dict[str, str]:
    """value → SetIdentifier 매핑을 구성한다."""
    mapping: dict[str, str] = {}
    for rec in records:
        for val in rec.values:
            mapping[val] = rec.set_identifier
    return mapping

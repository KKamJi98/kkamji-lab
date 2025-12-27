"""AWS 클라이언트 관리 모듈."""

from functools import lru_cache

import boto3


@lru_cache
def get_route53_client():
    """Route53 클라이언트 반환."""
    return boto3.client("route53")


@lru_cache
def get_cloudfront_client():
    """CloudFront 클라이언트 반환."""
    return boto3.client("cloudfront")


@lru_cache
def get_elbv2_client(region: str = "ap-northeast-2"):
    """ELBv2 클라이언트 반환."""
    return boto3.client("elbv2", region_name=region)


@lru_cache
def get_elb_client(region: str = "ap-northeast-2"):
    """Classic ELB 클라이언트 반환."""
    return boto3.client("elb", region_name=region)


@lru_cache
def get_ec2_client(region: str = "ap-northeast-2"):
    """EC2 클라이언트 반환."""
    return boto3.client("ec2", region_name=region)


@lru_cache
def get_s3_client():
    """S3 클라이언트 반환."""
    return boto3.client("s3")

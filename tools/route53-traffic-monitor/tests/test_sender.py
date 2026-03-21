"""dns_monitor.sender.TrafficSender._identify 단위 테스트."""

from __future__ import annotations

from unittest.mock import MagicMock

from dns_monitor.aws import WeightedRecord, build_value_to_identifier_map
from dns_monitor.config import MonitorConfig
from dns_monitor.resolver import AliasResolution
from dns_monitor.sender import TrafficSender
from dns_monitor.stats import Stats


def _make_sender(
    records: list[WeightedRecord],
    alias_resolution: AliasResolution | None = None,
) -> TrafficSender:
    """테스트용 TrafficSender를 생성한다."""
    config = MonitorConfig(
        endpoint="https://api.example.com",
        hosted_zone_id="Z001",
        record_name="api.example.com",
        tps=10,
    )
    stats = Stats()
    resolver = MagicMock()
    return TrafficSender(
        config=config,
        stats=stats,
        records=records,
        resolver=resolver,
        alias_resolution=alias_resolution,
    )


# ---------------------------------------------------------------------------
# _identify: 직접 매핑 (A/CNAME value가 IP 또는 DNS 값)
# ---------------------------------------------------------------------------


def test_identify_direct_ip_mapping():
    """A 레코드 IP가 value_map에 있으면 올바른 SetIdentifier를 반환해야 한다."""
    records = [
        WeightedRecord(set_identifier="blue", weight=50, record_type="A", values=["10.0.0.1"]),
        WeightedRecord(set_identifier="green", weight=50, record_type="A", values=["10.0.0.2"]),
    ]
    sender = _make_sender(records)

    assert sender._identify(["10.0.0.1"]) == "blue"
    assert sender._identify(["10.0.0.2"]) == "green"


def test_identify_empty_ips_returns_none():
    """빈 IP 리스트는 None을 반환해야 한다."""
    records = [
        WeightedRecord(set_identifier="blue", weight=100, record_type="A", values=["10.0.0.1"]),
    ]
    sender = _make_sender(records)

    assert sender._identify([]) is None


def test_identify_unknown_ip_returns_none():
    """value_map에 없는 IP는 None을 반환해야 한다."""
    records = [
        WeightedRecord(set_identifier="blue", weight=100, record_type="A", values=["10.0.0.1"]),
    ]
    sender = _make_sender(records)

    assert sender._identify(["192.168.99.99"]) is None


# ---------------------------------------------------------------------------
# _identify: ALIAS 레코드 - ip_set_map 매핑
# ---------------------------------------------------------------------------


def test_identify_alias_ip_set_mapping():
    """IP-set이 alias_resolution.ip_set_map에 있으면 올바른 SetIdentifier를 반환해야 한다."""
    records: list[WeightedRecord] = []  # value_map은 비어 있음

    alias_resolution = AliasResolution()
    ip_set = frozenset(["203.0.113.10", "203.0.113.11"])
    alias_resolution.ip_set_map[ip_set] = "canary"

    sender = _make_sender(records, alias_resolution=alias_resolution)

    result = sender._identify(["203.0.113.10", "203.0.113.11"])
    assert result == "canary"


def test_identify_alias_ip_fallback_mapping():
    """ip_set_map에 없고 ip_map에 있으면 fallback으로 SetIdentifier를 반환해야 한다."""
    records: list[WeightedRecord] = []

    alias_resolution = AliasResolution()
    alias_resolution.ip_map["198.51.100.5"] = "stable"

    sender = _make_sender(records, alias_resolution=alias_resolution)

    # IP-set 매핑은 없지만 ip_map에는 있음
    result = sender._identify(["198.51.100.5"])
    assert result == "stable"


# ---------------------------------------------------------------------------
# build_value_to_identifier_map (aws.py 헬퍼 - sender가 내부적으로 사용)
# ---------------------------------------------------------------------------


def test_build_value_to_identifier_map_multiple_records():
    """여러 레코드의 값이 각각 올바른 SetIdentifier에 매핑돼야 한다."""
    records = [
        WeightedRecord(set_identifier="a", weight=50, record_type="A", values=["1.1.1.1"]),
        WeightedRecord(set_identifier="b", weight=50, record_type="A", values=["2.2.2.2"]),
    ]
    mapping = build_value_to_identifier_map(records)

    assert mapping["1.1.1.1"] == "a"
    assert mapping["2.2.2.2"] == "b"


def test_build_value_to_identifier_map_empty_records():
    """빈 레코드 리스트는 빈 매핑을 반환해야 한다."""
    assert build_value_to_identifier_map([]) == {}

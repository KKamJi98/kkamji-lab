"""dns_monitor.resolver 단위 테스트."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import dns.exception
import dns.resolver
import pytest

from dns_monitor.aws import WeightedRecord
from dns_monitor.resolver import WeightedResolver, resolve_alias_targets

# ---------------------------------------------------------------------------
# WeightedResolver 생성
# ---------------------------------------------------------------------------


@patch("dns_monitor.resolver.dns.resolver.Resolver")
def test_weighted_resolver_init_raises_when_no_ns_resolved(mock_resolver_cls):
    """모든 NS가 리졸브 실패이면 ValueError가 발생해야 한다."""
    mock_resolver = MagicMock()
    mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN
    mock_resolver_cls.return_value = mock_resolver

    with pytest.raises(ValueError, match="Failed to resolve any nameserver IPs"):
        WeightedResolver(
            nameservers=["ns-unreachable.example.com"],
            record_name="api.example.com",
            record_type="A",
        )


@patch("dns_monitor.resolver.dns.resolver.Resolver")
def test_weighted_resolver_init_skips_failed_ns(mock_resolver_cls):
    """일부 NS가 실패해도 성공한 NS가 있으면 초기화가 완료돼야 한다."""
    mock_resolver = MagicMock()

    def resolve_side_effect(ns, rdtype):
        if ns == "ns1.example.com":
            raise dns.resolver.NXDOMAIN
        answers = MagicMock()
        rdata = MagicMock()
        rdata.__str__ = lambda self: "10.0.0.53"
        answers.__iter__ = lambda self: iter([rdata])
        return answers

    mock_resolver.resolve.side_effect = resolve_side_effect
    mock_resolver_cls.return_value = mock_resolver

    resolver = WeightedResolver(
        nameservers=["ns1.example.com", "ns2.example.com"],
        record_name="api.example.com",
        record_type="A",
    )
    assert "10.0.0.53" in resolver._ns_ips


# ---------------------------------------------------------------------------
# WeightedResolver.resolve_once
# ---------------------------------------------------------------------------


@patch("dns_monitor.resolver.dns.resolver.Resolver")
@patch("dns_monitor.resolver.dns.query.udp")
@patch("dns_monitor.resolver.dns.message.make_query")
def test_resolve_once_returns_ips_on_success(mock_make_query, mock_udp, mock_resolver_cls):
    """정상 응답이면 IP 리스트를 반환해야 한다."""
    # NS 리졸브 성공 셋업
    mock_resolver = MagicMock()
    ns_rdata = MagicMock()
    ns_rdata.__str__ = lambda self: "10.0.0.53"
    ns_answers = MagicMock()
    ns_answers.__iter__ = lambda self: iter([ns_rdata])
    mock_resolver.resolve.return_value = ns_answers
    mock_resolver_cls.return_value = mock_resolver

    # DNS 응답 셋업
    a_rdata = MagicMock()
    a_rdata.__str__ = lambda self: "192.0.2.1"
    rrset = MagicMock()
    rrset.__iter__ = lambda self: iter([a_rdata])
    response = MagicMock()
    response.answer = [rrset]
    mock_udp.return_value = response

    resolver = WeightedResolver(
        nameservers=["ns1.example.com"],
        record_name="api.example.com",
        record_type="A",
    )
    ips = resolver.resolve_once()

    assert "192.0.2.1" in ips


@patch("dns_monitor.resolver.dns.resolver.Resolver")
@patch("dns_monitor.resolver.dns.query.udp")
@patch("dns_monitor.resolver.dns.message.make_query")
def test_resolve_once_returns_empty_on_dns_exception(mock_make_query, mock_udp, mock_resolver_cls):
    """DNSException 발생 시 빈 리스트를 반환해야 한다."""
    mock_resolver = MagicMock()
    ns_rdata = MagicMock()
    ns_rdata.__str__ = lambda self: "10.0.0.53"
    ns_answers = MagicMock()
    ns_answers.__iter__ = lambda self: iter([ns_rdata])
    mock_resolver.resolve.return_value = ns_answers
    mock_resolver_cls.return_value = mock_resolver

    mock_udp.side_effect = dns.exception.DNSException("timeout")

    resolver = WeightedResolver(
        nameservers=["ns1.example.com"],
        record_name="api.example.com",
        record_type="A",
    )
    ips = resolver.resolve_once()

    assert ips == []


@patch("dns_monitor.resolver.dns.resolver.Resolver")
@patch("dns_monitor.resolver.dns.query.udp")
@patch("dns_monitor.resolver.dns.message.make_query")
def test_resolve_once_returns_empty_on_oserror(mock_make_query, mock_udp, mock_resolver_cls):
    """OSError(네트워크 오류) 발생 시 빈 리스트를 반환해야 한다."""
    mock_resolver = MagicMock()
    ns_rdata = MagicMock()
    ns_rdata.__str__ = lambda self: "10.0.0.53"
    ns_answers = MagicMock()
    ns_answers.__iter__ = lambda self: iter([ns_rdata])
    mock_resolver.resolve.return_value = ns_answers
    mock_resolver_cls.return_value = mock_resolver

    mock_udp.side_effect = OSError("network unreachable")

    resolver = WeightedResolver(
        nameservers=["ns1.example.com"],
        record_name="api.example.com",
        record_type="A",
    )
    ips = resolver.resolve_once()

    assert ips == []


# ---------------------------------------------------------------------------
# resolve_alias_targets
# ---------------------------------------------------------------------------


@patch("dns_monitor.resolver.dns.resolver.Resolver")
def test_resolve_alias_targets_dns_exception_adds_warning(mock_resolver_cls):
    """ALIAS 대상 리졸브 실패 시 warnings 목록에 항목이 추가돼야 한다."""
    mock_resolver = MagicMock()
    mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN
    mock_resolver_cls.return_value = mock_resolver

    records = [
        WeightedRecord(
            set_identifier="blue",
            weight=100,
            record_type="ALIAS",
            values=["unreachable.example.com"],
        )
    ]

    result = resolve_alias_targets(records)

    assert len(result.warnings) >= 1
    assert any("blue" in w for w in result.warnings)


@patch("dns_monitor.resolver.dns.resolver.Resolver")
def test_resolve_alias_targets_skips_non_alias_records(mock_resolver_cls):
    """ALIAS 타입이 아닌 레코드는 리졸브 시도를 건너뛰어야 한다."""
    mock_resolver = MagicMock()
    mock_resolver_cls.return_value = mock_resolver

    records = [
        WeightedRecord(
            set_identifier="blue",
            weight=100,
            record_type="A",
            values=["10.0.0.1"],
        )
    ]

    result = resolve_alias_targets(records)

    mock_resolver.resolve.assert_not_called()
    assert result.targets == {}

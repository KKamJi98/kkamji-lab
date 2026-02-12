"""dnspython 기반 DNS 조회 모듈.

권한 NS에 직접 질의하여 Route53 가중치 라우팅 분포를 측정한다.
dns.query.udp()로 직접 패킷을 보내 resolver 캐시를 완전히 우회한다.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import dns.message
import dns.query
import dns.rdatatype
import dns.resolver


class WeightedResolver:
    """Route53 권한 NS에 직접 DNS 조회를 수행한다.

    dns.query.udp()를 사용하여 매 조회마다 독립적인 UDP 패킷을 전송한다.
    resolver 캐시를 완전히 우회하여 Route53의 가중치 라우팅 결정을 정확히 측정한다.
    """

    def __init__(
        self,
        nameservers: list[str],
        record_name: str,
        record_type: str,
    ):
        self._record_name = record_name
        self._query_type = "A" if record_type in ("A", "ALIAS") else record_type

        # 권한 NS IP 주소 리졸브
        ns_ips: list[str] = []
        default_resolver = dns.resolver.Resolver()
        for ns in nameservers:
            try:
                answers = default_resolver.resolve(ns, "A")
                for rdata in answers:
                    ns_ips.append(str(rdata))
            except dns.resolver.DNSException:
                continue

        if not ns_ips:
            raise ValueError(f"Failed to resolve any nameserver IPs from: {nameservers}")

        self._ns_ips = ns_ips

    def resolve_once(self) -> list[str]:
        """DNS 조회를 1회 수행하고 모든 응답 IP를 반환한다.

        매 호출마다 새로운 UDP 패킷을 전송하여 캐시 영향을 완전히 배제한다.
        권한 NS를 랜덤 선택하여 부하를 분산한다.

        Returns:
            IP 주소 리스트. 실패 시 빈 리스트.
        """
        try:
            qname = dns.name.from_text(self._record_name)
            rdtype = dns.rdatatype.from_text(self._query_type)
            request = dns.message.make_query(qname, rdtype)
            # RD(Recursion Desired) 비활성화 - 권한 NS에 직접 질의
            request.flags &= ~dns.flags.RD

            ns_ip = random.choice(self._ns_ips)
            response = dns.query.udp(request, ns_ip, timeout=5.0)

            ips: list[str] = []
            for rrset in response.answer:
                for rdata in rrset:
                    ips.append(str(rdata).rstrip("."))
            return ips
        except Exception:
            return []


@dataclass
class AliasResolution:
    """ALIAS 대상별 해석 결과."""

    # SetIdentifier → {alias_dns, resolved IPs}
    targets: dict[str, AliasTarget] = field(default_factory=dict)
    # IP → SetIdentifier 매핑
    ip_map: dict[str, str] = field(default_factory=dict)
    # IP set (frozenset) → SetIdentifier 매핑
    ip_set_map: dict[frozenset[str], str] = field(default_factory=dict)
    # 경고 메시지
    warnings: list[str] = field(default_factory=list)
    # 구분 불가 여부
    indistinguishable: bool = False


@dataclass
class AliasTarget:
    """개별 ALIAS 대상."""

    set_identifier: str
    alias_dns: str
    ips: list[str] = field(default_factory=list)


def resolve_alias_targets(
    records: list,  # list[WeightedRecord] - 순환 import 방지
) -> AliasResolution:
    """ALIAS 레코드의 대상을 해석하고 IP 매핑을 구성한다.

    각 ALIAS 대상을 IP로 리졸브하여:
    1. IP → SetIdentifier 직접 매핑 (겹침 없을 때)
    2. IP-set → SetIdentifier 매핑 (겹침 시 fallback)
    3. 겹침/실패 감지 및 경고

    Returns:
        AliasResolution with mappings and diagnostics.
    """
    result = AliasResolution()
    resolver = dns.resolver.Resolver()

    # 각 ALIAS 대상 리졸브
    for rec in records:
        if rec.record_type != "ALIAS":
            continue
        for alias_dns in rec.values:
            ips: list[str] = []
            try:
                answers = resolver.resolve(alias_dns, "A")
                ips = [str(rdata) for rdata in answers]
            except dns.resolver.DNSException:
                result.warnings.append(f"{rec.set_identifier}: {alias_dns} 리졸브 실패")
            result.targets[rec.set_identifier] = AliasTarget(
                set_identifier=rec.set_identifier,
                alias_dns=alias_dns,
                ips=ips,
            )

    # IP → SetIdentifier 매핑 구성 + 겹침 감지
    overlap_ips: set[str] = set()
    for sid, target in result.targets.items():
        ip_set = frozenset(target.ips)
        if ip_set:
            result.ip_set_map[ip_set] = sid
        for ip in target.ips:
            if ip in result.ip_map and result.ip_map[ip] != sid:
                overlap_ips.add(ip)
            result.ip_map[ip] = sid

    if overlap_ips:
        # 어떤 identifier들이 겹치는지 파악
        overlapping_sids: set[str] = set()
        for ip in overlap_ips:
            for sid, target in result.targets.items():
                if ip in target.ips:
                    overlapping_sids.add(sid)

        # 모든 IP가 겹치면 구분 불가
        all_ips = {ip for t in result.targets.values() for ip in t.ips}
        if overlap_ips == all_ips:
            result.indistinguishable = True
            sids = ", ".join(sorted(overlapping_sids))
            result.warnings.append(
                f"모든 ALIAS 대상이 동일한 IP로 해석됩니다 ({sids}). "
                "DNS 응답만으로는 트래픽 분포를 구분할 수 없습니다."
            )
        else:
            result.warnings.append(
                f"일부 IP가 겹칩니다: {', '.join(sorted(overlapping_sids))}. "
                "분포 측정이 부정확할 수 있습니다."
            )

    return result

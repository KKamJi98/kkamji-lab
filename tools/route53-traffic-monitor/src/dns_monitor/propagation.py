"""DNS 전파 모니터링 모듈.

여러 공용 DNS 리졸버에 반복 질의하여 DNS 전파 상태를 추적한다.
Route53 가중치 모니터링(watch)과 달리 AWS 자격증명이 불필요하다.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import dns.message
import dns.name
import dns.query
import dns.rdatatype

from .stats import PropagationStats

DEFAULT_RESOLVERS: list[tuple[str, str]] = [
    ("8.8.8.8", "Google"),
    ("1.1.1.1", "Cloudflare"),
    ("9.9.9.9", "Quad9"),
    ("208.67.222.222", "OpenDNS"),
]


@dataclass
class PropagationConfig:
    """Propagation 모니터링 설정."""

    record_name: str
    resolvers: list[tuple[str, str]] = field(default_factory=lambda: list(DEFAULT_RESOLVERS))
    tps: int = 2
    record_type: str = "A"

    def __post_init__(self):
        if self.tps < 1:
            raise ValueError("TPS must be >= 1")
        if self.tps > 100:
            raise ValueError("TPS must be <= 100")


class PropagationResolver:
    """공용 DNS 리졸버에 재귀 질의를 수행한다.

    RD(Recursion Desired) 플래그를 활성화하여 공용 리졸버의 캐시/재귀 경로를 통해
    DNS 전파 상태를 측정한다.
    """

    def __init__(self, record_name: str, record_type: str = "A"):
        self._record_name = record_name
        self._query_type = record_type

    def resolve_one(self, resolver_ip: str, timeout: float = 5.0) -> list[str]:
        """단일 리졸버에 1회 질의하고 응답 값을 반환한다.

        Returns:
            응답 값 리스트 (IP 또는 CNAME). 실패 시 빈 리스트.
        """
        try:
            qname = dns.name.from_text(self._record_name)
            rdtype = dns.rdatatype.from_text(self._query_type)
            request = dns.message.make_query(qname, rdtype)
            # RD=1: 공용 리졸버에 재귀 질의 요청
            request.flags |= dns.flags.RD

            response = dns.query.udp(request, resolver_ip, timeout=timeout)

            values: list[str] = []
            for rrset in response.answer:
                for rdata in rrset:
                    values.append(str(rdata).rstrip("."))
            return values
        except Exception:
            return []


class PropagationProber:
    """TPS 속도로 모든 리졸버에 병렬 질의를 수행한다."""

    def __init__(
        self,
        config: PropagationConfig,
        stats: PropagationStats,
        resolver: PropagationResolver,
    ):
        self._config = config
        self._stats = stats
        self._resolver = resolver
        self._running = False

    async def run(self) -> None:
        """TPS 속도로 질의 루프를 실행한다."""
        self._running = True
        interval = 1.0 / self._config.tps
        loop = asyncio.get_event_loop()

        try:
            while self._running:
                start = time.monotonic()
                # 모든 리졸버에 병렬 질의
                tasks = [
                    loop.run_in_executor(None, self._probe_resolver, ip, label)
                    for ip, label in self._config.resolvers
                ]
                await asyncio.gather(*tasks)
                elapsed = time.monotonic() - start
                sleep_time = max(0, interval - elapsed)
                await asyncio.sleep(sleep_time)
        except asyncio.CancelledError:
            pass

    def _probe_resolver(self, resolver_ip: str, resolver_label: str) -> None:
        """단일 리졸버에 질의하고 결과를 stats에 기록한다."""
        t0 = time.monotonic()
        values = self._resolver.resolve_one(resolver_ip)
        latency = time.monotonic() - t0

        if not values:
            self._stats.record_error()
            return

        for value in values:
            self._stats.record_response(resolver_label, value, latency)

    def stop(self) -> None:
        """루프 중단."""
        self._running = False

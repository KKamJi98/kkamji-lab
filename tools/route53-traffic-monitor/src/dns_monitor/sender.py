"""비동기 DNS 조회 + HTTP 트래픽 생성 모듈."""

from __future__ import annotations

import asyncio
import time

import httpx

from .aws import WeightedRecord, build_value_to_identifier_map, get_weighted_records
from .config import MonitorConfig
from .resolver import AliasResolution, WeightedResolver, resolve_alias_targets
from .stats import Stats


class TrafficSender:
    """DNS 조회 기반 트래픽 분포 측정 + 선택적 HTTP 트래픽 생성."""

    def __init__(
        self,
        config: MonitorConfig,
        stats: Stats,
        records: list[WeightedRecord],
        resolver: WeightedResolver,
        alias_resolution: AliasResolution | None = None,
    ):
        self._config = config
        self._stats = stats
        self._records = records
        self._resolver = resolver
        self._running = False

        # value → SetIdentifier 매핑 (A/CNAME 직접 매칭)
        self._value_map = build_value_to_identifier_map(records)

        # ALIAS 레코드: IP 기반 매핑
        self._alias_resolution = alias_resolution or AliasResolution()

    def _identify(self, resolved_ips: list[str]) -> str | None:
        """DNS 응답 IP를 SetIdentifier로 매핑한다."""
        if not resolved_ips:
            return None

        first_ip = resolved_ips[0]

        # 1. 직접 매칭 (A, CNAME - value가 IP/DNS인 경우)
        if first_ip in self._value_map:
            return self._value_map[first_ip]

        # 2. ALIAS: IP-set 매칭 (겹침에 강건)
        response_set = frozenset(resolved_ips)
        if response_set in self._alias_resolution.ip_set_map:
            return self._alias_resolution.ip_set_map[response_set]

        # 3. ALIAS: 개별 IP 매칭 (fallback)
        if first_ip in self._alias_resolution.ip_map:
            return self._alias_resolution.ip_map[first_ip]

        return None

    async def run(self) -> None:
        """TPS 속도로 DNS 조회 루프를 실행한다."""
        self._running = True
        interval = 1.0 / self._config.tps
        http_client: httpx.AsyncClient | None = None

        if self._config.http_enabled:
            http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                follow_redirects=True,
                verify=False,
            )

        try:
            while self._running:
                start = time.monotonic()
                asyncio.ensure_future(self._probe_once(http_client))
                elapsed = time.monotonic() - start
                sleep_time = max(0, interval - elapsed)
                await asyncio.sleep(sleep_time)
        finally:
            if http_client:
                await http_client.aclose()

    async def _probe_once(self, http_client: httpx.AsyncClient | None) -> None:
        """DNS 조회 1회 + 선택적 HTTP 요청."""
        t0 = time.monotonic()
        resolved_ips = self._resolver.resolve_once()
        dns_latency = time.monotonic() - t0

        if not resolved_ips:
            self._stats.record_error()
            return

        identifier = self._identify(resolved_ips)
        if identifier is None:
            self._stats.record_error()
            return

        latency: float = dns_latency

        if http_client is not None:
            try:
                url = f"https://{resolved_ips[0]}"
                t0 = time.monotonic()
                await http_client.get(
                    url,
                    headers={"Host": self._config.record_name},
                )
                latency = time.monotonic() - t0
            except httpx.HTTPError:
                pass  # HTTP 실패는 무시, DNS 매핑은 유효

        self._stats.record_hit(identifier, latency)

    def stop(self) -> None:
        """루프 중단."""
        self._running = False

    def update_records(self, records: list[WeightedRecord]) -> None:
        """Route53 가중치 레코드 갱신 시 매핑을 업데이트한다."""
        self._records = records
        self._value_map = build_value_to_identifier_map(records)
        has_alias = any(r.record_type == "ALIAS" for r in records)
        if has_alias:
            self._alias_resolution = resolve_alias_targets(records)


async def poll_route53(
    config: MonitorConfig,
    sender: TrafficSender,
    records_ref: list[list[WeightedRecord]],
    interval: float = 30.0,
) -> None:
    """주기적으로 Route53 가중치 레코드를 갱신한다."""
    while True:
        await asyncio.sleep(interval)
        try:
            new_records = await asyncio.get_event_loop().run_in_executor(
                None,
                get_weighted_records,
                config.hosted_zone_id,
                config.record_name,
            )
            if new_records:
                records_ref[0] = new_records
                sender.update_records(new_records)
        except Exception:
            pass  # 갱신 실패는 무시, 기존 데이터 유지

"""Thread-safe 통계 수집 모듈."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass
class StatsSnapshot:
    """특정 시점의 통계 스냅샷 (display에 전달)."""

    total_requests: int
    distribution: dict[str, int]
    errors: int
    elapsed_seconds: float
    avg_latency_ms: float | None
    current_tps: float


class Stats:
    """Thread-safe 통계 컨테이너."""

    def __init__(self):
        self._lock = threading.Lock()
        self._total_requests: int = 0
        self._distribution: dict[str, int] = {}
        self._errors: int = 0
        self._start_time: float = time.monotonic()
        self._latencies: deque[float] = deque(maxlen=200)
        self._recent_timestamps: deque[float] = deque(maxlen=100)

    def record_hit(self, set_identifier: str, latency: float | None = None) -> None:
        """DNS 조회 결과를 기록한다."""
        now = time.monotonic()
        with self._lock:
            self._total_requests += 1
            self._distribution[set_identifier] = self._distribution.get(set_identifier, 0) + 1
            self._recent_timestamps.append(now)
            if latency is not None:
                self._latencies.append(latency)

    def record_error(self) -> None:
        """에러를 기록한다."""
        with self._lock:
            self._errors += 1
            self._total_requests += 1

    def get_snapshot(self) -> StatsSnapshot:
        """현재 상태의 스냅샷을 반환한다."""
        now = time.monotonic()
        with self._lock:
            elapsed = now - self._start_time
            avg_latency = None
            if self._latencies:
                avg_latency = sum(self._latencies) / len(self._latencies) * 1000  # ms

            # 최근 TPS 계산 (최근 타임스탬프 기반)
            current_tps = 0.0
            if len(self._recent_timestamps) >= 2:
                window = now - self._recent_timestamps[0]
                if window > 0:
                    current_tps = len(self._recent_timestamps) / window

            return StatsSnapshot(
                total_requests=self._total_requests,
                distribution=dict(self._distribution),
                errors=self._errors,
                elapsed_seconds=elapsed,
                avg_latency_ms=avg_latency,
                current_tps=current_tps,
            )


@dataclass
class PropagationSnapshot:
    """Propagation 모드의 통계 스냅샷."""

    total_queries: int
    overall_distribution: dict[str, int]  # IP → count
    resolver_distribution: dict[str, dict[str, int]]  # resolver_label → {IP → count}
    errors: int
    elapsed_seconds: float
    avg_latency_ms: float | None
    current_tps: float


class PropagationStats:
    """Propagation 모드 전용 Thread-safe 통계 컨테이너.

    리졸버별 × 응답 IP별 2차원 분포를 추적한다.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._total_queries: int = 0
        self._errors: int = 0
        self._start_time: float = time.monotonic()
        self._latencies: deque[float] = deque(maxlen=200)
        self._recent_timestamps: deque[float] = deque(maxlen=100)
        # 전체 IP 분포
        self._overall: dict[str, int] = {}
        # 리졸버별 IP 분포
        self._per_resolver: dict[str, dict[str, int]] = {}

    def record_response(
        self, resolver_label: str, response_ip: str, latency: float | None = None
    ) -> None:
        """DNS 응답을 기록한다."""
        now = time.monotonic()
        with self._lock:
            self._total_queries += 1
            self._recent_timestamps.append(now)
            if latency is not None:
                self._latencies.append(latency)
            # overall
            self._overall[response_ip] = self._overall.get(response_ip, 0) + 1
            # per-resolver
            if resolver_label not in self._per_resolver:
                self._per_resolver[resolver_label] = {}
            bucket = self._per_resolver[resolver_label]
            bucket[response_ip] = bucket.get(response_ip, 0) + 1

    def record_error(self) -> None:
        """에러를 기록한다."""
        with self._lock:
            self._errors += 1
            self._total_queries += 1

    def get_snapshot(self) -> PropagationSnapshot:
        """현재 상태의 스냅샷을 반환한다."""
        now = time.monotonic()
        with self._lock:
            elapsed = now - self._start_time
            avg_latency = None
            if self._latencies:
                avg_latency = sum(self._latencies) / len(self._latencies) * 1000

            current_tps = 0.0
            if len(self._recent_timestamps) >= 2:
                window = now - self._recent_timestamps[0]
                if window > 0:
                    current_tps = len(self._recent_timestamps) / window

            return PropagationSnapshot(
                total_queries=self._total_queries,
                overall_distribution=dict(self._overall),
                resolver_distribution={k: dict(v) for k, v in self._per_resolver.items()},
                errors=self._errors,
                elapsed_seconds=elapsed,
                avg_latency_ms=avg_latency,
                current_tps=current_tps,
            )

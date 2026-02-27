"""Async HTTP runner with fixed-TPS rate control."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import httpx

from swagger_loadgen.parser import Endpoint


@dataclass
class RequestResult:
    """Outcome of a single HTTP request."""

    url: str
    path: str
    status: int
    latency_ms: float
    error: str | None = None


@dataclass
class RunStats:
    """Accumulated results from a load test run."""

    results: list[RequestResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.error is None and r.status < 400)

    @property
    def failure_count(self) -> int:
        return self.total - self.success_count


class _TokenBucket:
    """Simple token-bucket rate limiter for fixed TPS."""

    def __init__(self, tps: float) -> None:
        self._interval = 1.0 / tps
        self._next_time = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if now < self._next_time:
                await asyncio.sleep(self._next_time - now)
            self._next_time = max(time.monotonic(), self._next_time) + self._interval


async def run_load(
    endpoints: list[Endpoint],
    tps: float,
    duration: float,
    headers: dict[str, str] | None = None,
    param_values: dict[str, str] | None = None,
    on_result: asyncio.Queue[RequestResult] | None = None,
) -> RunStats:
    """Fire GET requests at *tps* rate for *duration* seconds.

    Args:
        endpoints: Target endpoints (round-robin).
        tps: Requests per second.
        duration: Total run time in seconds.
        headers: Extra HTTP headers (auth, etc.).
        param_values: Path parameter substitution map.
        on_result: Optional queue for streaming results to a reporter.

    Returns:
        RunStats with all collected RequestResult entries.
    """
    if not endpoints:
        return RunStats()

    bucket = _TokenBucket(tps)
    stats = RunStats()
    deadline = time.monotonic() + duration
    idx = 0
    ep_count = len(endpoints)

    async with httpx.AsyncClient(
        headers=headers or {},
        timeout=httpx.Timeout(10.0),
        follow_redirects=True,
    ) as client:
        while time.monotonic() < deadline:
            await bucket.acquire()
            if time.monotonic() >= deadline:
                break

            ep = endpoints[idx % ep_count]
            idx += 1
            url = ep.resolve_url(param_values)

            t0 = time.monotonic()
            try:
                resp = await client.get(url)
                latency = (time.monotonic() - t0) * 1000
                result = RequestResult(
                    url=url,
                    path=ep.path,
                    status=resp.status_code,
                    latency_ms=latency,
                )
            except httpx.HTTPError as exc:
                latency = (time.monotonic() - t0) * 1000
                result = RequestResult(
                    url=url,
                    path=ep.path,
                    status=0,
                    latency_ms=latency,
                    error=str(exc),
                )

            stats.results.append(result)
            if on_result is not None:
                await on_result.put(result)

    return stats

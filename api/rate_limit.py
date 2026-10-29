from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    """In-process token bucket.

    v1 is single-process. Behind multiple workers this is per-worker, not a
    global limiter; use a shared store for a real deployment. The key is the
    direct client host; proxy headers are not trusted by default.
    """

    def __init__(
        self,
        *,
        per_minute: int,
        burst: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.capacity = max(1.0, float(burst))
        self.refill_per_second = max(1e-9, per_minute / 60.0)
        self.clock = clock
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> float | None:
        """Return None if allowed, or seconds until a token is available."""
        now = self.clock()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=self.capacity, updated=now)
                self._buckets[key] = bucket
            else:
                elapsed = max(0.0, now - bucket.updated)
                bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self.refill_per_second)
                bucket.updated = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                self._prune(now)
                return None
            needed = 1.0 - bucket.tokens
            return max(0.01, needed / self.refill_per_second)

    def _prune(self, now: float) -> None:
        if len(self._buckets) <= 10_000:
            return
        stale = [
            key
            for key, bucket in self._buckets.items()
            if now - bucket.updated > 300 and bucket.tokens >= self.capacity
        ]
        for key in stale:
            self._buckets.pop(key, None)
        if len(self._buckets) > 20_000:
            # Hard cap; keep the most recently active half.
            ordered = sorted(self._buckets.items(), key=lambda item: item[1].updated, reverse=True)
            self._buckets = dict(ordered[:10_000])


def ceil_retry_after(seconds: float) -> int:
    return max(1, math.ceil(seconds))

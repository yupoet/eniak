"""Tiny in-process rate limiter.

We deliberately avoid pulling in slowapi/limits because a single-replica
backend with a known traffic shape doesn't need a distributed store. If we
scale horizontally we'll swap this for Redis-backed limits.

Limit format: ``"<n>/<unit>"`` where unit is ``second`` / ``minute`` / ``hour``.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock

_UNITS = {"second": 1, "minute": 60, "hour": 3600}


class RateLimitExceededError(Exception):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"Rate limit exceeded, retry in {retry_after:.1f}s")
        self.retry_after = retry_after


# Backwards-compatible alias for older import paths.
RateLimitExceeded = RateLimitExceededError


class SlidingWindowLimiter:
    def __init__(self, spec: str) -> None:
        n, unit = spec.split("/")
        self.limit = int(n)
        self.window = _UNITS[unit.strip().lower()]
        self._buckets: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                retry = bucket[0] - cutoff
                raise RateLimitExceeded(retry)
            bucket.append(now)

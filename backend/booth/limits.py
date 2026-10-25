"""Abuse protection for a public deployment: per-client rate limits, broadcast caps and a daily model budget.

Everything is in-memory, which is right for a single Container Apps replica. With more replicas each one
enforces its own limits, so divide the numbers by the replica count (or move them to a shared store).
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import Request


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass(frozen=True)
class LimitConfig:
    max_streams: int = 20
    max_streams_per_client: int = 2
    requests_per_minute: int = 30
    trust_proxy: bool = False
    stream_lease_s: float = 2 * 3600

    @classmethod
    def from_env(cls) -> LimitConfig:
        return cls(
            max_streams=_env_int("BOOTH_MAX_STREAMS", 20),
            max_streams_per_client=_env_int("BOOTH_MAX_STREAMS_PER_CLIENT", 2),
            requests_per_minute=_env_int("BOOTH_REQUESTS_PER_MINUTE", 30),
            trust_proxy=os.getenv("BOOTH_TRUST_PROXY", "false").lower() == "true",
        )


def client_id(request: Request, trust_proxy: bool) -> str:
    """The client address. Behind a proxy we trust (Container Apps ingress), use the address it appended
    last to X-Forwarded-For; earlier entries are supplied by the client and can be forged."""
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """Token bucket per client: ``per_minute`` tokens, refilled continuously."""

    def __init__(self, per_minute: int):
        self.capacity = float(per_minute)
        self.rate = per_minute / 60.0
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, cost: float = 1.0) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last) * self.rate)
            allowed = tokens >= cost
            self._buckets[key] = (tokens - cost if allowed else tokens, now)
            if len(self._buckets) > 10_000:
                self._prune(now)
            return allowed

    def _prune(self, now: float) -> None:
        idle = 2 * self.capacity / max(self.rate, 1e-9)
        for key, (_, last) in list(self._buckets.items()):
            if now - last > idle:
                del self._buckets[key]


@dataclass
class StreamSlots:
    """Caps concurrent broadcasts overall and per client. Leases expire, so a slot can never leak."""

    max_total: int
    max_per_client: int
    lease_s: float
    _leases: dict[str, tuple[str, float]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def acquire(self, client: str) -> str | None:
        now = time.monotonic()
        with self._lock:
            self._leases = {k: v for k, v in self._leases.items() if v[1] > now}
            if len(self._leases) >= self.max_total:
                return None
            if sum(1 for c, _ in self._leases.values() if c == client) >= self.max_per_client:
                return None
            lease = uuid.uuid4().hex
            self._leases[lease] = (client, now + self.lease_s)
            return lease

    def release(self, lease: str) -> None:
        with self._lock:
            self._leases.pop(lease, None)

    @property
    def active(self) -> int:
        now = time.monotonic()
        with self._lock:
            return sum(1 for _, expiry in self._leases.values() if expiry > now)


class DailyBudget:
    """At most ``limit`` units (model calls, speech characters) per UTC day (0 = unlimited)."""

    def __init__(self, limit: int):
        self.limit = limit
        self._day = self._today()
        self.used = 0
        self._lock = threading.Lock()

    @staticmethod
    def _today() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def _roll(self) -> None:
        today = self._today()
        if today != self._day:
            self._day, self.used = today, 0

    def take(self, amount: int = 1) -> bool:
        with self._lock:
            self._roll()
            if self.limit and self.used + amount > self.limit:
                return False
            self.used += amount
            return True

    def exhausted(self) -> bool:
        with self._lock:
            self._roll()
            return bool(self.limit) and self.used >= self.limit

    def status(self) -> dict:
        with self._lock:
            self._roll()
            return {"daily_limit": self.limit or None, "used_today": self.used}

from __future__ import annotations

import math
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class RateLimitDecision:
    limited: bool
    retry_after: int = 0


class LoginRateLimiter:
    """Bounded, single-process sliding-window limiter for failed logins."""

    def __init__(
        self,
        *,
        max_failures: int,
        window_seconds: int,
        max_clients: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if min(max_failures, window_seconds, max_clients) < 1:
            raise ValueError("Rate limit values must be greater than zero")
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self._clock = clock
        self._failures: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def check(self, client_key: str) -> RateLimitDecision:
        now = self._clock()
        with self._lock:
            failures = self._active_failures(client_key, now)
            if failures is None or len(failures) < self.max_failures:
                return RateLimitDecision(limited=False)
            retry_after = max(
                1,
                math.ceil(failures[0] + self.window_seconds - now),
            )
            return RateLimitDecision(limited=True, retry_after=retry_after)

    def record_failure(self, client_key: str) -> None:
        now = self._clock()
        with self._lock:
            failures = self._active_failures(client_key, now)
            if failures is None:
                self._remove_expired_clients(now)
                while len(self._failures) >= self.max_clients:
                    self._failures.popitem(last=False)
                failures = deque()
                self._failures[client_key] = failures
            failures.append(now)
            self._failures.move_to_end(client_key)

    def record_success(self, client_key: str) -> None:
        with self._lock:
            self._failures.pop(client_key, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()

    def _active_failures(
        self, client_key: str, now: float
    ) -> deque[float] | None:
        failures = self._failures.get(client_key)
        if failures is None:
            return None
        cutoff = now - self.window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if not failures:
            del self._failures[client_key]
            return None
        self._failures.move_to_end(client_key)
        return failures

    def _remove_expired_clients(self, now: float) -> None:
        for client_key in list(self._failures):
            self._active_failures(client_key, now)


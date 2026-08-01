"""Resilience primitives for the connector framework.

Three standalone, independently testable pieces that the base connector composes
around every provider call

* :class:`RetryPolicy` — bounded retries with exponential backoff + jitter
  gated on whether the raised error is retriable.
* :class:`CircuitBreaker`— CLOSED → OPEN → HALF_OPEN state machine that stops
  hammering a failing provider and probes for recovery.
* :class:`RateLimiter` — token-bucket limiter that smooths call volume.

All three take an injectable ``clock`` (monotonic seconds) and, where relevant
an injectable ``sleep`` so tests are fully deterministic and never wall-sleep.
"""

from __future__ import annotations

import threading
import time as _time
from typing import Callable, Optional

from backend.app.services.integrations.base.exceptions import (
    CircuitOpenError,
    ConnectorError,
    RateLimitError,
)


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------
class RetryPolicy:
    """Bounded retry with exponential backoff.

    A call is retried only when it raises a :class:`ConnectorError` whose
    ``retriable`` flag is true (or any exception when ``retry_all`` is set). The
    backoff for attempt *n* (1-indexed) is ``base * 2**(n-1)`` capped at
    ``max_backoff``, multiplied by a deterministic jitter factor.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_backoff: float = 0.05,
        max_backoff: float = 2.0,
        jitter: float = 0.0,
        retry_all: bool = False,
        sleep: Callable[[float], None] = _time.sleep,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.max_attempts = max_attempts
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self.jitter = jitter
        self.retry_all = retry_all
        self._sleep = sleep

    def backoff_for(self, attempt: int) -> float:
        """Backoff (seconds) before the given 1-indexed attempt's *retry*."""
        raw = self.base_backoff * (2 ** (attempt - 1))
        capped = min(raw, self.max_backoff)
        # Deterministic jitter: scale by a fixed factor derived from attempt.
        if self.jitter:
            capped += self.jitter * (attempt % 2)
        return capped

    def _should_retry(self, exc: Exception) -> bool:
        if self.retry_all:
            return True
        return isinstance(exc, ConnectorError) and exc.retriable

    def run(self, fn: Callable[[], object]) -> object:
        """Execute ``fn`` with retries. Returns its value or re-raises the last error."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 - retry decision made below
                last_exc = exc
                if attempt >= self.max_attempts or not self._should_retry(exc):
                    raise
                self._sleep(self.backoff_for(attempt))
        # Unreachable, but keeps type-checkers happy.
        assert last_exc is not None
        raise last_exc


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------
class CircuitState(str):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """A classic three-state circuit breaker.

    * **CLOSED** — calls flow; consecutive failures are counted. At
      ``failure_threshold`` the circuit trips OPEN.
    * **OPEN** — calls are short-circuited with :class:`CircuitOpenError` until
      ``recovery_timeout`` seconds elapse, then the circuit goes HALF_OPEN.
    * **HALF_OPEN** — a limited number of trial calls are allowed. Enough
      successes close it; any failure re-opens it.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 1,
        clock: Callable[[], float] = _time.monotonic,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self._clock = clock
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._successes = 0
        self._opened_at: Optional[float] = None

    @property
    def state(self) -> str:
        # Resolve a possible OPEN → HALF_OPEN transition on read.
        with self._lock:
            self._maybe_half_open()
            return self._state

    def _maybe_half_open(self) -> None:
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            if self._clock() - self._opened_at >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._successes = 0

    def allow(self) -> bool:
        """Whether a call may proceed right now."""
        with self._lock:
            self._maybe_half_open()
            return self._state != CircuitState.OPEN

    def record_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._successes += 1
                if self._successes >= self.success_threshold:
                    self._reset()
            else:
                self._failures = 0

    def record_failure(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._trip()
                return
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._trip()

    def _trip(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = self._clock()
        self._successes = 0

    def _reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._successes = 0
        self._opened_at = None

    def call(self, fn: Callable[[], object]) -> object:
        """Run ``fn`` under the breaker, raising :class:`CircuitOpenError` when open."""
        if not self.allow():
            raise CircuitOpenError("circuit breaker is open")
        try:
            result = fn()
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
class RateLimiter:
    """Token-bucket rate limiter.

    The bucket holds up to ``capacity`` tokens and refills at ``rate`` tokens
    per second. :meth:`acquire` consumes one token, returning ``True`` if one
    was available. :meth:`enforce` raises :class:`RateLimitError` instead.
    """

    def __init__(
        self,
        rate: float = 10.0,
        capacity: Optional[float] = None,
        clock: Callable[[], float] = _time.monotonic,
    ):
        if rate <= 0:
            raise ValueError("rate must be > 0")
        self.rate = rate
        self.capacity = capacity if capacity is not None else rate
        self._clock = clock
        self._tokens = float(self.capacity)
        self._last = clock()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = self._clock()
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last = now

    def acquire(self, tokens: float = 1.0) -> bool:
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def enforce(self, tokens: float = 1.0) -> None:
        if not self.acquire(tokens):
            raise RateLimitError("rate limit exceeded")

    @property
    def available(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens

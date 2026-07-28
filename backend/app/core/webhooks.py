"""Webhook delivery robustness (Phase 11, M10).

Complements the Phase-7 webhook subscription/emit store
(`services/integrations/apiplatform/webhooks.py`) with the delivery-robustness
primitives an enterprise webhook system needs:

* **Replay-proof signing** — Stripe-style `t=<ts>,v1=<hmac>` signatures over
  ``<timestamp>.<body>``; verification enforces a timestamp tolerance so a
  captured request cannot be replayed later.
* **Retry with exponential backoff** — a deterministic backoff schedule with a
  cap and max attempts.
* **Dispatcher** — drives send → retry-on-failure over a pluggable transport,
  records every attempt, and supports **replay** of a past event.

Transport is injected, so this is fully unit-testable and has no network
dependency of its own.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

SIGNATURE_HEADER = "X-Webhook-Signature"
DEFAULT_TOLERANCE_SECONDS = 300


# ===========================================================================
# Signing / verification (replay-protected)
# ===========================================================================
def _canonical(body: Any) -> str:
    if isinstance(body, (str, bytes)):
        return body.decode() if isinstance(body, bytes) else body
    return json.dumps(body, separators=(",", ":"), sort_keys=True, default=str)


def sign(secret: str, body: Any, *, timestamp: int | None = None) -> str:
    """Return a signature header value: ``t=<ts>,v1=<hex-hmac>``."""
    ts = int(timestamp if timestamp is not None else time.time())
    payload = f"{ts}.{_canonical(body)}".encode()
    mac = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


def verify(
    secret: str,
    body: Any,
    header: str,
    *,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    now: int | None = None,
) -> bool:
    """Constant-time verify a signature header and reject stale/replayed ones."""
    try:
        parts = dict(kv.split("=", 1) for kv in header.split(","))
        ts = int(parts["t"])
        provided = parts["v1"]
    except (ValueError, KeyError):
        return False
    current = int(now if now is not None else time.time())
    if abs(current - ts) > tolerance_seconds:
        return False  # outside tolerance window → treat as replay
    payload = f"{ts}.{_canonical(body)}".encode()
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


# ===========================================================================
# Retry policy
# ===========================================================================
@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 6
    base_delay_seconds: float = 1.0
    factor: float = 3.0
    max_delay_seconds: float = 3600.0

    def delay_for(self, attempt: int) -> float:
        """Backoff before ``attempt`` (1-indexed). attempt 1 -> 0 (immediate)."""
        if attempt <= 1:
            return 0.0
        delay = self.base_delay_seconds * (self.factor ** (attempt - 2))
        return min(delay, self.max_delay_seconds)

    def schedule(self) -> list[float]:
        return [self.delay_for(a) for a in range(1, self.max_attempts + 1)]


# ===========================================================================
# Dispatcher
# ===========================================================================
@dataclass
class DeliveryAttempt:
    attempt: int
    ok: bool
    status_code: int | None = None
    error: str | None = None


@dataclass
class DeliveryResult:
    event: str
    delivered: bool
    attempts: list[DeliveryAttempt] = field(default_factory=list)

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)


# Transport: (url, headers, body) -> HTTP status code. Raise to signal failure.
Transport = Callable[[str, dict[str, str], str], int]


class WebhookDispatcher:
    """Signs and delivers webhooks, retrying failures per :class:`RetryPolicy`."""

    def __init__(
        self,
        transport: Transport,
        *,
        policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._transport = transport
        self._policy = policy or RetryPolicy()
        self._sleep = sleep or (lambda _s: None)
        self._clock = clock

    def deliver(self, url: str, secret: str, event: str, payload: dict[str, Any]) -> DeliveryResult:
        body = _canonical({"event": event, "data": payload})
        result = DeliveryResult(event=event, delivered=False)
        for attempt in range(1, self._policy.max_attempts + 1):
            delay = self._policy.delay_for(attempt)
            if delay:
                self._sleep(delay)
            signature = sign(secret, body, timestamp=int(self._clock()))
            headers = {
                "Content-Type": "application/json",
                SIGNATURE_HEADER: signature,
                "X-Webhook-Event": event,
                "X-Webhook-Attempt": str(attempt),
            }
            try:
                status = self._transport(url, headers, body)
                if 200 <= status < 300:
                    result.attempts.append(DeliveryAttempt(attempt, ok=True, status_code=status))
                    result.delivered = True
                    return result
                result.attempts.append(DeliveryAttempt(attempt, ok=False, status_code=status))
            except Exception as exc:  # transport raised
                result.attempts.append(DeliveryAttempt(attempt, ok=False, error=str(exc)))
        return result

    def replay(self, url: str, secret: str, event: str, payload: dict[str, Any]) -> DeliveryResult:
        """Re-deliver a previously-emitted event (fresh signature/timestamp)."""
        return self.deliver(url, secret, event, payload)


__all__ = [
    "DEFAULT_TOLERANCE_SECONDS",
    "SIGNATURE_HEADER",
    "DeliveryAttempt",
    "DeliveryResult",
    "RetryPolicy",
    "Transport",
    "WebhookDispatcher",
    "sign",
    "verify",
]

"""Lightweight in-process TTL cache (Phase 5, Milestone 14).

A dependency-free cache for hot, slow-changing reads (reference config, catalogs).
Not a distributed cache — one per process — but enough to cut repeated DB hits
for values that change rarely. Thread-safe for the simple get/set/invalidate ops.

``monotonic`` time is injected so tests can advance the clock deterministically
(the workflow-runtime restrictions on ``time`` do not apply to app code, but we
keep it injectable for testability regardless).
"""

from __future__ import annotations

import threading
import time as _time
from typing import Any, Callable, Dict, Optional, Tuple


class TTLCache:
    def __init__(self, ttl_seconds: float = 60.0, clock: Callable[[], float] = _time.monotonic):
        self.ttl = ttl_seconds
        self._clock = clock
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if self._clock() >= expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        with self._lock:
            self._store[key] = (self._clock() + (ttl if ttl is not None else self.ttl), value)

    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: Optional[float] = None) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value, ttl=ttl)
        return value

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

"""Cache platform (Phase 8, Milestone 10).

A tenant-aware cache with a pluggable backend abstraction, TTLs, tag/prefix
invalidation, cache warming and hit/miss statistics. The default
:class:`MemoryCacheBackend` is in-process; :class:`RedisCacheBackend` is a stub
implementing the same interface so a distributed Redis cache can be dropped in
without touching call sites.

Tenant awareness: keys are namespaced ``t{tenant}:{key}`` (or ``global:{key}``)
so one tenant can never read or invalidate another tenant's entries. Callers use
the module-level helpers, which read the active tenant from the request context.
"""

from __future__ import annotations

import threading
import time as _time
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from backend.app.services.saas.context import current_tenant_id


class CacheBackend(Protocol):
    name: str

    def get(self, key: str) -> Tuple[bool, Any]: ...

    def set(self, key: str, value: Any, ttl: Optional[float]) -> None: ...

    def delete(self, key: str) -> None: ...

    def delete_prefix(self, prefix: str) -> int: ...

    def clear(self) -> None: ...

    def keys(self) -> List[str]: ...


class MemoryCacheBackend:
    name = "memory"

    def __init__(self, clock: Callable[[], float] = _time.monotonic):
        self._clock = clock
        self._store: Dict[str, Tuple[Optional[float], Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Tuple[bool, Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False, None
            expires_at, value = entry
            if expires_at is not None and self._clock() >= expires_at:
                self._store.pop(key, None)
                return False, None
            return True, value

    def set(self, key: str, value: Any, ttl: Optional[float]) -> None:
        with self._lock:
            self._store[key] = (self._clock() + ttl if ttl else None, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def delete_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                self._store.pop(k, None)
            return len(keys)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def keys(self) -> List[str]:
        with self._lock:
            return list(self._store)


class RedisCacheBackend:  # pragma: no cover - abstraction placeholder
    name = "redis"

    def __init__(self, url: Optional[str] = None):
        self.url = url

    def get(self, key): raise NotImplementedError("Redis cache not configured")
    def set(self, key, value, ttl): raise NotImplementedError("Redis cache not configured")
    def delete(self, key): raise NotImplementedError("Redis cache not configured")
    def delete_prefix(self, prefix): raise NotImplementedError("Redis cache not configured")
    def clear(self): raise NotImplementedError("Redis cache not configured")
    def keys(self): raise NotImplementedError("Redis cache not configured")


class CachePlatform:
    def __init__(self, backend: Optional[CacheBackend] = None, default_ttl: float = 60.0):
        self.backend: CacheBackend = backend or MemoryCacheBackend()
        self.default_ttl = default_ttl
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "invalidations": 0}
        self._lock = threading.Lock()

    def _namespaced(self, key: str, tenant_id: Optional[int]) -> str:
        tid = tenant_id if tenant_id is not None else current_tenant_id()
        scope = f"t{tid}" if tid is not None else "global"
        return f"{scope}:{key}"

    def get(self, key: str, *, tenant_id: Optional[int] = None) -> Optional[Any]:
        found, value = self.backend.get(self._namespaced(key, tenant_id))
        with self._lock:
            self._stats["hits" if found else "misses"] += 1
        return value if found else None

    def set(self, key: str, value: Any, *, ttl: Optional[float] = None,
            tenant_id: Optional[int] = None) -> None:
        self.backend.set(self._namespaced(key, tenant_id), value,
                         ttl if ttl is not None else self.default_ttl)
        with self._lock:
            self._stats["sets"] += 1

    def get_or_set(self, key: str, factory: Callable[[], Any], *,
                   ttl: Optional[float] = None, tenant_id: Optional[int] = None) -> Any:
        cached = self.get(key, tenant_id=tenant_id)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value, ttl=ttl, tenant_id=tenant_id)
        return value

    def invalidate(self, key: str, *, tenant_id: Optional[int] = None) -> None:
        self.backend.delete(self._namespaced(key, tenant_id))
        with self._lock:
            self._stats["invalidations"] += 1

    def invalidate_prefix(self, prefix: str, *, tenant_id: Optional[int] = None) -> int:
        count = self.backend.delete_prefix(self._namespaced(prefix, tenant_id))
        with self._lock:
            self._stats["invalidations"] += count
        return count

    def invalidate_tenant(self, tenant_id: int) -> int:
        """Flush an entire tenant's cache namespace."""
        count = self.backend.delete_prefix(f"t{tenant_id}:")
        with self._lock:
            self._stats["invalidations"] += count
        return count

    def warm(self, entries: List[Tuple[str, Any]], *, ttl: Optional[float] = None,
             tenant_id: Optional[int] = None) -> int:
        for key, value in entries:
            self.set(key, value, ttl=ttl, tenant_id=tenant_id)
        return len(entries)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total) if total else 0.0
            return {**self._stats, "hit_rate": round(hit_rate, 4),
                    "backend": self.backend.name, "size": len(self.backend.keys())}

    def clear(self) -> None:
        self.backend.clear()


# The process-wide cache. Swap the backend for Redis in production via
# ``platform_cache.backend = RedisCacheBackend(url)``.
platform_cache = CachePlatform()

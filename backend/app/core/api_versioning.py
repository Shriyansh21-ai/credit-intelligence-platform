"""API versioning & lifecycle (Phase 11, M10).

A small, framework-agnostic version registry plus a Starlette middleware that
advertises API lifecycle state on every response using the IETF standard
headers (`Deprecation`, `Sunset`, and a `Link rel="deprecation"` to the docs).

This is additive: existing unversioned routes keep working. New/public routes
opt into a version by prefix (``/api/v1/...``) and inherit lifecycle metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class VersionStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"  # past sunset date — should be refused by the gateway


@dataclass(frozen=True)
class APIVersion:
    name: str  # e.g. "v1"
    status: VersionStatus = VersionStatus.ACTIVE
    deprecated_on: date | None = None
    sunset_on: date | None = None
    docs_url: str = "/docs"

    def is_sunset(self, *, on: date | None = None) -> bool:
        ref = on or _today()
        return self.sunset_on is not None and ref >= self.sunset_on

    def is_deprecated(self, *, on: date | None = None) -> bool:
        if self.status in (VersionStatus.DEPRECATED, VersionStatus.SUNSET):
            return True
        ref = on or _today()
        return self.deprecated_on is not None and ref >= self.deprecated_on


def _today() -> date:
    # Indirection kept tiny so tests can monkeypatch the clock.
    return datetime.now(UTC).date()


class VersionRegistry:
    """Holds the API's declared versions and their lifecycle state."""

    def __init__(self) -> None:
        self._versions: dict[str, APIVersion] = {}
        self._current: str | None = None

    def register(self, version: APIVersion, *, current: bool = False) -> None:
        self._versions[version.name] = version
        if current or self._current is None:
            self._current = version.name

    def get(self, name: str) -> APIVersion | None:
        return self._versions.get(name)

    @property
    def current(self) -> str | None:
        return self._current

    def all(self) -> dict[str, APIVersion]:
        return dict(self._versions)

    def extract_version(self, path: str) -> str | None:
        """Return the version segment of an ``/api/<v>/...`` path, if any."""
        parts = [p for p in path.split("/") if p]
        for i, part in enumerate(parts):
            if part == "api" and i + 1 < len(parts) and parts[i + 1] in self._versions:
                return parts[i + 1]
        return None


# Default registry: v1 is current/active. Newer versions register here as they
# ship; older ones flip to DEPRECATED with dates, then SUNSET.
registry = VersionRegistry()
registry.register(APIVersion("v1", status=VersionStatus.ACTIVE), current=True)


class APIVersionMiddleware(BaseHTTPMiddleware):
    """Stamps lifecycle headers for versioned requests.

    * `X-API-Version` — the resolved version (or the current default).
    * `Deprecation: true` + `Sunset: <RFC1123-ish date>` when applicable.
    * `Link: <docs>; rel="deprecation"` pointing at migration docs.
    """

    def __init__(self, app, version_registry: VersionRegistry | None = None) -> None:
        super().__init__(app)
        self._registry = version_registry or registry

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        name = self._registry.extract_version(request.url.path) or self._registry.current
        if not name:
            return response
        version = self._registry.get(name)
        response.headers.setdefault("X-API-Version", name)
        if version and version.is_deprecated():
            response.headers["Deprecation"] = "true"
            if version.sunset_on:
                response.headers["Sunset"] = version.sunset_on.isoformat()
            response.headers["Link"] = f'<{version.docs_url}>; rel="deprecation"'
        return response


__all__ = [
    "APIVersion",
    "APIVersionMiddleware",
    "VersionRegistry",
    "VersionStatus",
    "registry",
]

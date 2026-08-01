"""Config-driven connector registry.

Providers register a factory under a logical connector key (e.g. ``"gst"``) and
a :class:`ProviderMode`. Callers ask the registry to *create* a connector for a
key; the active mode comes from configuration (a ``ConnectorConfig`` row, or the
supplied default), so switching mock → sandbox → production is a config change
with no code edits and no tight coupling to any single provider.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Union

from backend.app.services.integrations.base.connector import BaseConnector
from backend.app.services.integrations.base.exceptions import ConfigurationError
from backend.app.services.integrations.base.types import ConnectorCategory, ProviderMode

ConnectorFactory = Callable[..., BaseConnector]


class ConnectorRegistry:
    def __init__(self) -> None:
        # key -> mode -> factory
        self._factories: Dict[str, Dict[ProviderMode, ConnectorFactory]] = {}
        # key -> category (for discovery / grouping)
        self._categories: Dict[str, ConnectorCategory] = {}

    def register(
        self,
        key: str,
        mode: Union[ProviderMode, str],
        factory: ConnectorFactory,
        *,
        category: Optional[ConnectorCategory] = None,
    ) -> None:
        mode = ProviderMode(mode) if not isinstance(mode, ProviderMode) else mode
        self._factories.setdefault(key, {})[mode] = factory
        if category is not None:
            self._categories[key] = category

    def is_registered(self, key: str, mode: Optional[Union[ProviderMode, str]] = None) -> bool:
        if key not in self._factories:
            return False
        if mode is None:
            return True
        mode = ProviderMode(mode) if not isinstance(mode, ProviderMode) else mode
        return mode in self._factories[key]

    def modes(self, key: str) -> List[str]:
        return [m.value for m in self._factories.get(key, {})]

    def keys(self) -> List[str]:
        return sorted(self._factories.keys())

    def category_of(self, key: str) -> Optional[str]:
        cat = self._categories.get(key)
        return cat.value if cat else None

    def create(
        self,
        key: str,
        mode: Union[ProviderMode, str] = ProviderMode.MOCK,
        **kwargs: Any,
    ) -> BaseConnector:
        if key not in self._factories:
            raise ConfigurationError(f"no connector registered for key '{key}'")
        mode = ProviderMode(mode) if not isinstance(mode, ProviderMode) else mode
        factories = self._factories[key]
        if mode not in factories:
            available = ", ".join(m.value for m in factories) or "none"
            raise ConfigurationError(
                f"connector '{key}' has no '{mode.value}' provider (available: {available})"
            )
        # Forward the resolved mode so the instance's ``self.mode`` matches the
        # provider that was selected (otherwise it would default to MOCK).
        kwargs.setdefault("mode", mode)
        return factories[mode](**kwargs)

    def describe(self) -> List[Dict[str, Any]]:
        """A catalog of registered connectors for discovery endpoints."""
        out: List[Dict[str, Any]] = []
        for key in self.keys():
            out.append({
                "key": key,
                "category": self.category_of(key),
                "modes": self.modes(key),
            })
        return out


# Process-wide default registry. Domain packages register on import.
registry = ConnectorRegistry()

"""Provider selection.

Resolves the active :class:`DataProvider` from the ``DATA_PROVIDER`` setting so
the rest of the platform never hardcodes a source. Providers are instantiated
lazily and cached per name.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from backend.app.core.settings import get_settings
from backend.app.services.providers.base import DataProvider
from backend.app.services.providers.demo import DemoDataProvider
from backend.app.services.providers.production import (
    ProductionDataProvider,
    PublicDataProvider,
)

# name -> factory. Register new providers here (or via register_provider()).
_FACTORIES: Dict[str, Callable[[], DataProvider]] = {
    "demo": DemoDataProvider,
    "public": PublicDataProvider,
    "production": ProductionDataProvider,
}

_INSTANCES: Dict[str, DataProvider] = {}


def register_provider(name: str, factory: Callable[[], DataProvider]) -> None:
    """Register (or override) a provider factory by name."""
    _FACTORIES[name.lower()] = factory
    _INSTANCES.pop(name.lower(), None)


def available_providers() -> List[str]:
    return sorted(_FACTORIES)


def get_data_provider(name: Optional[str] = None) -> DataProvider:
    """Return the provider named ``name`` (or the configured default).

    Falls back to the demo provider for an unknown name so the seed / demo
    flows always have a working source in development.
    """
    key = (name or get_settings().data_provider or "demo").lower()
    if key not in _FACTORIES:
        key = "demo"
    if key not in _INSTANCES:
        _INSTANCES[key] = _FACTORIES[key]()
    return _INSTANCES[key]

"""System Configuration service.

Database-driven configuration with a seeded default catalog. Nothing the admin
can tune is hardcoded in route logic — callers read via ``get_config``.
"""

from backend.app.services.config.catalog import CONFIG_DEFAULTS
from backend.app.services.config.service import (
    get_all_config,
    get_config,
    list_categories,
    set_config,
    sync_config,
)

__all__ = [
    "CONFIG_DEFAULTS",
    "get_config",
    "get_all_config",
    "set_config",
    "sync_config",
    "list_categories",
]

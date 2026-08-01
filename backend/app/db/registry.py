"""ORM model registry.

Importing this module imports every ORM model module under
``backend.app.models`` so that all SQLAlchemy mappers and their inter-model
relationships (e.g. ``User.user_roles``) are registered on ``Base.metadata``.

The FastAPI app registers models via its own explicit import block in
``main.py``; standalone processes (the worker and scheduler) have no such block
so they import this instead. Using package introspection keeps the registry
complete automatically as new model modules are added.
"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import List

from backend.app import models as _models_pkg

# Modules in the models package that are NOT ORM model definitions.
_EXCLUDE = {"schemas"}


def import_all_models() -> List[ModuleType]:
    """Import every ORM model module; return the list of imported modules."""
    imported: List[ModuleType] = []
    for module_info in pkgutil.iter_modules(_models_pkg.__path__):
        name = module_info.name
        if name.startswith("_") or name in _EXCLUDE:
            continue
        imported.append(importlib.import_module(f"{_models_pkg.__name__}.{name}"))
    return imported


# Import eagerly on module import so a simple ``import ...db.registry`` is enough.
import_all_models()

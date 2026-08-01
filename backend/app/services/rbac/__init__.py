"""Role-Based Access Control.

Enterprise RBAC for the Credit Decision Platform. Roles and permissions are
fully **database-driven** (see :mod:`catalog` for the canonical seed data and
:mod:`seeding` for the idempotent sync used by migrations and tests).

Public surface
    - ``require_permission(code)`` / ``require_any_permission(*codes)`` — FastAPI
      dependencies that enforce a permission on the current user.
    - ``user_permission_codes(db, user)`` — the effective permission set.
    - ``has_permission(db, user, code)`` — boolean check.
    - ``sync_rbac(db)`` — upsert catalog into the DB (idempotent).
    - ``assign_role`` / ``ensure_user_role`` — grant a role to a user.
"""

from backend.app.services.rbac.access import (
    has_permission,
    require_any_permission,
    require_permission,
    user_permission_codes,
    user_role_names,
)
from backend.app.services.rbac.seeding import (
    assign_role,
    ensure_user_role,
    sync_rbac,
)

__all__ = [
    "has_permission",
    "require_any_permission",
    "require_permission",
    "user_permission_codes",
    "user_role_names",
    "assign_role",
    "ensure_user_role",
    "sync_rbac",
]

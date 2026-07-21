"""Idempotent RBAC seeding.

``sync_rbac`` upserts the catalog (:mod:`catalog`) into the database. It is safe
to call repeatedly — on every run it inserts anything missing and re-syncs each
role's permission set. Used by the RBAC migration, the app bootstrap, and tests.
"""

from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from backend.app.models.rbac import Permission, Role
from backend.app.models.user import User
from backend.app.services.rbac import catalog


def sync_rbac(db: Session) -> None:
    """Ensure every catalog permission and role exists, with correct mappings."""
    # 1) Permissions
    existing_perms = {p.code: p for p in db.query(Permission).all()}
    for code, category, description in catalog.PERMISSIONS:
        perm = existing_perms.get(code)
        if perm is None:
            perm = Permission(code=code, category=category, description=description)
            db.add(perm)
            existing_perms[code] = perm
        else:
            perm.category = category
            perm.description = description
    db.flush()

    # 2) Roles
    existing_roles = {r.name: r for r in db.query(Role).all()}
    for name, display_name, description in catalog.ROLES:
        role = existing_roles.get(name)
        if role is None:
            role = Role(name=name, display_name=display_name, description=description)
            db.add(role)
            existing_roles[name] = role
        else:
            role.display_name = display_name
            role.description = description
    db.flush()

    # 3) Role -> permission mappings
    for name, role in existing_roles.items():
        wanted = set(catalog.resolved_role_permissions(name))
        role.permissions = [existing_perms[c] for c in wanted if c in existing_perms]
    db.commit()


def _get_role(db: Session, role_name: str) -> Role:
    role = db.query(Role).filter(Role.name == role_name).first()
    if role is None:
        raise ValueError(f"Unknown role: {role_name!r}")
    return role


def assign_role(db: Session, user: User, role_name: str, *, replace: bool = False) -> User:
    """Grant ``role_name`` to ``user``. With ``replace``, clears other roles."""
    role = _get_role(db, role_name)
    current = {r.name for r in user.roles}
    if replace:
        user.roles = [role]
    elif role.name not in current:
        user.roles.append(role)
    db.commit()
    db.refresh(user)
    return user


def ensure_user_role(db: Session, user: User, role_name: str) -> User:
    """Assign ``role_name`` only if the user currently has no roles at all."""
    if not user.roles:
        return assign_role(db, user, role_name)
    return user


def backfill_default_roles(db: Session, role_name: str | None = None) -> int:
    """Give every role-less user the backfill role. Returns count updated."""
    role_name = role_name or catalog.DEFAULT_BACKFILL_ROLE
    role = _get_role(db, role_name)
    updated = 0
    for user in db.query(User).all():
        if not user.roles:
            user.roles.append(role)
            updated += 1
    db.commit()
    return updated


def user_ids_without_roles(db: Session) -> Iterable[int]:
    return [u.id for u in db.query(User).all() if not u.roles]

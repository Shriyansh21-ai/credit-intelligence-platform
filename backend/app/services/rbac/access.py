"""RBAC enforcement — permission resolution and FastAPI dependencies.

``require_permission`` / ``require_any_permission`` return dependencies that load
the current user's effective permissions and raise 403 when the check fails.
Administrators (users holding a role that maps to ``"*"``) always pass.
"""

from __future__ import annotations

from typing import List, Set

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.user import User


def user_role_names(user: User) -> List[str]:
    return [r.name for r in user.roles]


def user_permission_codes(db: Session, user: User) -> Set[str]:
    """The union of every permission granted by the user's roles.

    ``db`` is accepted for API symmetry / future caching; the roles relationship
    already eager-loads permissions, so no extra query is issued here.
    """
    codes: Set[str] = set()
    for role in user.roles:
        for perm in role.permissions:
            codes.add(perm.code)
    return codes


def has_permission(db: Session, user: User, code: str) -> bool:
    return code in user_permission_codes(db, user)


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def require_permission(code: str):
    """Dependency factory: require a single permission ``code``."""

    def _dependency(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not has_permission(db, user, code):
            raise _forbidden(f"Missing required permission: {code}")
        return user

    return _dependency


def require_any_permission(*codes: str):
    """Dependency factory: require at least one of ``codes``."""

    def _dependency(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        granted = user_permission_codes(db, user)
        if not any(c in granted for c in codes):
            raise _forbidden("Missing required permission: one of " + ", ".join(codes))
        return user

    return _dependency

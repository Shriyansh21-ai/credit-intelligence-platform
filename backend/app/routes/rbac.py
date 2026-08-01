"""RBAC administration API.

    GET /api/rbac/permissions list all permissions (grouped-ready)
    GET /api/rbac/roles list roles with their permission codes
    GET /api/rbac/me current user's roles + effective permissions
    GET /api/rbac/users/{user_id}/roles a user's roles + permissions
    POST /api/rbac/users/{user_id}/roles assign a role (users.manage)
    PUT /api/rbac/users/{user_id}/roles replace a user's role set (users.manage)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.models.rbac import Permission, Role
from backend.app.models.user import User
from backend.app.schemas.rbac import (
    AssignRoleRequest,
    PermissionOut,
    RoleOut,
    SetRolesRequest,
    UserRolesOut,
)
from backend.app.services import audit
from backend.app.services.rbac import (
    require_permission,
    user_permission_codes,
    user_role_names,
)
from backend.app.services.rbac.seeding import assign_role

router = APIRouter(prefix="/api/rbac", tags=["RBAC"])


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("roles.manage")),
):
    perms = db.query(Permission).order_by(Permission.category, Permission.code).all()
    return [
        PermissionOut(code=p.code, category=p.category, description=p.description)
        for p in perms
    ]


@router.get("/roles", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("roles.manage")),
):
    roles = db.query(Role).order_by(Role.name).all()
    return [
        RoleOut(
            id=r.id,
            name=r.name,
            display_name=r.display_name,
            description=r.description,
            permissions=sorted(p.code for p in r.permissions),
        )
        for r in roles
    ]


@router.get("/me", response_model=UserRolesOut)
def my_access(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return UserRolesOut(
        user_id=user.id,
        email=user.email,
        roles=sorted(user_role_names(user)),
        permissions=sorted(user_permission_codes(db, user)),
    )


def _user_or_404(db: Session, user_id: int) -> User:
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return target


@router.get("/users/{user_id}/roles", response_model=UserRolesOut)
def get_user_roles(
    user_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("users.manage")),
):
    target = _user_or_404(db, user_id)
    return UserRolesOut(
        user_id=target.id,
        email=target.email,
        roles=sorted(user_role_names(target)),
        permissions=sorted(user_permission_codes(db, target)),
    )


@router.post("/users/{user_id}/roles", response_model=UserRolesOut)
def add_user_role(
    user_id: int,
    request: AssignRoleRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("users.manage")),
):
    target = _user_or_404(db, user_id)
    before = sorted(user_role_names(target))
    try:
        assign_role(db, target, request.role, replace=request.replace)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    after = sorted(user_role_names(target))
    audit.record(
        db,
        actor=actor,
        action="rbac.assign_role",
        entity_type="user",
        entity_id=target.id,
        previous_value={"roles": before},
        new_value={"roles": after},
        reason=f"Assigned role {request.role}",
    )
    return UserRolesOut(
        user_id=target.id,
        email=target.email,
        roles=after,
        permissions=sorted(user_permission_codes(db, target)),
    )


@router.put("/users/{user_id}/roles", response_model=UserRolesOut)
def set_user_roles(
    user_id: int,
    request: SetRolesRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("users.manage")),
):
    target = _user_or_404(db, user_id)
    before = sorted(user_role_names(target))
    roles = []
    for name in request.roles:
        role = db.query(Role).filter(Role.name == name).first()
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown role: {name}"
            )
        roles.append(role)
    target.roles = roles
    db.commit()
    db.refresh(target)
    after = sorted(user_role_names(target))
    audit.record(
        db,
        actor=actor,
        action="rbac.set_roles",
        entity_type="user",
        entity_id=target.id,
        previous_value={"roles": before},
        new_value={"roles": after},
        reason="Replaced role set",
    )
    return UserRolesOut(
        user_id=target.id,
        email=target.email,
        roles=after,
        permissions=sorted(user_permission_codes(db, target)),
    )

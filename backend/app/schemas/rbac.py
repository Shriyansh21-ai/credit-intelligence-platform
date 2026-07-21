"""Pydantic schemas for the RBAC API (Phase 5, Milestone 3)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class PermissionOut(BaseModel):
    code: str
    category: str
    description: Optional[str] = None


class RoleOut(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    permissions: List[str] = []


class UserRolesOut(BaseModel):
    user_id: int
    email: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []


class AssignRoleRequest(BaseModel):
    role: str
    replace: bool = False


class SetRolesRequest(BaseModel):
    roles: List[str]

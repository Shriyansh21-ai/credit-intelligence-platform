"""RBAC persistence models (Phase 5, Milestone 3).

Roles and permissions are stored in the database and linked many-to-many via
association tables, so access control is fully data-driven rather than hardcoded.

    users ──< user_roles >── roles ──< role_permissions >── permissions
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.app.db.database import Base

# --- Association tables -----------------------------------------------------

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, nullable=False, unique=True, index=True)
    category = Column(String, nullable=False, default="General")
    description = Column(String, nullable=True)

    roles = relationship(
        "Role", secondary=role_permissions, back_populates="permissions"
    )


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    display_name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    permissions = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin",
    )
    users = relationship(
        "User", secondary=user_roles, back_populates="roles"
    )

    __table_args__ = (UniqueConstraint("name", name="uq_roles_name"),)

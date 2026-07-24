"""Feature-flag persistence (Phase 8, Milestone 5).

A global flag registry (:class:`FeatureFlag`) plus per-scope overrides
(:class:`FeatureFlagOverride`). Evaluation supports global on/off, tenant and
role targeting, percentage/canary rollout, experimental flags, expiration and
prerequisite dependencies — resolved in ``services/saas/flags``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint,
)

from backend.app.db.database import Base


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    # Default state when no override matches.
    enabled = Column(Boolean, nullable=False, default=False)
    # Rollout across the whole population, 0..100. Deterministic per (flag, tenant).
    rollout_percentage = Column(Float, nullable=False, default=0.0)
    kind = Column(String, nullable=False, default="release")  # release|experimental|canary|ops|permission
    # Roles the flag is limited to (empty = all roles).
    target_roles = Column(JSON, nullable=False, default=list)
    # Prerequisite flag keys that must be ON for this flag to evaluate ON.
    dependencies = Column(JSON, nullable=False, default=list)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FeatureFlagOverride(Base):
    """Explicit per-tenant (or per-org) override that wins over the global flag."""

    __tablename__ = "feature_flag_overrides"
    __table_args__ = (
        UniqueConstraint("flag_key", "tenant_id", name="uq_flag_override_tenant"),
    )

    id = Column(Integer, primary_key=True, index=True)
    flag_key = Column(String, ForeignKey("feature_flags.key"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    enabled = Column(Boolean, nullable=False, default=True)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

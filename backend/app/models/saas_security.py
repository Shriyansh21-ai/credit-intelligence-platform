"""Enterprise security persistence.

Additive, tenant-scoped tables for session management, device tracking, IP
allow-lists, secret references (secrets are stored by reference, never in
plaintext), and identity-provider configuration. MFA/SSO/SAML/OIDC/SCIM are
represented as *ready* abstractions: :class:`IdentityProviderConfig` captures
the configuration surface so a real IdP can be wired without a schema change.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text,
)

from backend.app.db.database import Base


class SecuritySession(Base):
    __tablename__ = "security_sessions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_token = Column(String, nullable=False, unique=True, index=True)
    device_id = Column(Integer, ForeignKey("security_devices.id"), nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")  # active|revoked|expired
    mfa_verified = Column(Boolean, nullable=False, default=False)
    expires_at = Column(DateTime, nullable=True)
    last_active_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class SecurityDevice(Base):
    __tablename__ = "security_devices"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    fingerprint = Column(String, nullable=False, index=True)
    name = Column(String, nullable=True)
    platform = Column(String, nullable=True)
    trusted = Column(Boolean, nullable=False, default=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class IpAllowEntry(Base):
    __tablename__ = "ip_allow_entries"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    cidr = Column(String, nullable=False)  # e.g. 203.0.113.0/24 or a single IP
    description = Column(String, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SecretRef(Base):
    """A reference to a secret held in an external manager (Vault/KMS/env).

    ``value_encrypted`` holds a local at-rest envelope only for the built-in
    provider; production deployments point ``manager`` at a real backend and the
    value lives there. Supports key rotation via ``version``.
    """

    __tablename__ = "secret_refs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    name = Column(String, nullable=False, index=True)
    manager = Column(String, nullable=False, default="local")  # local|vault|aws-kms|azure-kv|gcp-sm
    version = Column(Integer, nullable=False, default=1)
    value_encrypted = Column(Text, nullable=True)
    rotated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class IdentityProviderConfig(Base):
    """SSO/SAML/OIDC/SCIM-ready configuration for a tenant."""

    __tablename__ = "identity_provider_configs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    protocol = Column(String, nullable=False, default="oidc")  # oidc|saml|scim
    display_name = Column(String, nullable=True)
    enabled = Column(Boolean, nullable=False, default=False)
    # Non-secret config (issuer, entity id, ACS URL, attribute mappings).
    config = Column(JSON, nullable=False, default=dict)
    # Secret material stored by reference.
    client_secret_ref = Column(String, nullable=True)
    mfa_required = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

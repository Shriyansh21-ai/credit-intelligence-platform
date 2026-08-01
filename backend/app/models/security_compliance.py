"""Enterprise Security & Compliance persistence (Stage 4).

Additive, tenant-scoped tables that record the outputs of the security
programme: scan runs and their findings, compliance-framework assessments, the
enterprise risk register, privacy (DSAR) requests and point-in-time posture
snapshots. Everything is new — nothing from Stages 1-3 is modified.

Design notes
------------
* ``tenant_id`` is nullable on every table so the historical single-tenant
  deployment keeps working; multi-tenant deployments scope every row.
* Free-form structure (per-control results, gap lists, evidence) is stored in
  ``JSON`` columns so the schema is stable as catalogs evolve.
* Rows reference subjects by string ``*_ref`` fields rather than hard FKs so the
  module stays decoupled from the rest of the platform.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from backend.app.db.database import Base


class SecurityScan(Base):
    """One execution of a security assessment (threat/OWASP/supply-chain/...)."""

    __tablename__ = "sec_scans"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    scan_type = Column(String, nullable=False, index=True)  # owasp|threat|supply_chain|...
    status = Column(String, nullable=False, default="completed")  # running|completed|failed
    score = Column(Float, nullable=True)  # 0-100 posture score for this scan
    grade = Column(String, nullable=True)  # A+..F
    summary = Column(JSON, nullable=False, default=dict)
    findings_count = Column(Integer, nullable=False, default=0)
    critical_count = Column(Integer, nullable=False, default=0)
    high_count = Column(Integer, nullable=False, default=0)
    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SecurityFinding(Base):
    """A single finding produced by a scan or a manual review."""

    __tablename__ = "sec_findings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    scan_id = Column(Integer, ForeignKey("sec_scans.id"), nullable=True, index=True)
    code = Column(String, nullable=False, index=True)  # stable machine id, e.g. OWASP-A01
    category = Column(String, nullable=False, index=True)  # domain: owasp|authz|tenant|...
    severity = Column(String, nullable=False, index=True)  # critical|high|medium|low|info
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False, default="")
    recommendation = Column(Text, nullable=False, default="")
    reference = Column(String, nullable=True)  # CWE / OWASP / control reference
    component = Column(String, nullable=True)  # affected component / file / area
    status = Column(String, nullable=False, default="open", index=True)  # open|acknowledged|resolved|accepted|false_positive
    evidence = Column(JSON, nullable=False, default=dict)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComplianceAssessment(Base):
    """A point-in-time assessment against a compliance framework."""

    __tablename__ = "sec_compliance_assessments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    framework = Column(String, nullable=False, index=True)  # soc2|iso27001|gdpr|pci_dss|rbi_dl|nist_csf
    version = Column(String, nullable=True)
    score = Column(Float, nullable=False, default=0.0)  # 0-100 readiness
    readiness = Column(String, nullable=False, default="not_ready")  # ready|substantial|partial|not_ready
    total_controls = Column(Integer, nullable=False, default=0)
    satisfied = Column(Integer, nullable=False, default=0)
    partial = Column(Integer, nullable=False, default=0)
    gaps = Column(Integer, nullable=False, default=0)
    results = Column(JSON, nullable=False, default=list)  # per-control result list
    gap_items = Column(JSON, nullable=False, default=list)
    assessed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class RiskRegisterEntry(Base):
    """An entry in the enterprise security risk register."""

    __tablename__ = "sec_risk_register"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)  # threat category
    description = Column(Text, nullable=False, default="")
    likelihood = Column(Integer, nullable=False, default=3)  # 1-5
    impact = Column(Integer, nullable=False, default=3)  # 1-5
    inherent_score = Column(Integer, nullable=False, default=9)  # likelihood*impact
    treatment = Column(String, nullable=False, default="mitigate")  # mitigate|accept|transfer|avoid
    residual_likelihood = Column(Integer, nullable=False, default=2)
    residual_impact = Column(Integer, nullable=False, default=2)
    residual_score = Column(Integer, nullable=False, default=4)
    mitigations = Column(JSON, nullable=False, default=list)
    owner = Column(String, nullable=True)
    status = Column(String, nullable=False, default="open", index=True)  # open|mitigating|closed|accepted
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PrivacyRequest(Base):
    """A data-subject privacy request (access / erasure / rectification / export)."""

    __tablename__ = "sec_privacy_requests"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    subject_ref = Column(String, nullable=False, index=True)  # subject identifier (masked in logs)
    request_type = Column(String, nullable=False, index=True)  # access|erasure|rectification|portability|restriction|objection
    status = Column(String, nullable=False, default="received", index=True)  # received|verifying|in_progress|completed|rejected
    legal_basis = Column(String, nullable=True)
    notes = Column(Text, nullable=False, default="")
    due_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PostureSnapshot(Base):
    """A point-in-time snapshot of the overall security posture score."""

    __tablename__ = "sec_posture_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    overall_score = Column(Float, nullable=False, default=0.0)
    grade = Column(String, nullable=False, default="F")
    dimensions = Column(JSON, nullable=False, default=dict)  # per-domain scores
    open_findings = Column(Integer, nullable=False, default=0)
    open_critical = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SecretAuditRecord(Base):
    """Metadata about a managed secret (never the secret value itself)."""

    __tablename__ = "sec_secret_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_sec_secret_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    name = Column(String, nullable=False, index=True)  # logical name, e.g. JWT_SECRET_KEY
    provider = Column(String, nullable=False, default="env")  # env|file|aws|vault
    version = Column(Integer, nullable=False, default=1)
    rotated_at = Column(DateTime, nullable=True)
    rotation_interval_days = Column(Integer, nullable=False, default=90)
    strong = Column(Boolean, nullable=False, default=True)  # passes strength policy
    status = Column(String, nullable=False, default="active")  # active|stale|weak|missing
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


__all__ = [
    "ComplianceAssessment",
    "PostureSnapshot",
    "PrivacyRequest",
    "RiskRegisterEntry",
    "SecretAuditRecord",
    "SecurityFinding",
    "SecurityScan",
]

"""Compliance toolkit.

Framework-agnostic abstractions that map the platform's *actual* technical
controls (built across M5-M11) to the requirements of the major frameworks a
Tier-1 bank must satisfy, and provide the operational machinery for privacy
rights and evidence collection

* Frameworks & control mapping — SOC 2, ISO 27001, PCI DSS, GDPR, RBI. The
  :data:`control_catalog` maps internal control ids to framework requirement ids
  with an implementation status, so a coverage report is derivable, not asserted.
* Consent management (:class:`ConsentLedger`) — purpose-scoped, versioned
  auditable grant/withdraw with point-in-time lookup (GDPR Art. 6/7).
* Data residency (:class:`ResidencyPolicy`) — allowed regions per data category.
* Data subject rights — :class:`DataExporter` (portability / DSAR, Art. 15/20)
  and :class:`DataEraser` (erasure / "right to be forgotten", Art. 17) over
  pluggable per-source collectors.
* Evidence collection + compliance reports — assemble auditor-ready evidence and
  a per-framework coverage report; audit-log export.

Pure, dependency-light, and fully unit-testable (clocks/collectors injected).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class Framework(StrEnum):
    SOC2 = "SOC2"
    ISO27001 = "ISO27001"
    PCI_DSS = "PCI_DSS"
    GDPR = "GDPR"
    RBI = "RBI"


class ControlStatus(StrEnum):
    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    PLANNED = "planned"
    NOT_APPLICABLE = "not_applicable"


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ===========================================================================
# Control catalogue + framework mapping
# ===========================================================================
@dataclass(frozen=True)
class Control:
    """An internal technical control and the framework requirements it satisfies."""

    id: str
    title: str
    status: ControlStatus
    evidence_hint: str
    mappings: dict[Framework, tuple[str, ...]] = field(default_factory=dict)

    def covers(self, framework: Framework) -> tuple[str, ...]:
        return self.mappings.get(framework, ())


# Real mappings from controls delivered in (M5-M11) to framework refs.
control_catalog: list[Control] = [
    Control(
        "access-control-rbac",
        "RBAC + least privilege",
        ControlStatus.IMPLEMENTED,
        "services/rbac + audit of grants",
        {
            Framework.SOC2: ("CC6.1", "CC6.3"),
            Framework.ISO27001: ("A.9.1", "A.9.2"),
            Framework.PCI_DSS: ("7.1", "7.2"),
            Framework.RBI: ("access-control",),
        },
    ),
    Control(
        "mfa",
        "Multi-factor authentication",
        ControlStatus.IMPLEMENTED,
        "core/authn.Totp + risk-based step-up",
        {
            Framework.SOC2: ("CC6.1",),
            Framework.ISO27001: ("A.9.4",),
            Framework.PCI_DSS: ("8.4", "8.5"),
            Framework.RBI: ("mfa",),
        },
    ),
    Control(
        "encryption-at-rest",
        "Field-level + storage encryption (AES-GCM/KMS)",
        ControlStatus.IMPLEMENTED,
        "core/crypto.FieldCipher + KMS (terraform)",
        {
            Framework.SOC2: ("CC6.7",),
            Framework.ISO27001: ("A.10.1",),
            Framework.PCI_DSS: ("3.4", "3.5"),
            Framework.GDPR: ("Art.32",),
            Framework.RBI: ("data-encryption",),
        },
    ),
    Control(
        "encryption-in-transit",
        "TLS everywhere + HSTS",
        ControlStatus.IMPLEMENTED,
        "SecurityHeadersMiddleware + ALB/CloudFront TLS",
        {Framework.PCI_DSS: ("4.1",), Framework.ISO27001: ("A.13.1",), Framework.GDPR: ("Art.32",)},
    ),
    Control(
        "audit-logging",
        "Immutable audit trail",
        ControlStatus.IMPLEMENTED,
        "AuditMiddleware + audit model (7y retention)",
        {
            Framework.SOC2: ("CC7.2", "CC7.3"),
            Framework.ISO27001: ("A.12.4",),
            Framework.PCI_DSS: ("10.1", "10.2"),
            Framework.RBI: ("audit-trail",),
        },
    ),
    Control(
        "monitoring-alerting",
        "Observability, SLOs, alerting",
        ControlStatus.IMPLEMENTED,
        "telemetry + prometheus alerts (M7)",
        {Framework.SOC2: ("CC7.1",), Framework.ISO27001: ("A.12.1",), Framework.PCI_DSS: ("10.6",)},
    ),
    Control(
        "vuln-management",
        "SAST/DAST/dependency + secret scanning",
        ControlStatus.IMPLEMENTED,
        "security.yml pipeline (M5)",
        {
            Framework.SOC2: ("CC7.1",),
            Framework.ISO27001: ("A.12.6",),
            Framework.PCI_DSS: ("6.2", "11.2"),
        },
    ),
    Control(
        "backup-dr",
        "Backup, PITR, recovery drills",
        ControlStatus.IMPLEMENTED,
        "core/dr + backup CronJob (M11)",
        {
            Framework.SOC2: ("A1.2", "A1.3"),
            Framework.ISO27001: ("A.17.1",),
            Framework.RBI: ("bcp-dr",),
        },
    ),
    Control(
        "change-management",
        "PR review, CODEOWNERS, protected branches, CI gates",
        ControlStatus.IMPLEMENTED,
        "CI/CD + branch protection (M5)",
        {
            Framework.SOC2: ("CC8.1",),
            Framework.ISO27001: ("A.12.1.2",),
            Framework.PCI_DSS: ("6.4",),
        },
    ),
    Control(
        "data-retention",
        "Retention policies + secure deletion",
        ControlStatus.IMPLEMENTED,
        "core/crypto.RetentionRegistry + secure_overwrite",
        {
            Framework.GDPR: ("Art.5", "Art.17"),
            Framework.ISO27001: ("A.18.1",),
            Framework.RBI: ("data-retention",),
        },
    ),
    Control(
        "consent-management",
        "Purpose-scoped consent ledger",
        ControlStatus.IMPLEMENTED,
        "core/compliance.ConsentLedger",
        {Framework.GDPR: ("Art.6", "Art.7")},
    ),
    Control(
        "data-subject-rights",
        "Export (portability) + erasure",
        ControlStatus.IMPLEMENTED,
        "core/compliance.DataExporter/DataEraser",
        {Framework.GDPR: ("Art.15", "Art.17", "Art.20")},
    ),
    Control(
        "data-residency",
        "Region-pinned data storage",
        ControlStatus.IMPLEMENTED,
        "core/compliance.ResidencyPolicy + regional infra",
        {Framework.GDPR: ("Art.44",), Framework.RBI: ("data-localisation",)},
    ),
]


# ===========================================================================
# Compliance report
# ===========================================================================
def generate_report(
    framework: Framework, *, catalog: list[Control] | None = None
) -> dict[str, Any]:
    """Coverage report for a framework, derived from the control catalogue."""
    cat = catalog if catalog is not None else control_catalog
    relevant = [c for c in cat if framework in c.mappings]
    implemented = [c for c in relevant if c.status == ControlStatus.IMPLEMENTED]
    requirements: set[str] = set()
    for c in relevant:
        requirements.update(c.covers(framework))
    coverage = round(100 * len(implemented) / len(relevant), 1) if relevant else 0.0
    return {
        "framework": framework.value,
        "generated_at": _utcnow().isoformat(),
        "controls_total": len(relevant),
        "controls_implemented": len(implemented),
        "coverage_percent": coverage,
        "requirements_covered": sorted(requirements),
        "controls": [
            {
                "id": c.id,
                "title": c.title,
                "status": c.status.value,
                "requirements": list(c.covers(framework)),
                "evidence": c.evidence_hint,
            }
            for c in relevant
        ],
    }


def policy_matrix(*, catalog: list[Control] | None = None) -> dict[str, dict[str, list[str]]]:
    """Control → {framework: [requirement ids]} matrix for auditors."""
    cat = catalog if catalog is not None else control_catalog
    return {c.id: {fw.value: list(reqs) for fw, reqs in c.mappings.items()} for c in cat}


# ===========================================================================
# Consent management
# ===========================================================================
@dataclass(frozen=True)
class ConsentRecord:
    subject_id: str
    purpose: str
    granted: bool
    policy_version: str
    at: str


class ConsentLedger:
    """Append-only, purpose-scoped consent history with point-in-time lookup."""

    def __init__(self, clock: Callable[[], datetime] = _utcnow) -> None:
        self._records: list[ConsentRecord] = []
        self._clock = clock

    def grant(self, subject_id: str, purpose: str, *, policy_version: str = "1.0") -> ConsentRecord:
        return self._record(subject_id, purpose, True, policy_version)

    def withdraw(
        self, subject_id: str, purpose: str, *, policy_version: str = "1.0"
    ) -> ConsentRecord:
        return self._record(subject_id, purpose, False, policy_version)

    def _record(self, subject_id: str, purpose: str, granted: bool, version: str) -> ConsentRecord:
        rec = ConsentRecord(subject_id, purpose, granted, version, self._clock().isoformat())
        self._records.append(rec)
        return rec

    def has_consent(self, subject_id: str, purpose: str) -> bool:
        latest = None
        for r in self._records:
            if r.subject_id == subject_id and r.purpose == purpose:
                latest = r
        return bool(latest and latest.granted)

    def history(self, subject_id: str) -> list[ConsentRecord]:
        return [r for r in self._records if r.subject_id == subject_id]


# ===========================================================================
# Data residency
# ===========================================================================
class ResidencyViolation(Exception):
    """Raised when data placement would violate a residency policy."""


@dataclass
class ResidencyPolicy:
    """Allowed storage regions per data category (e.g. RBI data-localisation)."""

    allowed: dict[str, set[str]] = field(default_factory=dict)

    def allow(self, category: str, regions: set[str]) -> None:
        self.allowed[category] = set(regions)

    def is_allowed(self, category: str, region: str) -> bool:
        permitted = self.allowed.get(category)
        return permitted is None or region in permitted

    def enforce(self, category: str, region: str) -> None:
        if not self.is_allowed(category, region):
            raise ResidencyViolation(f"{category!r} may not be stored in region {region!r}")


# ===========================================================================
# Data subject rights: export + erasure
# ===========================================================================
class DataExporter:
    """Assembles a subject's data across sources (GDPR portability / DSAR)."""

    def __init__(self) -> None:
        self._collectors: dict[str, Callable[[str], Any]] = {}

    def register(self, source: str, collector: Callable[[str], Any]) -> None:
        self._collectors[source] = collector

    def export(self, subject_id: str) -> dict[str, Any]:
        return {
            "subject_id": subject_id,
            "generated_at": _utcnow().isoformat(),
            "data": {src: fn(subject_id) for src, fn in self._collectors.items()},
        }

    def export_json(self, subject_id: str) -> str:
        return json.dumps(self.export(subject_id), indent=2, default=str)


@dataclass
class ErasureResult:
    subject_id: str
    erased: dict[str, int]
    at: str

    @property
    def total(self) -> int:
        return sum(self.erased.values())


class DataEraser:
    """Orchestrates right-to-erasure across sources (each returns a delete count)."""

    def __init__(self) -> None:
        self._erasers: dict[str, Callable[[str], int]] = {}

    def register(self, source: str, eraser: Callable[[str], int]) -> None:
        self._erasers[source] = eraser

    def erase(self, subject_id: str) -> ErasureResult:
        erased = {src: int(fn(subject_id)) for src, fn in self._erasers.items()}
        return ErasureResult(subject_id=subject_id, erased=erased, at=_utcnow().isoformat())


# ===========================================================================
# Evidence collection + audit export
# ===========================================================================
@dataclass
class Evidence:
    control_id: str
    collected_at: str
    kind: str
    payload: dict[str, Any]


class EvidenceCollector:
    """Gathers auditor-ready evidence for controls from registered providers."""

    def __init__(self) -> None:
        self._providers: dict[str, Callable[[], dict[str, Any]]] = {}

    def register(self, control_id: str, provider: Callable[[], dict[str, Any]]) -> None:
        self._providers[control_id] = provider

    def collect(self, *, kind: str = "snapshot") -> list[Evidence]:
        out: list[Evidence] = []
        for control_id, provider in self._providers.items():
            try:
                payload = provider()
            except Exception as exc:  # evidence gathering must never crash an audit
                payload = {"error": str(exc)}
            out.append(Evidence(control_id, _utcnow().isoformat(), kind, payload))
        return out

    def bundle(self) -> dict[str, Any]:
        return {
            "generated_at": _utcnow().isoformat(),
            "evidence": [asdict(e) for e in self.collect()],
        }


def export_audit_ndjson(rows: list[dict[str, Any]]) -> str:
    """Serialise audit rows to newline-delimited JSON for auditor hand-off."""
    return "\n".join(json.dumps(r, default=str, sort_keys=True) for r in rows)


__all__ = [
    "ConsentLedger",
    "ConsentRecord",
    "Control",
    "ControlStatus",
    "DataEraser",
    "DataExporter",
    "ErasureResult",
    "Evidence",
    "EvidenceCollector",
    "Framework",
    "ResidencyPolicy",
    "ResidencyViolation",
    "control_catalog",
    "export_audit_ndjson",
    "generate_report",
    "policy_matrix",
]

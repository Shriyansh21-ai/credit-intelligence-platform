"""Privacy engineering (Milestone 12).

Consent, retention, right-to-erasure and DSAR lifecycle. The catalog of privacy
controls plus DB-backed request management (see ``service.py``). This module
holds the pure control catalog and lifecycle rules.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Dict, List

from backend.app.core.crypto import default_retention

# GDPR/DPDP data-subject request types and their statutory response windows.
REQUEST_TYPES: Dict[str, Dict[str, object]] = {
    "access": {"label": "Right of access (SAR)", "sla_days": 30, "gdpr": "Art.15"},
    "erasure": {"label": "Right to erasure", "sla_days": 30, "gdpr": "Art.17"},
    "rectification": {"label": "Right to rectification", "sla_days": 30, "gdpr": "Art.16"},
    "portability": {"label": "Data portability", "sla_days": 30, "gdpr": "Art.20"},
    "restriction": {"label": "Restriction of processing", "sla_days": 30, "gdpr": "Art.18"},
    "objection": {"label": "Right to object", "sla_days": 30, "gdpr": "Art.21"},
}

REQUEST_STATES = ["received", "verifying", "in_progress", "completed", "rejected"]

PRIVACY_CONTROLS: List[Dict[str, str]] = [
    {"control": "Consent capture & versioning", "status": "satisfied",
     "detail": "Explicit consent recorded with purpose and timestamp."},
    {"control": "Data minimisation", "status": "satisfied",
     "detail": "Only need-based fields collected (PII catalog)."},
    {"control": "Retention policies", "status": "satisfied",
     "detail": "Retention registry per data category (7y audit, 10y KYC, ...)."},
    {"control": "Right to erasure", "status": "satisfied",
     "detail": "Erasure workflow + crypto-shredding for encrypted data."},
    {"control": "Audit retention", "status": "satisfied",
     "detail": "Immutable audit trail retained 7 years."},
    {"control": "Document lifecycle", "status": "satisfied",
     "detail": "Documents expire per retention policy; secure deletion."},
    {"control": "Backup retention", "status": "satisfied",
     "detail": "Backups retained per policy; erasure honoured on restore."},
    {"control": "AI memory retention", "status": "partial",
     "detail": "Tenant-scoped memory with forget(); formal TTL policy pending."},
]


def request_sla_due(request_type: str, created):
    """Return the statutory due date for a request type from its creation time."""
    meta = REQUEST_TYPES.get(request_type)
    days = int(meta["sla_days"]) if meta else 30
    return created + timedelta(days=days)


def retention_summary() -> List[Dict[str, object]]:
    out = []
    for cat, policy in default_retention.all().items():
        out.append({
            "category": cat,
            "retention_days": policy.retention_days,
            "years": round(policy.retention_days / 365, 1),
            "legal_hold": policy.legal_hold,
            "description": policy.description,
        })
    return out


def privacy_overview() -> Dict[str, object]:
    satisfied = sum(1 for c in PRIVACY_CONTROLS if c["status"] == "satisfied")
    score = round(100.0 * satisfied / len(PRIVACY_CONTROLS), 1)
    findings = [
        {
            "code": "PRIVACY-AI-TTL", "category": "privacy", "severity": "low",
            "title": "AI memory retention policy incomplete",
            "description": "AI long-term memory lacks a formal TTL/retention policy.",
            "recommendation": "Define and enforce a TTL for AI memory per data category.",
            "component": "ai_platform/memory",
        }
    ] if any(c["status"] == "partial" for c in PRIVACY_CONTROLS) else []
    return {
        "controls": PRIVACY_CONTROLS,
        "request_types": REQUEST_TYPES,
        "request_states": REQUEST_STATES,
        "retention": retention_summary(),
        "score": score,
        "findings": findings,
    }

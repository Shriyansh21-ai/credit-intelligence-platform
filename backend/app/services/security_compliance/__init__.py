"""Enterprise Security & Compliance Platform (Stage 4).

Additive, offline-first, deterministic security programme layered over Stages
1-3. Nothing here mutates or removes prior functionality; every capability is
new and reachable under ``/api/sec/*``.

Sub-modules
-----------
* ``catalog``          — pure data: STRIDE, attack surface, OWASP, frameworks, PII.
* ``common``           — deterministic scoring / grading primitives.
* ``threat_model``     — STRIDE, attack surface & attack trees (M1).
* ``owasp``            — OWASP Top 10 / API Top 10 / ASVS review (M2).
* ``authz``            — auth hardening (M3) + tenant isolation audit (M4).
* ``secrets``          — secret inventory & rotation status (M5).
* ``data_protection``  — classification, PII catalog, encryption/masking (M6).
* ``compliance``       — SOC2/ISO/GDPR/PCI/RBI/NIST matrix + gaps (M7).
* ``supply_chain``     — SBOM, dependency & license reports (M8).
* ``hardening``        — container / Kubernetes hardening (M9).
* ``ai_ml``            — AI security (M10) + ML security (M11).
* ``privacy``          — privacy engineering / DSAR (M12).
* ``posture``          — aggregate security posture (M14).
* ``service``          — DB-backed scans, findings, risk register, snapshots.
"""

from __future__ import annotations

from . import (  # noqa: F401
    ai_ml,
    authz,
    catalog,
    common,
    compliance,
    data_protection,
    hardening,
    owasp,
    posture,
    privacy,
    secrets,
    service,
    supply_chain,
    threat_model,
)

__all__ = [
    "ai_ml",
    "authz",
    "catalog",
    "common",
    "compliance",
    "data_protection",
    "hardening",
    "owasp",
    "posture",
    "privacy",
    "secrets",
    "service",
    "supply_chain",
    "threat_model",
]

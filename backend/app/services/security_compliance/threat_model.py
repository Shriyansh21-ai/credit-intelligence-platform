"""Threat modeling engine (Milestone 1) — STRIDE, attack surface, attack trees.

Deterministic: derives the model from the static catalog plus the live settings
profile, so the output is reproducible and reflects the actual configuration.
"""

from __future__ import annotations

from typing import Dict, List

from backend.app.core.settings import get_settings

from . import catalog
from .common import clamp


def stride_analysis() -> Dict[str, object]:
    """Full STRIDE analysis grouped by category with residual-risk rollup."""
    by_category: Dict[str, List[dict]] = {c: [] for c in catalog.STRIDE_CATEGORIES}
    for threat in catalog.STRIDE_THREATS:
        by_category[threat["category"]].append(dict(threat))

    residual_rank = {"low": 1, "medium": 2, "high": 3}
    categories = []
    for cat, meaning in catalog.STRIDE_CATEGORIES.items():
        threats = by_category[cat]
        worst = max((residual_rank[t["residual"]] for t in threats), default=0)
        categories.append({
            "category": cat,
            "meaning": meaning,
            "threat_count": len(threats),
            "worst_residual": {1: "low", 2: "medium", 3: "high", 0: "none"}[worst],
            "threats": threats,
        })
    return {
        "categories": categories,
        "total_threats": len(catalog.STRIDE_THREATS),
        "residual_distribution": _residual_distribution(),
    }


def _residual_distribution() -> Dict[str, int]:
    dist = {"low": 0, "medium": 0, "high": 0}
    for t in catalog.STRIDE_THREATS:
        dist[t["residual"]] += 1
    return dist


def attack_surface() -> Dict[str, object]:
    """Enumerate the platform attack surface with a live posture note."""
    settings = get_settings()
    surfaces = [dict(s) for s in catalog.ATTACK_SURFACE]
    # Live signal: metrics/probes should not be public in production.
    note = ("Metrics/probes and admin surfaces must be network-restricted in "
            "production." if settings.is_production_like else
            "Development profile — surfaces are broadly reachable locally.")
    risk_rank = {"low": 1, "medium": 2, "high": 3}
    high = sum(1 for s in surfaces if s["risk"] == "high")
    return {
        "surfaces": surfaces,
        "total": len(surfaces),
        "high_risk": high,
        "public_surfaces": [s["surface"] for s in surfaces if s["exposure"] == "public"],
        "note": note,
        "max_risk": max((risk_rank[s["risk"]] for s in surfaces), default=0),
    }


def trust_boundaries() -> List[Dict[str, str]]:
    return [dict(b) for b in catalog.TRUST_BOUNDARIES]


def attack_trees() -> List[Dict[str, object]]:
    """Small library of attack trees for the highest-value goals."""
    return [
        {
            "goal": "Compromise a user account",
            "and_or": "OR",
            "paths": [
                {"vector": "Credential brute force", "leaf": "guess password",
                 "mitigations": ["AccountLockout", "PasswordPolicy", "MFA"]},
                {"vector": "Token theft", "leaf": "steal/replay JWT",
                 "mitigations": ["short expiry", "refresh rotation + reuse detection", "HTTPS/HSTS"]},
                {"vector": "Phishing", "leaf": "trick user into revealing creds",
                 "mitigations": ["MFA", "risk-based auth", "user education"]},
            ],
        },
        {
            "goal": "Read another tenant's data",
            "and_or": "OR",
            "paths": [
                {"vector": "IDOR", "leaf": "manipulate object id",
                 "mitigations": ["tenant_id scoping", "ownership checks", "isolation tests"]},
                {"vector": "Missing tenant filter", "leaf": "query without scope",
                 "mitigations": ["TenantMiddleware", "service-layer scoping", "audits"]},
                {"vector": "Cache/RAG bleed", "leaf": "cross-tenant cache key",
                 "mitigations": ["tenant-prefixed keys", "memory isolation"]},
            ],
        },
        {
            "goal": "Exfiltrate data via AI",
            "and_or": "OR",
            "paths": [
                {"vector": "Prompt injection", "leaf": "override system prompt",
                 "mitigations": ["input hardening", "tool allow-lists", "output validation"]},
                {"vector": "RAG poisoning", "leaf": "inject malicious document",
                 "mitigations": ["source vetting", "ingestion controls", "provenance"]},
            ],
        },
        {
            "goal": "Escalate to administrator",
            "and_or": "AND",
            "paths": [
                {"vector": "Find missing authz", "leaf": "unguarded route",
                 "mitigations": ["require_permission everywhere", "authz tests"]},
                {"vector": "Abuse role assignment", "leaf": "self-grant role",
                 "mitigations": ["roles.manage gated", "audit", "SoD"]},
            ],
        },
    ]


def build_threat_model() -> Dict[str, object]:
    """The consolidated threat model (STRIDE + boundaries + surface + trees)."""
    stride = stride_analysis()
    surface = attack_surface()
    # A coarse model-health score: fewer high residuals + fewer high surfaces = better.
    high_residual = stride["residual_distribution"]["high"]
    penalty = high_residual * 8 + surface["high_risk"] * 3
    score = round(clamp(100 - penalty), 1)
    return {
        "stride": stride,
        "trust_boundaries": trust_boundaries(),
        "attack_surface": surface,
        "attack_trees": attack_trees(),
        "model_health_score": score,
        "high_residual_threats": high_residual,
    }

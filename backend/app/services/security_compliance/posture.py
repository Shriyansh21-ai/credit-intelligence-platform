"""Security posture aggregator (Milestone 14).

Fuses every assessment dimension into a single enterprise security posture score
and grade. Config/catalog-derived (no DB) so it is cheap to call on every
dashboard load; the route layer augments it with live DB counters.
"""

from __future__ import annotations

from typing import Dict

from . import ai_ml, authz, compliance, data_protection, hardening, owasp, privacy, secrets, supply_chain, threat_model
from .common import grade_from_score, weighted_average

# Relative weight of each posture dimension in the overall score.
_WEIGHTS = {
    "threat_model": 1.0,
    "owasp": 1.5,
    "authz": 1.5,
    "tenant_isolation": 1.5,
    "secrets": 1.5,
    "data_protection": 1.0,
    "compliance": 1.0,
    "supply_chain": 1.0,
    "container": 1.0,
    "ai_security": 1.0,
    "ml_security": 1.0,
    "privacy": 1.0,
}


def dimension_scores() -> Dict[str, float]:
    """Compute the score for every posture dimension."""
    return {
        "threat_model": float(threat_model.build_threat_model()["model_health_score"]),
        "owasp": float(owasp.owasp_assessment()["overall_score"]),
        "authz": float(authz.authz_audit()["score"]),
        "tenant_isolation": float(authz.tenant_isolation_audit()["score"]),
        "secrets": float(secrets.secret_inventory()["score"]),
        "data_protection": float(data_protection.data_protection_report()["score"]),
        "compliance": float(compliance.compliance_matrix()["overall_readiness_score"]),
        "supply_chain": float(supply_chain.supply_chain_report()["score"]),
        "container": float(hardening.container_hardening()["score"]),
        "ai_security": float(ai_ml.ai_security()["score"]),
        "ml_security": float(ai_ml.ml_security()["score"]),
        "privacy": float(privacy.privacy_overview()["score"]),
    }


def security_posture() -> Dict[str, object]:
    dims = dimension_scores()
    overall = weighted_average(dims, _WEIGHTS)
    return {
        "overall_score": overall,
        "grade": grade_from_score(overall),
        "dimensions": dims,
        "weights": _WEIGHTS,
        "weakest": min(dims, key=dims.get) if dims else None,
        "strongest": max(dims, key=dims.get) if dims else None,
    }

"""AI security and ML security assessments.

Maps the platform's AI/ML controls to the OWASP LLM Top 10 and an ML-pipeline
threat baseline, turning control status into findings and a posture score.
"""

from __future__ import annotations

from typing import Dict, List

from . import catalog
from .common import clamp

_STATUS_CREDIT = {"satisfied": 1.0, "partial": 0.5, "gap": 0.0}
_STATUS_SEVERITY = {"gap": "high", "partial": "medium", "satisfied": "info"}


def _score(controls: List[dict]) -> float:
    if not controls:
        return 0.0
    total = sum(_STATUS_CREDIT.get(c["status"], 0.0) for c in controls)
    return round(clamp(100.0 * total / len(controls)), 1)


def ai_security() -> Dict[str, object]:
    controls = [dict(c) for c in catalog.AI_SECURITY_CONTROLS]
    findings: List[dict] = []
    for c in controls:
        if c["status"] == "satisfied":
            continue
        findings.append({
            "code": f"AISEC-{c['id']}", "category": "ai_security",
            "severity": _STATUS_SEVERITY[c["status"]],
            "title": f"{c['threat']} ({c['owasp_llm']}): {c['status']}",
            "description": c["control"],
            "recommendation": f"Strengthen control for {c['threat']}.",
            "reference": f"OWASP LLM {c['owasp_llm']}",
        })
    return {
        "controls": controls,
        "score": _score(controls),
        "findings": findings,
        "open_findings": len(findings),
        "surface": ["prompt injection", "jailbreaks", "RAG poisoning", "hallucination",
                    "unsafe tool execution", "memory poisoning", "agent abuse",
                    "model misuse", "data leakage", "unsafe outputs"],
    }


def ml_security() -> Dict[str, object]:
    controls = [dict(c) for c in catalog.ML_SECURITY_CONTROLS]
    findings: List[dict] = []
    for c in controls:
        if c["status"] == "satisfied":
            continue
        findings.append({
            "code": f"MLSEC-{c['id']}", "category": "ml_security",
            "severity": _STATUS_SEVERITY[c["status"]],
            "title": f"{c['area']}: {c['threat']} ({c['status']})",
            "description": c["control"],
            "recommendation": f"Strengthen {c['area']} control against {c['threat']}.",
            "reference": c["area"],
        })
    return {
        "controls": controls,
        "score": _score(controls),
        "findings": findings,
        "open_findings": len(findings),
        "areas": ["training pipeline", "model registry", "feature store",
                  "dataset lineage", "model integrity", "SHAP integrity", "drift detection"],
    }

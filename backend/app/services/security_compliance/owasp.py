"""OWASP assessment engine (Milestone 2).

Evaluates the platform against OWASP Top 10 (2021), OWASP API Security Top 10
(2023) and an ASVS chapter checklist, turning control status into findings and a
coverage score.
"""

from __future__ import annotations

from typing import Dict, List

from . import catalog
from .common import clamp

# status -> credit toward the coverage score / finding severity.
_STATUS_CREDIT = {"satisfied": 1.0, "partial": 0.5, "gap": 0.0}
_STATUS_SEVERITY = {"gap": "high", "partial": "medium", "satisfied": "info"}


def _score(controls: List[dict]) -> float:
    if not controls:
        return 0.0
    total = sum(_STATUS_CREDIT.get(c["status"], 0.0) for c in controls)
    return round(clamp(100.0 * total / len(controls)), 1)


def _findings(controls: List[dict], prefix: str) -> List[dict]:
    out: List[dict] = []
    for c in controls:
        if c["status"] == "satisfied":
            continue
        out.append({
            "code": f"{prefix}-{c['id']}",
            "category": "owasp",
            "severity": _STATUS_SEVERITY[c["status"]],
            "title": f"{c['id']} {c['name']}: {c['status']}",
            "description": c["description"],
            "recommendation": "Strengthen controls: " + ", ".join(c["platform_controls"]),
            "reference": f"OWASP {prefix} {c['id']}",
        })
    return out


def owasp_top10() -> Dict[str, object]:
    controls = [dict(c) for c in catalog.OWASP_TOP_10_2021]
    return {
        "controls": controls,
        "score": _score(controls),
        "findings": _findings(controls, "OWASP"),
    }


def owasp_api_top10() -> Dict[str, object]:
    controls = [dict(c) for c in catalog.OWASP_API_TOP_10_2023]
    return {
        "controls": controls,
        "score": _score(controls),
        "findings": _findings(controls, "API"),
    }


def asvs() -> Dict[str, object]:
    chapters = [dict(c) for c in catalog.ASVS_CHAPTERS]
    return {"chapters": chapters, "score": _score(chapters)}


def owasp_assessment() -> Dict[str, object]:
    """Consolidated OWASP review across Top 10, API Top 10 and ASVS."""
    top10 = owasp_top10()
    api = owasp_api_top10()
    asvs_res = asvs()
    findings = top10["findings"] + api["findings"]
    overall = round((top10["score"] + api["score"] + asvs_res["score"]) / 3, 1)
    return {
        "top10": top10,
        "api_top10": api,
        "asvs": asvs_res,
        "overall_score": overall,
        "findings": findings,
        "open_findings": len(findings),
    }

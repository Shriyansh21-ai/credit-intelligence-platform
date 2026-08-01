"""Compliance framework engine (Milestone 7).

Assesses the platform against SOC 2, ISO 27001, GDPR, PCI DSS, RBI Digital
Lending, RBI Cyber Security, RBI Outsourcing and NIST CSF, producing a readiness
score, gap analysis and an aggregate compliance matrix.
"""

from __future__ import annotations

from typing import Dict, List

from . import catalog
from .common import compliance_score, readiness_label


def assess_framework(framework: str) -> Dict[str, object]:
    """Assess a single framework -> score, readiness, per-control results, gaps."""
    fw = catalog.COMPLIANCE_FRAMEWORKS.get(framework)
    if fw is None:
        raise ValueError(f"Unknown compliance framework: {framework}")
    controls: List[dict] = [dict(c) for c in fw["controls"]]  # type: ignore[index]
    score = compliance_score(controls)
    satisfied = sum(1 for c in controls if c["status"] == "satisfied")
    partial = sum(1 for c in controls if c["status"] == "partial")
    gaps = [c for c in controls if c["status"] == "gap"]
    gap_items = [
        {
            "control": c["id"], "domain": c["domain"], "requirement": c["requirement"],
            "status": c["status"],
            "remediation": f"Implement/complete: {c['requirement']}",
        }
        for c in controls if c["status"] in ("gap", "partial")
    ]
    return {
        "framework": framework,
        "name": fw["name"],
        "version": fw.get("version"),
        "score": score,
        "readiness": readiness_label(score),
        "total_controls": len(controls),
        "satisfied": satisfied,
        "partial": partial,
        "gaps": len(gaps),
        "results": controls,
        "gap_items": gap_items,
    }


def compliance_matrix() -> Dict[str, object]:
    """Aggregate readiness across every framework."""
    frameworks: List[dict] = []
    total = 0.0
    for fid in catalog.framework_ids():
        res = assess_framework(fid)
        frameworks.append({
            "framework": fid, "name": res["name"], "version": res["version"],
            "score": res["score"], "readiness": res["readiness"],
            "total_controls": res["total_controls"], "satisfied": res["satisfied"],
            "partial": res["partial"], "gaps": res["gaps"],
        })
        total += res["score"]
    overall = round(total / max(1, len(frameworks)), 1)
    return {
        "frameworks": frameworks,
        "overall_readiness_score": overall,
        "overall_readiness": readiness_label(overall),
        "framework_count": len(frameworks),
    }


def gap_analysis() -> Dict[str, object]:
    """Every partial/gap control across every framework, most-severe first."""
    all_gaps: List[dict] = []
    for fid in catalog.framework_ids():
        res = assess_framework(fid)
        for g in res["gap_items"]:
            all_gaps.append({**g, "framework": fid, "framework_name": res["name"]})
    # gaps before partials
    all_gaps.sort(key=lambda g: 0 if g["status"] == "gap" else 1)
    return {
        "gaps": all_gaps,
        "total_gaps": sum(1 for g in all_gaps if g["status"] == "gap"),
        "total_partials": sum(1 for g in all_gaps if g["status"] == "partial"),
    }


def readiness_score() -> Dict[str, object]:
    matrix = compliance_matrix()
    return {
        "overall_readiness_score": matrix["overall_readiness_score"],
        "overall_readiness": matrix["overall_readiness"],
        "by_framework": {f["framework"]: f["score"] for f in matrix["frameworks"]},
    }

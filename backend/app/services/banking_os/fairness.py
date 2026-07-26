"""M13 — Model Governance: Bias / Fairness / Drift.

Deterministic fairness and drift diagnostics that extend the Phase 9 model
governance platform. Fairness evaluates group parity over labeled prediction
records (demographic-parity difference, disparate-impact ratio / 80% rule,
equal-opportunity difference when outcomes are present). Drift computes the
Population Stability Index (PSI) between a baseline and a current distribution.
All metrics are closed-form and reproducible — no sampling, no LLM.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.banking_os import ModelFairnessRun

DISPARATE_IMPACT_THRESHOLD = 0.8   # 80% rule
PSI_WARN, PSI_ALERT = 0.1, 0.2


# ---------------------------------------------------------------------------
# Fairness (pure)
# ---------------------------------------------------------------------------
def evaluate_fairness(records: List[dict], *, protected_attribute: str = "group") -> Dict[str, Any]:
    """Group-fairness metrics over ``[{<attr>, approved[, actual]}]`` records.

    ``approved`` is truthy for a positive decision; ``actual`` (optional, truthy
    for a genuine positive) enables equal-opportunity (TPR parity).
    """
    groups: Dict[str, Dict[str, int]] = defaultdict(lambda: {"n": 0, "approved": 0,
                                                             "tp": 0, "pos": 0})
    for r in records:
        g = str(r.get(protected_attribute, "unknown"))
        gg = groups[g]
        gg["n"] += 1
        approved = bool(r.get("approved"))
        if approved:
            gg["approved"] += 1
        if "actual" in r:
            if r.get("actual"):
                gg["pos"] += 1
                if approved:
                    gg["tp"] += 1

    group_rows = []
    for g, gg in groups.items():
        rate = gg["approved"] / gg["n"] if gg["n"] else 0.0
        tpr = (gg["tp"] / gg["pos"]) if gg["pos"] else None
        group_rows.append({"group": g, "n": gg["n"], "approval_rate": round(rate, 4),
                           "tpr": round(tpr, 4) if tpr is not None else None})
    rates = [row["approval_rate"] for row in group_rows]
    metrics: Dict[str, Any] = {}
    if rates:
        hi, lo = max(rates), min(rates)
        metrics["demographic_parity_diff"] = round(hi - lo, 4)
        metrics["disparate_impact_ratio"] = round(lo / hi, 4) if hi > 0 else None
        tprs = [row["tpr"] for row in group_rows if row["tpr"] is not None]
        if len(tprs) >= 2:
            metrics["equal_opportunity_diff"] = round(max(tprs) - min(tprs), 4)
    di = metrics.get("disparate_impact_ratio")
    passed = di is None or di >= DISPARATE_IMPACT_THRESHOLD
    return {"kind": "fairness", "protected_attribute": protected_attribute,
            "groups": sorted(group_rows, key=lambda x: x["group"]), "metrics": metrics,
            "passed": passed,
            "summary": _fairness_summary(metrics, passed)}


def _fairness_summary(metrics: Dict[str, Any], passed: bool) -> str:
    di = metrics.get("disparate_impact_ratio")
    if di is None:
        return "Insufficient groups to assess disparate impact."
    verdict = "PASS" if passed else "FAIL (80% rule breached)"
    return f"Disparate-impact ratio {di} — {verdict}."


def population_stability_index(baseline: List[float], current: List[float], *,
                               bins: int = 10) -> Dict[str, Any]:
    """PSI between two score distributions using equal-width bins over [0,1]-ish range."""
    if not baseline or not current:
        return {"psi": None, "bins": [], "band": "unknown"}
    lo = min(min(baseline), min(current))
    hi = max(max(baseline), max(current))
    if hi <= lo:
        return {"psi": 0.0, "bins": [], "band": "stable"}
    width = (hi - lo) / bins

    def hist(vals: List[float]) -> List[float]:
        counts = [0] * bins
        for v in vals:
            idx = min(bins - 1, int((v - lo) / width))
            counts[idx] += 1
        total = len(vals)
        return [c / total for c in counts]

    b, c = hist(baseline), hist(current)
    psi = 0.0
    bin_rows = []
    for i in range(bins):
        bp = max(b[i], 1e-6)
        cp = max(c[i], 1e-6)
        contrib = (cp - bp) * math.log(cp / bp)
        psi += contrib
        bin_rows.append({"bin": i, "baseline": round(b[i], 4), "current": round(c[i], 4),
                         "contribution": round(contrib, 5)})
    band = "stable" if psi < PSI_WARN else "shift" if psi < PSI_ALERT else "significant_drift"
    return {"psi": round(psi, 4), "bins": bin_rows, "band": band}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def run_fairness(db: Session, *, model_key: str, records: List[dict],
                 protected_attribute: str = "group",
                 tenant_id: Optional[int] = None) -> Dict[str, Any]:
    result = evaluate_fairness(records, protected_attribute=protected_attribute)
    row = ModelFairnessRun(tenant_id=tenant_id, model_key=model_key, kind="fairness",
                           protected_attribute=protected_attribute, metrics=result["metrics"],
                           groups=result["groups"], passed=result["passed"],
                           summary=result["summary"])
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"run_id": row.id, **result}


def run_drift(db: Session, *, model_key: str, baseline: List[float], current: List[float],
              tenant_id: Optional[int] = None) -> Dict[str, Any]:
    psi = population_stability_index(baseline, current)
    passed = psi["psi"] is None or psi["psi"] < PSI_ALERT
    row = ModelFairnessRun(tenant_id=tenant_id, model_key=model_key, kind="drift",
                           metrics={"psi": psi["psi"], "band": psi["band"]},
                           groups=psi["bins"], passed=passed,
                           summary=f"PSI {psi['psi']} — {psi['band']}.")
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"run_id": row.id, "kind": "drift", "passed": passed, **psi}


def history(db: Session, *, model_key: Optional[str] = None, kind: Optional[str] = None,
            tenant_id: Optional[int] = None, limit: int = 100) -> List[ModelFairnessRun]:
    q = db.query(ModelFairnessRun).filter(ModelFairnessRun.tenant_id == tenant_id)
    if model_key:
        q = q.filter(ModelFairnessRun.model_key == model_key)
    if kind:
        q = q.filter(ModelFairnessRun.kind == kind)
    return q.order_by(ModelFairnessRun.created_at.desc()).limit(limit).all()


def run_dict(r: ModelFairnessRun) -> Dict[str, Any]:
    return {"id": r.id, "model_key": r.model_key, "kind": r.kind,
            "protected_attribute": r.protected_attribute, "metrics": r.metrics,
            "groups": r.groups, "passed": r.passed, "summary": r.summary,
            "created_at": r.created_at.isoformat() if r.created_at else None}

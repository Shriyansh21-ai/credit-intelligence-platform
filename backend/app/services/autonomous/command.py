"""M9 — Executive Command Center.

Role-tailored executive dashboards (CEO, Chief Risk Officer, Chief Credit
Officer, Board, Regional Head) aggregating the whole platform into KPIs,
portfolio risk, capital usage, approvals pipeline, watchlist, industry/geographic
exposure, fraud trends, ML drift and business growth — each with drill-down
references. All read-only aggregation over existing + Phase 9 data; defensive so
a missing subsystem degrades to zeros rather than erroring.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from . import alerts as alerts_svc
from . import data_access, optimization, stress
from .common import clamp


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


def portfolio_kpis(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    profs = data_access.portfolio_profiles(db)
    n = len(profs)
    exposure = sum((p.get("exposure") or 0) for p in profs)
    pds = [p["pd"] for p in profs if isinstance(p.get("pd"), (int, float))]
    scores = [p["credit_score"] for p in profs if isinstance(p.get("credit_score"), (int, float))]
    el = sum((p.get("expected_loss") or 0) for p in profs)
    high_risk = [p for p in profs if (p.get("pd") or 0) >= 0.10]
    return {
        "companies": n, "total_exposure": round(exposure, 2),
        "avg_pd": round(sum(pds) / len(pds), 4) if pds else None,
        "avg_credit_score": round(sum(scores) / len(scores), 1) if scores else None,
        "expected_loss": round(el, 2),
        "high_risk_count": len(high_risk),
        "high_risk_share": round(len(high_risk) / n, 4) if n else 0.0,
    }


def watchlist(db: Session, *, tenant_id: Optional[int] = None, limit: int = 15) -> List[Dict[str, Any]]:
    profs = data_access.portfolio_profiles(db)
    ranked = sorted(profs, key=lambda p: -(p.get("pd") or 0))
    out = []
    for p in ranked[:limit]:
        if (p.get("pd") or 0) < 0.06:
            continue
        out.append({"company_ref": p.get("company_ref"), "industry": p.get("industry"),
                    "rating": p.get("rating"), "pd": p.get("pd"),
                    "exposure": p.get("exposure"), "credit_score": p.get("credit_score")})
    return out


def industry_exposure(db: Session, *, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    profs = data_access.portfolio_profiles(db)
    agg: Dict[str, Dict[str, float]] = defaultdict(lambda: {"exposure": 0.0, "count": 0, "el": 0.0})
    for p in profs:
        k = p.get("industry") or "Unclassified"
        agg[k]["exposure"] += p.get("exposure") or 0
        agg[k]["count"] += 1
        agg[k]["el"] += p.get("expected_loss") or 0
    total = sum(v["exposure"] for v in agg.values()) or 1.0
    return sorted([{"industry": k, "exposure": round(v["exposure"], 2), "count": int(v["count"]),
                    "expected_loss": round(v["el"], 2), "share": round(v["exposure"] / total, 4)}
                   for k, v in agg.items()], key=lambda x: -x["exposure"])


def geographic_exposure(db: Session, *, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    profs = data_access.portfolio_profiles(db)
    agg: Dict[str, float] = defaultdict(float)
    for p in profs:
        agg[p.get("country") or "Unclassified"] += p.get("exposure") or 0
    total = sum(agg.values()) or 1.0
    return sorted([{"region": k, "exposure": round(v, 2), "share": round(v / total, 4)}
                   for k, v in agg.items()], key=lambda x: -x["exposure"])


def approvals_pipeline(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    def q():
        from backend.app.models.application import Application
        rows = db.query(Application).all()
        by_status: Dict[str, int] = defaultdict(int)
        for r in rows:
            by_status[getattr(r, "status", "unknown")] += 1
        return {"total": len(rows), "by_status": dict(by_status)}
    return _safe(q, {"total": 0, "by_status": {}})


def fraud_trends(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    def q():
        from backend.app.models.fraud import FraudCheck
        rows = db.query(FraudCheck).all()
        detected = sum(1 for r in rows if getattr(r, "fraud_detected", False))
        by_risk: Dict[str, int] = defaultdict(int)
        for r in rows:
            by_risk[getattr(r, "fraud_risk", "unknown") or "unknown"] += 1
        return {"total_checks": len(rows), "detected": detected,
                "detection_rate": round(detected / len(rows), 4) if rows else 0.0,
                "by_risk": dict(by_risk)}
    return _safe(q, {"total_checks": 0, "detected": 0, "detection_rate": 0.0, "by_risk": {}})


def ml_drift_summary(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    def q():
        from backend.app.models.ml_platform import MLDriftReport
        rows = db.query(MLDriftReport).order_by(MLDriftReport.id.desc()).limit(50).all()
        drifted = sum(1 for r in rows if getattr(r, "drift_detected", False))
        return {"reports": len(rows), "drift_detected": drifted}
    return _safe(q, {"reports": 0, "drift_detected": 0})


def business_growth(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    profs = data_access.all_assessments(db)
    by_month: Dict[str, int] = defaultdict(int)
    for a in profs:
        if getattr(a, "created_at", None):
            by_month[a.created_at.strftime("%Y-%m")] += 1
    months = sorted(by_month.items())
    trend = [{"month": m, "new_assessments": c} for m, c in months]
    growth_rate = None
    if len(months) >= 2 and months[-2][1]:
        growth_rate = round((months[-1][1] - months[-2][1]) / months[-2][1], 4)
    return {"monthly": trend, "total": sum(by_month.values()), "mom_growth": growth_rate}


def alert_overview(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    return alerts_svc.summary(db, tenant_id=tenant_id)


# ---------------------------------------------------------------------------
# Persona dashboards
# ---------------------------------------------------------------------------
def _base(db, tenant_id):
    return {"generated_at": None, "kpis": portfolio_kpis(db, tenant_id=tenant_id),
            "alerts": alert_overview(db, tenant_id=tenant_id)}


def ceo_dashboard(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    d = _base(db, tenant_id)
    d.update({"persona": "ceo", "growth": business_growth(db, tenant_id=tenant_id),
              "industry_exposure": industry_exposure(db, tenant_id=tenant_id)[:8],
              "geographic_exposure": geographic_exposure(db, tenant_id=tenant_id)[:8]})
    return d


def cro_dashboard(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    d = _base(db, tenant_id)
    d.update({"persona": "chief_risk_officer",
              "watchlist": watchlist(db, tenant_id=tenant_id),
              "stress_summary": _safe(lambda: stress.compare_scenarios(db, tenant_id=tenant_id), {}),
              "fraud_trends": fraud_trends(db, tenant_id=tenant_id),
              "ml_drift": ml_drift_summary(db, tenant_id=tenant_id)})
    return d


def cco_dashboard(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    d = _base(db, tenant_id)
    d.update({"persona": "chief_credit_officer",
              "approvals_pipeline": approvals_pipeline(db, tenant_id=tenant_id),
              "concentration": _safe(lambda: optimization.analyze(db, tenant_id=tenant_id)["concentration"], {}),
              "limit_breaches": _safe(lambda: optimization.analyze(db, tenant_id=tenant_id)["limit_breaches"], []),
              "watchlist": watchlist(db, tenant_id=tenant_id, limit=10)})
    return d


def board_dashboard(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    d = _base(db, tenant_id)
    opt = _safe(lambda: optimization.analyze(db, tenant_id=tenant_id), {})
    d.update({"persona": "board",
              "capital_required": opt.get("capital_required"),
              "portfolio_raroc": opt.get("portfolio_raroc"),
              "net_return": opt.get("net_return"),
              "growth": business_growth(db, tenant_id=tenant_id),
              "industry_exposure": industry_exposure(db, tenant_id=tenant_id)[:6]})
    return d


def regional_dashboard(db: Session, *, region: Optional[str] = None,
                       tenant_id: Optional[int] = None) -> Dict[str, Any]:
    d = _base(db, tenant_id)
    geo = geographic_exposure(db, tenant_id=tenant_id)
    d.update({"persona": "regional_head", "region": region,
              "geographic_exposure": geo,
              "regional_stress": _safe(lambda: stress.run(db, scenario="moderate", scope="region",
                                                          scope_ref=region, tenant_id=tenant_id,
                                                          persist=False), {}) if region else None,
              "watchlist": watchlist(db, tenant_id=tenant_id)})
    return d


DASHBOARDS = {
    "ceo": ceo_dashboard, "chief_risk_officer": cro_dashboard, "cro": cro_dashboard,
    "chief_credit_officer": cco_dashboard, "cco": cco_dashboard,
    "board": board_dashboard, "regional_head": regional_dashboard,
}


def dashboard(db: Session, persona: str, *, tenant_id: Optional[int] = None,
              region: Optional[str] = None) -> Dict[str, Any]:
    fn = DASHBOARDS.get(persona)
    if fn is None:
        raise ValueError(f"unknown persona: {persona}")
    if fn is regional_dashboard:
        return fn(db, region=region, tenant_id=tenant_id)
    result = fn(db, tenant_id=tenant_id)
    result["generated_at"] = datetime.utcnow().isoformat()
    return result

"""M12 — Enterprise Business Intelligence Platform.

Executive analytics that compute *real* metrics from across the platform:
revenue, product, customer, risk, AI, adoption, operational, financial and growth
analytics, forecast dashboards, board reports and saveable interactive dashboards.
Every metric is grounded in a live read (assessments, customers, plugins,
deployments), never a placeholder. Saved dashboards persist to ``ent_bi_dashboards``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.enterprise_platform import (
    EntBiDashboard, EntCustomer, EntDeployment, EntPlugin,
)
from . import data_access as da
from .common import grounding_block, iso, mean, safe_div, slugify, utcnow

CATEGORIES = ["revenue", "product", "customer", "risk", "ai", "adoption",
              "operational", "financial", "growth", "executive"]


def _revenue(db: Session, tenant_id: Optional[int]) -> Dict[str, Any]:
    q = db.query(EntCustomer)
    if tenant_id is not None:
        q = q.filter(EntCustomer.tenant_id == tenant_id)
    customers = q.all()
    arr = sum(c.arr for c in customers)
    live = [c for c in customers if c.status == "live"]
    return {"total_arr": round(arr, 2), "customers": len(customers), "live_customers": len(live),
            "avg_arr": round(safe_div(arr, len(customers), 0.0) or 0, 2),
            "arr_by_segment": _group_sum(customers, "segment", "arr")}


def _group_sum(rows, key, field) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for r in rows:
        out[getattr(r, key)] = round(out.get(getattr(r, key), 0.0) + getattr(r, field), 2)
    return out


def _customer(db: Session, tenant_id: Optional[int]) -> Dict[str, Any]:
    q = db.query(EntCustomer)
    if tenant_id is not None:
        q = q.filter(EntCustomer.tenant_id == tenant_id)
    customers = q.all()
    if not customers:
        return {"count": 0, "avg_health": None, "at_risk": 0, "churn_rate_pct": 0.0}
    at_risk = sum(1 for c in customers if c.status == "at_risk")
    churned = sum(1 for c in customers if c.status == "churned")
    return {"count": len(customers), "avg_health": round(mean([c.health_score for c in customers]), 1),
            "avg_adoption": round(mean([c.adoption_score for c in customers]), 1),
            "at_risk": at_risk, "churned": churned,
            "churn_rate_pct": round(100.0 * safe_div(churned, len(customers), 0.0), 2)}


def _product(db: Session, tenant_id: Optional[int]) -> Dict[str, Any]:
    q = db.query(EntPlugin)
    if tenant_id is not None:
        q = q.filter(EntPlugin.tenant_id == tenant_id)
    plugins = q.all()
    return {"plugins": len(plugins), "published": sum(1 for p in plugins if p.status == "published"),
            "total_installs": sum(p.install_count or 0 for p in plugins)}


def _risk(db: Session) -> Dict[str, Any]:
    counts = da.platform_counts(db)
    return {"assessments": counts.get("assessments", 0), "portfolios": counts.get("portfolios", 0)}


def _operational(db: Session, tenant_id: Optional[int]) -> Dict[str, Any]:
    q = db.query(EntDeployment)
    if tenant_id is not None:
        q = q.filter(EntDeployment.tenant_id == tenant_id)
    deployments = q.all()
    success = sum(1 for d in deployments if d.status == "succeeded")
    return {"deployments": len(deployments), "success_rate_pct":
            round(100.0 * safe_div(success, len(deployments), 1.0), 1)}


def analytics(db: Session, *, category: str = "executive", tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Compute a category of executive analytics from live platform data."""
    if category not in CATEGORIES:
        raise ValueError(f"unknown category '{category}'")
    counts = da.platform_counts(db)
    if category == "revenue" or category == "financial":
        data = _revenue(db, tenant_id)
    elif category == "customer":
        data = _customer(db, tenant_id)
    elif category == "product":
        data = _product(db, tenant_id)
    elif category == "risk":
        data = _risk(db)
    elif category == "operational":
        data = _operational(db, tenant_id)
    elif category == "ai":
        data = {"ai_reports": counts.get("ai_reports", 0), "assessments": counts.get("assessments", 0)}
    elif category == "adoption":
        data = {"tenants": counts.get("tenants", 0), "users": counts.get("users", 0),
                **_customer(db, tenant_id)}
    elif category == "growth":
        rev = _revenue(db, tenant_id)
        cust = _customer(db, tenant_id)
        data = {"arr": rev["total_arr"], "customers": rev["customers"],
                "net_retention_proxy_pct": round(100 - cust["churn_rate_pct"], 2)}
    else:  # executive
        data = {"revenue": _revenue(db, tenant_id), "customer": _customer(db, tenant_id),
                "product": _product(db, tenant_id), "operational": _operational(db, tenant_id),
                "platform": counts}
    g = grounding_block(f"{category} analytics", data if isinstance(data, dict) else {"data": data})
    return {"category": category, "metrics": data, "grounding": g, "generated_at": iso(utcnow())}


def board_report(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """A single board-level roll-up across every analytics category."""
    sections = {c: analytics(db, category=c, tenant_id=tenant_id)["metrics"]
                for c in ("revenue", "customer", "product", "risk", "operational", "growth")}
    rev = sections["revenue"]
    cust = sections["customer"]
    headline = (f"ARR {rev['total_arr']:,.0f} across {rev['customers']} customers; "
                f"avg health {cust.get('avg_health')}; churn {cust.get('churn_rate_pct')}%.")
    return {"title": "Board Report", "headline": headline, "sections": sections,
            "generated_at": iso(utcnow())}


def save_dashboard(db: Session, *, name: str, category: str, widgets: List[Dict[str, Any]],
                   layout: Optional[dict] = None, is_board_report: bool = False, key: Optional[str] = None,
                   tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    if category not in CATEGORIES:
        raise ValueError(f"unknown category '{category}'")
    key = key or slugify(name)
    existing = db.query(EntBiDashboard).filter(EntBiDashboard.tenant_id == tenant_id,
                                               EntBiDashboard.key == key).first()
    if existing:
        existing.widgets = widgets
        existing.layout = layout or existing.layout
        db.commit()
        db.refresh(existing)
        return {"dashboard_id": existing.id, "key": existing.key, "updated": True}
    row = EntBiDashboard(tenant_id=tenant_id, key=key, name=name, category=category, widgets=widgets,
                         layout=layout or {}, is_board_report=is_board_report, created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"dashboard_id": row.id, "key": row.key, "updated": False}


def list_dashboards(db: Session, *, category: Optional[str] = None,
                    tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntBiDashboard)
    if tenant_id is not None:
        q = q.filter(EntBiDashboard.tenant_id == tenant_id)
    if category:
        q = q.filter(EntBiDashboard.category == category)
    return [{"dashboard_id": d.id, "key": d.key, "name": d.name, "category": d.category,
             "widget_count": len(d.widgets or []), "is_board_report": d.is_board_report}
            for d in q.order_by(EntBiDashboard.id.desc()).all()]

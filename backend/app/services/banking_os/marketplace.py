"""M12 — AI Recommendation Marketplace.

A plugin architecture for credit-action recommendations. Each plugin is a small
deterministic function over a subject's risk context that either fires a
recommendation (action + rationale + confidence + evidence) or stays silent.
Plugins are cataloged, installable and individually enable-able per tenant, so a
bank curates its own recommendation surface. Built-in plugins cover the standard
credit playbook; custom plugins register through the same interface.

All logic is deterministic and evidence-carrying — never fabricated, no LLM.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.banking_os import MarketplacePlugin, PluginRecommendation
from .common import clamp, confidence_from_evidence, evidence


def _n(ctx: Dict[str, Any], key: str, default: Optional[float] = None) -> Optional[float]:
    v = ctx.get(key, default)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Built-in plugins: each returns a recommendation dict or None.
# ---------------------------------------------------------------------------
def _reject_application(ctx: Dict[str, Any]) -> Optional[dict]:
    pd = _n(ctx, "pd")
    rating = str(ctx.get("rating", "")).upper()
    ev = []
    if pd is not None and pd >= 0.30:
        ev.append(evidence("pd", pd, source="assessment"))
    if rating in ("C", "CC", "CCC", "D"):
        ev.append(evidence("rating", rating, source="assessment"))
    if not ev:
        return None
    return {"action": "reject", "title": "Reject application",
            "rationale": "Probability of default and/or rating breach the risk appetite.",
            "priority": "high", "confidence": confidence_from_evidence(len(ev), base=0.6),
            "evidence": ev, "params": {}}


def _restructure_loan(ctx: Dict[str, Any]) -> Optional[dict]:
    pd, dscr = _n(ctx, "pd"), _n(ctx, "dscr")
    if pd is not None and 0.15 <= pd < 0.30 and (dscr is None or dscr < 1.2):
        ev = [evidence("pd", pd, source="assessment")]
        if dscr is not None:
            ev.append(evidence("dscr", dscr, source="assessment"))
        return {"action": "restructure", "title": "Restructure loan",
                "rationale": "Elevated PD with weak debt-service coverage — restructure tenor/rate.",
                "priority": "high", "confidence": confidence_from_evidence(len(ev)),
                "evidence": ev, "params": {"suggested_tenor_extension_months": 12}}
    return None


def _increase_collateral(ctx: Dict[str, Any]) -> Optional[dict]:
    cov, exp = _n(ctx, "collateral_coverage"), _n(ctx, "exposure")
    if cov is not None and cov < 1.0 and (exp or 0) > 0:
        ev = [evidence("collateral_coverage", cov, source="collateral")]
        gap = round((1.0 - cov) * (exp or 0), 2)
        return {"action": "increase_collateral", "title": "Increase collateral",
                "rationale": "Collateral coverage below 1.0x — top up security to cover exposure.",
                "priority": "medium", "confidence": confidence_from_evidence(len(ev)),
                "evidence": ev, "params": {"coverage_gap": gap}}
    return None


def _reduce_exposure(ctx: Dict[str, Any]) -> Optional[dict]:
    exp, pd = _n(ctx, "exposure"), _n(ctx, "pd")
    threshold = _n(ctx, "exposure_limit") or 25_000_000
    if exp is not None and exp > threshold and (pd is None or pd >= 0.10):
        ev = [evidence("exposure", exp, source="portfolio"),
              evidence("exposure_limit", threshold, source="policy")]
        return {"action": "reduce_exposure", "title": "Reduce exposure",
                "rationale": "Exposure exceeds the single-obligor limit at elevated PD.",
                "priority": "high", "confidence": confidence_from_evidence(len(ev)),
                "evidence": ev, "params": {"reduce_by": round(exp - threshold, 2)}}
    return None


def _increase_pricing(ctx: Dict[str, Any]) -> Optional[dict]:
    pd, rate = _n(ctx, "pd"), _n(ctx, "interest_rate")
    if pd is not None and pd >= 0.08:
        ev = [evidence("pd", pd, source="assessment")]
        suggested = round((rate or 10.0) + min(4.0, pd * 20), 2)
        return {"action": "increase_pricing", "title": "Reprice for risk",
                "rationale": "PD warrants a higher risk-based spread.",
                "priority": "medium", "confidence": confidence_from_evidence(len(ev)),
                "evidence": ev, "params": {"suggested_rate": suggested}}
    return None


def _monitor_account(ctx: Dict[str, Any]) -> Optional[dict]:
    pd = _n(ctx, "pd")
    if pd is not None and 0.05 <= pd < 0.15:
        ev = [evidence("pd", pd, source="assessment")]
        return {"action": "monitor", "title": "Enhanced monitoring",
                "rationale": "Watch-list PD band — increase monitoring cadence.",
                "priority": "low", "confidence": confidence_from_evidence(len(ev)),
                "evidence": ev, "params": {"cadence_days": 30}}
    return None


def _schedule_inspection(ctx: Dict[str, Any]) -> Optional[dict]:
    cov = _n(ctx, "collateral_coverage")
    if cov is not None and cov < 1.5 and (ctx.get("has_physical_collateral", True)):
        ev = [evidence("collateral_coverage", cov, source="collateral")]
        return {"action": "schedule_inspection", "title": "Schedule collateral inspection",
                "rationale": "Borderline collateral coverage — verify asset condition/value.",
                "priority": "low", "confidence": confidence_from_evidence(len(ev)),
                "evidence": ev, "params": {}}
    return None


def _recommend_covenant(ctx: Dict[str, Any]) -> Optional[dict]:
    dte = _n(ctx, "debt_to_equity")
    if dte is not None and dte >= 2.0:
        ev = [evidence("debt_to_equity", dte, source="financials")]
        return {"action": "add_covenant", "title": "Add leverage covenant",
                "rationale": "High leverage — bind a maximum debt/equity covenant.",
                "priority": "medium", "confidence": confidence_from_evidence(len(ev)),
                "evidence": ev, "params": {"max_debt_to_equity": round(dte, 2)}}
    return None


def _recommend_guarantee(ctx: Dict[str, Any]) -> Optional[dict]:
    pd = _n(ctx, "pd")
    if pd is not None and pd >= 0.12 and not ctx.get("has_guarantee", False):
        ev = [evidence("pd", pd, source="assessment")]
        return {"action": "add_guarantee", "title": "Require promoter guarantee",
                "rationale": "Elevated PD without a guarantee — secure a personal/corporate guarantee.",
                "priority": "medium", "confidence": confidence_from_evidence(len(ev)),
                "evidence": ev, "params": {}}
    return None


# key -> (name, category, description, fn)
PLUGIN_REGISTRY: Dict[str, Dict[str, Any]] = {
    "reject_application": {"name": "Reject Application", "category": "decision",
                           "description": "Recommend rejection when PD/rating breach appetite.",
                           "fn": _reject_application},
    "restructure_loan": {"name": "Restructure Loan", "category": "remediation",
                         "description": "Suggest restructuring for stressed but viable credits.",
                         "fn": _restructure_loan},
    "increase_collateral": {"name": "Increase Collateral", "category": "security",
                            "description": "Top up security when coverage < 1.0x.", "fn": _increase_collateral},
    "reduce_exposure": {"name": "Reduce Exposure", "category": "concentration",
                        "description": "Trim exposure above single-obligor limits.", "fn": _reduce_exposure},
    "increase_pricing": {"name": "Reprice for Risk", "category": "pricing",
                         "description": "Raise the spread to match PD.", "fn": _increase_pricing},
    "monitor_account": {"name": "Enhanced Monitoring", "category": "monitoring",
                        "description": "Watch-list accounts in the mid PD band.", "fn": _monitor_account},
    "schedule_inspection": {"name": "Schedule Inspection", "category": "monitoring",
                            "description": "Inspect collateral with borderline coverage.", "fn": _schedule_inspection},
    "recommend_covenant": {"name": "Add Covenant", "category": "structuring",
                           "description": "Bind covenants on highly-levered borrowers.", "fn": _recommend_covenant},
    "recommend_guarantee": {"name": "Require Guarantee", "category": "structuring",
                            "description": "Secure guarantees for elevated-PD credits.", "fn": _recommend_guarantee},
}

# Custom (runtime-registered) plugins live here so tenants can extend the marketplace.
_CUSTOM_PLUGINS: Dict[str, Callable[[Dict[str, Any]], Optional[dict]]] = {}


def register_custom_plugin(key: str, fn: Callable[[Dict[str, Any]], Optional[dict]]) -> None:
    _CUSTOM_PLUGINS[key] = fn


def _plugin_fn(key: str) -> Optional[Callable[[Dict[str, Any]], Optional[dict]]]:
    if key in PLUGIN_REGISTRY:
        return PLUGIN_REGISTRY[key]["fn"]
    return _CUSTOM_PLUGINS.get(key)


# ---------------------------------------------------------------------------
# Catalog / installation
# ---------------------------------------------------------------------------
def seed_builtin_plugins(db: Session, *, tenant_id: Optional[int] = None,
                         install: bool = True) -> int:
    n = 0
    for key, meta in PLUGIN_REGISTRY.items():
        row = (db.query(MarketplacePlugin)
               .filter(MarketplacePlugin.tenant_id == tenant_id,
                       MarketplacePlugin.key == key).first())
        if row is None:
            row = MarketplacePlugin(tenant_id=tenant_id, key=key, name=meta["name"],
                                    category=meta["category"], description=meta["description"],
                                    publisher="builtin", installed=install, enabled=True)
            db.add(row)
            n += 1
    db.commit()
    return n


def list_plugins(db: Session, *, tenant_id: Optional[int] = None,
                 installed_only: bool = False) -> List[MarketplacePlugin]:
    q = db.query(MarketplacePlugin).filter(MarketplacePlugin.tenant_id == tenant_id)
    if installed_only:
        q = q.filter(MarketplacePlugin.installed.is_(True))
    return q.order_by(MarketplacePlugin.category, MarketplacePlugin.key).all()


def set_plugin_state(db: Session, key: str, *, installed: Optional[bool] = None,
                     enabled: Optional[bool] = None, tenant_id: Optional[int] = None) -> MarketplacePlugin:
    row = (db.query(MarketplacePlugin)
           .filter(MarketplacePlugin.tenant_id == tenant_id, MarketplacePlugin.key == key).first())
    if row is None:
        raise ValueError("plugin not found")
    if installed is not None:
        row.installed = installed
    if enabled is not None:
        row.enabled = enabled
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Running the marketplace
# ---------------------------------------------------------------------------
def _resolve_context(db: Session, *, assessment_id: Optional[int], context: Optional[dict]) -> Dict[str, Any]:
    ctx = dict(context or {})
    if assessment_id is not None:
        try:
            from backend.app.models.enterprise_assessment import EnterpriseAssessment
            a = db.query(EnterpriseAssessment).filter(EnterpriseAssessment.id == assessment_id).first()
            if a is not None:
                ctx.setdefault("pd", a.probability_of_default)
                ctx.setdefault("rating", a.risk_rating)
                ctx.setdefault("exposure", a.recommended_loan_amount)
                ctx.setdefault("interest_rate", getattr(a, "recommended_interest_rate", None))
                ei = a.engine_input or {}
                ctx.setdefault("debt_to_equity", ei.get("debt_to_equity"))
                ctx.setdefault("current_ratio", ei.get("current_ratio"))
                ctx.setdefault("dscr", ei.get("dscr"))
        except Exception:
            pass
    return ctx


def run_marketplace(db: Session, *, subject_ref: Optional[str] = None,
                    assessment_id: Optional[int] = None, context: Optional[dict] = None,
                    tenant_id: Optional[int] = None, persist: bool = True) -> Dict[str, Any]:
    ctx = _resolve_context(db, assessment_id=assessment_id, context=context)
    plugins = [p for p in list_plugins(db, tenant_id=tenant_id, installed_only=True) if p.enabled]
    recs: List[Dict[str, Any]] = []
    for p in plugins:
        fn = _plugin_fn(p.key)
        if fn is None:
            continue
        out = fn(ctx)
        if not out:
            continue
        rec = {"plugin_key": p.key, "subject_ref": subject_ref, **out}
        recs.append(rec)
        if persist:
            row = PluginRecommendation(
                tenant_id=tenant_id, plugin_key=p.key, subject_ref=subject_ref,
                assessment_id=assessment_id, action=out["action"], title=out["title"],
                rationale=out.get("rationale"), confidence=clamp(out.get("confidence", 0.5)),
                priority=out.get("priority", "medium"), evidence=out.get("evidence", []),
                params=out.get("params", {}))
            db.add(row)
    if persist and recs:
        db.commit()
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: (priority_rank.get(r.get("priority"), 1), -r.get("confidence", 0)))
    return {"subject_ref": subject_ref, "count": len(recs), "recommendations": recs,
            "context_used": ctx}


def list_recommendations(db: Session, *, subject_ref: Optional[str] = None,
                         plugin_key: Optional[str] = None, tenant_id: Optional[int] = None,
                         limit: int = 100) -> List[PluginRecommendation]:
    q = db.query(PluginRecommendation).filter(PluginRecommendation.tenant_id == tenant_id)
    if subject_ref:
        q = q.filter(PluginRecommendation.subject_ref == subject_ref)
    if plugin_key:
        q = q.filter(PluginRecommendation.plugin_key == plugin_key)
    return q.order_by(PluginRecommendation.created_at.desc()).limit(limit).all()


def set_recommendation_status(db: Session, rec_id: int, status: str) -> PluginRecommendation:
    if status not in ("proposed", "accepted", "rejected"):
        raise ValueError("invalid status")
    row = db.query(PluginRecommendation).filter(PluginRecommendation.id == rec_id).first()
    if row is None:
        raise ValueError("recommendation not found")
    row.status = status
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def plugin_dict(p: MarketplacePlugin) -> Dict[str, Any]:
    return {"id": p.id, "key": p.key, "name": p.name, "category": p.category,
            "description": p.description, "version": p.version, "publisher": p.publisher,
            "installed": p.installed, "enabled": p.enabled}


def recommendation_dict(r: PluginRecommendation) -> Dict[str, Any]:
    return {"id": r.id, "plugin_key": r.plugin_key, "subject_ref": r.subject_ref,
            "action": r.action, "title": r.title, "rationale": r.rationale,
            "confidence": r.confidence, "priority": r.priority, "evidence": r.evidence,
            "params": r.params, "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None}

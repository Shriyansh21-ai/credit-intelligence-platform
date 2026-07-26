"""M3 — Early Warning Signal (EWS) Engine.

A banking-grade Early Warning framework. Given a company's assessment profile plus
an optional richer ``context`` (prior-period financials, MCA/tax flags, covenant
states, concentration and sector metrics), it detects the standard distress
signals and emits, for each: severity, confidence, business impact, recommended
action and supporting evidence. Signals aggregate into a 0-100 EWS score and a
green/amber/red band; red-band runs escalate into unified intelligence alerts.

Everything is deterministic and grounded in supplied data — a signal only fires
when its inputs are present (no fabrication; absent inputs simply don't trigger).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.autonomous import EWSAssessment
from . import alerts as alerts_svc
from . import data_access
from .common import SEVERITY_WEIGHT, band_from_score, clamp, evidence, pct_change

# EWS signal catalog: code -> (name, default recommended action).
EWS_CATALOG: Dict[str, Dict[str, str]] = {
    "cash_flow_deterioration": {"name": "Cash flow deterioration",
                                "action": "Review liquidity runway and short-term funding."},
    "margin_compression": {"name": "Margin compression",
                           "action": "Investigate cost base and pricing power."},
    "working_capital_stress": {"name": "Working capital stress",
                               "action": "Assess receivable/payable cycle and WC funding."},
    "sales_decline": {"name": "Sales decline",
                      "action": "Validate demand outlook and order book."},
    "rapid_leverage_increase": {"name": "Rapid leverage increase",
                                "action": "Reassess debt serviceability and covenants."},
    "director_change": {"name": "Director change(s)",
                        "action": "Confirm management continuity and governance."},
    "auditor_resignation": {"name": "Auditor resignation",
                            "action": "Escalate to committee; verify accounts integrity."},
    "tax_default": {"name": "Tax / statutory default",
                    "action": "Quantify liability; check for statutory dues priority."},
    "covenant_breach": {"name": "Loan covenant breach",
                        "action": "Trigger cure period; reassess facility terms."},
    "negative_trend": {"name": "Negative multi-period trend",
                       "action": "Deep-dive trend drivers; tighten monitoring frequency."},
    "sector_deterioration": {"name": "Sector deterioration",
                             "action": "Reweight sector exposure; apply sector overlay."},
    "supplier_concentration": {"name": "Supplier concentration",
                               "action": "Assess supply-chain single-point-of-failure risk."},
    "customer_concentration": {"name": "Customer concentration",
                               "action": "Stress revenue for loss of the top customer."},
}


def _signal(code: str, severity: str, confidence: float, impact: str,
            ev: List[dict]) -> Dict[str, Any]:
    meta = EWS_CATALOG[code]
    return {"code": code, "name": meta["name"], "severity": severity,
            "confidence": round(clamp(confidence), 2), "business_impact": impact,
            "recommended_action": meta["action"], "evidence": ev}


# ---------------------------------------------------------------------------
# Detectors — each returns 0..1 signals from (profile, context)
# ---------------------------------------------------------------------------
def _num(d: Dict[str, Any], *keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)):
            return v
    return None


def _detectors(profile: Dict[str, Any], ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    eng = profile.get("engine_input") or {}
    health = profile.get("health") or {}
    prev = ctx.get("previous") or {}
    out: List[Dict[str, Any]] = []

    # cash flow deterioration
    cf_now, cf_prev = _num(eng, "operating_cash_flow", "cash_flow"), _num(prev, "operating_cash_flow", "cash_flow")
    ch = pct_change(cf_prev, cf_now)
    if (ch is not None and ch < -0.1) or (health.get("liquidity") is not None and health["liquidity"] < 40):
        sev = "high" if (ch is not None and ch < -0.3) or (health.get("liquidity") or 100) < 25 else "medium"
        out.append(_signal("cash_flow_deterioration", sev, 0.75,
                           "Reduced ability to service obligations from operations.",
                           [evidence("operating_cash_flow_change", round(ch, 4) if ch is not None else None),
                            evidence("liquidity_health", health.get("liquidity"))]))

    # margin compression
    m_now, m_prev = _num(eng, "net_margin", "net_profit_margin"), _num(prev, "net_margin", "net_profit_margin")
    ch = pct_change(m_prev, m_now)
    if ch is not None and ch < -0.1:
        out.append(_signal("margin_compression", "high" if ch < -0.25 else "medium", 0.7,
                           "Falling profitability erodes debt-service coverage.",
                           [evidence("net_margin_change", round(ch, 4))]))

    # working capital stress
    wc = health.get("working_capital")
    wc_cycle = _num(eng, "working_capital_cycle_days", "wc_cycle_days")
    if (wc is not None and wc < 40) or (wc_cycle is not None and wc_cycle > 120):
        out.append(_signal("working_capital_stress", "medium" if (wc or 100) >= 25 else "high", 0.65,
                           "Cash locked in the operating cycle strains liquidity.",
                           [evidence("working_capital_health", wc), evidence("wc_cycle_days", wc_cycle)]))

    # sales decline
    r_now, r_prev = _num(eng, "revenue", "annual_revenue", "turnover"), _num(prev, "revenue", "annual_revenue", "turnover")
    ch = pct_change(r_prev, r_now)
    if ch is not None and ch < -0.1:
        out.append(_signal("sales_decline", "high" if ch < -0.25 else "medium", 0.75,
                           "Top-line contraction pressures coverage and covenants.",
                           [evidence("revenue_change", round(ch, 4))]))

    # rapid leverage increase
    l_now, l_prev = _num(eng, "debt_to_equity", "leverage"), _num(prev, "debt_to_equity", "leverage")
    ch = pct_change(l_prev, l_now)
    if (ch is not None and ch > 0.25) or (health.get("debt") is not None and health["debt"] < 35):
        out.append(_signal("rapid_leverage_increase", "high" if (ch or 0) > 0.5 else "medium", 0.7,
                           "Rising leverage increases default probability.",
                           [evidence("leverage_change", round(ch, 4) if ch is not None else None),
                            evidence("debt_health", health.get("debt"))]))

    # director change
    if ctx.get("director_changes"):
        n = ctx["director_changes"]
        out.append(_signal("director_change", "high" if n >= 2 else "medium", 0.8,
                           "Management churn signals possible governance instability.",
                           [evidence("director_changes", n, source="mca")]))

    # auditor resignation
    if ctx.get("auditor_resigned"):
        out.append(_signal("auditor_resignation", "critical", 0.9,
                           "Auditor exit is a strong red flag on accounts reliability.",
                           [evidence("auditor_resigned", True, source="mca")]))

    # tax default
    if ctx.get("tax_default") or ctx.get("gst_defaulter"):
        out.append(_signal("tax_default", "high", 0.8,
                           "Statutory dues take priority and signal cash stress.",
                           [evidence("tax_default", True, source="gst")]))

    # covenant breach
    breaches = ctx.get("covenant_breaches") or []
    if breaches:
        out.append(_signal("covenant_breach", "high", 0.85,
                           "Breach may accelerate the facility or trigger repricing.",
                           [evidence("breached_covenants", breaches, source="covenants")]))

    # negative multi-period trend
    trend = ctx.get("trend")  # 'improving'|'flat'|'deteriorating'
    if trend == "deteriorating":
        out.append(_signal("negative_trend", "medium", 0.6,
                           "Sustained deterioration compounds credit risk.",
                           [evidence("trend", trend)]))

    # sector deterioration
    sector_move = _num(ctx, "sector_index_change")
    if sector_move is not None and sector_move < -0.1:
        out.append(_signal("sector_deterioration", "medium" if sector_move > -0.25 else "high", 0.6,
                           "Sector-wide stress raises correlated default risk.",
                           [evidence("sector_index_change", round(sector_move, 4), source="market"),
                            evidence("industry", profile.get("industry"))]))

    # supplier concentration
    sc = _num(ctx, "supplier_concentration")
    if sc is not None and sc > 0.4:
        out.append(_signal("supplier_concentration", "high" if sc > 0.6 else "medium", 0.65,
                           "Dependence on few suppliers is a supply-chain vulnerability.",
                           [evidence("top_supplier_share", round(sc, 3))]))

    # customer concentration
    cc = _num(ctx, "customer_concentration")
    if cc is not None and cc > 0.4:
        out.append(_signal("customer_concentration", "high" if cc > 0.6 else "medium", 0.65,
                           "Loss of the top customer would materially hit revenue.",
                           [evidence("top_customer_share", round(cc, 3))]))

    return out


def evaluate(db: Session, *, company_ref: Optional[str] = None, assessment_id: Optional[int] = None,
             context: Optional[Dict[str, Any]] = None, tenant_id: Optional[int] = None,
             persist: bool = True, escalate: bool = True) -> Dict[str, Any]:
    """Run the EWS engine for a company and (optionally) persist + escalate."""
    ctx = context or {}
    assessment = data_access.resolve(db, assessment_id=assessment_id, company_ref=company_ref)
    prof = data_access.profile(assessment) or {"company_ref": company_ref or "unknown",
                                               "engine_input": {}, "health": {}, "industry": None}
    ref = prof.get("company_ref") or company_ref or "unknown"
    signals = _detectors(prof, ctx)

    # Aggregate score: severity-weighted, confidence-scaled, saturating.
    raw = sum(SEVERITY_WEIGHT.get(s["severity"], 0.3) * s["confidence"] for s in signals)
    ews_score = round(clamp(100 * (1 - (0.75 ** raw)) if raw else 0.0, 0, 100), 2)
    band = band_from_score(ews_score)
    summary = _summarize(ref, signals, band)

    result = {
        "company_ref": ref, "assessment_id": prof.get("assessment_id"),
        "ews_score": ews_score, "ews_band": band, "signal_count": len(signals),
        "signals": signals, "summary": summary,
    }

    if persist:
        row = EWSAssessment(tenant_id=tenant_id, company_ref=ref,
                            assessment_id=prof.get("assessment_id"), ews_score=ews_score,
                            ews_band=band, signal_count=len(signals), signals=signals,
                            summary=summary)
        db.add(row)
        db.commit()
        db.refresh(row)
        result["id"] = row.id

    if escalate and band == "red":
        top = max(signals, key=lambda s: SEVERITY_WEIGHT.get(s["severity"], 0), default=None)
        if top:
            alerts_svc.raise_alert(
                db, company_ref=ref, category="ews", alert_type=top["code"],
                title=f"EWS RED: {top['name']}", severity=top["severity"],
                confidence=top["confidence"], business_impact=top["business_impact"],
                recommended_action=top["recommended_action"], evidence=top["evidence"],
                exposure=prof.get("exposure"), assessment_id=prof.get("assessment_id"),
                tenant_id=tenant_id, dedup_key=f"ews:{ref}")
    return result


def _summarize(ref: str, signals: List[dict], band: str) -> str:
    if not signals:
        return f"No early-warning signals detected for {ref}. Band: GREEN."
    names = ", ".join(s["name"] for s in signals[:4])
    more = f" (+{len(signals) - 4} more)" if len(signals) > 4 else ""
    return (f"{ref} shows {len(signals)} early-warning signal(s) — {names}{more}. "
            f"Overall band: {band.upper()}.")


def history(db: Session, company_ref: str, *, tenant_id: Optional[int] = None,
            limit: int = 20) -> List[EWSAssessment]:
    return (db.query(EWSAssessment)
            .filter(EWSAssessment.tenant_id == tenant_id, EWSAssessment.company_ref == company_ref)
            .order_by(EWSAssessment.created_at.desc()).limit(limit).all())

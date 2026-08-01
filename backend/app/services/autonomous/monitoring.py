"""M2 — Real-Time Risk Monitoring engine.

A continuous monitoring engine that ingests *observations* from every platform
source (financials, connectors, payments, GST, MCA, bureau, portfolio, news
document uploads, market data), detects material changes deterministically, and
turns them into prioritized :class:`MonitoringSignal` rows. High-severity signals
are escalated into unified :class:`IntelligenceAlert` rows and can spawn
monitoring tasks + reassessment recommendations.

The engine is *pull*-driven: callers hand it the current (and optional previous)
observation for a company. This keeps the engine testable and provider-agnostic
the connectors / sync jobs supply the observations in production, and a
background job can call :func:`run_monitoring` on a schedule.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.autonomous import MonitoringSignal
from . import alerts as alerts_svc
from .common import clamp, pct_change, priority_score, severity_from_score

# A detector takes an observation dict and returns a list of raw signal dicts.
Detector = Callable[[Dict[str, Any]], List[Dict[str, Any]]]

MONITORING_SOURCES = [
    "financial", "connector", "payment", "gst", "mca", "bureau",
    "portfolio", "news", "document", "market",
]


# ---------------------------------------------------------------------------
# Detectors — one per source. Each is a pure function of the observation.
# ---------------------------------------------------------------------------
def _sig(source, signal_type, direction, severity, detail, *, magnitude=None, payload=None):
    return {"source": source, "signal_type": signal_type, "direction": direction,
            "severity": severity, "detail": detail, "magnitude": magnitude,
            "payload": payload or {}}


def detect_financial(obs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compare current vs previous financial metrics for deterioration."""
    cur = obs.get("current") or {}
    prev = obs.get("previous") or {}
    out: List[Dict[str, Any]] = []
    # (metric, human, worse_direction) — 'down' means a drop is bad.
    checks = [
        ("revenue", "Revenue", "down"), ("net_margin", "Net margin", "down"),
        ("current_ratio", "Current ratio", "down"), ("dscr", "DSCR", "down"),
        ("cash_balance", "Cash balance", "down"), ("ebitda", "EBITDA", "down"),
        ("debt_to_equity", "Debt-to-equity", "up"), ("leverage", "Leverage", "up"),
    ]
    for metric, human, bad_dir in checks:
        change = pct_change(prev.get(metric), cur.get(metric))
        if change is None:
            continue
        deteriorating = (change < 0 and bad_dir == "down") or (change > 0 and bad_dir == "up")
        mag = abs(change)
        if not deteriorating or mag < 0.05:
            continue
        score = clamp(mag * 100, 0, 100)
        out.append(_sig("financial", f"{metric}_deterioration",
                        "negative", severity_from_score(score),
                        f"{human} moved {change:+.1%}", magnitude=round(change, 4),
                        payload={"metric": metric, "from": prev.get(metric), "to": cur.get(metric)}))
    return out


def detect_payment(obs: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    dpd = obs.get("dpd")
    if dpd is not None and dpd > 0:
        score = clamp(dpd / 90 * 100, 0, 100)
        out.append(_sig("payment", "payment_delay", "negative", severity_from_score(score),
                        f"{dpd} days past due", magnitude=dpd, payload={"dpd": dpd}))
    bounced = obs.get("bounced_cheques") or obs.get("bounced")
    if bounced:
        score = clamp(bounced * 30, 0, 100)
        out.append(_sig("payment", "cheque_bounce", "negative", severity_from_score(score),
                        f"{bounced} cheque bounce(s)", magnitude=bounced))
    return out


def detect_gst(obs: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    status = (obs.get("filing_status") or "").lower()
    if status in ("delayed", "late", "non_compliant", "defaulter"):
        sev = "high" if status in ("non_compliant", "defaulter") else "medium"
        out.append(_sig("gst", "gst_filing_issue", "negative", sev,
                        f"GST filing status: {status}", payload={"filing_status": status}))
    change = pct_change(obs.get("previous_turnover"), obs.get("turnover"))
    if change is not None and change < -0.15:
        out.append(_sig("gst", "gst_turnover_drop", "negative",
                        severity_from_score(clamp(abs(change) * 100, 0, 100)),
                        f"GST turnover down {change:+.1%}", magnitude=round(change, 4)))
    return out


def detect_mca(obs: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    if obs.get("director_changes"):
        n = obs["director_changes"]
        out.append(_sig("mca", "director_change", "negative",
                        "high" if n >= 2 else "medium",
                        f"{n} director change(s) filed", magnitude=n))
    if obs.get("auditor_resigned"):
        out.append(_sig("mca", "auditor_resignation", "negative", "critical",
                        "Statutory auditor resignation filed"))
    if obs.get("charge_created"):
        out.append(_sig("mca", "new_charge", "negative", "medium",
                        "New charge/lien registered with MCA"))
    if (obs.get("status") or "").lower() in ("strike_off", "under_liquidation", "dormant"):
        out.append(_sig("mca", "adverse_status", "negative", "critical",
                        f"MCA status: {obs.get('status')}"))
    return out


def detect_bureau(obs: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    change = obs.get("score")
    prev = obs.get("previous_score")
    if change is not None and prev is not None and change < prev:
        drop = prev - change
        score = clamp(drop / 100 * 100, 0, 100)
        out.append(_sig("bureau", "bureau_score_drop", "negative", severity_from_score(score),
                        f"Bureau score fell {drop:.0f} pts ({prev}→{change})", magnitude=-drop))
    if obs.get("new_defaults"):
        out.append(_sig("bureau", "new_default", "negative", "critical",
                        f"{obs['new_defaults']} new default(s) reported"))
    if obs.get("overdue_amount"):
        out.append(_sig("bureau", "overdue_reported", "negative", "high",
                        f"Overdue amount reported: {obs['overdue_amount']}"))
    return out


def detect_connector(obs: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    if obs.get("stale_days") and obs["stale_days"] > 30:
        out.append(_sig("connector", "stale_data", "negative", "low",
                        f"Connector data {obs['stale_days']}d stale"))
    if obs.get("new_snapshot"):
        out.append(_sig("connector", "data_refresh", "neutral", "info",
                        "New connector snapshot ingested"))
    return out


def detect_portfolio(obs: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    conc = obs.get("concentration")
    if conc is not None and conc > 0.25:
        out.append(_sig("portfolio", "concentration_breach", "negative",
                        "high" if conc > 0.4 else "medium",
                        f"Single-name concentration {conc:.0%}", magnitude=conc))
    return out


def detect_news(obs: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for item in obs.get("items", []) if isinstance(obs, dict) else []:
        sentiment = (item.get("sentiment") or "").lower()
        if sentiment in ("negative", "very_negative"):
            sev = "high" if sentiment == "very_negative" else "medium"
            out.append(_sig("news", "adverse_news", "negative", sev,
                            item.get("headline", "Adverse news event"),
                            payload={"headline": item.get("headline")}))
    return out


def detect_document(obs: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    if obs.get("new_upload"):
        out.append(_sig("document", "document_uploaded", "neutral", "info",
                        f"New document uploaded: {obs.get('doc_type', 'document')}"))
    if obs.get("validation_failed"):
        out.append(_sig("document", "document_validation_failed", "negative", "medium",
                        "Uploaded document failed validation"))
    return out


def detect_market(obs: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    move = obs.get("sector_index_change")
    if move is not None and move < -0.1:
        out.append(_sig("market", "sector_downturn", "negative",
                        severity_from_score(clamp(abs(move) * 100, 0, 100)),
                        f"Sector index down {move:+.1%}", magnitude=move))
    if obs.get("commodity_spike"):
        out.append(_sig("market", "commodity_spike", "negative", "medium",
                        f"Input commodity price spike {obs['commodity_spike']:+.1%}"))
    return out


DETECTORS: Dict[str, Detector] = {
    "financial": detect_financial, "payment": detect_payment, "gst": detect_gst,
    "mca": detect_mca, "bureau": detect_bureau, "connector": detect_connector,
    "portfolio": detect_portfolio, "news": detect_news, "document": detect_document,
    "market": detect_market,
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
def record_signal(db: Session, *, company_ref: str, source: str, signal_type: str,
                  severity: str = "info", direction: str = "neutral",
                  detail: Optional[str] = None, magnitude: Optional[float] = None,
                  payload: Optional[dict] = None, exposure: Optional[float] = None,
                  assessment_id: Optional[int] = None, tenant_id: Optional[int] = None,
                  confidence: float = 0.7) -> MonitoringSignal:
    row = MonitoringSignal(
        tenant_id=tenant_id, company_ref=company_ref, assessment_id=assessment_id,
        source=source, signal_type=signal_type, direction=direction, magnitude=magnitude,
        severity=severity, priority_score=priority_score(severity, confidence, exposure=exposure),
        detail=detail, payload=payload or {})
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def run_monitoring(db: Session, company_ref: str, observations: Dict[str, Any], *,
                   assessment_id: Optional[int] = None, tenant_id: Optional[int] = None,
                   exposure: Optional[float] = None, escalate: bool = True) -> Dict[str, Any]:
    """Run every relevant detector, persist signals, and escalate the material ones.

    Returns a summary with the signals, generated alerts, whether a reassessment
    is recommended, and an overall priority score.
    """
    signals: List[MonitoringSignal] = []
    for source, obs in (observations or {}).items():
        detector = DETECTORS.get(source)
        if detector is None or obs is None:
            continue
        try:
            raw = detector(obs)
        except Exception:
            raw = []
        for r in raw:
            signals.append(record_signal(
                db, company_ref=company_ref, source=r["source"], signal_type=r["signal_type"],
                severity=r["severity"], direction=r["direction"], detail=r["detail"],
                magnitude=r.get("magnitude"), payload=r.get("payload"), exposure=exposure,
                assessment_id=assessment_id, tenant_id=tenant_id))

    generated_alerts = []
    reassess = False
    max_priority = 0.0
    for s in signals:
        max_priority = max(max_priority, s.priority_score)
        if escalate and s.severity in ("high", "critical"):
            alert = alerts_svc.raise_alert(
                db, company_ref=company_ref, category="monitoring", alert_type=s.signal_type,
                title=f"{s.source.title()} alert: {s.signal_type.replace('_', ' ')}",
                severity=s.severity, confidence=0.75, business_impact=s.detail,
                recommended_action=_recommend_action(s), evidence=[{
                    "label": s.signal_type, "value": s.detail, "source": s.source}],
                exposure=exposure, assessment_id=assessment_id, tenant_id=tenant_id,
                dedup_key=f"monitoring:{s.signal_type}:{company_ref}")
            generated_alerts.append(alert)
            reassess = True

    return {
        "company_ref": company_ref,
        "signals": [_signal_dict(s) for s in signals],
        "signal_count": len(signals),
        "alerts": [alerts_svc.as_dict(a) for a in generated_alerts],
        "reassessment_recommended": reassess,
        "priority_score": round(max_priority, 2),
        "escalation": _escalation(max_priority),
    }


def _recommend_action(s: MonitoringSignal) -> str:
    mapping = {
        "auditor_resignation": "Escalate to credit committee; freeze new exposure.",
        "adverse_status": "Escalate to credit committee; initiate recovery review.",
        "new_default": "Downgrade rating and trigger immediate reassessment.",
        "payment_delay": "Contact relationship manager; review repayment capacity.",
        "director_change": "Verify management continuity; request board resolution.",
        "concentration_breach": "Rebalance portfolio; cap further exposure to this name.",
    }
    return mapping.get(s.signal_type, "Trigger reassessment and notify the risk owner.")


def _escalation(priority: float) -> str:
    if priority >= 80:
        return "credit_committee"
    if priority >= 60:
        return "risk_manager"
    if priority >= 40:
        return "senior_analyst"
    return "monitor"


def _signal_dict(s: MonitoringSignal) -> Dict[str, Any]:
    return {"id": s.id, "source": s.source, "signal_type": s.signal_type,
            "direction": s.direction, "severity": s.severity, "magnitude": s.magnitude,
            "priority_score": s.priority_score, "detail": s.detail,
            "detected_at": s.detected_at.isoformat() if s.detected_at else None}


def recent_signals(db: Session, *, company_ref: Optional[str] = None,
                   tenant_id: Optional[int] = None, source: Optional[str] = None,
                   limit: int = 100) -> List[MonitoringSignal]:
    q = db.query(MonitoringSignal).filter(MonitoringSignal.tenant_id == tenant_id)
    if company_ref:
        q = q.filter(MonitoringSignal.company_ref == company_ref)
    if source:
        q = q.filter(MonitoringSignal.source == source)
    return q.order_by(MonitoringSignal.detected_at.desc()).limit(limit).all()

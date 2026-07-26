"""M10 — Natural Language Analytics.

Translates free-text banking questions into a *structured query* (intent +
filters + sort + limit) and executes it deterministically against platform data.
No LLM is required — a transparent, auditable rule parser handles the supported
question families and logs every query. (The M4 LLM adapter can optionally phrase
the results, but the numbers always come from this deterministic path.)

Supported families::

    "Show high-risk textile companies."
    "Which customers deteriorated this month?"
    "Top borrowers by exposure."
    "Show covenant breaches."
    "Which companies have improving cash flow?"
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.autonomous import EWSAssessment, MonitoringSignal, NLQueryLog
from . import alerts as alerts_svc
from . import data_access

_RISK_HIGH = ["high-risk", "high risk", "risky", "distressed", "risky companies"]
_RISK_LOW = ["low-risk", "low risk", "safe", "healthy", "strong"]
_SORT_WORDS = ["top", "highest", "largest", "biggest", "most"]
_METRIC_WORDS = {
    "exposure": ["exposure", "borrower", "borrowers", "loan", "outstanding"],
    "pd": ["pd", "probability of default", "riskiest"],
    "credit_score": ["score", "rating", "creditworthy"],
}


def parse(question: str, industries: List[str]) -> Dict[str, Any]:
    """Parse a question into a structured query dict + a confidence."""
    q = (question or "").lower().strip()
    sq: Dict[str, Any] = {"intent": "list_companies", "filters": {}, "sort": None,
                          "order": "desc", "limit": 20}
    conf = 0.5

    # covenant breaches
    if "covenant" in q:
        sq["intent"] = "covenant_breaches"
        return {"structured_query": sq, "confidence": 0.85}

    # deterioration
    if any(w in q for w in ["deteriorat", "declin", "worsen", "downgrad", "got worse"]):
        sq["intent"] = "deteriorated"
        if "this month" in q or "month" in q:
            sq["filters"]["window"] = "month"
        return {"structured_query": sq, "confidence": 0.8}

    # improving cash flow
    if "improv" in q and ("cash" in q or "cashflow" in q or "cash flow" in q):
        sq["intent"] = "improving_cash_flow"
        return {"structured_query": sq, "confidence": 0.8}

    # alerts
    if "alert" in q or "warning" in q:
        sq["intent"] = "alerts"
        return {"structured_query": sq, "confidence": 0.75}

    # top-N by metric
    if any(w in q for w in _SORT_WORDS):
        sq["intent"] = "top_by"
        for metric, words in _METRIC_WORDS.items():
            if any(w in q for w in words):
                sq["sort"] = metric
                break
        sq["sort"] = sq["sort"] or "exposure"
        conf = 0.8

    # risk-level filter
    if any(w in q for w in _RISK_HIGH):
        sq["filters"]["risk"] = "high"
        conf = max(conf, 0.75)
    elif any(w in q for w in _RISK_LOW):
        sq["filters"]["risk"] = "low"
        conf = max(conf, 0.75)

    # industry filter (dynamic match against the actual book + common sectors)
    known = set(i.lower() for i in industries if i) | {
        "textile", "manufacturing", "retail", "pharma", "it", "services",
        "construction", "agriculture", "trading", "logistics", "steel", "auto"}
    for token in re.findall(r"[a-z]+", q):
        if token in known and token not in ("companies", "company"):
            sq["filters"]["industry"] = token
            conf = max(conf, 0.7)
            break

    # explicit limit ("top 5")
    m = re.search(r"\b(top|first)\s+(\d+)", q)
    if m:
        sq["limit"] = int(m.group(2))

    return {"structured_query": sq, "confidence": round(conf, 2)}


def _match_industry(prof: Dict[str, Any], target: str) -> bool:
    return target in (prof.get("industry") or "").lower()


def execute(db: Session, sq: Dict[str, Any], *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    intent = sq.get("intent", "list_companies")
    filters = sq.get("filters", {})
    limit = int(sq.get("limit", 20))

    if intent == "covenant_breaches":
        rows = alerts_svc.list_alerts(db, tenant_id=tenant_id, limit=limit)
        data = [alerts_svc.as_dict(a) for a in rows
                if "covenant" in (a.alert_type or "") or "covenant" in (a.title or "").lower()]
        return {"columns": ["company_ref", "title", "severity"], "rows": data, "count": len(data)}

    if intent == "alerts":
        rows = alerts_svc.list_alerts(db, tenant_id=tenant_id, status="open", limit=limit)
        data = [alerts_svc.as_dict(a) for a in rows]
        return {"columns": ["company_ref", "title", "severity", "priority_score"],
                "rows": data, "count": len(data)}

    if intent == "deteriorated":
        # companies with a red/amber EWS or negative monitoring signals recently
        ews_rows = (db.query(EWSAssessment).filter(EWSAssessment.tenant_id == tenant_id,
                    EWSAssessment.ews_band.in_(["amber", "red"]))
                    .order_by(EWSAssessment.created_at.desc()).limit(500).all())
        seen = {}
        for r in ews_rows:
            seen.setdefault(r.company_ref, {"company_ref": r.company_ref, "ews_score": r.ews_score,
                                            "ews_band": r.ews_band})
        sig_rows = (db.query(MonitoringSignal).filter(MonitoringSignal.tenant_id == tenant_id,
                    MonitoringSignal.direction == "negative")
                    .order_by(MonitoringSignal.detected_at.desc()).limit(500).all())
        for s in sig_rows:
            seen.setdefault(s.company_ref, {"company_ref": s.company_ref,
                                            "signal": s.signal_type, "severity": s.severity})
        data = list(seen.values())[:limit]
        return {"columns": ["company_ref", "ews_band", "ews_score"], "rows": data, "count": len(data)}

    # profile-based intents
    profs = data_access.portfolio_profiles(db)
    if filters.get("risk") == "high":
        profs = [p for p in profs if (p.get("pd") or 0) >= 0.10]
    elif filters.get("risk") == "low":
        profs = [p for p in profs if (p.get("pd") or 1) < 0.05]
    if filters.get("industry"):
        profs = [p for p in profs if _match_industry(p, filters["industry"])]

    if intent == "improving_cash_flow":
        profs = [p for p in profs if ((p.get("health") or {}).get("liquidity") or 0) >= 65]
        profs.sort(key=lambda p: -((p.get("health") or {}).get("liquidity") or 0))

    sort = sq.get("sort")
    if intent == "top_by" or sort:
        key = sort or "exposure"
        reverse = sq.get("order", "desc") == "desc"
        if key == "pd":
            reverse = True
        profs.sort(key=lambda p: (p.get(key) if isinstance(p.get(key), (int, float)) else -1),
                   reverse=reverse)

    rows = [{"company_ref": p.get("company_ref"), "industry": p.get("industry"),
             "rating": p.get("rating"), "pd": p.get("pd"), "credit_score": p.get("credit_score"),
             "exposure": p.get("exposure")} for p in profs[:limit]]
    return {"columns": ["company_ref", "industry", "rating", "pd", "credit_score", "exposure"],
            "rows": rows, "count": len(rows)}


def query(db: Session, question: str, *, user_id: Optional[int] = None,
          tenant_id: Optional[int] = None, persist: bool = True) -> Dict[str, Any]:
    """Full NL → structured → execute pipeline with logging."""
    industries = sorted({(p.get("industry") or "") for p in data_access.portfolio_profiles(db)})
    parsed = parse(question, industries)
    sq = parsed["structured_query"]
    result = execute(db, sq, tenant_id=tenant_id)

    if persist:
        row = NLQueryLog(tenant_id=tenant_id, user_id=user_id, question=question,
                         intent=sq["intent"], structured_query=sq,
                         result_count=result["count"], confidence=parsed["confidence"])
        db.add(row)
        db.commit()

    return {"question": question, "intent": sq["intent"], "structured_query": sq,
            "confidence": parsed["confidence"], **result}


def history(db: Session, *, user_id: Optional[int] = None, tenant_id: Optional[int] = None,
            limit: int = 50) -> List[NLQueryLog]:
    q = db.query(NLQueryLog).filter(NLQueryLog.tenant_id == tenant_id)
    if user_id is not None:
        q = q.filter(NLQueryLog.user_id == user_id)
    return q.order_by(NLQueryLog.created_at.desc()).limit(limit).all()

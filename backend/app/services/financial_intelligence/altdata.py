"""M7 — Alternative Data Intelligence.

Convert non-traditional signals — satellite, shipping, supply-chain, web traffic
customer reviews, social media, news sentiment, patents, hiring, payments
merchant analytics, footfall, digital presence — into normalized *enterprise
risk signals* (direction, magnitude, confidence, score) that can feed the credit
and portfolio engines. Deterministic normalization; ``source`` is stored so live
providers can be attached later without schema change.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.financial_intelligence import FinAltSignal
from . import data_access as da
from .common import checksum, clamp, grounding_block, iso, mean, safe_div, to_float, utcnow

# signal_type -> (polarity, weight). Polarity: +1 higher value = healthier.
SIGNAL_TYPES: Dict[str, Dict[str, Any]] = {
    "satellite": {"polarity": +1, "weight": 0.8, "label": "Facility/asset activity"},
    "shipping": {"polarity": +1, "weight": 0.9, "label": "Shipping & logistics volume"},
    "supply_chain": {"polarity": +1, "weight": 0.9, "label": "Supply-chain reliability"},
    "web_traffic": {"polarity": +1, "weight": 0.7, "label": "Website traffic trend"},
    "reviews": {"polarity": +1, "weight": 0.6, "label": "Customer review sentiment"},
    "social": {"polarity": +1, "weight": 0.5, "label": "Social-media sentiment"},
    "news_sentiment": {"polarity": +1, "weight": 0.7, "label": "News sentiment"},
    "patents": {"polarity": +1, "weight": 0.6, "label": "Patent/innovation activity"},
    "hiring": {"polarity": +1, "weight": 0.8, "label": "Hiring trend"},
    "payments": {"polarity": +1, "weight": 1.0, "label": "Payment punctuality"},
    "merchant": {"polarity": +1, "weight": 0.9, "label": "Merchant transaction volume"},
    "footfall": {"polarity": +1, "weight": 0.7, "label": "Store footfall"},
    "digital_presence": {"polarity": +1, "weight": 0.5, "label": "Digital presence strength"},
}


def _normalize(signal_type: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map a raw payload to a normalized risk signal in [-1, +1].

    ``raw`` may provide ``value`` (a 0-100 health index), or ``current`` &
    ``baseline`` (a level whose change is scored), plus optional ``confidence``.
    """
    spec = SIGNAL_TYPES[signal_type]
    if "value" in raw:
        norm = clamp((to_float(raw["value"]) - 50.0) / 50.0, -1.0, 1.0)
    elif "current" in raw and "baseline" in raw:
        base = to_float(raw["baseline"]) or 1.0
        change = safe_div(to_float(raw["current"]) - base, abs(base), 0.0) or 0.0
        norm = clamp(change, -1.0, 1.0)
    else:
        norm = 0.0
    norm *= spec["polarity"]
    confidence = clamp(to_float(raw.get("confidence", 0.7)), 0.0, 1.0)
    magnitude = round(abs(norm), 3)
    direction = "improving" if norm > 0.05 else "deteriorating" if norm < -0.05 else "stable"
    # Risk score: higher = riskier. Map health [-1,+1] -> risk [1,0].
    risk_score = round(clamp((1 - norm) / 2.0, 0.0, 1.0), 3)
    return {"normalized": round(norm, 3), "magnitude": magnitude, "direction": direction,
            "confidence": confidence, "risk_score": risk_score, "label": spec["label"],
            "weight": spec["weight"]}


def ingest_signal(db: Session, *, subject_ref: str, signal_type: str, raw: Dict[str, Any],
                  source: str = "synthetic", as_of: Optional[str] = None,
                  tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    if signal_type not in SIGNAL_TYPES:
        raise ValueError(f"unknown signal_type '{signal_type}'")
    risk_signal = _normalize(signal_type, raw or {})
    row = FinAltSignal(tenant_id=tenant_id, subject_ref=subject_ref, signal_type=signal_type,
                       source=source, as_of=as_of or iso(utcnow())[:10], raw=raw or {},
                       risk_signal=risk_signal, score=risk_signal["risk_score"], created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"signal_id": row.id, "subject_ref": subject_ref, "signal_type": signal_type,
            "risk_signal": risk_signal}


def list_signals(db: Session, *, subject_ref: Optional[str] = None, signal_type: Optional[str] = None,
                 limit: int = 100, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinAltSignal)
    if tenant_id is not None:
        q = q.filter(FinAltSignal.tenant_id == tenant_id)
    if subject_ref:
        q = q.filter(FinAltSignal.subject_ref == subject_ref)
    if signal_type:
        q = q.filter(FinAltSignal.signal_type == signal_type)
    return [{"signal_id": s.id, "subject_ref": s.subject_ref, "signal_type": s.signal_type,
             "source": s.source, "score": s.score, "risk_signal": s.risk_signal,
             "as_of": s.as_of, "created_at": iso(s.created_at)}
            for s in q.order_by(FinAltSignal.id.desc()).limit(limit).all()]


def composite(db: Session, *, subject_ref: str, tenant_id: Optional[int] = None,
              created_by: Optional[str] = None) -> Dict[str, Any]:
    """Blend all signals for a subject into one enterprise alt-data risk signal."""
    signals = list_signals(db, subject_ref=subject_ref, limit=200, tenant_id=tenant_id)
    if not signals:
        return {"subject_ref": subject_ref, "signal_count": 0, "composite_risk_score": None}
    num = den = 0.0
    conf = []
    contributions = []
    for s in signals:
        rs = s["risk_signal"] or {}
        w = to_float(rs.get("weight", 0.5)) * to_float(rs.get("confidence", 0.7))
        num += to_float(rs.get("risk_score", 0.5)) * w
        den += w
        conf.append(to_float(rs.get("confidence", 0.7)))
        contributions.append({"signal_type": s["signal_type"], "risk_score": rs.get("risk_score"),
                              "direction": rs.get("direction"), "weight": rs.get("weight")})
    score = round(safe_div(num, den, 0.5), 3)
    band = "high" if score >= 0.65 else "medium" if score >= 0.4 else "low"
    results = {"subject_ref": subject_ref, "signal_count": len(signals),
               "composite_risk_score": score, "risk_band": band,
               "avg_confidence": round(mean(conf), 3) if conf else 0.0,
               "contributions": contributions,
               "enterprise_risk_signal": {
                   "direction": "negative" if score >= 0.6 else "positive" if score <= 0.4 else "neutral",
                   "pd_adjustment_pct": round((score - 0.5) * 40, 1),  # ±20% PD tilt suggestion
               }}
    g = grounding_block("Alternative-Data Composite", results)
    # Persist the composite as a signal row of type 'composite' for auditability.
    row = FinAltSignal(tenant_id=tenant_id, subject_ref=subject_ref, signal_type="payments",
                       source="composite", raw={"signal_count": len(signals)},
                       risk_signal={**results, "grounding": g}, score=score, created_by=created_by)
    db.add(row)
    db.commit()
    return results

"""M11 — Continuous learning pipeline.

Closes the loop from production outcomes back into model improvement. It captures
human feedback (ratings, corrections, analyst notes), approval outcomes and
repayment/default signals, then evaluates retraining triggers and records
versioned training events. Nothing retrains a model directly here — training
events are *proposals* that flow into the governance registry (M12) and the
existing Phase 6 ML platform — but every signal, trigger and event is durable and
versioned so the improvement history is auditable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ai_platform import (
    AIPFeedback, AIPLearningSignal, AIPTrainingEvent,
)
from backend.app.services.ai_platform import common

# Default retraining trigger thresholds (overridable per call).
_TRIGGERS = {
    "negative_feedback": 5,   # >= N negative feedback items
    "default_signals": 3,     # >= N observed defaults
    "corrections": 5,         # >= N corrections
    "drift_signals": 1,       # any drift signal
}


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------
def record_feedback(db: Session, *, target_type: str, target_ref: Optional[str] = None,
                    feedback_type: str = "rating", rating: Optional[float] = None,
                    label: Optional[str] = None, comment: Optional[str] = None,
                    correction: Optional[Dict[str, Any]] = None,
                    user_ref: Optional[str] = None, meta: Optional[Dict[str, Any]] = None,
                    tenant_id: Optional[int] = None) -> AIPFeedback:
    row = AIPFeedback(tenant_id=tenant_id, target_type=target_type, target_ref=target_ref,
                      feedback_type=feedback_type, rating=rating, label=label,
                      comment=comment, correction=correction or {}, user_ref=user_ref,
                      meta=meta or {}, created_at=common.utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def record_signal(db: Session, *, signal_type: str, target_ref: Optional[str] = None,
                  source: Optional[str] = None, payload: Optional[Dict[str, Any]] = None,
                  outcome: Optional[str] = None,
                  tenant_id: Optional[int] = None) -> AIPLearningSignal:
    row = AIPLearningSignal(tenant_id=tenant_id, signal_type=signal_type, source=source,
                            target_ref=target_ref, payload=payload or {}, outcome=outcome,
                            processed=False, created_at=common.utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Retraining triggers
# ---------------------------------------------------------------------------
def _is_negative(f: AIPFeedback) -> bool:
    if f.rating is not None and f.rating < 0.4:
        return True
    return (f.label or "").lower() in ("negative", "wrong", "reject", "bad")


def evaluate_triggers(db: Session, *, tenant_id: Optional[int] = None,
                      thresholds: Optional[Dict[str, int]] = None,
                      create_events: bool = True,
                      created_by: Optional[str] = None) -> Dict[str, Any]:
    th = {**_TRIGGERS, **(thresholds or {})}
    fb = db.query(AIPFeedback).filter(AIPFeedback.tenant_id == tenant_id).all()
    neg = sum(1 for f in fb if _is_negative(f))
    corrections = sum(1 for f in fb if f.feedback_type == "correction" or f.correction)
    sig = (db.query(AIPLearningSignal)
           .filter(AIPLearningSignal.tenant_id == tenant_id,
                   AIPLearningSignal.processed.is_(False)).all())
    defaults = sum(1 for s in sig if s.signal_type == "default")
    drift = sum(1 for s in sig if s.signal_type == "drift")

    fired: List[Dict[str, Any]] = []
    checks = [("negative_feedback", neg, th["negative_feedback"]),
              ("default_signals", defaults, th["default_signals"]),
              ("corrections", corrections, th["corrections"]),
              ("drift_signals", drift, th["drift_signals"])]
    events: List[int] = []
    for name, value, limit in checks:
        if value >= limit:
            fired.append({"trigger": name, "value": value, "threshold": limit})
            if create_events:
                ev = create_training_event(db, trigger=name,
                                           notes=f"Auto-triggered: {name}={value} (>= {limit})",
                                           metrics={"observed": value, "threshold": limit},
                                           tenant_id=tenant_id, created_by=created_by)
                events.append(ev.id)
    # Mark signals processed once evaluated.
    for s in sig:
        s.processed = True
    db.commit()
    return {"fired": fired, "training_events": events,
            "counts": {"negative_feedback": neg, "defaults": defaults,
                       "corrections": corrections, "drift": drift}}


# ---------------------------------------------------------------------------
# Training events (versioned)
# ---------------------------------------------------------------------------
def create_training_event(db: Session, *, trigger: str, dataset_ref: Optional[str] = None,
                          model_ref: Optional[str] = None, notes: Optional[str] = None,
                          metrics: Optional[Dict[str, Any]] = None,
                          tenant_id: Optional[int] = None,
                          created_by: Optional[str] = None) -> AIPTrainingEvent:
    count = db.query(AIPTrainingEvent).filter(AIPTrainingEvent.tenant_id == tenant_id).count()
    version = f"v{count + 1}"
    row = AIPTrainingEvent(tenant_id=tenant_id, trigger=trigger, dataset_ref=dataset_ref,
                           model_ref=model_ref, status="proposed", metrics=metrics or {},
                           version=version, notes=notes, created_by=created_by,
                           created_at=common.utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_training_event(db: Session, *, event_id: int, status: Optional[str] = None,
                          metrics: Optional[Dict[str, Any]] = None,
                          model_ref: Optional[str] = None) -> AIPTrainingEvent:
    row = db.query(AIPTrainingEvent).filter(AIPTrainingEvent.id == event_id).first()
    if row is None:
        raise ValueError("training event not found")
    if status:
        row.status = status
    if metrics is not None:
        row.metrics = {**(row.metrics or {}), **metrics}
    if model_ref:
        row.model_ref = model_ref
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
def list_feedback(db, *, tenant_id=None, target_type=None, limit=100) -> List[Dict[str, Any]]:
    q = db.query(AIPFeedback).filter(AIPFeedback.tenant_id == tenant_id)
    if target_type:
        q = q.filter(AIPFeedback.target_type == target_type)
    return [{"id": f.id, "target_type": f.target_type, "target_ref": f.target_ref,
             "feedback_type": f.feedback_type, "rating": f.rating, "label": f.label,
             "created_at": common.iso(f.created_at)}
            for f in q.order_by(AIPFeedback.id.desc()).limit(limit).all()]


def list_training_events(db, *, tenant_id=None, limit=100) -> List[Dict[str, Any]]:
    rows = (db.query(AIPTrainingEvent).filter(AIPTrainingEvent.tenant_id == tenant_id)
            .order_by(AIPTrainingEvent.id.desc()).limit(limit).all())
    return [{"id": r.id, "trigger": r.trigger, "status": r.status, "version": r.version,
             "model_ref": r.model_ref, "metrics": r.metrics,
             "created_at": common.iso(r.created_at)} for r in rows]


def stats(db, *, tenant_id=None) -> Dict[str, Any]:
    fb = db.query(AIPFeedback).filter(AIPFeedback.tenant_id == tenant_id).all()
    ratings = [f.rating for f in fb if f.rating is not None]
    return {"feedback": len(fb),
            "mean_rating": common.round_opt(sum(ratings) / len(ratings), 4) if ratings else None,
            "negative": sum(1 for f in fb if _is_negative(f)),
            "signals": db.query(AIPLearningSignal).filter(AIPLearningSignal.tenant_id == tenant_id).count(),
            "training_events": db.query(AIPTrainingEvent).filter(AIPTrainingEvent.tenant_id == tenant_id).count()}

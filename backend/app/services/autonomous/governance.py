"""M13 — Model Governance Platform.

A governance layer *on top of* the model registry (it never rewrites it).
It adds the formal controls a regulated bank needs around ML: a validation gate
(``model_validations``), an immutable governance audit trail
(``model_governance_events``), champion/challenger comparison, model lineage, and
a governance-aware approval that refuses to approve a model that has not passed
validation. Registry mechanics (versioning, promote, rollback, deployment history)
are delegated to the existing ``services.ml.registry``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.autonomous import ModelGovernanceEvent, ModelValidation
from backend.app.models.ml_platform import MLModel

# Minimum validation thresholds (transparent, overridable per deployment).
VALIDATION_THRESHOLDS = {"auc": 0.65, "accuracy": 0.6, "ks": 0.2}


def _registry():
    from backend.app.services.ml import registry
    return registry


def record_event(db: Session, *, event_type: str, model: Optional[MLModel] = None,
                 model_id: Optional[int] = None, model_key: Optional[str] = None,
                 version: Optional[int] = None, actor: Optional[str] = None,
                 detail: Optional[str] = None, payload: Optional[dict] = None) -> ModelGovernanceEvent:
    row = ModelGovernanceEvent(
        model_id=model_id or (model.id if model else None),
        model_key=model_key or (model.model_key if model else None),
        version=version or (model.version if model else None),
        event_type=event_type, actor=actor, detail=detail, payload=payload or {})
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Validation gate
# ---------------------------------------------------------------------------
def validate_model(db: Session, model_id: int, *, validator: Optional[str] = None,
                   thresholds: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    model = db.query(MLModel).filter(MLModel.id == model_id).first()
    if model is None:
        raise ValueError("model not found")
    th = {**VALIDATION_THRESHOLDS, **(thresholds or {})}
    metrics = model.metrics or {}
    checks: List[Dict[str, Any]] = []

    def check(name, ok, actual, required=None, hard=True):
        checks.append({"check": name, "passed": bool(ok), "actual": actual,
                       "required": required, "severity": "hard" if hard else "soft"})

    check("has_metrics", bool(metrics), bool(metrics))
    for metric, floor in th.items():
        val = metrics.get(metric)
        check(f"{metric}_threshold", (val is not None and val >= floor), val, floor)
    check("has_feature_names", bool(model.feature_names), len(model.feature_names or []))
    check("documented", bool(model.report), bool(model.report), hard=False)

    hard_failures = [c for c in checks if c["severity"] == "hard" and not c["passed"]]
    soft_failures = [c for c in checks if c["severity"] == "soft" and not c["passed"]]
    if hard_failures:
        status = "failed"
    elif soft_failures:
        status = "conditional"
    else:
        status = "passed"

    row = ModelValidation(model_id=model.id, model_key=model.model_key, version=model.version,
                          status=status, checks=checks, metrics=metrics, validator=validator,
                          notes=f"{len(hard_failures)} hard / {len(soft_failures)} soft failure(s)")
    db.add(row)
    db.commit()
    db.refresh(row)
    record_event(db, event_type="validation", model=model, actor=validator,
                 detail=f"Validation {status}", payload={"validation_id": row.id, "status": status})
    return validation_as_dict(row)


def latest_validation(db: Session, model_id: int) -> Optional[ModelValidation]:
    return (db.query(ModelValidation).filter(ModelValidation.model_id == model_id)
            .order_by(ModelValidation.id.desc()).first())


# ---------------------------------------------------------------------------
# Governance-aware approval + promotion
# ---------------------------------------------------------------------------
def approve_with_governance(db: Session, model_id: int, *, actor: Optional[str] = None,
                            require_validation: bool = True) -> Dict[str, Any]:
    val = latest_validation(db, model_id)
    if require_validation and (val is None or val.status == "failed"):
        raise ValueError("model must pass validation before governance approval")
    reg = _registry()
    # registry expects submit->approve; submit is idempotent-ish, guard it.
    try:
        reg.submit_for_approval(db, model_id, actor=actor)
    except Exception:
        pass
    model = reg.approve(db, model_id, actor=actor, note="governance-approved")
    record_event(db, event_type="approval", model=model, actor=actor,
                 detail="Approved via governance gate",
                 payload={"validation_status": val.status if val else None})
    return reg.model_as_dict(model)


def promote_with_governance(db: Session, model_id: int, *, actor: Optional[str] = None) -> Dict[str, Any]:
    reg = _registry()
    model = reg.promote(db, model_id, actor=actor, note="governance-promoted")
    record_event(db, event_type="deployment", model=model, actor=actor,
                 detail="Promoted to production")
    return reg.model_as_dict(model)


def rollback_with_governance(db: Session, model_key: str, *, actor: Optional[str] = None) -> Dict[str, Any]:
    reg = _registry()
    model = reg.rollback(db, model_key, actor=actor, note="governance-rollback")
    record_event(db, event_type="rollback", model=model, actor=actor,
                 detail="Rolled back production model")
    return reg.model_as_dict(model)


# ---------------------------------------------------------------------------
# Champion / challenger
# ---------------------------------------------------------------------------
def champion_challenger(db: Session, model_key: str) -> Dict[str, Any]:
    """Compare the production champion against the best non-production challenger."""
    versions = db.query(MLModel).filter(MLModel.model_key == model_key).all()
    champion = next((m for m in versions if m.production_status == "production"), None)
    challengers = [m for m in versions if m is not champion]

    def score(m):
        return (m.metrics or {}).get("auc") or (m.metrics or {}).get("accuracy") or 0.0

    challenger = max(challengers, key=score, default=None)
    verdict = "no_comparison"
    if champion and challenger:
        c_s, ch_s = score(champion), score(challenger)
        verdict = ("challenger_wins" if ch_s > c_s + 0.01
                   else "champion_holds" if c_s >= ch_s else "tie")
    return {
        "model_key": model_key,
        "champion": _model_summary(champion),
        "challenger": _model_summary(challenger),
        "verdict": verdict,
    }


def _model_summary(m: Optional[MLModel]) -> Optional[Dict[str, Any]]:
    if m is None:
        return None
    return {"id": m.id, "version": m.version, "algorithm": m.algorithm,
            "approval_status": m.approval_status, "production_status": m.production_status,
            "metrics": m.metrics}


# ---------------------------------------------------------------------------
# Lineage + dashboard
# ---------------------------------------------------------------------------
def model_lineage(db: Session, model_key: str) -> Dict[str, Any]:
    reg = _registry()
    versions = sorted(db.query(MLModel).filter(MLModel.model_key == model_key).all(),
                      key=lambda m: m.version)
    events = (db.query(ModelGovernanceEvent)
              .filter(ModelGovernanceEvent.model_key == model_key)
              .order_by(ModelGovernanceEvent.created_at.asc()).all())
    validations = (db.query(ModelValidation)
                   .filter(ModelValidation.model_key == model_key)
                   .order_by(ModelValidation.id.asc()).all())
    return {
        "model_key": model_key,
        "versions": [{"id": m.id, "version": m.version, "parent_model_id": m.parent_model_id,
                      "dataset_id": m.dataset_id, "approval_status": m.approval_status,
                      "production_status": m.production_status,
                      "deployment_history": [reg.event_as_dict(e) for e in reg.deployment_history(db, m.id)]}
                     for m in versions],
        "governance_events": [event_as_dict(e) for e in events],
        "validations": [validation_as_dict(v) for v in validations],
    }


def governance_dashboard(db: Session) -> Dict[str, Any]:
    models = db.query(MLModel).all()
    by_approval: Dict[str, int] = {}
    by_production: Dict[str, int] = {}
    keys = set()
    for m in models:
        keys.add(m.model_key)
        by_approval[m.approval_status] = by_approval.get(m.approval_status, 0) + 1
        by_production[m.production_status] = by_production.get(m.production_status, 0) + 1
    validations = db.query(ModelValidation).all()
    val_by_status: Dict[str, int] = {}
    for v in validations:
        val_by_status[v.status] = val_by_status.get(v.status, 0) + 1
    events = db.query(ModelGovernanceEvent).order_by(ModelGovernanceEvent.id.desc()).limit(20).all()
    return {
        "model_keys": sorted(keys), "total_versions": len(models),
        "by_approval_status": by_approval, "by_production_status": by_production,
        "validations": {"total": len(validations), "by_status": val_by_status},
        "recent_events": [event_as_dict(e) for e in events],
    }


def event_as_dict(e: ModelGovernanceEvent) -> Dict[str, Any]:
    return {"id": e.id, "model_id": e.model_id, "model_key": e.model_key, "version": e.version,
            "event_type": e.event_type, "actor": e.actor, "detail": e.detail,
            "payload": e.payload, "created_at": e.created_at.isoformat() if e.created_at else None}


def validation_as_dict(v: ModelValidation) -> Dict[str, Any]:
    return {"id": v.id, "model_id": v.model_id, "model_key": v.model_key, "version": v.version,
            "status": v.status, "checks": v.checks, "metrics": v.metrics,
            "validator": v.validator, "notes": v.notes,
            "created_at": v.created_at.isoformat() if v.created_at else None}

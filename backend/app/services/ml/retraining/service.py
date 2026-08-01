"""Automated Retraining.

Orchestrates the retraining lifecycle by composing the training pipeline, the
model registry and drift detection

* **Triggers** — manual, scheduled and drift-triggered (a breached drift report
  recommends retraining).
* **Dataset snapshotting** — every retrain trains on a freshly snapshotted
  reproducible dataset registered in the registry.
* **Champion / challenger** — the new model (challenger) is compared to the live
  production model (champion) on held-out ROC-AUC; the winner is reported.
* **Approval workflow + promotion** — a winning challenger is submitted for
  approval and, when auto-promotion is enabled, approved and promoted; otherwise
  it waits for a human decision.
* **Rollback** — delegated to the registry's rollback.

Retraining never deletes or mutates a prior model; it always produces a new
versioned model, so every step is auditable and reversible.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ml_platform import MLModel
from backend.app.services.ml import drift, registry
from backend.app.services.ml.data.dataset import make_synthetic_dataset
from backend.app.services.ml.training import train

TRIGGER_MANUAL = "manual"
TRIGGER_SCHEDULED = "scheduled"
TRIGGER_DRIFT = "drift"


def should_retrain(db: Session, model_key: str) -> Dict[str, Any]:
    """Recommend retraining when the most recent drift report is breached."""
    reports = drift.history(db, model_key=model_key, limit=1)
    latest = reports[0] if reports else None
    breached = bool(latest and latest.breached)
    return {
        "model_key": model_key,
        "should_retrain": breached,
        "reason": ("latest drift report breached thresholds" if breached
                   else "no breaching drift detected"),
        "latest_drift": drift.report_as_dict(latest) if latest else None,
    }


def _compare(champion: Optional[MLModel], challenger_metrics: Dict[str, Any]) -> Dict[str, Any]:
    challenger_auc = float(challenger_metrics.get("roc_auc") or 0.0)
    if champion is None:
        return {"winner": "challenger", "champion_auc": None,
                "challenger_auc": challenger_auc, "delta": None,
                "note": "No incumbent production model; challenger becomes champion."}
    champion_auc = float((champion.metrics or {}).get("roc_auc") or 0.0)
    delta = challenger_auc - champion_auc
    winner = "challenger" if delta >= 0 else "champion"
    return {
        "winner": winner,
        "champion_auc": round(champion_auc, 6),
        "challenger_auc": round(challenger_auc, 6),
        "delta": round(delta, 6),
        "note": ("Challenger matches or beats champion." if winner == "challenger"
                 else "Champion retained; challenger did not improve on it."),
    }


def run_retraining(
    db: Session,
    model_key: str,
    *,
    algorithm: Optional[str] = None,
    trigger: str = TRIGGER_MANUAL,
    dataset_seed: int = 4242,
    n_rows: int = 4000,
    drift_shift: Optional[Dict[str, float]] = None,
    author: Optional[str] = None,
    auto_promote: bool = False,
    tune: bool = False,
) -> Dict[str, Any]:
    """Train a challenger, register it, compare to the champion and (optionally)
    promote the winner."""
    champion = registry.production_model(db, model_key)
    algo = algorithm or (champion.algorithm if champion else model_key)

    # 1. Snapshot a fresh, reproducible dataset (optionally with drift baked in).
    dataset = make_synthetic_dataset(
        name=f"retrain_{model_key}", seed=dataset_seed, n_rows=n_rows, drift=drift_shift,
    )
    dataset_row = registry.register_dataset(db, dataset.snapshot(), created_by=author)

    # 2. Train the challenger.
    result = train(dataset, algo, tune=tune, cv_folds=5)

    # 3. Register the challenger as a new version.
    challenger = registry.register_model(
        db, result, model_key=model_key, author=author, dataset=dataset_row,
    )
    registry.service._event(
        db, challenger, "retrain", None, challenger.approval_status,
        actor=author, note=f"Retraining triggered by: {trigger}",
    )

    # 4. Champion / challenger comparison.
    comparison = _compare(champion, result.metrics.as_dict())

    # 5. Governance: submit; auto-promote the winner only when allowed.
    promoted = False
    if comparison["winner"] == "challenger":
        registry.submit_for_approval(db, challenger.id, actor=author)
        if auto_promote:
            registry.approve(db, challenger.id, actor=author or "auto-retrain",
                             note="Auto-approved: challenger outperformed champion.")
            registry.promote(db, challenger.id, actor=author or "auto-retrain",
                             note=f"Auto-promoted via {trigger} retraining.")
            promoted = True

    return {
        "trigger": trigger,
        "model_key": model_key,
        "algorithm": algo,
        "champion_id": champion.id if champion else None,
        "challenger_id": challenger.id,
        "challenger_version": challenger.version,
        "dataset_id": dataset_row.id,
        "comparison": comparison,
        "auto_promoted": promoted,
        "challenger_approval_status": challenger.approval_status,
        "challenger_production_status": challenger.production_status,
        "metrics": result.metrics.as_dict(),
        "recommendation": (
            "promote challenger" if comparison["winner"] == "challenger" and not promoted
            else "challenger promoted" if promoted else "retain champion"
        ),
    }


def champion_challenger(db: Session, model_key: str, challenger_id: int) -> Dict[str, Any]:
    """Compare a specific challenger model to the current champion."""
    champion = registry.production_model(db, model_key)
    challenger = registry.service.get_model(db, challenger_id)
    if challenger is None:
        raise registry.RegistryError(f"Challenger model {challenger_id} not found.")
    return {
        "model_key": model_key,
        "champion_id": champion.id if champion else None,
        "challenger_id": challenger_id,
        "comparison": _compare(champion, challenger.metrics or {}),
    }


def rollback(db: Session, model_key: str, *, actor: Optional[str] = None) -> MLModel:
    """Roll production back to the previous version (delegates to the registry)."""
    return registry.rollback(db, model_key, actor=actor, note="Rollback via retraining service")


def scan_and_retrain(db: Session, *, auto_promote: bool = False,
                     author: str = "scheduled-job") -> List[Dict[str, Any]]:
    """Job hook: retrain every production model whose latest drift is breached."""
    outcomes: List[Dict[str, Any]] = []
    production = registry.list_models(db, production_status=registry.service.PROD_PRODUCTION)
    for model in production:
        decision = should_retrain(db, model.model_key)
        if decision["should_retrain"]:
            outcomes.append(run_retraining(
                db, model.model_key, trigger=TRIGGER_DRIFT,
                author=author, auto_promote=auto_promote,
            ))
    return outcomes

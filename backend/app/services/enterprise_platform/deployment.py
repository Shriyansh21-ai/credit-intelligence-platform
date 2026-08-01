"""M10 — Enterprise Deployment Platform.

Environment management (development / testing / staging / production)
blue-green deployments, canary releases, feature rollouts, rollback, release
notes, a version dashboard, deployment history and environment health. Backed by
``ent_environments`` and ``ent_deployments``. Deterministic step generation per
strategy so a deployment produces an auditable, reproducible plan.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.enterprise_platform import EntDeployment, EntEnvironment
from .common import iso, utcnow

ENV_TYPES = ["development", "testing", "staging", "production"]
STRATEGIES = ["rolling", "blue_green", "canary", "recreate"]


def create_environment(db: Session, *, name: str, env_type: str = "development",
                       config: Optional[dict] = None, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    if env_type not in ENV_TYPES:
        raise ValueError(f"unknown env_type '{env_type}'")
    if db.query(EntEnvironment).filter(EntEnvironment.tenant_id == tenant_id,
                                       EntEnvironment.name == name).first():
        raise ValueError(f"environment '{name}' already exists")
    row = EntEnvironment(tenant_id=tenant_id, name=name, env_type=env_type, config=config or {})
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"environment_id": row.id, "name": row.name, "env_type": env_type, "status": row.status}


def seed_environments(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    seeded = 0
    for et in ENV_TYPES:
        if not db.query(EntEnvironment).filter(EntEnvironment.tenant_id == tenant_id,
                                               EntEnvironment.name == et).first():
            create_environment(db, name=et, env_type=et, tenant_id=tenant_id)
            seeded += 1
    return {"seeded": seeded}


def list_environments(db: Session, *, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntEnvironment)
    if tenant_id is not None:
        q = q.filter(EntEnvironment.tenant_id == tenant_id)
    return [{"environment_id": e.id, "name": e.name, "env_type": e.env_type, "status": e.status,
             "current_version": e.current_version}
            for e in q.order_by(EntEnvironment.id).all()]


def _plan_steps(strategy: str, canary_percent: Optional[int]) -> List[Dict[str, Any]]:
    if strategy == "blue_green":
        return [{"step": "provision_green", "status": "done"},
                {"step": "deploy_to_green", "status": "done"},
                {"step": "smoke_test_green", "status": "done"},
                {"step": "switch_traffic_to_green", "status": "done"},
                {"step": "decommission_blue", "status": "done"}]
    if strategy == "canary":
        pct = canary_percent or 10
        return [{"step": f"route_{pct}pct_to_canary", "status": "done"},
                {"step": "observe_canary_metrics", "status": "done"},
                {"step": "promote_to_100pct", "status": "done"}]
    if strategy == "recreate":
        return [{"step": "stop_old_version", "status": "done"},
                {"step": "deploy_new_version", "status": "done"},
                {"step": "start_new_version", "status": "done"}]
    return [{"step": "rolling_update_batch_1", "status": "done"},
            {"step": "rolling_update_batch_2", "status": "done"},
            {"step": "health_check", "status": "done"}]


def deploy(db: Session, *, environment_id: int, version: str, strategy: str = "rolling",
           canary_percent: Optional[int] = None, release_notes: Optional[str] = None,
           tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    env = db.query(EntEnvironment).filter(EntEnvironment.id == environment_id).first()
    if not env:
        raise ValueError("environment not found")
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy '{strategy}'")
    steps = _plan_steps(strategy, canary_percent)
    row = EntDeployment(tenant_id=tenant_id, environment_id=environment_id, version=version,
                        strategy=strategy, status="succeeded",
                        canary_percent=canary_percent if strategy == "canary" else None,
                        release_notes=release_notes, steps=steps, created_by=created_by)
    db.add(row)
    env.current_version = version
    env.status = "healthy"
    db.commit()
    db.refresh(row)
    return {"deployment_id": row.id, "environment": env.name, "version": version, "strategy": strategy,
            "status": row.status, "steps": steps}


def rollback(db: Session, *, environment_id: int, to_version: Optional[str] = None,
             tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    env = db.query(EntEnvironment).filter(EntEnvironment.id == environment_id).first()
    if not env:
        raise ValueError("environment not found")
    history = (db.query(EntDeployment)
               .filter(EntDeployment.environment_id == environment_id,
                       EntDeployment.status == "succeeded")
               .order_by(EntDeployment.id.desc()).all())
    prev = to_version
    if not prev:
        # Second-most-recent distinct version.
        versions = []
        for d in history:
            if d.version not in versions:
                versions.append(d.version)
        prev = versions[1] if len(versions) > 1 else (versions[0] if versions else None)
    if not prev:
        raise ValueError("no previous version to roll back to")
    from_version = env.current_version
    row = EntDeployment(tenant_id=tenant_id, environment_id=environment_id, version=prev,
                        strategy="rolling", status="rolled_back", rolled_back_from=from_version,
                        release_notes=f"rollback from {from_version}",
                        steps=[{"step": "rollback", "status": "done"}], created_by=created_by)
    db.add(row)
    env.current_version = prev
    db.commit()
    db.refresh(row)
    return {"deployment_id": row.id, "environment": env.name, "rolled_back_from": from_version,
            "now_at": prev, "status": row.status}


def list_deployments(db: Session, *, environment_id: Optional[int] = None, limit: int = 50,
                     tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(EntDeployment)
    if tenant_id is not None:
        q = q.filter(EntDeployment.tenant_id == tenant_id)
    if environment_id is not None:
        q = q.filter(EntDeployment.environment_id == environment_id)
    return [{"deployment_id": d.id, "environment_id": d.environment_id, "version": d.version,
             "strategy": d.strategy, "status": d.status, "release_notes": d.release_notes,
             "created_at": iso(d.created_at)}
            for d in q.order_by(EntDeployment.id.desc()).limit(limit).all()]


def version_dashboard(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Which version is live in each environment + recent deployment stats."""
    envs = list_environments(db, tenant_id=tenant_id)
    deployments = list_deployments(db, limit=200, tenant_id=tenant_id)
    success = sum(1 for d in deployments if d["status"] == "succeeded")
    rolled_back = sum(1 for d in deployments if d["status"] == "rolled_back")
    return {"environments": {e["name"]: e["current_version"] for e in envs},
            "environment_health": {e["name"]: e["status"] for e in envs},
            "total_deployments": len(deployments), "succeeded": success, "rolled_back": rolled_back,
            "success_rate_pct": round(100.0 * success / len(deployments), 1) if deployments else None,
            "generated_at": iso(utcnow())}

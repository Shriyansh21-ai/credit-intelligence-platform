"""M8 — Prompt Management Platform.

Versioned, governed LLM prompts: templates with immutable versions, declared
``{{variables}}``, a draft → approved → deployed lifecycle, deterministic
evaluation against test cases, a render/playground and per-version metrics. The
deployed version is what the copilot / report generators resolve at runtime, so
prompt changes are auditable and reversible without a code deploy.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.banking_os import (
    PromptEvaluation, PromptTemplate, PromptVersion,
)
from .common import tokenize

_VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def extract_variables(content: str) -> List[str]:
    seen: List[str] = []
    for m in _VAR_RE.finditer(content or ""):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


# ---------------------------------------------------------------------------
# Templates + versions
# ---------------------------------------------------------------------------
def create_template(db: Session, *, key: str, name: str, category: Optional[str] = None,
                    description: Optional[str] = None, tenant_id: Optional[int] = None,
                    created_by: Optional[str] = None) -> PromptTemplate:
    key = (key or "").strip()
    if not key:
        raise ValueError("prompt key required")
    if db.query(PromptTemplate).filter(PromptTemplate.tenant_id == tenant_id,
                                       PromptTemplate.key == key).first():
        raise ValueError(f"prompt '{key}' already exists")
    t = PromptTemplate(tenant_id=tenant_id, key=key, name=name or key, category=category,
                       description=description, created_by=created_by, status="draft")
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def get_template(db: Session, template_id: int) -> Optional[PromptTemplate]:
    return db.query(PromptTemplate).filter(PromptTemplate.id == template_id).first()


def get_template_by_key(db: Session, key: str, *, tenant_id: Optional[int] = None) -> Optional[PromptTemplate]:
    return (db.query(PromptTemplate)
            .filter(PromptTemplate.tenant_id == tenant_id, PromptTemplate.key == key).first())


def list_templates(db: Session, *, category: Optional[str] = None,
                   tenant_id: Optional[int] = None) -> List[PromptTemplate]:
    q = db.query(PromptTemplate).filter(PromptTemplate.tenant_id == tenant_id)
    if category:
        q = q.filter(PromptTemplate.category == category)
    return q.order_by(PromptTemplate.key).all()


def list_versions(db: Session, template_id: int) -> List[PromptVersion]:
    return (db.query(PromptVersion).filter(PromptVersion.template_id == template_id)
            .order_by(PromptVersion.version.desc()).all())


def get_version(db: Session, template_id: int, version: int) -> Optional[PromptVersion]:
    return (db.query(PromptVersion)
            .filter(PromptVersion.template_id == template_id, PromptVersion.version == version).first())


def add_version(db: Session, template_id: int, *, content: str, variables: Optional[list] = None,
                model_hint: Optional[str] = None, params: Optional[dict] = None,
                created_by: Optional[str] = None) -> PromptVersion:
    t = get_template(db, template_id)
    if t is None:
        raise ValueError("prompt not found")
    if not content or not content.strip():
        raise ValueError("prompt content required")
    declared = variables or extract_variables(content)
    next_version = db.query(PromptVersion).filter(PromptVersion.template_id == template_id).count() + 1
    v = PromptVersion(template_id=template_id, version=next_version, content=content,
                      variables=declared, model_hint=model_hint, params=params or {},
                      status="draft", created_by=created_by)
    db.add(v)
    t.current_version = next_version
    t.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(v)
    return v


def approve_version(db: Session, template_id: int, version: int, *,
                    approver: Optional[str] = None) -> PromptVersion:
    v = get_version(db, template_id, version)
    if v is None:
        raise ValueError("version not found")
    v.status = "approved"
    v.approved_by = approver
    v.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(v)
    return v


def deploy_version(db: Session, template_id: int, version: int) -> PromptTemplate:
    t = get_template(db, template_id)
    if t is None:
        raise ValueError("prompt not found")
    v = get_version(db, template_id, version)
    if v is None:
        raise ValueError("version not found")
    if v.status not in ("approved", "deployed"):
        raise ValueError("version must be approved before deployment")
    # Demote any currently-deployed version.
    for other in db.query(PromptVersion).filter(PromptVersion.template_id == template_id,
                                                PromptVersion.status == "deployed").all():
        if other.version != version:
            other.status = "approved"
    v.status = "deployed"
    t.deployed_version = version
    t.status = "active"
    db.commit()
    db.refresh(t)
    return t


# ---------------------------------------------------------------------------
# Rendering + evaluation
# ---------------------------------------------------------------------------
def render(db: Session, template_id: int, *, variables: Optional[dict] = None,
           version: Optional[int] = None) -> Dict[str, Any]:
    t = get_template(db, template_id)
    if t is None:
        raise ValueError("prompt not found")
    ver = version or t.deployed_version or t.current_version
    v = get_version(db, template_id, ver)
    if v is None:
        raise ValueError("version not found")
    variables = variables or {}
    missing = [name for name in v.variables if name not in variables]
    rendered = _VAR_RE.sub(lambda m: str(variables.get(m.group(1), m.group(0))), v.content)
    return {"template_id": template_id, "version": ver, "rendered": rendered,
            "missing_variables": missing, "complete": not missing,
            "model_hint": v.model_hint, "params": v.params}


def _case_score(case: Dict[str, Any], v: PromptVersion) -> Dict[str, Any]:
    """Deterministically score one evaluation case.

    If the case supplies an ``output``, score token overlap against ``expected``.
    Otherwise score render completeness: does the case ``input`` resolve every
    declared variable? Either way it is reproducible without calling an LLM.
    """
    inp = case.get("input") or {}
    if "output" in case and "expected" in case:
        out_t, exp_t = set(tokenize(str(case["output"]))), set(tokenize(str(case["expected"])))
        score = len(out_t & exp_t) / len(exp_t) if exp_t else 0.0
        return {"input": inp, "expected": case.get("expected"), "output": case.get("output"),
                "score": round(score, 3), "passed": score >= 0.6, "mode": "overlap"}
    missing = [name for name in v.variables if name not in inp]
    score = 1.0 - (len(missing) / max(1, len(v.variables))) if v.variables else 1.0
    return {"input": inp, "missing_variables": missing, "score": round(score, 3),
            "passed": not missing, "mode": "render_completeness"}


def evaluate(db: Session, template_id: int, *, version: int, cases: List[dict],
             created_by: Optional[str] = None) -> Dict[str, Any]:
    v = get_version(db, template_id, version)
    if v is None:
        raise ValueError("version not found")
    scored = [_case_score(c, v) for c in (cases or [])]
    avg = round(sum(c["score"] for c in scored) / len(scored), 3) if scored else 0.0
    passed = all(c["passed"] for c in scored) if scored else False
    row = PromptEvaluation(template_id=template_id, version=version, cases=scored, score=avg,
                           passed=passed, metrics={"n": len(scored),
                               "pass_rate": round(sum(1 for c in scored if c["passed"]) / len(scored), 3) if scored else 0.0},
                           created_by=created_by)
    db.add(row)
    v.eval_score = avg
    db.commit()
    db.refresh(row)
    return {"evaluation_id": row.id, "score": avg, "passed": passed, "cases": scored,
            "metrics": row.metrics}


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def template_dict(t: PromptTemplate) -> Dict[str, Any]:
    return {"id": t.id, "key": t.key, "name": t.name, "category": t.category,
            "description": t.description, "status": t.status,
            "current_version": t.current_version, "deployed_version": t.deployed_version,
            "created_by": t.created_by,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None}


def version_dict(v: PromptVersion) -> Dict[str, Any]:
    return {"id": v.id, "version": v.version, "content": v.content, "variables": v.variables,
            "model_hint": v.model_hint, "params": v.params, "status": v.status,
            "approved_by": v.approved_by, "eval_score": v.eval_score,
            "created_at": v.created_at.isoformat() if v.created_at else None}

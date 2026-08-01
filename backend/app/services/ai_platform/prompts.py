"""M4 — Enterprise prompt engineering platform.

A governed prompt registry so no prompt is ever hardcoded in application logic

    register → add_version → evaluate → approve → deploy → (rollback)
                            └────────── A/B experiment ──────────┘

Every prompt is a parameterised template (``{{variable}}`` placeholders) with a
declared variable list, an optional system message, a target model and params.
Versions move through ``draft → in_review → approved → deployed → archived`` with
an approval workflow, a lightweight evaluation harness that scores a version over
a dataset, deterministic A/B allocation, and one-call rollback.

The renderer validates that every required variable is supplied, so a malformed
call fails loudly instead of silently emitting a broken prompt.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ai_platform import (
    AIPPrompt, AIPPromptEval, AIPPromptExperiment, AIPPromptVersion,
)
from backend.app.services.ai_platform import common

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def declared_variables(template: str) -> List[str]:
    return list(dict.fromkeys(_VAR_RE.findall(template or "")))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def register(db: Session, *, key: str, name: str, description: Optional[str] = None,
             task: Optional[str] = None, tags: Optional[List[str]] = None,
             tenant_id: Optional[int] = None, created_by: Optional[str] = None) -> AIPPrompt:
    existing = (db.query(AIPPrompt)
                .filter(AIPPrompt.tenant_id == tenant_id, AIPPrompt.key == key).first())
    if existing:
        existing.name = name
        existing.description = description
        existing.task = task
        existing.tags = tags or existing.tags
        db.commit()
        db.refresh(existing)
        return existing
    p = AIPPrompt(tenant_id=tenant_id, key=key, name=name, description=description,
                  task=task, tags=tags or [], created_by=created_by,
                  created_at=common.utcnow(), updated_at=common.utcnow())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _get_prompt(db, *, prompt_id=None, key=None, tenant_id=None) -> AIPPrompt:
    q = db.query(AIPPrompt).filter(AIPPrompt.tenant_id == tenant_id)
    p = (q.filter(AIPPrompt.id == prompt_id).first() if prompt_id is not None
         else q.filter(AIPPrompt.key == key).first())
    if p is None:
        raise ValueError("prompt not found")
    return p


def list_prompts(db, *, tenant_id=None) -> List[AIPPrompt]:
    return (db.query(AIPPrompt).filter(AIPPrompt.tenant_id == tenant_id)
            .order_by(AIPPrompt.id.desc()).all())


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------
def add_version(db: Session, *, template: str, prompt_id: Optional[int] = None,
                key: Optional[str] = None, system: Optional[str] = None,
                model: Optional[str] = None, params: Optional[Dict[str, Any]] = None,
                notes: Optional[str] = None, variables: Optional[List[str]] = None,
                tenant_id: Optional[int] = None,
                created_by: Optional[str] = None) -> AIPPromptVersion:
    p = _get_prompt(db, prompt_id=prompt_id, key=key, tenant_id=tenant_id)
    version = p.current_version + 1
    v = AIPPromptVersion(
        prompt_id=p.id, version=version, template=template, system=system,
        variables=variables or declared_variables(template), model=model,
        params=params or {}, status="draft", notes=notes, created_by=created_by,
        created_at=common.utcnow())
    db.add(v)
    p.current_version = version
    db.commit()
    db.refresh(v)
    return v


def list_versions(db, *, prompt_id: int) -> List[AIPPromptVersion]:
    return (db.query(AIPPromptVersion).filter(AIPPromptVersion.prompt_id == prompt_id)
            .order_by(AIPPromptVersion.version.desc()).all())


def _get_version(db, *, version_id=None, prompt_id=None, version=None) -> AIPPromptVersion:
    q = db.query(AIPPromptVersion)
    if version_id is not None:
        v = q.filter(AIPPromptVersion.id == version_id).first()
    else:
        v = q.filter(AIPPromptVersion.prompt_id == prompt_id,
                     AIPPromptVersion.version == version).first()
    if v is None:
        raise ValueError("prompt version not found")
    return v


# ---------------------------------------------------------------------------
# Rendering (parameterised, validated)
# ---------------------------------------------------------------------------
def render(db: Session, *, variables: Dict[str, Any], key: Optional[str] = None,
           prompt_id: Optional[int] = None, version: Optional[int] = None,
           tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Render the deployed (or specified) version, validating required variables."""
    p = _get_prompt(db, prompt_id=prompt_id, key=key, tenant_id=tenant_id)
    target = version if version is not None else (p.deployed_version or p.current_version)
    if not target:
        raise ValueError("prompt has no versions")
    v = _get_version(db, prompt_id=p.id, version=target)
    required = v.variables or declared_variables(v.template)
    missing = [name for name in required if name not in variables]
    if missing:
        raise ValueError(f"missing template variables: {', '.join(missing)}")
    text = _VAR_RE.sub(lambda m: str(variables.get(m.group(1), "")), v.template)
    return {"prompt_key": p.key, "version": v.version, "system": v.system,
            "text": text, "model": v.model, "params": v.params,
            "status": v.status}


# ---------------------------------------------------------------------------
# Evaluation harness
# ---------------------------------------------------------------------------
def evaluate_version(db: Session, *, version_id: int,
                     dataset: Optional[List[Dict[str, Any]]] = None) -> AIPPromptEval:
    """Score a version over a dataset of ``{variables, must_include?}`` cases.

    Deterministic metrics: render success rate, required-keyword coverage and a
    template-quality heuristic (declares its variables, has a system message).
    """
    v = _get_version(db, version_id=version_id)
    dataset = dataset or [{"variables": {name: name.upper() for name in (v.variables or [])}}]
    rendered_ok = 0
    coverage_scores: List[float] = []
    for case in dataset:
        vars_ = case.get("variables", {})
        try:
            required = v.variables or declared_variables(v.template)
            missing = [n for n in required if n not in vars_]
            if missing:
                coverage_scores.append(0.0)
                continue
            text = _VAR_RE.sub(lambda m: str(vars_.get(m.group(1), "")), v.template)
            rendered_ok += 1
            must = case.get("must_include") or []
            if must:
                hits = sum(1 for m in must if str(m).lower() in text.lower())
                coverage_scores.append(hits / len(must))
            else:
                coverage_scores.append(1.0)
        except Exception:
            coverage_scores.append(0.0)
    render_rate = rendered_ok / len(dataset)
    coverage = sum(coverage_scores) / len(coverage_scores) if coverage_scores else 0.0
    quality = 0.5 + (0.25 if v.system else 0.0) + (0.25 if v.variables else 0.0)
    score = common.round_opt(0.4 * render_rate + 0.4 * coverage + 0.2 * quality, 4)
    metrics = {"render_rate": common.round_opt(render_rate, 4),
               "keyword_coverage": common.round_opt(coverage, 4),
               "template_quality": common.round_opt(quality, 4),
               "cases": len(dataset)}
    ev = AIPPromptEval(prompt_version_id=v.id, dataset=dataset, metrics=metrics,
                       score=score, passed=score >= 0.7, created_at=common.utcnow())
    db.add(ev)
    v.eval_score = score
    db.commit()
    db.refresh(ev)
    return ev


# ---------------------------------------------------------------------------
# Approval workflow / rollout / rollback
# ---------------------------------------------------------------------------
def submit_for_review(db, *, version_id: int) -> AIPPromptVersion:
    v = _get_version(db, version_id=version_id)
    v.status = "in_review"
    db.commit()
    db.refresh(v)
    return v


def approve(db, *, version_id: int, approver: Optional[str] = None) -> AIPPromptVersion:
    v = _get_version(db, version_id=version_id)
    v.status = "approved"
    v.approved_by = approver
    db.commit()
    db.refresh(v)
    return v


def deploy(db, *, prompt_id: int, version: int) -> AIPPrompt:
    v = _get_version(db, prompt_id=prompt_id, version=version)
    if v.status not in ("approved", "deployed"):
        raise ValueError("only an approved version can be deployed")
    # Demote a previously deployed version.
    for other in list_versions(db, prompt_id=prompt_id):
        if other.status == "deployed" and other.version != version:
            other.status = "approved"
    v.status = "deployed"
    p = _get_prompt(db, prompt_id=prompt_id)
    p.deployed_version = version
    db.commit()
    db.refresh(p)
    return p


def rollback(db, *, prompt_id: int, to_version: int) -> AIPPrompt:
    return deploy(db, prompt_id=prompt_id, version=to_version)


# ---------------------------------------------------------------------------
# A/B experiments
# ---------------------------------------------------------------------------
def start_experiment(db: Session, *, prompt_id: int, name: str,
                     variant_a_version: int, variant_b_version: int,
                     allocation: float = 0.5, tenant_id: Optional[int] = None) -> AIPPromptExperiment:
    _get_version(db, prompt_id=prompt_id, version=variant_a_version)
    _get_version(db, prompt_id=prompt_id, version=variant_b_version)
    exp = AIPPromptExperiment(
        tenant_id=tenant_id, prompt_id=prompt_id, name=name,
        variant_a_version=variant_a_version, variant_b_version=variant_b_version,
        allocation=allocation, status="running",
        results={"a": {"n": 0, "score_sum": 0.0}, "b": {"n": 0, "score_sum": 0.0}},
        created_at=common.utcnow())
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def assign_variant(experiment: AIPPromptExperiment, unit_key: str) -> str:
    """Deterministic bucketing: stable hash of the unit key vs the allocation."""
    frac = (int(common.short_hash(experiment.id, unit_key), 16) % 10000) / 10000.0
    return "a" if frac < experiment.allocation else "b"


def record_experiment_result(db: Session, *, experiment_id: int, variant: str,
                             score: float) -> AIPPromptExperiment:
    exp = db.query(AIPPromptExperiment).filter(AIPPromptExperiment.id == experiment_id).first()
    if exp is None:
        raise ValueError("experiment not found")
    results = dict(exp.results or {})
    bucket = results.setdefault(variant, {"n": 0, "score_sum": 0.0})
    bucket["n"] += 1
    bucket["score_sum"] += float(score)
    exp.results = results
    db.commit()
    db.refresh(exp)
    return exp


def conclude_experiment(db: Session, *, experiment_id: int) -> AIPPromptExperiment:
    exp = db.query(AIPPromptExperiment).filter(AIPPromptExperiment.id == experiment_id).first()
    if exp is None:
        raise ValueError("experiment not found")
    results = exp.results or {}

    def _mean(b):
        return (b.get("score_sum", 0.0) / b["n"]) if b.get("n") else 0.0
    a_mean, b_mean = _mean(results.get("a", {})), _mean(results.get("b", {}))
    exp.winner = "a" if a_mean >= b_mean else "b"
    exp.status = "concluded"
    results["a_mean"] = common.round_opt(a_mean, 4)
    results["b_mean"] = common.round_opt(b_mean, 4)
    exp.results = results
    db.commit()
    db.refresh(exp)
    return exp


# ---------------------------------------------------------------------------
# Default prompt seeding (so the platform ships with governed prompts, not
# hardcoded strings). Idempotent.
# ---------------------------------------------------------------------------
_DEFAULTS = [
    {"key": "rag_answer", "name": "RAG Answer", "task": "rag",
     "template": "Answer the banking question using only the grounding.\n"
                 "Question: {{question}}\nGrounding:\n{{grounding}}",
     "system": "You are a senior banking analyst. Use only the grounding; cite sources."},
    {"key": "credit_memo", "name": "Credit Memo", "task": "report",
     "template": "Prepare a credit memo for {{company}}.\nProfile:\n{{profile}}",
     "system": "You are a credit committee writer. Be precise and evidence-led."},
    {"key": "investigation_summary", "name": "Investigation Summary", "task": "investigation",
     "template": "Summarise the investigation of {{company}} with findings:\n{{findings}}",
     "system": "You are a forensic credit investigator."},
]


def seed_defaults(db: Session, *, tenant_id: Optional[int] = None) -> List[str]:
    created = []
    for d in _DEFAULTS:
        p = register(db, key=d["key"], name=d["name"], task=d["task"], tenant_id=tenant_id)
        if not p.current_version:
            v = add_version(db, prompt_id=p.id, template=d["template"], system=d["system"],
                            model="local", tenant_id=tenant_id, created_by="system")
            approve(db, version_id=v.id, approver="system")
            deploy(db, prompt_id=p.id, version=v.version)
            created.append(d["key"])
    return created

"""M8 — AI workflow builder + execution engine.

Persists visual workflow designs (a node/edge graph authored in the frontend
designer) and executes them deterministically. Node types cover the AI platform
surface:

    start · agent · rag · api · connector · approval · memory · condition · report · end

The graph is ``{"start": id, "nodes": [{id, type, config, next?, edges?}]}``.
Linear flow follows ``next``; a ``condition`` node branches via
``edges = {"true": id, "false": id}``. Execution accumulates each node's output
into a shared context (so later nodes can reference earlier results), enforces a
step cap to prevent cycles, and records every node result to ``aip_workflow_runs``.
Approval nodes pause the run (``awaiting_approval``) unless auto-approved.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ai_platform import AIPWorkflow, AIPWorkflowRun
from backend.app.services.ai_platform import (
    agents as agents_svc, common, memory as memory_svc, rag, reports as reports_svc,
)

NODE_TYPES = ["start", "agent", "rag", "api", "connector", "approval", "memory",
              "condition", "report", "end"]
_MAX_STEPS = 50


# ---------------------------------------------------------------------------
# Design / persistence
# ---------------------------------------------------------------------------
def validate_graph(graph: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    nodes = graph.get("nodes") or []
    ids = [n.get("id") for n in nodes]
    if not nodes:
        errors.append("graph has no nodes")
    if len(ids) != len(set(ids)):
        errors.append("duplicate node ids")
    if graph.get("start") not in ids:
        errors.append("start node not found")
    idset = set(ids)
    for n in nodes:
        if n.get("type") not in NODE_TYPES:
            errors.append(f"node {n.get('id')}: unknown type '{n.get('type')}'")
        if n.get("next") and n["next"] not in idset:
            errors.append(f"node {n.get('id')}: next '{n['next']}' not found")
        for edge in (n.get("edges") or {}).values():
            if edge and edge not in idset:
                errors.append(f"node {n.get('id')}: edge target '{edge}' not found")
    return errors


def save_workflow(db: Session, *, key: str, name: str, graph: Dict[str, Any],
                  description: Optional[str] = None, tags: Optional[List[str]] = None,
                  tenant_id: Optional[int] = None,
                  created_by: Optional[str] = None) -> AIPWorkflow:
    errors = validate_graph(graph)
    if errors:
        raise ValueError("invalid workflow graph: " + "; ".join(errors))
    existing = (db.query(AIPWorkflow)
                .filter(AIPWorkflow.tenant_id == tenant_id, AIPWorkflow.key == key).first())
    if existing:
        existing.name = name
        existing.description = description
        existing.graph = graph
        existing.tags = tags or existing.tags
        existing.version = existing.version + 1
        db.commit()
        db.refresh(existing)
        return existing
    wf = AIPWorkflow(tenant_id=tenant_id, key=key, name=name, description=description,
                     graph=graph, tags=tags or [], status="active", version=1,
                     created_by=created_by, created_at=common.utcnow(),
                     updated_at=common.utcnow())
    db.add(wf)
    db.commit()
    db.refresh(wf)
    return wf


def list_workflows(db, *, tenant_id=None) -> List[AIPWorkflow]:
    return (db.query(AIPWorkflow).filter(AIPWorkflow.tenant_id == tenant_id)
            .order_by(AIPWorkflow.id.desc()).all())


def get_workflow(db, *, workflow_id=None, key=None, tenant_id=None) -> Optional[AIPWorkflow]:
    q = db.query(AIPWorkflow).filter(AIPWorkflow.tenant_id == tenant_id)
    return (q.filter(AIPWorkflow.id == workflow_id).first() if workflow_id is not None
            else q.filter(AIPWorkflow.key == key).first())


# ---------------------------------------------------------------------------
# Node executors
# ---------------------------------------------------------------------------
def _resolve(value: Any, context: Dict[str, Any], run_input: Dict[str, Any]) -> Any:
    """Resolve a ``$input.x`` / ``$ctx.node.field`` reference, else literal."""
    if not isinstance(value, str) or not value.startswith("$"):
        return value
    parts = value[1:].split(".")
    root = run_input if parts[0] == "input" else context
    cur: Any = root
    for p in parts[1:] if parts[0] in ("input", "ctx") else parts:
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    return cur


def _exec_node(db, node, context, run_input, *, tenant_id, provider, created_by):
    ntype = node["type"]
    cfg = node.get("config") or {}
    if ntype in ("start", "end"):
        return {"status": "ok"}
    if ntype == "agent":
        goal = _resolve(cfg.get("goal", run_input.get("goal", "assess the borrower")), context, run_input)
        company = _resolve(cfg.get("company_ref", run_input.get("company_ref")), context, run_input)
        out = agents_svc.run(db, goal=goal, company_ref=company, roles=cfg.get("roles"),
                             tenant_id=tenant_id, provider=provider, created_by=created_by)
        return {"status": "ok", "decision": out["decision"], "run_id": out["run_id"],
                "confidence": out["confidence"]}
    if ntype == "rag":
        q = _resolve(cfg.get("query", run_input.get("query", "")), context, run_input)
        out = rag.answer(db, question=str(q), tenant_id=tenant_id,
                         source_types=cfg.get("source_types"), provider=provider,
                         created_by=created_by)
        return {"status": "ok", "answer": out["answer"], "confidence": out["confidence"],
                "citations": out["citations"]}
    if ntype == "memory":
        op = cfg.get("op", "write")
        if op == "recall":
            hits = memory_svc.recall(db, query=str(_resolve(cfg.get("query", ""), context, run_input)),
                                     scope=cfg.get("scope", "organization"),
                                     scope_ref=cfg.get("scope_ref"), tenant_id=tenant_id)
            return {"status": "ok", "memories": hits}
        m = memory_svc.write(db, content=str(_resolve(cfg.get("content", ""), context, run_input)),
                             memory_type=cfg.get("memory_type", "procedural"),
                             scope=cfg.get("scope", "organization"),
                             scope_ref=cfg.get("scope_ref"), tenant_id=tenant_id)
        return {"status": "ok", "memory_id": m.id}
    if ntype == "report":
        out = reports_svc.generate(db, report_type=cfg.get("report_type", "credit_memo"),
                                   company_ref=_resolve(cfg.get("company_ref", run_input.get("company_ref")), context, run_input),
                                   tenant_id=tenant_id, provider=provider, created_by=created_by)
        return {"status": "ok", "report_id": out["report_id"], "decision": out["decision"]}
    if ntype in ("api", "connector"):
        # External call node — records a deterministic, auditable stub (no real
        # egress in the offline default). Config declares the target + payload.
        return {"status": "ok", "target": cfg.get("target"), "method": cfg.get("method", "GET"),
                "kind": ntype, "echo": cfg.get("payload", {}),
                "note": "recorded (offline stub); wire a real connector to execute"}
    if ntype == "approval":
        if cfg.get("auto_approve"):
            return {"status": "approved", "approver": cfg.get("approver", "auto")}
        return {"status": "pending", "gate": cfg.get("gate", "approval")}
    if ntype == "condition":
        field = cfg.get("field")
        op = cfg.get("op", "eq")
        expected = cfg.get("value")
        actual = _resolve(field, context, run_input) if field else None
        result = _eval_condition(actual, op, expected)
        return {"status": "ok", "result": result, "actual": actual}
    return {"status": "skipped", "reason": f"unhandled node type {ntype}"}


def _eval_condition(actual, op, expected) -> bool:
    try:
        if op == "eq":
            return actual == expected
        if op == "ne":
            return actual != expected
        if op == "gt":
            return actual is not None and actual > expected
        if op == "gte":
            return actual is not None and actual >= expected
        if op == "lt":
            return actual is not None and actual < expected
        if op == "lte":
            return actual is not None and actual <= expected
        if op == "in":
            return actual in (expected or [])
        if op == "contains":
            return expected in (actual or "")
    except Exception:
        return False
    return False


# ---------------------------------------------------------------------------
# Execution engine
# ---------------------------------------------------------------------------
def run_workflow(db: Session, *, workflow_id: Optional[int] = None, key: Optional[str] = None,
                 run_input: Optional[Dict[str, Any]] = None, tenant_id: Optional[int] = None,
                 provider: Optional[str] = None, created_by: Optional[str] = None) -> Dict[str, Any]:
    wf = get_workflow(db, workflow_id=workflow_id, key=key, tenant_id=tenant_id)
    if wf is None:
        raise ValueError("workflow not found")
    graph = wf.graph or {}
    node_by_id = {n["id"]: n for n in graph.get("nodes", [])}
    run_input = run_input or {}
    context: Dict[str, Any] = {}
    node_results: List[Dict[str, Any]] = []

    run = AIPWorkflowRun(workflow_id=wf.id, tenant_id=tenant_id, status="running",
                         input=run_input, context={}, node_results=[],
                         created_by=created_by, started_at=common.utcnow())
    db.add(run)
    db.commit()
    db.refresh(run)

    current = graph.get("start")
    status = "completed"
    error = None
    steps = 0
    try:
        while current and steps < _MAX_STEPS:
            node = node_by_id.get(current)
            if node is None:
                error = f"node '{current}' not found"
                status = "failed"
                break
            out = _exec_node(db, node, context, run_input, tenant_id=tenant_id,
                             provider=provider, created_by=created_by)
            context[node["id"]] = out
            node_results.append({"node_id": node["id"], "type": node["type"], "output": out})
            steps += 1
            if node["type"] == "approval" and out.get("status") == "pending":
                status = "awaiting_approval"
                break
            if node["type"] == "end":
                break
            if node["type"] == "condition":
                edges = node.get("edges") or {}
                current = edges.get("true") if out.get("result") else edges.get("false")
            else:
                current = node.get("next")
        else:
            if steps >= _MAX_STEPS:
                status = "failed"
                error = "max steps exceeded (possible cycle)"
    except Exception as e:  # pragma: no cover - defensive
        status = "failed"
        error = str(e)

    run.status = status
    run.context = context
    run.node_results = node_results
    run.error = error
    run.completed_at = common.utcnow()
    db.commit()
    db.refresh(run)
    return {"run_id": run.id, "workflow_id": wf.id, "status": status, "error": error,
            "steps": steps, "node_results": node_results}


def get_run(db: Session, run_id: int) -> Optional[Dict[str, Any]]:
    r = db.query(AIPWorkflowRun).filter(AIPWorkflowRun.id == run_id).first()
    if not r:
        return None
    return {"run_id": r.id, "workflow_id": r.workflow_id, "status": r.status,
            "input": r.input, "node_results": r.node_results, "error": r.error,
            "started_at": common.iso(r.started_at), "completed_at": common.iso(r.completed_at)}


def list_runs(db: Session, *, workflow_id: int) -> List[Dict[str, Any]]:
    rows = (db.query(AIPWorkflowRun).filter(AIPWorkflowRun.workflow_id == workflow_id)
            .order_by(AIPWorkflowRun.id.desc()).all())
    return [{"run_id": r.id, "status": r.status, "error": r.error,
             "started_at": common.iso(r.started_at)} for r in rows]

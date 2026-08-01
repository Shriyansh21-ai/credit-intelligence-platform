"""M11 — Enterprise Workflow Studio.

Visual, versioned, BPMN-like workflows (drag-and-drop on the frontend) with a
deterministic execution engine. A definition is a directed graph of typed nodes
(start / task / decision / approval / automation / notification / end) connected
by edges that may carry a condition. The engine walks the graph from ``start``
resolves decision branches by evaluating edge conditions against the run context
(reusing the policy condition evaluator), records a full step trace, and
pauses at ``approval`` nodes unless the context authorizes auto-approval.

Deterministic and loop-guarded — every run is reproducible and auditable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.banking_os import WorkflowDefinition, WorkflowRun
from .policy import eval_condition

NODE_TYPES = ["start", "task", "decision", "approval", "automation", "notification", "end"]
_MAX_STEPS = 200


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_graph(graph: Any) -> List[str]:
    problems: List[str] = []
    if not isinstance(graph, dict):
        return ["graph must be an object with 'nodes' and 'edges'"]
    nodes = graph.get("nodes")
    edges = graph.get("edges", [])
    if not isinstance(nodes, list) or not nodes:
        return ["graph.nodes must be a non-empty list"]
    ids = [n.get("id") for n in nodes]
    if len(ids) != len(set(ids)):
        problems.append("duplicate node ids")
    types = {}
    for n in nodes:
        if not n.get("id"):
            problems.append("a node is missing 'id'")
        if n.get("type") not in NODE_TYPES:
            problems.append(f"node '{n.get('id')}' has invalid type '{n.get('type')}'")
        types[n.get("id")] = n.get("type")
    if list(types.values()).count("start") != 1:
        problems.append("graph must have exactly one 'start' node")
    if "end" not in types.values():
        problems.append("graph must have at least one 'end' node")
    idset = set(ids)
    for e in edges:
        if e.get("from") not in idset or e.get("to") not in idset:
            problems.append(f"edge {e.get('from')}->{e.get('to')} references unknown node")
    return problems


# ---------------------------------------------------------------------------
# Execution engine
# ---------------------------------------------------------------------------
def execute_graph(graph: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministically execute a workflow graph over ``context``.

    Returns ``{status, path, trace, outputs, current_node}``. ``status`` is
    ``completed`` (reached an end node), ``waiting`` (paused at an approval that
    was not auto-approved) or ``failed`` (dead end / loop guard).
    """
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    edges = graph.get("edges", [])
    start = next((n["id"] for n in graph.get("nodes", []) if n.get("type") == "start"), None)
    if start is None:
        return {"status": "failed", "path": [], "trace": [], "outputs": {},
                "current_node": None, "reason": "no start node"}

    outgoing: Dict[str, List[dict]] = {}
    for e in edges:
        outgoing.setdefault(e["from"], []).append(e)

    context = dict(context or {})
    trace: List[Dict[str, Any]] = []
    path: List[str] = []
    current = start
    steps = 0
    status = "failed"

    while current is not None and steps < _MAX_STEPS:
        steps += 1
        node = nodes.get(current)
        if node is None:
            trace.append({"node": current, "type": "?", "action": "error:unknown-node"})
            break
        ntype = node.get("type")
        path.append(current)
        entry = {"node": current, "type": ntype, "name": node.get("name")}

        if ntype == "end":
            entry["action"] = "completed"
            trace.append(entry)
            status = "completed"
            break

        if ntype == "approval":
            approved = bool(context.get(node.get("config", {}).get("approve_key", "approved"), False))
            if not approved:
                entry["action"] = "waiting-approval"
                trace.append(entry)
                status = "waiting"
                break
            entry["action"] = "approved"

        elif ntype == "automation":
            # Record the automation intent (side effects handled by callers/plugins).
            entry["action"] = "automation"
            entry["config"] = node.get("config", {})

        elif ntype == "notification":
            entry["action"] = "notify"
            entry["target"] = node.get("config", {}).get("target")

        elif ntype == "task":
            entry["action"] = "task"

        elif ntype == "decision":
            entry["action"] = "decision"

        # choose the next edge
        outs = outgoing.get(current, [])
        chosen = _choose_edge(outs, context)
        trace.append(entry)
        if chosen is None:
            if outs:
                status = "failed"
                entry["action"] = entry.get("action", "") + ":no-matching-edge"
            current = None
            break
        entry["next"] = chosen["to"]
        current = chosen["to"]

    if steps >= _MAX_STEPS:
        status = "failed"
    return {"status": status, "path": path, "trace": trace, "outputs": context,
            "current_node": current}


def _choose_edge(edges: List[dict], context: Dict[str, Any]) -> Optional[dict]:
    """Pick the first edge whose condition matches; fall back to a default/uncond edge."""
    default = None
    for e in edges:
        cond = e.get("condition")
        if cond is None:
            if default is None:
                default = e
            continue
        if e.get("default"):
            default = e
            continue
        if eval_condition(cond, context):
            return e
    return default


# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------
def create_definition(db: Session, *, key: str, name: str, graph: dict,
                      description: Optional[str] = None, tenant_id: Optional[int] = None,
                      created_by: Optional[str] = None, publish: bool = False) -> WorkflowDefinition:
    key = (key or "").strip()
    if not key:
        raise ValueError("workflow key required")
    problems = validate_graph(graph)
    if problems:
        raise ValueError("invalid workflow: " + "; ".join(problems))
    version = (db.query(WorkflowDefinition)
               .filter(WorkflowDefinition.tenant_id == tenant_id,
                       WorkflowDefinition.key == key).count()) + 1
    wf = WorkflowDefinition(tenant_id=tenant_id, key=key, name=name or key, description=description,
                            version=version, graph=graph, created_by=created_by,
                            status="active" if publish else "draft")
    db.add(wf)
    db.commit()
    db.refresh(wf)
    return wf


def get_definition(db: Session, key: str, *, version: Optional[int] = None,
                   tenant_id: Optional[int] = None) -> Optional[WorkflowDefinition]:
    q = db.query(WorkflowDefinition).filter(WorkflowDefinition.tenant_id == tenant_id,
                                            WorkflowDefinition.key == key)
    if version is not None:
        return q.filter(WorkflowDefinition.version == version).first()
    return q.order_by(WorkflowDefinition.version.desc()).first()


def list_definitions(db: Session, *, tenant_id: Optional[int] = None) -> List[WorkflowDefinition]:
    return (db.query(WorkflowDefinition).filter(WorkflowDefinition.tenant_id == tenant_id)
            .order_by(WorkflowDefinition.key, WorkflowDefinition.version.desc()).all())


def publish_definition(db: Session, key: str, version: int, *, tenant_id: Optional[int] = None) -> WorkflowDefinition:
    wf = get_definition(db, key, version=version, tenant_id=tenant_id)
    if wf is None:
        raise ValueError("workflow version not found")
    wf.status = "active"
    db.commit()
    db.refresh(wf)
    return wf


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------
def run(db: Session, *, key: str, context: Optional[dict] = None, subject_ref: Optional[str] = None,
        version: Optional[int] = None, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    wf = get_definition(db, key, version=version, tenant_id=tenant_id)
    if wf is None:
        raise ValueError(f"workflow '{key}' not found")
    result = execute_graph(wf.graph, context or {})
    row = WorkflowRun(tenant_id=tenant_id, definition_key=key, definition_version=wf.version,
                      subject_ref=subject_ref, status=result["status"], context=context or {},
                      trace=result["trace"], path=result["path"], current_node=result["current_node"],
                      outputs=result["outputs"],
                      finished_at=datetime.utcnow() if result["status"] != "waiting" else None)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"run_id": row.id, **result, "definition_version": wf.version}


def resume(db: Session, run_id: int, *, context_update: Optional[dict] = None) -> Dict[str, Any]:
    """Resume a waiting run (e.g. after an approval) from its start with merged context."""
    row = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if row is None:
        raise ValueError("run not found")
    if row.status != "waiting":
        raise ValueError("run is not waiting")
    wf = get_definition(db, row.definition_key, version=row.definition_version, tenant_id=row.tenant_id)
    merged = {**(row.context or {}), **(context_update or {})}
    result = execute_graph(wf.graph, merged)
    row.status = result["status"]
    row.context = merged
    row.trace = result["trace"]
    row.path = result["path"]
    row.current_node = result["current_node"]
    row.outputs = result["outputs"]
    row.finished_at = datetime.utcnow() if result["status"] != "waiting" else None
    db.commit()
    db.refresh(row)
    return {"run_id": row.id, **result}


def list_runs(db: Session, *, key: Optional[str] = None, status: Optional[str] = None,
              tenant_id: Optional[int] = None) -> List[WorkflowRun]:
    q = db.query(WorkflowRun).filter(WorkflowRun.tenant_id == tenant_id)
    if key:
        q = q.filter(WorkflowRun.definition_key == key)
    if status:
        q = q.filter(WorkflowRun.status == status)
    return q.order_by(WorkflowRun.started_at.desc()).all()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def definition_dict(w: WorkflowDefinition) -> Dict[str, Any]:
    return {"id": w.id, "key": w.key, "name": w.name, "description": w.description,
            "version": w.version, "status": w.status, "graph": w.graph,
            "node_count": len(w.graph.get("nodes", [])) if isinstance(w.graph, dict) else 0,
            "created_by": w.created_by}


def run_dict(r: WorkflowRun) -> Dict[str, Any]:
    return {"id": r.id, "definition_key": r.definition_key, "version": r.definition_version,
            "subject_ref": r.subject_ref, "status": r.status, "path": r.path,
            "current_node": r.current_node,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None}

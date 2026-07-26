"""M7 — Enterprise Policy Engine.

A no-code, versioned, deterministic business-rule engine. Policies live in
governance *domains* (loan / AML / KYC / exposure / sector / collateral /
approval / country / risk-appetite / fraud). Each published
:class:`PolicyVersion` carries a rule DSL evaluated in priority order against an
input subject at runtime — no code deploys, fully auditable, never an LLM.

Rule DSL (one entry in ``rules``)::

    {
      "id": "high-pd",
      "name": "Reject very high PD",
      "when": [{"field": "pd", "op": "gte", "value": 0.25}],
      "then": {"decision": "reject", "action": "decline",
               "message": "PD above risk appetite", "params": {}},
      "priority": 100,        # higher fires first
      "stop": true            # stop after this rule (first_match/highest_priority)
    }

``when`` is an AND of conditions; ``op`` is one of the operators in
:data:`OPERATORS`. ``combine`` on the version controls how multiple matches are
resolved. The engine returns the final decision, the matched rules, the ordered
actions, human-readable reasons and evidence — never fabricated.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.banking_os import Policy, PolicyEvaluation, PolicyVersion
from .common import evidence

# Governance domains (drives UI grouping + validation).
DOMAINS = [
    "loan", "aml", "kyc", "exposure", "sector", "collateral", "approval",
    "country", "risk_appetite", "fraud", "pricing", "general",
]

# Terminal decisions ordered by severity (worst wins under "all"/"highest_priority").
DECISION_SEVERITY = {"pass": 0, "flag": 1, "refer": 2, "conditional": 2, "reject": 3, "block": 4}

OPERATORS = [
    "eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "contains",
    "not_contains", "exists", "not_exists", "between", "regex", "starts_with",
]


# ---------------------------------------------------------------------------
# Pure evaluation core (no DB) — reused by the playground + persistence path.
# ---------------------------------------------------------------------------
def _resolve(field: str, data: Dict[str, Any]) -> Any:
    """Dotted-path lookup into a nested dict (``a.b.c``); ``None`` if missing."""
    cur: Any = data
    for part in str(field).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _num(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def eval_condition(cond: Dict[str, Any], data: Dict[str, Any]) -> bool:
    """Evaluate one ``{field, op, value}`` condition deterministically."""
    op = cond.get("op", "eq")
    field = cond.get("field")
    target = cond.get("value")
    actual = _resolve(field, data) if field else None

    if op == "exists":
        return actual is not None
    if op == "not_exists":
        return actual is None
    if op in ("eq", "ne"):
        eq = actual == target
        # numeric-tolerant equality
        if not eq and _num(actual) is not None and _num(target) is not None:
            eq = _num(actual) == _num(target)
        return eq if op == "eq" else not eq
    if op in ("gt", "gte", "lt", "lte"):
        a, b = _num(actual), _num(target)
        if a is None or b is None:
            return False
        return {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[op]
    if op == "between":
        a = _num(actual)
        if a is None or not isinstance(target, (list, tuple)) or len(target) != 2:
            return False
        lo, hi = _num(target[0]), _num(target[1])
        return lo is not None and hi is not None and lo <= a <= hi
    if op == "in":
        return isinstance(target, (list, tuple, set)) and actual in target
    if op == "not_in":
        return isinstance(target, (list, tuple, set)) and actual not in target
    if op == "contains":
        if isinstance(actual, (list, tuple, set, str)):
            return target in actual
        return False
    if op == "not_contains":
        if isinstance(actual, (list, tuple, set, str)):
            return target not in actual
        return True
    if op == "starts_with":
        return isinstance(actual, str) and isinstance(target, str) and actual.lower().startswith(target.lower())
    if op == "regex":
        try:
            return actual is not None and re.search(str(target), str(actual)) is not None
        except re.error:
            return False
    return False


def rule_matches(rule: Dict[str, Any], data: Dict[str, Any]) -> bool:
    """A rule matches when *all* of its ``when`` conditions hold (empty → always)."""
    conds = rule.get("when") or []
    return all(eval_condition(c, data) for c in conds)


def evaluate_rules(rules: List[Dict[str, Any]], data: Dict[str, Any], *,
                   combine: str = "first_match",
                   default_decision: str = "pass") -> Dict[str, Any]:
    """Evaluate a rule list against ``data``; returns the decision bundle.

    ``combine``:
      * ``first_match`` — rules sorted by priority desc; stop at the first match
        (or the first match with ``stop=true``).
      * ``highest_priority`` — evaluate all, the highest-priority match decides.
      * ``all`` — evaluate all; the worst decision (by severity) wins; every
        matched rule's action is collected.
    """
    ordered = sorted(enumerate(rules), key=lambda kv: (-int(kv[1].get("priority", 0)), kv[0]))
    matched: List[Dict[str, Any]] = []
    for _idx, rule in ordered:
        if not rule_matches(rule, data):
            continue
        then = rule.get("then") or {}
        matched.append({
            "id": rule.get("id"), "name": rule.get("name"),
            "decision": then.get("decision", "flag"),
            "action": then.get("action"), "params": then.get("params") or {},
            "message": then.get("message") or rule.get("name"),
            "priority": int(rule.get("priority", 0)),
        })
        if combine == "first_match" and rule.get("stop", True):
            break

    if not matched:
        return {"decision": default_decision, "matched_rules": [], "actions": [],
                "reasons": [f"No rule matched; default decision '{default_decision}'."]}

    if combine == "all":
        decision = max(matched, key=lambda m: DECISION_SEVERITY.get(m["decision"], 0))["decision"]
    elif combine == "highest_priority":
        decision = max(matched, key=lambda m: m["priority"])["decision"]
    else:  # first_match
        decision = matched[0]["decision"]

    actions = [{"action": m["action"], "params": m["params"], "rule": m["id"]}
               for m in matched if m.get("action")]
    reasons = [m["message"] for m in matched if m.get("message")]
    return {"decision": decision, "matched_rules": matched, "actions": actions,
            "reasons": reasons}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_rules(rules: Any) -> List[str]:
    """Return a list of human-readable problems with a ruleset (empty = valid)."""
    problems: List[str] = []
    if not isinstance(rules, list):
        return ["rules must be a list"]
    seen_ids = set()
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            problems.append(f"rule[{i}] must be an object")
            continue
        rid = rule.get("id")
        if not rid:
            problems.append(f"rule[{i}] missing 'id'")
        elif rid in seen_ids:
            problems.append(f"duplicate rule id '{rid}'")
        else:
            seen_ids.add(rid)
        for j, cond in enumerate(rule.get("when") or []):
            if not isinstance(cond, dict) or "field" not in cond:
                problems.append(f"rule[{i}].when[{j}] needs a 'field'")
            elif cond.get("op", "eq") not in OPERATORS:
                problems.append(f"rule[{i}].when[{j}] unknown op '{cond.get('op')}'")
        then = rule.get("then")
        if not isinstance(then, dict) or "decision" not in then:
            problems.append(f"rule[{i}].then needs a 'decision'")
    return problems


# ---------------------------------------------------------------------------
# Repository / lifecycle
# ---------------------------------------------------------------------------
def create_policy(db: Session, *, key: str, name: str, domain: str,
                  description: Optional[str] = None, tenant_id: Optional[int] = None,
                  tags: Optional[list] = None, created_by: Optional[str] = None) -> Policy:
    key = (key or "").strip()
    if not key:
        raise ValueError("policy key required")
    if domain not in DOMAINS:
        raise ValueError(f"unknown domain '{domain}'")
    if db.query(Policy).filter(Policy.tenant_id == tenant_id, Policy.key == key).first():
        raise ValueError(f"policy '{key}' already exists")
    p = Policy(tenant_id=tenant_id, key=key, name=name or key, domain=domain,
               description=description, tags=tags or [], created_by=created_by,
               status="draft", current_version=0)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def add_version(db: Session, policy_id: int, *, rules: list,
                combine: str = "first_match", default_decision: str = "pass",
                notes: Optional[str] = None, created_by: Optional[str] = None,
                publish: bool = False) -> PolicyVersion:
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if policy is None:
        raise ValueError("policy not found")
    problems = validate_rules(rules)
    if problems:
        raise ValueError("invalid ruleset: " + "; ".join(problems))
    next_version = (db.query(PolicyVersion)
                    .filter(PolicyVersion.policy_id == policy_id).count()) + 1
    pv = PolicyVersion(policy_id=policy_id, version=next_version, rules=rules,
                       combine=combine, default_decision=default_decision,
                       notes=notes, created_by=created_by,
                       status="published" if publish else "draft")
    db.add(pv)
    if publish:
        policy.current_version = next_version
        policy.status = "active"
    db.commit()
    db.refresh(pv)
    return pv


def publish_version(db: Session, policy_id: int, version: int) -> Policy:
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if policy is None:
        raise ValueError("policy not found")
    pv = (db.query(PolicyVersion)
          .filter(PolicyVersion.policy_id == policy_id, PolicyVersion.version == version).first())
    if pv is None:
        raise ValueError("version not found")
    pv.status = "published"
    policy.current_version = version
    policy.status = "active"
    db.commit()
    db.refresh(policy)
    return policy


def archive_policy(db: Session, policy_id: int) -> Policy:
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if policy is None:
        raise ValueError("policy not found")
    policy.status = "archived"
    db.commit()
    db.refresh(policy)
    return policy


def get_policy(db: Session, *, policy_id: Optional[int] = None, key: Optional[str] = None,
               tenant_id: Optional[int] = None) -> Optional[Policy]:
    q = db.query(Policy)
    if policy_id is not None:
        return q.filter(Policy.id == policy_id).first()
    return q.filter(Policy.tenant_id == tenant_id, Policy.key == key).first()


def active_version(db: Session, policy: Policy) -> Optional[PolicyVersion]:
    if not policy.current_version:
        return None
    return (db.query(PolicyVersion)
            .filter(PolicyVersion.policy_id == policy.id,
                    PolicyVersion.version == policy.current_version).first())


def list_policies(db: Session, *, tenant_id: Optional[int] = None,
                  domain: Optional[str] = None, status: Optional[str] = None) -> List[Policy]:
    q = db.query(Policy).filter(Policy.tenant_id == tenant_id)
    if domain:
        q = q.filter(Policy.domain == domain)
    if status:
        q = q.filter(Policy.status == status)
    return q.order_by(Policy.domain, Policy.key).all()


def list_versions(db: Session, policy_id: int) -> List[PolicyVersion]:
    return (db.query(PolicyVersion).filter(PolicyVersion.policy_id == policy_id)
            .order_by(PolicyVersion.version.desc()).all())


# ---------------------------------------------------------------------------
# Evaluation (real-time execution)
# ---------------------------------------------------------------------------
def evaluate(db: Session, *, policy_key: str, data: Dict[str, Any],
             subject_ref: Optional[str] = None, tenant_id: Optional[int] = None,
             persist: bool = True) -> Dict[str, Any]:
    """Evaluate the *active* version of a policy against ``data`` in real time."""
    policy = get_policy(db, key=policy_key, tenant_id=tenant_id)
    if policy is None:
        raise ValueError(f"policy '{policy_key}' not found")
    if policy.status != "active":
        raise ValueError(f"policy '{policy_key}' is not active")
    pv = active_version(db, policy)
    if pv is None:
        raise ValueError(f"policy '{policy_key}' has no published version")
    result = evaluate_rules(pv.rules, data, combine=pv.combine,
                            default_decision=pv.default_decision)
    ev = [evidence(f"rule:{m['id']}", m["decision"], source="policy_engine")
          for m in result["matched_rules"]]
    bundle = {
        "policy_key": policy_key, "policy_id": policy.id, "version": pv.version,
        "domain": policy.domain, "subject_ref": subject_ref,
        "decision": result["decision"], "matched_rules": result["matched_rules"],
        "actions": result["actions"], "reasons": result["reasons"],
        "evidence": ev, "confidence": 1.0,  # deterministic → full confidence
    }
    if persist:
        row = PolicyEvaluation(
            tenant_id=tenant_id, policy_id=policy.id, policy_key=policy_key,
            version=pv.version, subject_ref=subject_ref, input=data,
            decision=result["decision"], matched_rules=result["matched_rules"],
            actions=result["actions"], reasons=result["reasons"])
        db.add(row)
        db.commit()
        db.refresh(row)
        bundle["evaluation_id"] = row.id
    return bundle


def evaluate_domain(db: Session, *, domain: str, data: Dict[str, Any],
                    subject_ref: Optional[str] = None, tenant_id: Optional[int] = None,
                    persist: bool = True) -> Dict[str, Any]:
    """Evaluate every active policy in a ``domain`` and aggregate the worst decision."""
    policies = [p for p in list_policies(db, tenant_id=tenant_id, domain=domain, status="active")]
    results = []
    for p in policies:
        try:
            results.append(evaluate(db, policy_key=p.key, data=data,
                                    subject_ref=subject_ref, tenant_id=tenant_id, persist=persist))
        except ValueError:
            continue
    if not results:
        return {"domain": domain, "decision": "pass", "policies": [], "reasons": []}
    worst = max(results, key=lambda r: DECISION_SEVERITY.get(r["decision"], 0))
    reasons = [reason for r in results for reason in r["reasons"]]
    return {"domain": domain, "decision": worst["decision"], "policies": results,
            "reasons": reasons, "policy_count": len(results)}


def playground(rules: list, data: Dict[str, Any], *, combine: str = "first_match",
               default_decision: str = "pass") -> Dict[str, Any]:
    """Dry-run a ruleset without persistence (visual rule builder preview)."""
    problems = validate_rules(rules)
    if problems:
        return {"valid": False, "problems": problems}
    result = evaluate_rules(rules, data, combine=combine, default_decision=default_decision)
    return {"valid": True, **result}


def evaluation_history(db: Session, *, policy_key: Optional[str] = None,
                       subject_ref: Optional[str] = None, tenant_id: Optional[int] = None,
                       limit: int = 100) -> List[PolicyEvaluation]:
    q = db.query(PolicyEvaluation).filter(PolicyEvaluation.tenant_id == tenant_id)
    if policy_key:
        q = q.filter(PolicyEvaluation.policy_key == policy_key)
    if subject_ref:
        q = q.filter(PolicyEvaluation.subject_ref == subject_ref)
    return q.order_by(PolicyEvaluation.created_at.desc()).limit(limit).all()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def policy_dict(p: Policy) -> Dict[str, Any]:
    return {"id": p.id, "key": p.key, "name": p.name, "domain": p.domain,
            "description": p.description, "status": p.status,
            "current_version": p.current_version, "tags": p.tags,
            "created_by": p.created_by,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None}


def version_dict(v: PolicyVersion) -> Dict[str, Any]:
    return {"id": v.id, "version": v.version, "rules": v.rules, "combine": v.combine,
            "default_decision": v.default_decision, "status": v.status,
            "notes": v.notes, "created_by": v.created_by,
            "created_at": v.created_at.isoformat() if v.created_at else None}


def evaluation_dict(e: PolicyEvaluation) -> Dict[str, Any]:
    return {"id": e.id, "policy_key": e.policy_key, "version": e.version,
            "subject_ref": e.subject_ref, "decision": e.decision,
            "matched_rules": e.matched_rules, "actions": e.actions,
            "reasons": e.reasons,
            "created_at": e.created_at.isoformat() if e.created_at else None}

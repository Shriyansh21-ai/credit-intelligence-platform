"""M1 — Enterprise Knowledge Graph: advanced analytics.

Extends the Phase 9 knowledge graph (``kg_entities`` / ``kg_relationships``) with
the regulated-lending analytics banks need: **Ultimate Beneficial Owner** (UBO)
resolution with effective ownership, **connected-lending** detection (credit
extended to related parties), **cross-holding** cycle detection, and an entity
**timeline**. Read-only over the Phase 9 tables — nothing in Phase 9 is modified.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from backend.app.models.autonomous import KGEntity, KGRelationship

# Edges where source *owns* target.
OWNERSHIP_DOWN = {"parent_of", "promoter_of", "shareholder_of"}
# Edges where source is *owned by* target (reverse ownership).
OWNERSHIP_UP = {"subsidiary_of"}
# Edges that carry credit between parties.
LENDING_TYPES = {"lends_to", "guarantees", "pledged_as_collateral"}


def _entities(db: Session, tenant_id: Optional[int]) -> Dict[int, KGEntity]:
    return {e.id: e for e in db.query(KGEntity).filter(KGEntity.tenant_id == tenant_id).all()}


def _edges(db: Session, tenant_id: Optional[int]) -> List[KGRelationship]:
    return db.query(KGRelationship).filter(KGRelationship.tenant_id == tenant_id).all()


def _find(db: Session, ref: str, tenant_id: Optional[int]) -> Optional[KGEntity]:
    return (db.query(KGEntity)
            .filter(KGEntity.tenant_id == tenant_id, KGEntity.ref == ref).first())


def _ownership_fraction(edge: KGRelationship) -> float:
    """Effective ownership fraction for an ownership edge (0..1)."""
    attrs = edge.attributes or {}
    pct = attrs.get("ownership_pct")
    if pct is not None:
        try:
            return max(0.0, min(1.0, float(pct) / 100.0))
        except (TypeError, ValueError):
            pass
    return max(0.0, min(1.0, edge.strength or 0.5))


# ---------------------------------------------------------------------------
# Ultimate Beneficial Owners
# ---------------------------------------------------------------------------
def ultimate_beneficial_owners(db: Session, company_ref: str, *, tenant_id: Optional[int] = None,
                               min_fraction: float = 0.10, max_depth: int = 6) -> Dict[str, Any]:
    """Resolve UBOs of a company by walking ownership edges owner-ward.

    Effective ownership along a path is the product of edge ownership fractions.
    Terminal owners (no further owners above them) with effective ownership ≥
    ``min_fraction`` are reported as UBOs.
    """
    company = _find(db, company_ref, tenant_id)
    if company is None:
        raise ValueError("company not found")
    entities = _entities(db, tenant_id)
    edges = _edges(db, tenant_id)

    # owners_of[node] -> list of (owner_id, fraction)
    owners_of: Dict[int, List[Tuple[int, float]]] = defaultdict(list)
    for e in edges:
        if e.rel_type in OWNERSHIP_DOWN:
            owners_of[e.target_id].append((e.source_id, _ownership_fraction(e)))
        elif e.rel_type in OWNERSHIP_UP:
            owners_of[e.source_id].append((e.target_id, _ownership_fraction(e)))

    ubos: Dict[int, float] = defaultdict(float)
    intermediaries: Set[int] = set()

    def walk(node_id: int, acc: float, depth: int, seen: Set[int]):
        parents = owners_of.get(node_id, [])
        if not parents or depth >= max_depth:
            if node_id != company.id:
                ubos[node_id] += acc
            return
        for owner_id, frac in parents:
            if owner_id in seen:  # cycle guard
                continue
            intermediaries.add(node_id) if node_id != company.id else None
            walk(owner_id, acc * frac, depth + 1, seen | {owner_id})

    walk(company.id, 1.0, 0, {company.id})
    result = []
    for oid, frac in ubos.items():
        if frac >= min_fraction and oid in entities:
            e = entities[oid]
            result.append({"id": e.id, "ref": e.ref, "name": e.name,
                           "entity_type": e.entity_type,
                           "effective_ownership": round(frac, 4),
                           "risk_score": e.risk_score})
    result.sort(key=lambda x: -x["effective_ownership"])
    return {"company_ref": company_ref, "ubos": result, "ubo_count": len(result),
            "min_fraction": min_fraction}


# ---------------------------------------------------------------------------
# Connected lending
# ---------------------------------------------------------------------------
def connected_lending(db: Session, entity_ref: str, *, tenant_id: Optional[int] = None,
                      max_depth: int = 3) -> Dict[str, Any]:
    """Detect credit extended to parties related to ``entity_ref``.

    Builds the related-party set (any non-lending relationship within
    ``max_depth``) then flags lending/guarantee edges that touch two related
    parties — the classic connected-lending exposure regulators probe.
    """
    root = _find(db, entity_ref, tenant_id)
    if root is None:
        raise ValueError("entity not found")
    entities = _entities(db, tenant_id)
    edges = _edges(db, tenant_id)

    adj: Dict[int, List[int]] = defaultdict(list)
    for e in edges:
        if e.rel_type not in LENDING_TYPES:
            adj[e.source_id].append(e.target_id)
            adj[e.target_id].append(e.source_id)
    # BFS related-party set
    related: Set[int] = {root.id}
    q = deque([(root.id, 0)])
    while q:
        cur, d = q.popleft()
        if d >= max_depth:
            continue
        for nbr in adj.get(cur, []):
            if nbr not in related:
                related.add(nbr)
                q.append((nbr, d + 1))

    flagged = []
    total_exposure = 0.0
    for e in edges:
        if e.rel_type in LENDING_TYPES and e.source_id in related and e.target_id in related:
            exp = e.exposure or 0.0
            total_exposure += exp
            flagged.append({
                "rel_type": e.rel_type, "exposure": exp,
                "from": entities[e.source_id].ref if e.source_id in entities else e.source_id,
                "to": entities[e.target_id].ref if e.target_id in entities else e.target_id,
            })
    flagged.sort(key=lambda x: -(x["exposure"] or 0))
    return {"entity_ref": entity_ref, "related_parties": len(related),
            "connected_loans": flagged, "connected_loan_count": len(flagged),
            "connected_exposure": round(total_exposure, 2),
            "flag": len(flagged) > 0}


# ---------------------------------------------------------------------------
# Cross holdings (ownership cycles)
# ---------------------------------------------------------------------------
def cross_holdings(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Detect ownership cycles (A owns B … owns A) — circular cross-holdings."""
    entities = _entities(db, tenant_id)
    edges = _edges(db, tenant_id)
    owns: Dict[int, List[int]] = defaultdict(list)
    for e in edges:
        if e.rel_type in OWNERSHIP_DOWN:
            owns[e.source_id].append(e.target_id)
        elif e.rel_type in OWNERSHIP_UP:
            owns[e.target_id].append(e.source_id)

    cycles: List[List[str]] = []
    seen_cycles: Set[frozenset] = set()

    def dfs(start: int, cur: int, path: List[int], visiting: Set[int]):
        for nxt in owns.get(cur, []):
            if nxt == start and len(path) >= 2:
                key = frozenset(path)
                if key not in seen_cycles:
                    seen_cycles.add(key)
                    cycles.append([entities[i].ref for i in path if i in entities])
            elif nxt not in visiting and len(path) < 8:
                dfs(start, nxt, path + [nxt], visiting | {nxt})

    for node in list(owns.keys()):
        dfs(node, node, [node], {node})
    return {"cross_holdings": cycles, "count": len(cycles)}


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------
def timeline(db: Session, entity_ref: str, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Chronological history of an entity and its relationships."""
    entity = _find(db, entity_ref, tenant_id)
    if entity is None:
        raise ValueError("entity not found")
    events = [{"at": entity.created_at.isoformat() if entity.created_at else None,
               "type": "entity_created", "detail": f"{entity.entity_type} {entity.name}"}]
    edges = _edges(db, tenant_id)
    entities = _entities(db, tenant_id)
    for e in edges:
        if e.source_id == entity.id or e.target_id == entity.id:
            other_id = e.target_id if e.source_id == entity.id else e.source_id
            other = entities.get(other_id)
            events.append({"at": e.created_at.isoformat() if e.created_at else None,
                           "type": f"relationship:{e.rel_type}",
                           "detail": f"{e.rel_type} → {other.ref if other else other_id}",
                           "exposure": e.exposure})
    events.sort(key=lambda x: (x["at"] or ""))
    return {"entity_ref": entity_ref, "events": events, "event_count": len(events)}

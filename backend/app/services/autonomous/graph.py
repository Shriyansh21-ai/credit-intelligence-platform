"""M1 — Enterprise Knowledge Graph.

A directed, weighted property graph over companies and their connected entities
(directors, promoters, subsidiaries, suppliers, customers, lenders, guarantors
shareholders, sectors, regions, collateral). Backed by ``kg_entities`` /
``kg_relationships``; pure-graph algorithms (traversal, scoring, similarity
connected exposure, risk propagation) are implemented in-memory over the loaded
edge set so they work on SQLite and Postgres alike.

Design
* Repository functions (``upsert_entity``, ``add_relationship``) are idempotent on
  the natural keys (``uq_kg_entity_ref`` / ``uq_kg_edge``).
* Analytical functions build a lightweight adjacency view once and operate on it.
* ``seed_from_assessment`` / ``ingest_network`` wire real platform data (company +
  the Customer-360 relationship network from ) into the graph.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from backend.app.models.autonomous import KGEntity, KGRelationship
from .common import clamp

# Canonical entity taxonomy (also drives frontend legends).
ENTITY_TYPES = [
    "company", "director", "promoter", "subsidiary", "supplier", "customer",
    "lender", "guarantor", "shareholder", "sector", "region", "collateral",
    "connected_entity",
]

# Relationship taxonomy with a default strength + whether it carries exposure.
REL_TYPES: Dict[str, Dict[str, Any]] = {
    "director_of": {"strength": 0.7, "exposure": False},
    "promoter_of": {"strength": 0.85, "exposure": False},
    "subsidiary_of": {"strength": 0.9, "exposure": True},
    "parent_of": {"strength": 0.9, "exposure": True},
    "supplies": {"strength": 0.5, "exposure": True},
    "customer_of": {"strength": 0.5, "exposure": True},
    "lends_to": {"strength": 0.8, "exposure": True},
    "guarantees": {"strength": 0.95, "exposure": True},
    "shareholder_of": {"strength": 0.6, "exposure": False},
    "operates_in_sector": {"strength": 0.4, "exposure": False},
    "located_in": {"strength": 0.3, "exposure": False},
    "pledged_as_collateral": {"strength": 0.7, "exposure": True},
    "connected_to": {"strength": 0.3, "exposure": False},
}


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------
def upsert_entity(db: Session, *, entity_type: str, ref: str, name: Optional[str] = None,
                  tenant_id: Optional[int] = None, attributes: Optional[dict] = None,
                  risk_score: Optional[float] = None) -> KGEntity:
    ref = (ref or name or "").strip()
    if not ref:
        raise ValueError("entity ref/name required")
    row = (db.query(KGEntity)
           .filter(KGEntity.tenant_id == tenant_id,
                   KGEntity.entity_type == entity_type, KGEntity.ref == ref).first())
    if row is None:
        row = KGEntity(tenant_id=tenant_id, entity_type=entity_type, ref=ref,
                       name=name or ref, attributes=attributes or {}, risk_score=risk_score)
        db.add(row)
    else:
        if name:
            row.name = name
        if attributes:
            merged = dict(row.attributes or {})
            merged.update(attributes)
            row.attributes = merged
        if risk_score is not None:
            row.risk_score = risk_score
    db.commit()
    db.refresh(row)
    return row


def add_relationship(db: Session, source: KGEntity, target: KGEntity, rel_type: str, *,
                     strength: Optional[float] = None, exposure: Optional[float] = None,
                     attributes: Optional[dict] = None, tenant_id: Optional[int] = None) -> KGRelationship:
    default = REL_TYPES.get(rel_type, {"strength": 0.5})
    row = (db.query(KGRelationship)
           .filter(KGRelationship.source_id == source.id,
                   KGRelationship.target_id == target.id,
                   KGRelationship.rel_type == rel_type).first())
    if row is None:
        row = KGRelationship(
            tenant_id=tenant_id, source_id=source.id, target_id=target.id, rel_type=rel_type,
            strength=clamp(strength if strength is not None else default["strength"]),
            exposure=exposure, attributes=attributes or {})
        db.add(row)
    else:
        if strength is not None:
            row.strength = clamp(strength)
        if exposure is not None:
            row.exposure = exposure
        if attributes:
            row.attributes = {**(row.attributes or {}), **attributes}
    db.commit()
    db.refresh(row)
    return row


def get_entity(db: Session, entity_id: int) -> Optional[KGEntity]:
    return db.query(KGEntity).filter(KGEntity.id == entity_id).first()


def find_entity(db: Session, ref: str, *, tenant_id: Optional[int] = None,
                entity_type: Optional[str] = None) -> Optional[KGEntity]:
    q = db.query(KGEntity).filter(KGEntity.tenant_id == tenant_id, KGEntity.ref == ref.strip())
    if entity_type:
        q = q.filter(KGEntity.entity_type == entity_type)
    return q.first()


def list_entities(db: Session, *, tenant_id: Optional[int] = None,
                  entity_type: Optional[str] = None, limit: int = 500) -> List[KGEntity]:
    q = db.query(KGEntity).filter(KGEntity.tenant_id == tenant_id)
    if entity_type:
        q = q.filter(KGEntity.entity_type == entity_type)
    return q.limit(limit).all()


# ---------------------------------------------------------------------------
# In-memory graph view
# ---------------------------------------------------------------------------
class GraphView:
    """A materialized undirected-adjacency view for graph algorithms."""

    def __init__(self, entities: List[KGEntity], edges: List[KGRelationship]):
        self.nodes: Dict[int, KGEntity] = {e.id: e for e in entities}
        self.edges = edges
        # adjacency: node -> list of (neighbor_id, edge, is_forward)
        self.adj: Dict[int, List[Tuple[int, KGRelationship, bool]]] = defaultdict(list)
        for e in edges:
            self.adj[e.source_id].append((e.target_id, e, True))
            self.adj[e.target_id].append((e.source_id, e, False))

    def neighbors(self, node_id: int) -> List[Tuple[int, KGRelationship, bool]]:
        return self.adj.get(node_id, [])


def load_view(db: Session, *, tenant_id: Optional[int] = None) -> GraphView:
    entities = db.query(KGEntity).filter(KGEntity.tenant_id == tenant_id).all()
    ids = {e.id for e in entities}
    edges = [e for e in db.query(KGRelationship).filter(KGRelationship.tenant_id == tenant_id).all()
             if e.source_id in ids and e.target_id in ids]
    return GraphView(entities, edges)


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------
def traverse(view: GraphView, start_id: int, *, max_depth: int = 2,
             min_strength: float = 0.0) -> Dict[int, Dict[str, Any]]:
    """BFS from ``start_id`` returning ``{node_id: {depth, path_strength}}``.

    ``path_strength`` is the product of edge strengths along the discovered path
    (a decayed connectivity measure in ``(0,1]``).
    """
    if start_id not in view.nodes:
        return {}
    visited: Dict[int, Dict[str, Any]] = {start_id: {"depth": 0, "path_strength": 1.0}}
    queue: deque[int] = deque([start_id])
    while queue:
        cur = queue.popleft()
        cur_info = visited[cur]
        if cur_info["depth"] >= max_depth:
            continue
        for nbr, edge, _fwd in view.neighbors(cur):
            if edge.strength < min_strength:
                continue
            new_strength = cur_info["path_strength"] * max(edge.strength, 1e-6)
            if nbr not in visited or new_strength > visited[nbr]["path_strength"]:
                if nbr not in visited or visited[nbr]["depth"] > cur_info["depth"] + 1:
                    depth = cur_info["depth"] + 1
                else:
                    depth = visited[nbr]["depth"]
                visited[nbr] = {"depth": depth, "path_strength": round(new_strength, 6)}
                queue.append(nbr)
    return visited


def connected_entities(db: Session, entity_id: int, *, max_depth: int = 2,
                       tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    view = load_view(db, tenant_id=tenant_id)
    reached = traverse(view, entity_id, max_depth=max_depth)
    out = []
    for nid, info in reached.items():
        if nid == entity_id:
            continue
        node = view.nodes[nid]
        out.append({
            "id": node.id, "ref": node.ref, "name": node.name,
            "entity_type": node.entity_type, "risk_score": node.risk_score,
            "depth": info["depth"], "path_strength": info["path_strength"],
        })
    out.sort(key=lambda x: (x["depth"], -(x["path_strength"] or 0)))
    return out


# ---------------------------------------------------------------------------
# Relationship scoring
# ---------------------------------------------------------------------------
def relationship_score(db: Session, source_id: int, target_id: int, *,
                       tenant_id: Optional[int] = None, max_depth: int = 3) -> Dict[str, Any]:
    """Strongest-path connectivity score between two entities in ``(0,1]``."""
    view = load_view(db, tenant_id=tenant_id)
    reached = traverse(view, source_id, max_depth=max_depth)
    info = reached.get(target_id)
    if info is None:
        return {"connected": False, "score": 0.0, "distance": None}
    return {"connected": True, "score": info["path_strength"], "distance": info["depth"]}


# ---------------------------------------------------------------------------
# Entity similarity (Jaccard over neighbor sets + attribute overlap)
# ---------------------------------------------------------------------------
def _neighbor_refs(view: GraphView, node_id: int) -> Set[str]:
    return {view.nodes[n].ref for n, _e, _f in view.neighbors(node_id) if n in view.nodes}


def entity_similarity(db: Session, entity_id: int, *, tenant_id: Optional[int] = None,
                      top_k: int = 10) -> List[Dict[str, Any]]:
    """Rank other entities of the same type by structural + attribute similarity."""
    view = load_view(db, tenant_id=tenant_id)
    if entity_id not in view.nodes:
        return []
    base = view.nodes[entity_id]
    base_nbrs = _neighbor_refs(view, entity_id)
    base_attrs = set((base.attributes or {}).items()) if isinstance(base.attributes, dict) else set()
    results = []
    for nid, node in view.nodes.items():
        if nid == entity_id or node.entity_type != base.entity_type:
            continue
        nbrs = _neighbor_refs(view, nid)
        union = base_nbrs | nbrs
        struct = len(base_nbrs & nbrs) / len(union) if union else 0.0
        attrs = set((node.attributes or {}).items()) if isinstance(node.attributes, dict) else set()
        attr_union = base_attrs | attrs
        attr_sim = len(base_attrs & attrs) / len(attr_union) if attr_union else 0.0
        score = round(0.7 * struct + 0.3 * attr_sim, 4)
        if score > 0:
            results.append({"id": node.id, "ref": node.ref, "name": node.name,
                            "entity_type": node.entity_type, "similarity": score})
    results.sort(key=lambda x: -x["similarity"])
    return results[:top_k]


# ---------------------------------------------------------------------------
# Connected exposure
# ---------------------------------------------------------------------------
def connected_exposure(db: Session, entity_id: int, *, max_depth: int = 2,
                       tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Aggregate exposure reachable from an entity, decayed by path strength.

    Direct exposure is summed at full weight; indirect exposure is discounted by
    the product of edge strengths, giving a conservative "network at risk" figure.
    """
    view = load_view(db, tenant_id=tenant_id)
    reached = traverse(view, entity_id, max_depth=max_depth)
    direct = 0.0
    weighted = 0.0
    contributors: List[Dict[str, Any]] = []
    for edge in view.edges:
        if edge.exposure is None:
            continue
        # attribute the edge to whichever endpoint is closer to the root
        src_info = reached.get(edge.source_id)
        tgt_info = reached.get(edge.target_id)
        if src_info is None and tgt_info is None:
            continue
        best = min([i for i in (src_info, tgt_info) if i is not None],
                   key=lambda i: i["depth"])
        decay = best["path_strength"]
        w = edge.exposure * decay
        weighted += w
        if best["depth"] <= 1:
            direct += edge.exposure
        contributors.append({
            "rel_type": edge.rel_type, "exposure": edge.exposure,
            "decay": round(decay, 4), "weighted": round(w, 2), "depth": best["depth"],
        })
    contributors.sort(key=lambda c: -c["weighted"])
    return {
        "entity_id": entity_id,
        "direct_exposure": round(direct, 2),
        "connected_exposure": round(weighted, 2),
        "edge_count": len(contributors),
        "contributors": contributors[:25],
    }


# ---------------------------------------------------------------------------
# Risk propagation
# ---------------------------------------------------------------------------
def propagate_risk(db: Session, *, tenant_id: Optional[int] = None, iterations: int = 3,
                   damping: float = 0.5) -> Dict[int, float]:
    """Diffuse intrinsic risk across the graph (a bounded PageRank-style pass).

    Each node's propagated risk = its intrinsic risk plus a damped, strength- and
    distance-weighted average of neighbors' risk. Deterministic; converges as
    ``damping < 1``. Returns ``{entity_id: propagated_risk_0_100}`` and persists it
    back onto each node's ``attributes['propagated_risk']``.
    """
    view = load_view(db, tenant_id=tenant_id)
    risk = {nid: float(n.risk_score) if n.risk_score is not None else 0.0
            for nid, n in view.nodes.items()}
    for _ in range(max(1, iterations)):
        nxt = dict(risk)
        for nid in view.nodes:
            nbrs = view.neighbors(nid)
            if not nbrs:
                continue
            acc, wsum = 0.0, 0.0
            for nbr, edge, _f in nbrs:
                acc += risk.get(nbr, 0.0) * edge.strength
                wsum += edge.strength
            neighbor_influence = (acc / wsum) if wsum else 0.0
            intrinsic = float(view.nodes[nid].risk_score or 0.0)
            nxt[nid] = clamp((1 - damping) * intrinsic + damping * neighbor_influence, 0, 100)
        risk = nxt
    # persist
    for nid, val in risk.items():
        node = view.nodes[nid]
        attrs = dict(node.attributes or {})
        attrs["propagated_risk"] = round(val, 2)
        node.attributes = attrs
    db.commit()
    return {nid: round(v, 2) for nid, v in risk.items()}


# ---------------------------------------------------------------------------
# Network visualization payload
# ---------------------------------------------------------------------------
def network(db: Session, *, root_id: Optional[int] = None, max_depth: int = 2,
            tenant_id: Optional[int] = None, limit: int = 300) -> Dict[str, Any]:
    """Return a ``{nodes, edges}`` payload for network visualization.

    With ``root_id`` it returns the ego-network up to ``max_depth``; otherwise the
    whole (capped) graph for the tenant.
    """
    view = load_view(db, tenant_id=tenant_id)
    if root_id is not None:
        reached = traverse(view, root_id, max_depth=max_depth)
        node_ids = set(reached.keys())
    else:
        node_ids = set(list(view.nodes.keys())[:limit])
    nodes = [{
        "id": n.id, "ref": n.ref, "name": n.name, "entity_type": n.entity_type,
        "risk_score": n.risk_score,
        "propagated_risk": (n.attributes or {}).get("propagated_risk") if isinstance(n.attributes, dict) else None,
        "depth": (reached.get(n.id, {}).get("depth") if root_id is not None else 0),
    } for nid, n in view.nodes.items() if nid in node_ids]
    edges = [{
        "id": e.id, "source": e.source_id, "target": e.target_id,
        "rel_type": e.rel_type, "strength": e.strength, "exposure": e.exposure,
    } for e in view.edges if e.source_id in node_ids and e.target_id in node_ids]
    return {"nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)}


def stats(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    view = load_view(db, tenant_id=tenant_id)
    by_type: Dict[str, int] = defaultdict(int)
    for n in view.nodes.values():
        by_type[n.entity_type] += 1
    by_rel: Dict[str, int] = defaultdict(int)
    for e in view.edges:
        by_rel[e.rel_type] += 1
    return {
        "entities": len(view.nodes), "relationships": len(view.edges),
        "by_entity_type": dict(by_type), "by_relationship_type": dict(by_rel),
    }


# ---------------------------------------------------------------------------
# Seeding from real platform data
# ---------------------------------------------------------------------------
def seed_from_assessment(db: Session, assessment, *, tenant_id: Optional[int] = None) -> KGEntity:
    """Create/refresh the company node (+ sector/region) from an assessment.

    Uses the assessment's risk figures for the node's intrinsic ``risk_score``
    (PD-scaled to 0-100) — never fabricated.
    """
    from .common import pd_from_score
    pd = assessment.probability_of_default
    if pd is None and assessment.enterprise_credit_score is not None:
        pd = pd_from_score(assessment.enterprise_credit_score)
    risk = round(clamp((pd or 0.0) * 100, 0, 100), 2)
    company = upsert_entity(
        db, entity_type="company", ref=assessment.company_name,
        name=assessment.company_name, tenant_id=tenant_id, risk_score=risk,
        attributes={"industry": assessment.industry, "rating": assessment.risk_rating,
                    "assessment_id": assessment.id,
                    "exposure": assessment.recommended_loan_amount})
    if assessment.industry:
        sector = upsert_entity(db, entity_type="sector", ref=assessment.industry,
                               name=assessment.industry, tenant_id=tenant_id)
        add_relationship(db, company, sector, "operates_in_sector", tenant_id=tenant_id)
    country = getattr(assessment, "country", None)
    if country:
        region = upsert_entity(db, entity_type="region", ref=country, name=country,
                               tenant_id=tenant_id)
        add_relationship(db, company, region, "located_in", tenant_id=tenant_id)
    return company


def ingest_network(db: Session, company_ref: str, relationships: Iterable[dict], *,
                   tenant_id: Optional[int] = None) -> Dict[str, int]:
    """Ingest a list of ``{entity_type, ref, name, rel_type, strength, exposure}`` edges.

    Compatible with the Customer-360 ``relationship_network`` shape, so a
    bank's connector data flows straight into the graph.
    """
    company = upsert_entity(db, entity_type="company", ref=company_ref, name=company_ref,
                            tenant_id=tenant_id)
    n_entities = n_edges = 0
    for rel in relationships or []:
        etype = rel.get("entity_type") or "connected_entity"
        ref = rel.get("ref") or rel.get("name")
        if not ref:
            continue
        node = upsert_entity(db, entity_type=etype, ref=ref, name=rel.get("name") or ref,
                             tenant_id=tenant_id, attributes=rel.get("attributes") or {},
                             risk_score=rel.get("risk_score"))
        n_entities += 1
        rel_type = rel.get("rel_type") or "connected_to"
        add_relationship(db, company, node, rel_type, strength=rel.get("strength"),
                         exposure=rel.get("exposure"), tenant_id=tenant_id)
        n_edges += 1
    return {"entities": n_entities, "relationships": n_edges, "company_id": company.id}
